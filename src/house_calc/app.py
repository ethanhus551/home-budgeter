"""Streamlit UI. No maths here: everything comes from models/solve/compare.

Run with:  streamlit run src/house_calc/app.py
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

# Make `house_calc` importable when the package isn't pip-installed
# (e.g. on Streamlit Community Cloud).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from house_calc import compare, report, solve  # noqa: E402
from house_calc.models import Scenario  # noqa: E402
from house_calc.settings import (  # noqa: E402
    DEFAULTS, MAX_NAME, MAX_NOTES, PlanError, decode_plan, encode_plan, make_plan,
    plan_from_file, scenario_from_settings,
)

st.set_page_config(page_title="Home Affordability", layout="wide")

# --- palette (validated categorical slots, light/dark steps) ----------------

LIGHT = dict(
    series=["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"],
    ink="#0b0b0b", ink2="#52514e", muted="#898781", grid="#e1e0d9", axis="#c3c2b7",
    critical="#d03b3b",
)
DARK = dict(
    series=["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300"],
    ink="#f0efec", ink2="#c3c2b7", muted="#898781", grid="#2c2c2a", axis="#383835",
    critical="#d03b3b",
)


def palette() -> dict:
    try:
        return DARK if st.context.theme.type == "dark" else LIGHT
    except Exception:
        return LIGHT


P = palette()


def style(fig: go.Figure, height: int = 360, **layout) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=88, b=8),
        title_y=0.97, title_yref="container", title_x=0, title_xref="paper",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif", color=P["ink2"], size=13),
        title_font=dict(color=P["ink"], size=15),
        legend=dict(orientation="h", yanchor="bottom", y=1.04, x=0, title=None, traceorder="normal"),
        hoverlabel=dict(font_family="system-ui, sans-serif"),
        **layout,
    )
    axis = dict(gridcolor=P["grid"], linecolor=P["axis"], zerolinecolor=P["axis"],
                tickfont=dict(color=P["muted"]), title_font=dict(color=P["ink2"]))
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    return fig


def money(x: float | None, cents: bool = False) -> str:
    if x is None:
        return "n/a"
    if math.isinf(x):
        return "no limit"
    return f"${x:,.2f}" if cents else f"${x:,.0f}"


# --- inputs -----------------------------------------------------------------

ss = st.session_state
for k, v in DEFAULTS.items():
    ss.setdefault(k, v)
    # Re-assigning keeps the value alive even while its widget is hidden
    # (e.g. dp_pct while the down payment is entered in $).
    ss[k] = ss[k]
ss.setdefault("saved", [])
ss.setdefault("plan_name", "")
ss.setdefault("plan_notes", "")


def apply_plan(plan: dict) -> None:
    """Load a plan into the inputs. Must run before the widgets are drawn
    (top of script or a widget callback)."""
    for k, v in plan["settings"].items():
        ss[k] = v
    ss.plan_name = plan["name"]
    ss.plan_notes = plan["notes"]
    ss.saved = [{"name": e["name"], "inputs": e["inputs"]} for e in plan["saved"]]


# A shared link carries the plan in ?plan=...; load it once per browser session.
if "_url_checked" not in ss:
    ss._url_checked = True
    _token = st.query_params.get("plan")
    if _token:
        try:
            _plan = decode_plan(_token)
            apply_plan(_plan)
            ss._flash = ("success", f"Opened shared plan: {_plan['name'] or 'untitled'}")
        except PlanError as err:
            ss._flash = ("error", f"{err} Showing the default example instead.")


def num(label: str, key: str, step: float = 100.0, fmt: str = "%.0f", **kw):
    return st.number_input(label, key=key, step=step, format=fmt, min_value=0.0, **kw)


with st.sidebar:
    st.header("Inputs")
    with st.expander("Property", expanded=True):
        num("Price ($)", "price", 5_000.0)
        num("Annual property tax ($)", "tax")
        num("Annual insurance ($)", "insurance")
        num("Monthly HOA ($)", "hoa", 10.0)
        num("Maintenance (% of value / yr)", "maint_pct", 0.1, "%.2f")
    with st.expander("Loan", expanded=True):
        st.radio("Down payment as", ["%", "$"], key="dp_mode", horizontal=True)
        if st.session_state.dp_mode == "%":
            num("Down payment (%)", "dp_pct", 1.0, "%.2f", max_value=100.0)
        else:
            num("Down payment ($)", "dp_amt", 1_000.0)
        num("Base rate (%)", "rate_pct", 0.125, "%.3f")
        st.selectbox("Term (years)", [10, 15, 20, 25, 30], key="term")
        num("Points", "points", 0.25, "%.2f")
        num("Rate cut per point (%)", "cut_pct", 0.05, "%.3f")
        num("Point cost (% of loan)", "point_cost_pct", 0.25, "%.2f")
        num("PMI rate (% / yr)", "pmi_pct", 0.05, "%.2f")
    with st.expander("Closing costs"):
        num("Lender fees ($)", "lender_fees")
        num("Title ($)", "title")
        num("Appraisal ($)", "appraisal", 50.0)
        num("Inspection ($)", "inspection", 50.0)
        num("Prepaid escrow ($)", "prepaid_escrow")
        num("Moving & repairs ($)", "moving")
    with st.expander("Buyer", expanded=True):
        num("Cash available ($)", "cash", 1_000.0)
        num("Target monthly payment ($)", "target", 50.0)
        num("Gross monthly income ($)", "income", 100.0)
        num("Other monthly debt ($)", "debt", 50.0)
        num("Max DTI (%)", "max_dti_pct", 1.0, "%.1f")
        st.number_input("Years expected to stay", key="stay", min_value=1, max_value=40, step=1)
    with st.expander("Goal-seek"):
        st.radio(
            "When solving for price, hold the down payment as",
            ["percent", "amount"], key="hold",
            format_func=lambda h: "% of price" if h == "percent" else "$ amount",
            help="Tax and insurance scale with price; HOA and closing costs stay fixed.",
        )

current = {k: ss[k] for k in DEFAULTS}
plan = make_plan(current, ss.plan_name, ss.plan_notes, ss.saved)
token = encode_plan(plan)
# Keep the address bar in sync: it is always a link to exactly this plan,
# and refreshing the page keeps your inputs.
if st.query_params.get("plan") != token:
    st.query_params["plan"] = token
try:
    base_url = (st.context.url or "").split("?")[0]
except Exception:
    base_url = ""
share_url = f"{base_url}?plan={token}" if base_url else ""

if "_flash" in ss:
    kind, msg = ss.pop("_flash")
    (st.success if kind == "success" else st.error)(msg)

try:
    sc = scenario_from_settings(current)
except ValidationError as e:
    st.title("Home affordability")
    for err in e.errors():
        st.error(err["msg"].removeprefix("Value error, "))
    st.stop()


@st.cache_data(show_spinner=False)
def cached_affordability(payload: str, hold: str) -> solve.Affordability:
    return solve.affordable_price(Scenario.model_validate_json(payload), hold)


aff = cached_affordability(sc.model_dump_json(), ss.hold)

# --- headline ---------------------------------------------------------------

st.title("Home affordability")
st.caption(
    f"{money(sc.property.price)} home · {sc.down_payment_pct:.1%} down · "
    f"{sc.loan.effective_rate:.3%} effective rate · {sc.loan.term_years}-year term"
)

for w in sc.warnings:
    st.warning(w, icon="⚠️")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Monthly total", money(sc.monthly_total),
          delta=f"{money(sc.monthly_total - ss.target)} vs target", delta_color="inverse")
c2.metric("Cash to close", money(sc.cash_to_close),
          delta=f"{money(ss.cash - sc.cash_to_close)} left over" if sc.cash_shortfall == 0
          else f"-{money(sc.cash_shortfall)} short")
c3.metric("DTI", f"{sc.dti:.1%}", delta=f"max {sc.buyer.max_dti:.0%}", delta_color="off")
BINDING = {"payment": "target payment", "cash": "cash to close", "dti": "max DTI"}
c4.metric("Affordable price", money(aff.price),
          delta=f"limited by {BINDING[aff.binding]}", delta_color="off")

tabs = st.tabs(["Monthly cost", "Amortisation", "Points", "Rate sensitivity",
                "Goal-seek", "Points vs down", "Compare", "Save & share"])

# --- monthly breakdown ------------------------------------------------------

with tabs[0]:
    parts = [
        ("Principal & interest", sc.principal_and_interest),
        ("Property tax", sc.monthly_tax),
        ("Insurance", sc.monthly_insurance),
        ("HOA", sc.property.monthly_hoa),
        ("PMI", sc.monthly_pmi),
        ("Maintenance", sc.monthly_maintenance),
    ]
    left, right = st.columns([3, 2])
    with left:
        fig = go.Figure()
        for i, (name, val) in enumerate(parts):
            if val <= 0:
                continue  # keep slot colour tied to the component, skip empty ones
            fig.add_bar(
                y=["Monthly"], x=[val], name=name, orientation="h",
                marker=dict(color=P["series"][i], line=dict(color="rgba(0,0,0,0)", width=0)),
                text=[money(val)] if val / sc.monthly_total > 0.08 else None,
                textposition="inside", insidetextanchor="middle",
                textfont=dict(color="#0b0b0b" if P["series"][i] in ("#eda100", "#c98500") else "#ffffff"),
                hovertemplate=f"{name}: %{{x:$,.0f}}<extra></extra>",
            )
        if ss.target > 0:
            fig.add_vline(x=ss.target, line=dict(color=P["ink2"], width=2, dash="dot"),
                          annotation_text=f"Target {money(ss.target)}",
                          annotation_font_color=P["ink2"], annotation_position="bottom right")
        style(fig, 220, barmode="stack", bargap=0.35, title="Monthly cost breakdown",
              xaxis_tickprefix="$", xaxis_tickformat=",.0f", yaxis_visible=False)
        fig.update_traces(marker_line_width=2, marker_line_color="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")
    with right:
        df = pd.DataFrame(parts + [("Total", sc.monthly_total)], columns=["Component", "Monthly"])
        df["Share"] = df["Monthly"] / sc.monthly_total
        st.dataframe(df, hide_index=True, width="stretch",
                     column_config={"Monthly": st.column_config.NumberColumn(format="dollar"),
                                    "Share": st.column_config.NumberColumn(format="percent")})

    tco = compare.cost_of_ownership(sc)
    st.subheader(f"Cost of ownership over {sc.buyer.years_expected_to_stay} years")
    k1, k2, k3 = st.columns(3)
    k1.metric("Total paid (excl. down payment)", money(tco.total_paid))
    k2.metric("Principal paid down (equity)", money(tco.principal_paid))
    k3.metric("Net cost", money(tco.net_cost), help="Total paid minus principal paid down. "
              "Ignores appreciation, selling costs and opportunity cost.")
    tco_rows = [("Interest", tco.interest), ("PMI", tco.pmi), ("Property tax", tco.tax),
                ("Insurance", tco.insurance), ("HOA", tco.hoa), ("Maintenance", tco.maintenance),
                ("Closing costs", tco.closing), ("Points", tco.points)]
    st.dataframe(pd.DataFrame(tco_rows, columns=["Cost", "Amount"]), hide_index=True,
                 column_config={"Amount": st.column_config.NumberColumn(format="dollar")})

# --- amortisation & PMI -----------------------------------------------------

with tabs[1]:
    rows = sc.schedule()
    sched = pd.DataFrame([r.__dict__ for r in rows])
    drop = sc.pmi_drop_off_month
    stay_m = sc.buyer.years_expected_to_stay * 12

    fig = go.Figure()
    fig.add_scatter(x=sched.month, y=sched.balance, mode="lines", name="Loan balance",
                    line=dict(color=P["series"][0], width=2),
                    hovertemplate="Month %{x}<br>Balance %{y:$,.0f}<extra></extra>")
    fig.add_hline(y=0.8 * sc.property.price, line=dict(color=P["muted"], width=1, dash="dash"),
                  annotation_text="80% LTV", annotation_font_color=P["ink2"],
                  annotation_position="top right")
    if drop:
        fig.add_vline(x=drop, line=dict(color=P["series"][4], width=2),
                      annotation_text=f"PMI ends: month {drop} (year {drop / 12:.1f})",
                      annotation_font_color=P["ink2"], annotation_position="top right")
    if stay_m <= len(rows):
        fig.add_vline(x=stay_m, line=dict(color=P["muted"], width=1, dash="dot"),
                      annotation_text="Expected move", annotation_font_color=P["ink2"],
                      annotation_position="bottom left")
    style(fig, 360, title="Loan balance and PMI drop-off", hovermode="x unified",
          yaxis_tickprefix="$", yaxis_tickformat=",.0f", xaxis_title="Month", showlegend=False)
    st.plotly_chart(fig, width="stretch")
    if not drop:
        st.caption("No PMI: down payment is at least 20%." if sc.monthly_pmi == 0 else "")

    yearly = sched.assign(year=(sched.month - 1) // 12 + 1).groupby("year")[["interest", "principal", "pmi"]].sum()
    fig = go.Figure()
    for i, (col, name) in enumerate([("principal", "Principal"), ("interest", "Interest"), ("pmi", "PMI")]):
        if yearly[col].sum() == 0:
            continue
        fig.add_bar(x=yearly.index, y=yearly[col], name=name,
                    marker_color=[P["series"][0], P["series"][1], P["series"][4]][i],
                    hovertemplate=f"Year %{{x}}<br>{name} %{{y:$,.0f}}<extra></extra>")
    style(fig, 320, barmode="stack", bargap=0.15, title="Where each year's payments go",
          yaxis_tickprefix="$", yaxis_tickformat=",.0f", xaxis_title="Year", hovermode="x unified")
    fig.update_traces(marker_line_width=1, marker_line_color="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")
    with st.expander("Schedule table"):
        st.dataframe(sched, hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="dollar")
                                    for c in ["payment", "interest", "principal", "balance", "pmi"]})

# --- points break-even ------------------------------------------------------

with tabs[2]:
    cap = float(int(solve.max_points(sc) * 100) / 100)
    eval_points = st.number_input("Points to evaluate", min_value=0.0, step=0.25, max_value=cap,
                                  value=min(float(sc.loan.points) or 1.0, cap))
    psc = sc.with_changes(loan={"points": eval_points})
    be = psc.points_breakeven_months
    a, b, c = st.columns(3)
    a.metric("Points cost", money(psc.points_cost))
    b.metric("P&I saving / month", money(psc.points_monthly_saving, cents=True))
    c.metric("Break-even", "never" if math.isinf(be) else f"{be:.0f} months ({be / 12:.1f} yrs)",
             delta=None if math.isinf(be) else
             ("before you move" if be <= stay_m else "after you move"),
             delta_color="normal" if be <= stay_m else "inverse")
    if psc.points_cost > 0:
        horizon = int(min(sc.loan.term_years * 12, max(stay_m, be if not math.isinf(be) else 0) * 1.5 + 12))
        months = list(range(0, horizon + 1))
        fig = go.Figure()
        fig.add_scatter(x=months, y=[m * psc.points_monthly_saving for m in months], mode="lines",
                        name="Cumulative P&I saving", line=dict(color=P["series"][0], width=2),
                        hovertemplate="Month %{x}<br>Saved %{y:$,.0f}<extra></extra>")
        fig.add_hline(y=psc.points_cost, line=dict(color=P["series"][1], width=2),
                      annotation_text=f"Points cost {money(psc.points_cost)}",
                      annotation_font_color=P["ink2"], annotation_position="top left")
        if not math.isinf(be):
            fig.add_scatter(x=[be], y=[psc.points_cost], mode="markers", name="Break-even",
                            marker=dict(size=10, color=P["series"][0], line=dict(color="white", width=2)),
                            hovertemplate="Break-even month %{x:.0f}<extra></extra>")
        fig.add_vline(x=stay_m, line=dict(color=P["muted"], width=1, dash="dot"),
                      annotation_text="Expected move", annotation_font_color=P["ink2"])
        style(fig, 360, title="Points break-even", showlegend=False, hovermode="x",
              yaxis_tickprefix="$", yaxis_tickformat=",.0f", xaxis_title="Month")
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No points: break-even is infinite.")

# --- rate sensitivity -------------------------------------------------------

with tabs[3]:
    grid = compare.rate_sensitivity(sc)
    rates = [r * 100 for r, _ in grid]
    totals = [t for _, t in grid]
    fig = go.Figure()
    fig.add_scatter(x=rates, y=totals, mode="lines+markers", name="Monthly total",
                    line=dict(color=P["series"][0], width=2), marker=dict(size=8),
                    hovertemplate="Base rate %{x:.3f}%<br>Monthly %{y:$,.0f}<extra></extra>")
    fig.add_scatter(x=[sc.loan.base_rate * 100], y=[sc.monthly_total], mode="markers",
                    name="Current", marker=dict(size=13, color=P["series"][1], line=dict(color="white", width=2)),
                    hovertemplate="Current %{x:.3f}%<br>%{y:$,.0f}<extra></extra>")
    if ss.target > 0:
        fig.add_hline(y=ss.target, line=dict(color=P["ink2"], width=1, dash="dot"),
                      annotation_text=f"Target {money(ss.target)}", annotation_font_color=P["ink2"])
    style(fig, 380, title="Monthly total vs base rate (±1%, 0.125% steps)", showlegend=False,
          xaxis_title="Base rate (%)", xaxis_ticksuffix="%", yaxis_tickprefix="$", yaxis_tickformat=",.0f")
    st.plotly_chart(fig, width="stretch")
    st.dataframe(pd.DataFrame({"Base rate": [f"{r:.3f}%" for r in rates], "Monthly total": totals,
                               "Change": [t - sc.monthly_total for t in totals]}),
                 hide_index=True, column_config={
                     "Monthly total": st.column_config.NumberColumn(format="dollar"),
                     "Change": st.column_config.NumberColumn(format="dollar")})

# --- goal-seek --------------------------------------------------------------

with tabs[4]:
    st.subheader("Maximum price by constraint")
    st.caption("Down payment held as " + ("% of price" if ss.hold == "percent" else "a fixed $ amount")
               + "; tax and insurance scale with price.")
    st.dataframe(pd.DataFrame([
        {"Constraint": BINDING[k], "Max price": money(v), "Binding": "✓" if k == aff.binding else ""}
        for k, v in aff.by_constraint.items()
    ]), hide_index=True)
    st.caption(f"Max housing payment allowed by DTI: {money(solve.max_housing_payment_for_dti(sc))}/month")

    st.subheader("Hit a monthly payment at this price")
    tgt = st.number_input("Target monthly ($)", min_value=0.0, step=50.0, value=float(ss.target), key="gs_target")
    pts = solve.points_for_payment(sc, tgt)
    dp = solve.down_payment_for_payment(sc, tgt)
    g1, g2 = st.columns(2)
    if pts is None:
        g1.metric("Points needed", "not reachable", help="Even maximum points don't get there.")
    else:
        g1.metric("Points needed", f"{pts:.2f}",
                  delta=f"costs {money(sc.with_changes(loan={'points': pts}).points_cost)}", delta_color="off")
    if dp is None:
        g2.metric("Down payment needed", "not reachable", help="Even paying cash in full doesn't.")
    else:
        g2.metric("Down payment needed", money(dp), delta=f"{dp / sc.property.price:.1%} of price",
                  delta_color="off")

# --- points vs down ---------------------------------------------------------

with tabs[5]:
    extra = st.number_input("Extra cash to spend ($)", min_value=0.0, step=1_000.0,
                            value=float(max(1_000.0, round(ss.cash - sc.cash_to_close, -3))))
    if extra > 0:
        opts = compare.points_vs_down_payment(sc, extra)
        st.dataframe(pd.DataFrame([{
            "Option": o.label,
            "Monthly total": o.scenario.monthly_total,
            "Cash to close": o.scenario.cash_to_close,
            "Effective rate": f"{o.scenario.loan.effective_rate:.3%}",
            "PMI ends (month)": str(o.scenario.pmi_drop_off_month or "none"),
            f"Net cost over {sc.buyer.years_expected_to_stay} yrs": o.cost.net_cost,
        } for o in opts]), hide_index=True, width="stretch", column_config={
            c: st.column_config.NumberColumn(format="dollar")
            for c in ["Monthly total", "Cash to close", f"Net cost over {sc.buyer.years_expected_to_stay} yrs"]})
        fig = go.Figure()
        fig.add_bar(x=[o.label for o in opts], y=[o.cost.net_cost for o in opts],
                    marker_color=P["series"][0], text=[money(o.cost.net_cost) for o in opts],
                    textposition="outside", textfont_color=P["ink2"],
                    hovertemplate="%{x}<br>Net cost %{y:$,.0f}<extra></extra>")
        style(fig, 340, title=f"Net cost over {sc.buyer.years_expected_to_stay} years "
              "(interest, PMI, carrying costs, closing, points)", showlegend=False,
              yaxis_tickprefix="$", yaxis_tickformat=",.0f", bargap=0.5)
        st.plotly_chart(fig, width="stretch")
        best = min(opts[1:], key=lambda o: o.cost.net_cost)
        st.success(f"Over your expected stay, **{best.label}** costs less, by "
                   f"{money(abs(opts[1].cost.net_cost - opts[2].cost.net_cost))}.")

# --- saved scenarios --------------------------------------------------------

def save_current(name: str) -> None:
    saved = ss.saved
    if len(saved) >= 3:
        saved.pop(0)
    saved.append({"name": name, "inputs": {k: ss[k] for k in DEFAULTS}})


def load(i: int) -> None:
    for k, v in ss.saved[i]["inputs"].items():
        ss[k] = v


def remove(i: int) -> None:
    ss.saved.pop(i)


with tabs[6]:
    n1, n2 = st.columns([3, 1])
    name = n1.text_input("Scenario name", value=f"Scenario {len(ss.saved) + 1}", label_visibility="collapsed")
    n2.button("Save current", on_click=save_current, args=(name,), width="stretch",
              help="Keeps up to 3; saving a 4th drops the oldest.")
    if not ss.saved:
        st.info("Save up to 3 scenarios to compare them side by side.")
    else:
        def summary(s: Scenario) -> dict:
            a = solve.affordable_price(s, ss.hold)
            t = compare.cost_of_ownership(s)
            return {
                "Price": money(s.property.price), "Down payment": f"{money(s.loan.down_payment)} ({s.down_payment_pct:.1%})",
                "Effective rate": f"{s.loan.effective_rate:.3%}", "Points": f"{s.loan.points:.2f}",
                "Monthly total": money(s.monthly_total), "P&I": money(s.principal_and_interest),
                "PMI": money(s.monthly_pmi), "Cash to close": money(s.cash_to_close),
                "Cash shortfall": money(s.cash_shortfall), "DTI": f"{s.dti:.1%}",
                "PMI ends (month)": str(s.pmi_drop_off_month or "none"),
                "Points break-even": "never" if math.isinf(s.points_breakeven_months)
                else f"{s.points_breakeven_months:.0f} mo",
                f"Net cost over stay": money(t.net_cost),
                "Affordable price": f"{money(a.price)} ({BINDING[a.binding]})",
            }

        cols = {"Current (unsaved)": summary(sc)} | {e["name"]: summary(scenario_from_settings(e["inputs"])) for e in ss.saved}
        st.dataframe(pd.DataFrame(cols), width="stretch")
        bcols = st.columns(len(ss.saved))
        for i, (col, e) in enumerate(zip(bcols, ss.saved)):
            with col:
                st.markdown(f"**{e['name']}**")
                st.button("Load into inputs", key=f"load{i}", on_click=load, args=(i,))
                st.button("Remove", key=f"rm{i}", on_click=remove, args=(i,))

# --- save & share -----------------------------------------------------------


@st.cache_data(show_spinner=False, max_entries=20)
def cached_html(token: str, url: str) -> str:
    return report.render_html(decode_plan(token), url)


@st.cache_data(show_spinner=False, max_entries=20)
def cached_text(token: str, url: str) -> str:
    return report.render_text(decode_plan(token), url)


def load_uploaded() -> None:
    f = ss.get("plan_file")
    if f is None:
        return
    try:
        loaded = plan_from_file(f.getvalue())
        apply_plan(loaded)
        ss._flash = ("success", f"Opened saved plan: {loaded['name'] or f.name}")
    except PlanError as err:
        ss._flash = ("error", str(err))


with tabs[7]:
    st.subheader("Save & share this plan")
    st.caption("Give your plan a name and notes, then download a summary or share a link. "
               "Both include everything in the sidebar and any scenarios saved on the "
               "Compare tab.")
    st.text_input("Plan name", key="plan_name", max_chars=MAX_NAME,
                  placeholder="e.g. Oak St, 10% down, 1 point")
    st.text_area("Notes", key="plan_notes", max_chars=MAX_NOTES, height=110,
                 placeholder="What you decided and why, questions for the lender, next steps...")

    html_doc = cached_html(token, share_url)
    slug = re.sub(r"[^a-z0-9]+", "-", (ss.plan_name or "home-plan").lower()).strip("-") or "home-plan"

    d1, d2 = st.columns(2)
    with d1:
        st.markdown("**Download a summary**")
        st.caption("A formatted page with every number. Open it in any browser, print it to PDF, "
                   "or send it to someone. Upload it below later to reopen the plan.")
        st.download_button("Download summary", data=html_doc, file_name=f"{slug}.html",
                           mime="text/html", type="primary", icon=":material/download:",
                           on_click="ignore")
    with d2:
        st.markdown("**Share a link**")
        if share_url:
            st.caption("Anyone who opens this link sees exactly this plan. "
                       "Your browser's address bar always holds this link too.")
            st.code(share_url, language=None, wrap_lines=True)
        else:
            st.caption("Copy the address from your browser's address bar. It always holds "
                       "a link to exactly this plan.")

    with st.expander("Text summary (to paste into a message or email)"):
        st.code(cached_text(token, share_url), language=None)
    with st.expander("Preview the summary"):
        st.iframe(html_doc, height=900)  # our own generated HTML; user text is escaped

    st.divider()
    st.markdown("**Open a saved plan**")
    st.file_uploader("Upload a summary downloaded from this app", type=["html", "json"],
                     key="plan_file", on_change=load_uploaded, label_visibility="collapsed")
    st.caption("Opening a plan replaces your current inputs and saved scenarios.")
