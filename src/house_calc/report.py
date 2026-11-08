"""Shareable plan summary: a self-contained HTML page and a plain-text version.

The HTML embeds the plan's settings, so uploading the file back into the app
restores it. No Streamlit here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from html import escape

from . import compare, solve
from .models import Scenario
from .settings import embed_plan, scenario_from_settings

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
BINDING = {"payment": "your target payment", "cash": "your cash to close", "dti": "the max DTI"}


def money(x: float | None, cents: bool = False) -> str:
    if x is None:
        return "n/a"
    if math.isinf(x):
        return "no limit"
    return f"${x:,.2f}" if cents else f"${x:,.0f}"


def pct(x: float, digits: int = 1) -> str:
    return f"{x:.{digits}%}"


def pmi_text(sc: Scenario, cents: bool = False) -> str:
    if sc.monthly_pmi == 0:
        return "None (20%+ down)"
    paid = (sc.pmi_drop_off_month or 1) - 1  # drop-off month is the first month without PMI
    return f"{money(sc.monthly_pmi, cents)}/mo for the first {months_text(paid)}"


def months_text(m: float | int | None) -> str:
    if m is None or (isinstance(m, float) and math.isinf(m)):
        return "never"
    return f"{m:.0f} months ({m / 12:.1f} years)"


@dataclass
class Facts:
    """Everything the summary shows, computed once."""
    name: str
    notes: str
    when: str
    url: str
    s: dict
    sc: Scenario
    aff: solve.Affordability
    tco: compare.CostOfOwnership
    breakdown: list[tuple[str, float]]
    cash_items: list[tuple[str, float]]
    rates: list[tuple[float, float]]
    saved: list[tuple[str, Scenario]]
    verdicts: list[tuple[bool, str]]


def build_facts(plan: dict, url: str = "") -> Facts:
    s = plan["settings"]
    sc = scenario_from_settings(s)
    aff = solve.affordable_price(sc, s["hold"])
    c = sc.closing
    today = date.today()

    saved = []
    for e in plan.get("saved", []):
        try:
            saved.append((e["name"], scenario_from_settings(e["inputs"])))
        except Exception:
            continue  # an invalid saved option is left out rather than failing the summary

    over = sc.monthly_total - s["target"]
    verdicts = [
        (over <= 0, f"Monthly total is {money(abs(over))} {'under' if over <= 0 else 'over'} "
                    f"your {money(s['target'])} target"),
        (sc.cash_shortfall == 0,
         f"Cash to close leaves {money(s['cash'] - sc.cash_to_close)} of your savings"
         if sc.cash_shortfall == 0 else f"You're {money(sc.cash_shortfall)} short on cash to close"),
        (sc.dti <= sc.buyer.max_dti,
         f"DTI of {pct(sc.dti)} is {'within' if sc.dti <= sc.buyer.max_dti else 'above'} "
         f"the {pct(sc.buyer.max_dti, 0)} limit"),
    ]

    return Facts(
        name=plan.get("name") or "Home purchase plan",
        notes=plan.get("notes", ""),
        when=f"{today:%B} {today.day}, {today.year}",
        url=url,
        s=s, sc=sc, aff=aff,
        tco=compare.cost_of_ownership(sc),
        breakdown=[
            ("Principal & interest", sc.principal_and_interest),
            ("Property tax", sc.monthly_tax),
            ("Insurance", sc.monthly_insurance),
            ("HOA", sc.property.monthly_hoa),
            ("PMI", sc.monthly_pmi),
            ("Maintenance", sc.monthly_maintenance),
        ],
        cash_items=[
            ("Down payment", sc.loan.down_payment),
            ("Lender fees", c.lender_fees), ("Title", c.title), ("Appraisal", c.appraisal),
            ("Inspection", c.inspection), ("Prepaid escrow", c.prepaid_escrow),
            ("Moving & repairs", c.moving_and_repairs), ("Points", sc.points_cost),
        ],
        rates=[(r, t) for r, t in compare.rate_sensitivity(sc, span=0.01, step=0.005)],
        saved=saved,
        verdicts=verdicts,
    )


def option_rows(sc: Scenario, hold: str) -> list[tuple[str, str]]:
    a = solve.affordable_price(sc, hold)
    return [
        ("Price", money(sc.property.price)),
        ("Down payment", f"{money(sc.loan.down_payment)} ({pct(sc.down_payment_pct)})"),
        ("Rate", f"{sc.loan.effective_rate:.3%}" + (f" ({sc.loan.points:g} pts)" if sc.loan.points else "")),
        ("Monthly total", money(sc.monthly_total)),
        ("Cash to close", money(sc.cash_to_close)),
        ("DTI", pct(sc.dti)),
        ("PMI", "none" if sc.monthly_pmi == 0 else f"first {(sc.pmi_drop_off_month or 1) - 1} months"),
        (f"Net cost over {sc.buyer.years_expected_to_stay} yrs", money(compare.cost_of_ownership(sc).net_cost)),
        ("Affordable price", money(a.price)),
    ]


# --- plain text ---------------------------------------------------------------

def render_text(plan: dict, url: str = "") -> str:
    f = build_facts(plan, url)
    sc, s = f.sc, f.s
    lines = [
        f.name.upper(),
        f"{money(sc.property.price)} home · {pct(sc.down_payment_pct)} down · "
        f"{sc.loan.effective_rate:.3%} · {sc.loan.term_years}-year fixed",
        f"Prepared {f.when}",
        "",
        "AT A GLANCE",
        *[f"  {'✓' if ok else '✗'} {text}" for ok, text in f.verdicts],
        "",
        f"  Monthly total:     {money(sc.monthly_total)}",
        f"  Cash to close:     {money(sc.cash_to_close)}",
        f"  DTI:               {pct(sc.dti)}",
        f"  Affordable price:  {money(f.aff.price)} (limited by {BINDING[f.aff.binding]})",
        "",
        "MONTHLY COST",
        *[f"  {name:<22}{money(v):>10}" for name, v in f.breakdown if v > 0],
        f"  {'Total':<22}{money(sc.monthly_total):>10}",
        "",
        "CASH TO CLOSE",
        *[f"  {name:<22}{money(v):>10}" for name, v in f.cash_items if v > 0],
        f"  {'Total':<22}{money(sc.cash_to_close):>10}",
        "",
        "LOAN",
        f"  Loan amount {money(sc.loan_amount)} at {sc.loan.effective_rate:.3%}, "
        f"P&I {money(sc.principal_and_interest)}/mo",
        f"  PMI: {pmi_text(sc)}",
    ]
    if sc.loan.points:
        lines.append(f"  Points: {sc.loan.points:g} for {money(sc.points_cost)}, "
                     f"break-even {months_text(sc.points_breakeven_months)}")
    lines += [
        "",
        f"OVER {s['stay']} YEARS",
        f"  Total paid (excl. down payment): {money(f.tco.total_paid)}",
        f"  Principal paid down (equity):    {money(f.tco.principal_paid)}",
        f"  Net cost of owning:              {money(f.tco.net_cost)}",
    ]
    if f.saved:
        lines += ["", "OPTIONS COMPARED"]
        for name, other in f.saved:
            rows = option_rows(other, s["hold"])
            lines.append(f"  {name}: " + ", ".join(f"{k} {v}" for k, v in rows[:5]))
    if f.notes.strip():
        lines += ["", "NOTES", *[f"  {ln}" for ln in f.notes.strip().splitlines()]]
    if url:
        lines += ["", f"Open this plan: {url}"]
    return "\n".join(lines)


# --- HTML ---------------------------------------------------------------------

CSS = """
:root{--bg:#fcfcfb;--card:#ffffff;--ink:#0b0b0b;--ink2:#52514e;--muted:#6f6d68;
--line:#e1e0d9;--good:#006300;--bad:#b42323;--accent:#2a78d6;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--card:#1d1d1c;--ink:#f0efec;
--ink2:#c3c2b7;--muted:#9a988f;--line:#2f2f2c;--good:#3fbf3f;--bad:#ef6b6b;--accent:#3987e5;
color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:860px;margin:0 auto;padding:40px 20px 64px}
header h1{font-size:30px;line-height:1.2;margin:0 0 6px;letter-spacing:-.01em}
.sub{color:var(--ink2);margin:0}
.when{color:var(--muted);font-size:13px;margin-top:4px}
h2{font-size:17px;margin:36px 0 12px;padding-bottom:6px;border-bottom:1px solid var(--line)}
.verdicts{list-style:none;padding:0;margin:24px 0 0;display:grid;gap:6px}
.verdicts li{display:flex;gap:10px;align-items:baseline}
.ok{color:var(--good);font-weight:700}.no{color:var(--bad);font-weight:700}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-top:24px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.card .k{color:var(--ink2);font-size:13px}
.card .v{font-size:26px;font-weight:600;margin-top:2px}
.card .d{color:var(--muted);font-size:13px}
.bar{display:flex;height:22px;border-radius:5px;overflow:hidden;gap:2px;margin:6px 0 14px}
.bar span{display:block;height:100%}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
td,th{padding:7px 4px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--ink2);font-weight:600;font-size:13px}
td.n,th.n{text-align:right}
tr.total td{font-weight:700;border-bottom:none}
.dot{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:8px}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:0 32px}
.scroll{overflow-x:auto}
.notes{white-space:pre-wrap;background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:14px 16px;margin:0}
.open{display:inline-block;margin-top:28px;padding:9px 16px;border-radius:8px;
background:var(--accent);color:#fff;text-decoration:none;font-weight:600}
footer{margin-top:40px;color:var(--muted);font-size:12.5px}
@media print{body{background:#fff;color:#000}main{padding:0}.open{display:none}
.card,.notes{break-inside:avoid}h2{break-after:avoid}}
"""


def _table(rows: list[tuple], head: tuple | None = None, total: tuple | None = None,
           numeric_cols: set[int] = frozenset({1})) -> str:
    def cells(row, tag="td"):
        return "".join(
            f'<{tag}{" class=n" if i in numeric_cols else ""}>{c}</{tag}>' for i, c in enumerate(row)
        )
    out = ['<div class="scroll"><table>']
    if head:
        out.append(f"<thead><tr>{cells(head, 'th')}</tr></thead>")
    out.append("<tbody>")
    out += [f"<tr>{cells(r)}</tr>" for r in rows]
    if total:
        out.append(f'<tr class="total">{cells(total)}</tr>')
    out.append("</tbody></table></div>")
    return "".join(out)


def render_html(plan: dict, url: str = "") -> str:
    f = build_facts(plan, url)
    sc, s, e = f.sc, f.s, escape

    verdicts = "".join(
        f'<li><span class="{"ok" if ok else "no"}">{"✓" if ok else "✗"}</span>{e(t)}</li>'
        for ok, t in f.verdicts
    )
    cards = "".join(
        f'<div class="card"><div class="k">{k}</div><div class="v">{v}</div><div class="d">{d}</div></div>'
        for k, v, d in [
            ("Monthly total", money(sc.monthly_total), f"target {money(s['target'])}"),
            ("Cash to close", money(sc.cash_to_close), f"of {money(s['cash'])} available"),
            ("Debt-to-income", pct(sc.dti), f"limit {pct(sc.buyer.max_dti, 0)}"),
            ("Affordable price", money(f.aff.price), f"limited by {BINDING[f.aff.binding]}"),
        ]
    )

    parts = [(n, v, SERIES[i]) for i, (n, v) in enumerate(f.breakdown) if v > 0]
    bar = "".join(
        f'<span style="flex:{v:.2f};background:{c}" title="{n}: {money(v)}"></span>' for n, v, c in parts
    )
    monthly = _table(
        [(f'<span class="dot" style="background:{c}"></span>{n}', money(v, True), pct(v / sc.monthly_total))
         for n, v, c in parts],
        head=("Monthly cost", "Amount", "Share"),
        total=("Total", money(sc.monthly_total, True), "100%"),
        numeric_cols={1, 2},
    )
    cash = _table(
        [(n, money(v)) for n, v in f.cash_items if v > 0],
        head=("Cash to close", "Amount"),
        total=("Total", money(sc.cash_to_close)),
    )

    loan_rows = [
        ("Loan amount", money(sc.loan_amount)),
        ("Loan-to-value", pct(sc.ltv)),
        ("Interest rate", f"{sc.loan.effective_rate:.3%}"
         + (f" (base {sc.loan.base_rate:.3%} less {sc.loan.points:g} point{'' if sc.loan.points == 1 else 's'})" if sc.loan.points else "")),
        ("Term", f"{sc.loan.term_years} years, fixed"),
        ("Principal & interest", f"{money(sc.principal_and_interest, True)}/mo"),
        ("PMI", pmi_text(sc, cents=True)),
    ]
    if sc.loan.points:
        loan_rows += [
            ("Points cost", money(sc.points_cost)),
            ("Points break-even", months_text(sc.points_breakeven_months)
             + (" ✓ before you move" if sc.points_breakeven_months <= s["stay"] * 12 else " ✗ after you move")),
        ]

    t = f.tco
    tco = _table(
        [("Interest", money(t.interest)), ("PMI", money(t.pmi)), ("Property tax", money(t.tax)),
         ("Insurance", money(t.insurance)), ("HOA", money(t.hoa)), ("Maintenance", money(t.maintenance)),
         ("Closing costs", money(t.closing)), ("Points", money(t.points))],
        total=("Net cost of owning", money(t.net_cost)),
    )

    afford = _table(
        [(f"Limited by {BINDING[k]}", money(v) + (" ← binding" if k == f.aff.binding else ""))
         for k, v in f.aff.by_constraint.items()],
        head=("Maximum price", ""),
    )
    rates = _table(
        [(f"{r:.3%}" + (" (current)" if abs(r - sc.loan.base_rate) < 1e-9 else ""), money(m),
          "" if abs(m - sc.monthly_total) < 0.5 else f"{'+' if m > sc.monthly_total else '−'}{money(abs(m - sc.monthly_total))}")
         for r, m in f.rates],
        head=("Base rate", "Monthly total", "Change"),
        numeric_cols={1, 2},
    )

    compared = ""
    if f.saved:
        options = [("This plan", sc)] + f.saved
        cols = [option_rows(o, s["hold"]) for _, o in options]
        head = ("",) + tuple(e(n) for n, _ in options)
        rows = [(cols[0][i][0],) + tuple(c[i][1] for c in cols) for i in range(len(cols[0]))]
        compared = "<h2>Options compared</h2>" + _table(
            rows, head=head, numeric_cols=set(range(1, len(options) + 1)))

    inputs = _table([
        ("Price", money(s["price"])), ("Property tax", f"{money(s['tax'])}/yr"),
        ("Insurance", f"{money(s['insurance'])}/yr"), ("HOA", f"{money(s['hoa'])}/mo"),
        ("Maintenance", f"{s['maint_pct']:g}% of value/yr"),
        ("Down payment", f"{money(sc.loan.down_payment)} ({pct(sc.down_payment_pct)})"),
        ("Base rate", f"{s['rate_pct']:.3f}%"), ("Points", f"{s['points']:g} "
         f"({s['cut_pct']:g}% off per point, {s['point_cost_pct']:g}% of loan each)"),
        ("PMI rate", f"{s['pmi_pct']:g}%/yr"),
    ], head=("Home & loan", ""))
    buyer = _table([
        ("Cash available", money(s["cash"])), ("Target monthly", money(s["target"])),
        ("Gross monthly income", money(s["income"])), ("Other monthly debt", money(s["debt"])),
        ("Max DTI", f"{s['max_dti_pct']:g}%"), ("Expected stay", f"{s['stay']} years"),
    ], head=("Buyer", ""))

    notes = f'<h2>Notes</h2><p class="notes">{e(f.notes.strip())}</p>' if f.notes.strip() else ""
    open_link = (f'<a class="open" href="{e(url, quote=True)}">Open this plan in the dashboard</a>'
                 if url else "")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(f.name)}</title><style>{CSS}</style></head>
<body><main>
<header>
<h1>{e(f.name)}</h1>
<p class="sub">{money(sc.property.price)} home · {pct(sc.down_payment_pct)} down ·
{sc.loan.effective_rate:.3%} · {sc.loan.term_years}-year fixed</p>
<div class="when">Prepared {f.when}</div>
</header>
<ul class="verdicts">{verdicts}</ul>
<div class="cards">{cards}</div>
{notes}
<h2>Monthly cost</h2>
<div class="bar" role="img" aria-label="Monthly cost breakdown">{bar}</div>
{monthly}
<div class="two">
<div><h2>Cash needed at closing</h2>{cash}</div>
<div><h2>The loan</h2>{_table(loan_rows)}</div>
</div>
<h2>Cost of owning for {s['stay']} years</h2>
<p class="sub">Total paid {money(t.total_paid)}, of which {money(t.principal_paid)} pays down the loan
and becomes your equity. The rest is the cost of owning:</p>
{tco}
<div class="two">
<div><h2>How much house you can afford</h2>{afford}</div>
<div><h2>If rates change</h2>{rates}</div>
</div>
{compared}
<h2>Inputs</h2>
<div class="two"><div>{inputs}</div><div>{buyer}</div></div>
{open_link}
<footer>Estimates only, not financial advice. Assumes a fixed-rate loan; tax, insurance and HOA
held flat; PMI ends at 80% of the purchase price. Ignores appreciation, selling costs, tax effects
and investment returns on cash. Upload this file to the dashboard to reopen the plan.</footer>
</main>
{embed_plan(plan)}
</body></html>"""
