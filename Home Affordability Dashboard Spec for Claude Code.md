# Home Affordability Dashboard: Spec for Claude Code

## Goal

Build a local Python dashboard that models the true cost of buying a house and can goal-seek backwards from targets (monthly payment, cash on hand) to price, down payment, or points. Start with Streamlit or Dash; the maths module stays separate so it can be moved to a static JS front end later.

## Stack

- Python 3.11+, Pydantic v2 for models
- SciPy (`brentq`) for goal-seek
- Streamlit (or Dash) for UI, Plotly for charts
- pytest for the maths module
- src/ layout, pyproject.toml

## Project layout

```
src/house_calc/
  models.py      # Pydantic models
  mortgage.py    # pure maths: amortisation, PMI, totals
  solve.py       # goal-seek functions
  app.py         # UI only, no maths
tests/
```

## Data models

### Property

- `price: float`
- `annual_property_tax: float`
- `annual_insurance: float`
- `monthly_hoa: float = 0`
- `maintenance_rate: float = 0.01` (fraction of value per year)

### Loan

- `down_payment: float` (amount; allow input as a percentage in the UI)
- `base_rate: float` (annual, e.g. 0.065)
- `term_years: int = 30`
- `points: float = 0`
- `rate_cut_per_point: float = 0.0025`
- `point_cost_pct: float = 0.01` (fraction of loan amount per point)
- `pmi_rate: float = 0.005` (annual, on loan amount; drops when LTV <= 80%)
- Computed: `effective_rate = base_rate - points * rate_cut_per_point`

### ClosingCosts

- `lender_fees`, `title`, `appraisal`, `inspection`, `prepaid_escrow`, `moving_and_repairs` (all floats, default 0)
- Computed: `total`

### Buyer

- `cash_available: float`
- `target_monthly_payment: float`
- `gross_monthly_income: float`
- `other_monthly_debt: float = 0`
- `max_dti: float = 0.36`
- `years_expected_to_stay: int`

### Scenario

Wraps Property, Loan, ClosingCosts, Buyer.

Computed fields:

- `loan_amount = price - down_payment`
- `principal_and_interest` (standard amortisation formula)
- `monthly_pmi` (0 if down payment >= 20%)
- `monthly_total` = P&I + tax/12 + insurance/12 + HOA + PMI + maintenance/12
- `points_cost = points * point_cost_pct * loan_amount`
- `cash_to_close = down_payment + closing.total + points_cost`
- `dti = (monthly_total + other_monthly_debt) / gross_monthly_income`
- `points_breakeven_months` = points\_cost / monthly P&I saving vs zero points
- `pmi_drop_off_month` from the amortisation schedule

Validators:

- down payment <= price
- cash\_to\_close <= cash\_available (warn, don't fail, so the UI can show the gap)
- effective\_rate > 0

## Goal-seek functions (solve.py)

Each takes a Scenario, a target, and one free variable; uses `brentq` with sensible bounds.

- `max_price_for_payment(scenario, target_monthly)`
- `max_price_for_cash(scenario)`: largest price where cash\_to\_close fits
- `max_price_for_dti(scenario)`
- `affordable_price(scenario)`: min of the three above, and which constraint binds
- `points_for_payment(scenario, target_monthly)`
- `down_payment_for_payment(scenario, target_monthly)`

## Comparisons

- Points vs bigger down payment: same cash, compare monthly payment and total cost over `years_expected_to_stay`
- Rate sensitivity: monthly\_total across rates +/- 1% in 0.125% steps
- Total cost of ownership over the stay period (interest, PMI, tax, insurance, maintenance, closing) minus principal paid down

## UI (app.py)

- Sidebar inputs grouped by model
- Headline cards: monthly total, cash to close, DTI, affordable price and binding constraint
- Charts: monthly cost breakdown (stacked bar), amortisation and PMI drop-off, points break-even line, rate sensitivity
- Side-by-side scenario compare (save up to 3 scenarios)

## Tests

- P&I matches a known amortisation example to the cent
- PMI turns off at 80% LTV
- Goal-seek results round-trip (solve price, recompute payment, equals target)
- Break-even is infinite when points = 0

## Later

- Static JS port (maths module only, Observable Plot or D3)
- Import lender Loan Estimates for side-by-side comparison
