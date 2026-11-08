"""Pydantic models. Computed fields delegate the maths to mortgage.py."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from . import mortgage


class _Base(BaseModel):
    model_config = ConfigDict(validate_assignment=True)


class Property(_Base):
    price: float = Field(gt=0)
    annual_property_tax: float = Field(ge=0)
    annual_insurance: float = Field(ge=0)
    monthly_hoa: float = Field(0, ge=0)
    maintenance_rate: float = Field(0.01, ge=0)  # fraction of value per year


class Loan(_Base):
    down_payment: float = Field(ge=0)
    base_rate: float = Field(ge=0)  # annual, e.g. 0.065
    term_years: int = Field(30, gt=0)
    points: float = Field(0, ge=0)
    rate_cut_per_point: float = Field(0.0025, ge=0)
    point_cost_pct: float = Field(0.01, ge=0)  # fraction of loan amount per point
    pmi_rate: float = Field(0.005, ge=0)  # annual, on loan amount

    @computed_field
    @property
    def effective_rate(self) -> float:
        return self.base_rate - self.points * self.rate_cut_per_point

    @model_validator(mode="after")
    def _rate_positive(self) -> Loan:
        if self.effective_rate <= 0:
            raise ValueError(
                f"effective_rate must be > 0 (got {self.effective_rate:.4%}); reduce points"
            )
        return self


class ClosingCosts(_Base):
    lender_fees: float = Field(0, ge=0)
    title: float = Field(0, ge=0)
    appraisal: float = Field(0, ge=0)
    inspection: float = Field(0, ge=0)
    prepaid_escrow: float = Field(0, ge=0)
    moving_and_repairs: float = Field(0, ge=0)

    @computed_field
    @property
    def total(self) -> float:
        return (
            self.lender_fees
            + self.title
            + self.appraisal
            + self.inspection
            + self.prepaid_escrow
            + self.moving_and_repairs
        )


class Buyer(_Base):
    cash_available: float = Field(ge=0)
    target_monthly_payment: float = Field(ge=0)
    gross_monthly_income: float = Field(gt=0)
    other_monthly_debt: float = Field(0, ge=0)
    max_dti: float = Field(0.36, gt=0)
    years_expected_to_stay: int = Field(gt=0)


class Scenario(_Base):
    property: Property
    loan: Loan
    closing: ClosingCosts = Field(default_factory=ClosingCosts)
    buyer: Buyer

    @model_validator(mode="after")
    def _down_payment_le_price(self) -> Scenario:
        if self.loan.down_payment > self.property.price:
            raise ValueError("down_payment cannot exceed price")
        return self

    # --- loan ---------------------------------------------------------------

    @computed_field
    @property
    def loan_amount(self) -> float:
        return self.property.price - self.loan.down_payment

    @computed_field
    @property
    def down_payment_pct(self) -> float:
        return self.loan.down_payment / self.property.price

    @computed_field
    @property
    def ltv(self) -> float:
        return self.loan_amount / self.property.price

    @computed_field
    @property
    def principal_and_interest(self) -> float:
        return mortgage.monthly_payment(
            self.loan_amount, self.loan.effective_rate, self.loan.term_years
        )

    @computed_field
    @property
    def monthly_pmi(self) -> float:
        return mortgage.monthly_pmi(self.loan_amount, self.property.price, self.loan.pmi_rate)

    # --- monthly carrying costs ---------------------------------------------

    @computed_field
    @property
    def monthly_tax(self) -> float:
        return self.property.annual_property_tax / 12

    @computed_field
    @property
    def monthly_insurance(self) -> float:
        return self.property.annual_insurance / 12

    @computed_field
    @property
    def monthly_maintenance(self) -> float:
        return self.property.price * self.property.maintenance_rate / 12

    @computed_field
    @property
    def monthly_total(self) -> float:
        return (
            self.principal_and_interest
            + self.monthly_tax
            + self.monthly_insurance
            + self.property.monthly_hoa
            + self.monthly_pmi
            + self.monthly_maintenance
        )

    # --- cash ---------------------------------------------------------------

    @computed_field
    @property
    def points_cost(self) -> float:
        return self.loan.points * self.loan.point_cost_pct * self.loan_amount

    @computed_field
    @property
    def cash_to_close(self) -> float:
        return self.loan.down_payment + self.closing.total + self.points_cost

    @computed_field
    @property
    def cash_shortfall(self) -> float:
        return max(0.0, self.cash_to_close - self.buyer.cash_available)

    @computed_field
    @property
    def dti(self) -> float:
        return (self.monthly_total + self.buyer.other_monthly_debt) / self.buyer.gross_monthly_income

    # --- points & PMI timing ------------------------------------------------

    @computed_field
    @property
    def points_monthly_saving(self) -> float:
        zero_points = mortgage.monthly_payment(
            self.loan_amount, self.loan.base_rate, self.loan.term_years
        )
        return zero_points - self.principal_and_interest

    @computed_field
    @property
    def points_breakeven_months(self) -> float:
        return mortgage.breakeven_months(self.points_cost, self.points_monthly_saving)

    @computed_field
    @property
    def pmi_drop_off_month(self) -> int | None:
        return mortgage.pmi_drop_off_month(self.schedule())

    # --- warnings (don't fail; the UI shows the gap) ------------------------

    @computed_field
    @property
    def warnings(self) -> list[str]:
        out = []
        if self.cash_shortfall > 0:
            out.append(
                f"Cash to close exceeds cash available by ${self.cash_shortfall:,.0f}"
            )
        if self.dti > self.buyer.max_dti:
            out.append(f"DTI {self.dti:.1%} exceeds max {self.buyer.max_dti:.0%}")
        if self.monthly_total > self.buyer.target_monthly_payment > 0:
            gap = self.monthly_total - self.buyer.target_monthly_payment
            out.append(f"Monthly total is ${gap:,.0f} over target")
        return out

    # --- helpers ------------------------------------------------------------

    def schedule(self) -> list[mortgage.ScheduleRow]:
        return mortgage.amortization_schedule(
            self.loan_amount,
            self.loan.effective_rate,
            self.loan.term_years,
            self.property.price,
            self.loan.pmi_rate,
        )

    def with_changes(self, *, property: dict | None = None, loan: dict | None = None,
                     closing: dict | None = None, buyer: dict | None = None) -> Scenario:
        """Validated copy with nested fields replaced."""

        def merge(model: BaseModel, upd: dict | None) -> dict:
            # Computed fields in the dump are ignored on validation (extra="ignore").
            return {**model.model_dump(), **(upd or {})}

        return Scenario(
            property=merge(self.property, property),
            loan=merge(self.loan, loan),
            closing=merge(self.closing, closing),
            buyer=merge(self.buyer, buyer),
        )
