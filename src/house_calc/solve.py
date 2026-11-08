"""Goal-seek: solve backwards from targets to price, down payment or points.

Each solver takes a Scenario, a target and one free variable, and uses brentq.

Price solvers rescale the scenario to the trial price (see `with_price`):
  - down payment holds its percentage of price (hold="percent", default) or
    its dollar amount (hold="amount");
  - property tax and insurance scale with price;
  - HOA and closing costs stay fixed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Literal

from scipy.optimize import brentq

from .models import Scenario

Hold = Literal["percent", "amount"]

PRICE_CAP = 1e9  # beyond this a constraint is treated as non-binding
XTOL = 1e-6


def with_price(scenario: Scenario, price: float, hold: Hold = "percent") -> Scenario:
    """Copy of the scenario at a new price, scaling price-linked inputs."""
    old = scenario.property.price
    ratio = price / old
    if hold == "percent":
        down = scenario.down_payment_pct * price
    else:
        down = min(scenario.loan.down_payment, price)
    return scenario.with_changes(
        property={
            "price": price,
            "annual_property_tax": scenario.property.annual_property_tax * ratio,
            "annual_insurance": scenario.property.annual_insurance * ratio,
        },
        loan={"down_payment": down},
    )


def _largest_feasible(f: Callable[[float], float], lo: float, hi: float) -> float:
    """Largest x >= lo with f(x) <= 0, for f non-decreasing.
    Returns 0.0 if f(lo) > 0 and inf if f stays <= 0 up to PRICE_CAP."""
    if f(lo) > 0:
        return 0.0
    while f(hi) <= 0:
        if hi >= PRICE_CAP:
            return math.inf
        lo, hi = hi, min(hi * 2, PRICE_CAP)
    return brentq(f, lo, hi, xtol=XTOL)


def _price_floor(scenario: Scenario, hold: Hold) -> float:
    return max(scenario.loan.down_payment, 1.0) if hold == "amount" else 1.0


def max_price_for_payment(scenario: Scenario, target_monthly: float, hold: Hold = "percent") -> float:
    """Largest price whose monthly_total is at or below target_monthly."""

    def f(price: float) -> float:
        return with_price(scenario, price, hold).monthly_total - target_monthly

    lo = _price_floor(scenario, hold)
    return _largest_feasible(f, lo, max(lo * 2, scenario.property.price))


def max_price_for_cash(scenario: Scenario, hold: Hold = "percent") -> float:
    """Largest price where cash_to_close fits within cash_available."""
    cash = scenario.buyer.cash_available

    def f(price: float) -> float:
        return with_price(scenario, price, hold).cash_to_close - cash

    lo = _price_floor(scenario, hold)
    return _largest_feasible(f, lo, max(lo * 2, scenario.property.price))


def max_housing_payment_for_dti(scenario: Scenario) -> float:
    b = scenario.buyer
    return b.max_dti * b.gross_monthly_income - b.other_monthly_debt


def max_price_for_dti(scenario: Scenario, hold: Hold = "percent") -> float:
    """Largest price where DTI stays at or below max_dti."""
    return max_price_for_payment(scenario, max_housing_payment_for_dti(scenario), hold)


@dataclass(frozen=True)
class Affordability:
    price: float
    binding: str
    by_constraint: dict[str, float]


def affordable_price(scenario: Scenario, hold: Hold = "percent") -> Affordability:
    """Min of the payment, cash and DTI limits, and which one binds."""
    limits = {
        "payment": max_price_for_payment(scenario, scenario.buyer.target_monthly_payment, hold),
        "cash": max_price_for_cash(scenario, hold),
        "dti": max_price_for_dti(scenario, hold),
    }
    binding = min(limits, key=limits.get)
    return Affordability(limits[binding], binding, limits)


def max_points(scenario: Scenario) -> float:
    """Most points before effective_rate hits zero."""
    loan = scenario.loan
    if loan.rate_cut_per_point <= 0:
        return 0.0
    return max(0.0, (loan.base_rate - 1e-5) / loan.rate_cut_per_point)


def points_for_payment(scenario: Scenario, target_monthly: float) -> float | None:
    """Fewest points that bring monthly_total to target. 0 if already met,
    None if no number of points gets there."""

    def f(points: float) -> float:
        return scenario.with_changes(loan={"points": points}).monthly_total - target_monthly

    if f(0.0) <= 0:
        return 0.0
    hi = max_points(scenario)
    if hi <= 0 or f(hi) > 0:
        return None
    return brentq(f, 0.0, hi, xtol=XTOL)


def down_payment_for_payment(scenario: Scenario, target_monthly: float) -> float | None:
    """Smallest down payment that brings monthly_total to target. 0 if already
    met, None if even paying cash in full doesn't."""
    price = scenario.property.price

    def f(down: float) -> float:
        return scenario.with_changes(loan={"down_payment": down}).monthly_total - target_monthly

    if f(0.0) <= 0:
        return 0.0
    if f(price) > 0:
        return None
    root = brentq(f, 0.0, price, xtol=XTOL)
    # monthly_total jumps down where PMI drops off (20% down). If the target sits
    # inside that gap brentq lands on the jump from the left; step over it.
    if f(root) > 1e-6:
        root = max(root, 0.2 * price)
    return root
