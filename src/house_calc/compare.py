"""Comparisons: total cost of ownership, points vs down payment, rate sensitivity."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .models import Scenario
from .solve import max_points


@dataclass(frozen=True)
class CostOfOwnership:
    months: int
    interest: float
    pmi: float
    tax: float
    insurance: float
    hoa: float
    maintenance: float
    closing: float
    points: float
    principal_paid: float

    @property
    def total_paid(self) -> float:
        """Every dollar out of pocket (excluding the down payment)."""
        return self.net_cost + self.principal_paid

    @property
    def net_cost(self) -> float:
        """Money gone: total paid minus principal paid down (which is equity)."""
        return (
            self.interest + self.pmi + self.tax + self.insurance
            + self.hoa + self.maintenance + self.closing + self.points
        )

    def as_dict(self) -> dict[str, float]:
        return {**asdict(self), "total_paid": self.total_paid, "net_cost": self.net_cost}


def cost_of_ownership(scenario: Scenario, years: int | None = None) -> CostOfOwnership:
    """Costs over the stay period (default: buyer.years_expected_to_stay).
    Ignores appreciation, selling costs and the time value of money."""
    years = years or scenario.buyer.years_expected_to_stay
    months = years * 12
    rows = scenario.schedule()[:months]
    return CostOfOwnership(
        months=months,
        interest=sum(r.interest for r in rows),
        pmi=sum(r.pmi for r in rows),
        tax=scenario.monthly_tax * months,
        insurance=scenario.monthly_insurance * months,
        hoa=scenario.property.monthly_hoa * months,
        maintenance=scenario.monthly_maintenance * months,
        closing=scenario.closing.total,
        points=scenario.points_cost,
        principal_paid=sum(r.principal for r in rows),
    )


@dataclass(frozen=True)
class Option:
    label: str
    scenario: Scenario
    cost: CostOfOwnership


def points_vs_down_payment(scenario: Scenario, extra_cash: float) -> list[Option]:
    """Spend the same extra cash on points or on a bigger down payment.

    Returns baseline, points and down-payment options. Points are bought at the
    baseline loan amount and capped where effective_rate would reach zero."""
    base = scenario
    cost_per_point = base.loan.point_cost_pct * base.loan_amount
    added_points = extra_cash / cost_per_point if cost_per_point > 0 else 0.0
    points = min(base.loan.points + added_points, max_points(base))
    with_points = base.with_changes(loan={"points": points})

    down = min(base.loan.down_payment + extra_cash, base.property.price)
    with_down = base.with_changes(loan={"down_payment": down})

    return [
        Option("Baseline", base, cost_of_ownership(base)),
        Option(f"+{points - base.loan.points:.2f} points", with_points, cost_of_ownership(with_points)),
        Option(f"+${extra_cash:,.0f} down", with_down, cost_of_ownership(with_down)),
    ]


def rate_sensitivity(
    scenario: Scenario, span: float = 0.01, step: float = 0.00125
) -> list[tuple[float, float]]:
    """(base_rate, monthly_total) across base_rate +/- span in `step` increments.
    Rates that would push effective_rate to zero or below are skipped."""
    n = round(span / step)
    out = []
    for i in range(-n, n + 1):
        rate = scenario.loan.base_rate + i * step
        if rate - scenario.loan.points * scenario.loan.rate_cut_per_point <= 0:
            continue
        out.append((rate, scenario.with_changes(loan={"base_rate": rate}).monthly_total))
    return out
