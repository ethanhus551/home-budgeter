import math

import pytest
from pydantic import ValidationError

from house_calc import Buyer, ClosingCosts, Loan, Property, Scenario
from house_calc import compare, mortgage, solve


def make(price=400_000, down=80_000, rate=0.065, points=0.0, **buyer_kw) -> Scenario:
    buyer = dict(
        cash_available=120_000,
        target_monthly_payment=3_000,
        gross_monthly_income=12_000,
        other_monthly_debt=500,
        years_expected_to_stay=7,
    ) | buyer_kw
    return Scenario(
        property=Property(price=price, annual_property_tax=4_800, annual_insurance=1_800, monthly_hoa=50),
        loan=Loan(down_payment=down, base_rate=rate, points=points),
        closing=ClosingCosts(lender_fees=3_000, title=2_000, appraisal=600, inspection=500),
        buyer=Buyer(**buyer),
    )


# --- amortisation ----------------------------------------------------------

@pytest.mark.parametrize(
    "principal, rate, years, expected",
    [
        (200_000, 0.065, 30, 1264.14),
        (100_000, 0.06, 30, 599.55),
        (300_000, 0.07, 15, 2696.48),
    ],
)
def test_payment_matches_known_examples_to_the_cent(principal, rate, years, expected):
    assert round(mortgage.monthly_payment(principal, rate, years), 2) == expected


def test_schedule_pays_off_loan():
    rows = mortgage.amortization_schedule(200_000, 0.065, 30, 250_000, 0.005)
    assert len(rows) == 360
    assert rows[-1].balance == 0
    assert sum(r.principal for r in rows) == pytest.approx(200_000)


def test_scenario_monthly_total_components():
    s = make()
    expected = s.principal_and_interest + 400 + 150 + 50 + 0 + 400_000 * 0.01 / 12
    assert s.monthly_total == pytest.approx(expected)
    assert s.cash_to_close == pytest.approx(80_000 + 6_100)


# --- PMI -------------------------------------------------------------------

def test_no_pmi_at_20_percent_down():
    s = make(down=80_000)
    assert s.monthly_pmi == 0
    assert s.pmi_drop_off_month is None


def test_pmi_charged_below_20_percent_down():
    s = make(down=79_000)
    assert s.monthly_pmi == pytest.approx(321_000 * 0.005 / 12)


def test_pmi_turns_off_at_80_percent_ltv():
    s = make(down=40_000)  # 90% LTV
    rows = s.schedule()
    m = s.pmi_drop_off_month
    assert m is not None
    # Month m starts with balance at or below 80% of value; month m-1 didn't.
    start_balance = lambda month: rows[month - 2].balance if month > 1 else s.loan_amount
    assert start_balance(m) <= 0.8 * s.property.price
    assert start_balance(m - 1) > 0.8 * s.property.price
    assert all(r.pmi > 0 for r in rows[: m - 1])
    assert all(r.pmi == 0 for r in rows[m - 1 :])


# --- points ----------------------------------------------------------------

def test_breakeven_infinite_with_zero_points():
    assert math.isinf(make(points=0).points_breakeven_months)


def test_breakeven_finite_with_points():
    s = make(points=1)
    assert s.loan.effective_rate == pytest.approx(0.0625)
    assert s.points_breakeven_months == pytest.approx(s.points_cost / s.points_monthly_saving)
    assert 0 < s.points_breakeven_months < 360


# --- validators ------------------------------------------------------------

def test_down_payment_cannot_exceed_price():
    with pytest.raises(ValidationError):
        make(down=500_000)


def test_effective_rate_must_be_positive():
    with pytest.raises(ValidationError):
        Loan(down_payment=0, base_rate=0.01, points=4)


def test_cash_shortfall_warns_not_fails():
    s = make(cash_available=50_000)
    assert s.cash_shortfall == pytest.approx(s.cash_to_close - 50_000)
    assert any("Cash to close" in w for w in s.warnings)


# --- goal-seek round trips -------------------------------------------------

@pytest.mark.parametrize("hold", ["percent", "amount"])
def test_max_price_for_payment_round_trips(hold):
    s = make()
    price = solve.max_price_for_payment(s, 2_800, hold)
    assert solve.with_price(s, price, hold).monthly_total == pytest.approx(2_800, abs=0.01)


def test_max_price_for_cash_round_trips():
    s = make(points=1)
    price = solve.max_price_for_cash(s)
    assert solve.with_price(s, price).cash_to_close == pytest.approx(s.buyer.cash_available, abs=0.01)


def test_max_price_for_cash_unbounded_when_amount_held_and_no_points():
    assert math.isinf(solve.max_price_for_cash(make(), hold="amount"))


def test_max_price_for_dti_round_trips():
    s = make()
    price = solve.max_price_for_dti(s)
    assert solve.with_price(s, price).dti == pytest.approx(s.buyer.max_dti, abs=1e-6)


def test_affordable_price_is_min_constraint():
    s = make()
    a = solve.affordable_price(s)
    assert a.price == min(a.by_constraint.values())
    assert a.by_constraint[a.binding] == a.price


def test_points_for_payment_round_trips():
    s = make()
    target = s.monthly_total - 100
    points = solve.points_for_payment(s, target)
    assert points is not None and points > 0
    assert s.with_changes(loan={"points": points}).monthly_total == pytest.approx(target, abs=0.01)


def test_points_for_payment_infeasible():
    assert solve.points_for_payment(make(), 500) is None


def test_down_payment_for_payment_round_trips():
    s = make()
    target = s.monthly_total - 150
    down = solve.down_payment_for_payment(s, target)
    assert s.with_changes(loan={"down_payment": down}).monthly_total == pytest.approx(target, abs=0.01)


def test_down_payment_for_payment_steps_over_pmi_jump():
    s = make(down=40_000)
    # A target between "just under 20% down" and "exactly 20% down" lands on the jump.
    just_under = s.with_changes(loan={"down_payment": 79_999}).monthly_total
    at_20 = s.with_changes(loan={"down_payment": 80_000}).monthly_total
    down = solve.down_payment_for_payment(s, (just_under + at_20) / 2)
    assert down == pytest.approx(80_000)


# --- comparisons -----------------------------------------------------------

def test_cost_of_ownership_net_excludes_principal():
    s = make()
    c = compare.cost_of_ownership(s)
    assert c.months == 84
    assert c.total_paid - c.net_cost == pytest.approx(c.principal_paid)
    monthly_outflow = s.monthly_total * 84
    assert c.total_paid - c.closing - c.points == pytest.approx(monthly_outflow)


def test_points_vs_down_spend_same_cash():
    s = make(down=40_000)
    base, pts, dwn = compare.points_vs_down_payment(s, 10_000)
    assert pts.scenario.cash_to_close - base.scenario.cash_to_close == pytest.approx(10_000)
    assert dwn.scenario.cash_to_close - base.scenario.cash_to_close == pytest.approx(10_000)
    assert pts.scenario.monthly_total < base.scenario.monthly_total
    assert dwn.scenario.monthly_total < base.scenario.monthly_total


def test_rate_sensitivity_grid():
    grid = compare.rate_sensitivity(make())
    assert len(grid) == 17
    rates = [r for r, _ in grid]
    assert rates[0] == pytest.approx(0.055) and rates[-1] == pytest.approx(0.075)
    totals = [t for _, t in grid]
    assert totals == sorted(totals)
