"""Pure mortgage maths. No models, no UI: plain numbers in, plain numbers out.

Kept dependency-free so it can be ported to JS line for line.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

PMI_LTV_CUTOFF = 0.80


def monthly_payment(principal: float, annual_rate: float, term_years: int) -> float:
    """Standard fixed-rate amortisation payment (principal and interest)."""
    if principal <= 0:
        return 0.0
    n = term_years * 12
    r = annual_rate / 12
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** -n)


def pmi_applies(balance: float, home_value: float, cutoff: float = PMI_LTV_CUTOFF) -> bool:
    """PMI is charged while LTV is above the cutoff (drops when LTV <= 80%)."""
    if home_value <= 0:
        return False
    return balance / home_value > cutoff + 1e-12


def monthly_pmi(loan_amount: float, home_value: float, pmi_rate: float) -> float:
    """Initial monthly PMI: annual rate on the original loan amount, if LTV > 80%."""
    if not pmi_applies(loan_amount, home_value):
        return 0.0
    return loan_amount * pmi_rate / 12


@dataclass(frozen=True)
class ScheduleRow:
    month: int
    payment: float  # P&I
    interest: float
    principal: float
    balance: float  # balance after this month's payment
    pmi: float


def amortization_schedule(
    principal: float,
    annual_rate: float,
    term_years: int,
    home_value: float,
    pmi_rate: float,
) -> list[ScheduleRow]:
    """Month-by-month schedule. PMI is charged in a month if the balance at the
    start of that month is above 80% of the original home value."""
    rows: list[ScheduleRow] = []
    if principal <= 0:
        return rows
    pmt = monthly_payment(principal, annual_rate, term_years)
    r = annual_rate / 12
    pmi_amount = principal * pmi_rate / 12
    balance = principal
    for month in range(1, term_years * 12 + 1):
        pmi = pmi_amount if pmi_applies(balance, home_value) else 0.0
        interest = balance * r
        princ = min(pmt - interest, balance)
        balance = balance - princ
        if balance < 1e-6:
            balance = 0.0
        rows.append(ScheduleRow(month, interest + princ, interest, princ, balance, pmi))
    return rows


def pmi_drop_off_month(schedule: list[ScheduleRow]) -> int | None:
    """First month with no PMI charged, after PMI has been charged.
    None if PMI never applies."""
    if not schedule or schedule[0].pmi == 0:
        return None
    for row in schedule:
        if row.pmi == 0:
            return row.month
    return None


def breakeven_months(upfront_cost: float, monthly_saving: float) -> float:
    """Months until a monthly saving repays an upfront cost. inf if it never does."""
    if upfront_cost <= 0 or monthly_saving <= 0:
        return math.inf
    return upfront_cost / monthly_saving
