import pytest

from house_calc import report
from house_calc.settings import (
    DEFAULTS, PlanError, clean_settings, decode_plan, encode_plan, make_plan,
    plan_from_file, scenario_from_settings,
)


def sample_plan():
    s = dict(DEFAULTS, price=525_000.0, dp_pct=20.0, points=1.0)
    other = dict(DEFAULTS, price=400_000.0)
    return make_plan(s, "Oak St <b>offer</b>", "Ask about rate lock.\nSecond line.",
                     [{"name": "Elm Ave", "inputs": other}])


def test_link_round_trip():
    plan = sample_plan()
    assert decode_plan(encode_plan(plan)) == plan


def test_link_is_short_enough():
    assert len(encode_plan(sample_plan())) < 2_000


def test_damaged_link_raises_plan_error():
    token = encode_plan(sample_plan())
    for bad in ["", "not-a-plan", token[: len(token) // 2]]:
        with pytest.raises(PlanError):
            decode_plan(bad)


def test_clean_settings_rejects_junk():
    s = clean_settings({"price": "abc", "term": 17, "dp_mode": "%", "hold": "x",
                        "cash": -5, "rate_pct": "7.25", "unknown": 1, "stay": 10})
    assert s["price"] == DEFAULTS["price"]
    assert s["term"] == DEFAULTS["term"]
    assert s["hold"] == DEFAULTS["hold"]
    assert s["cash"] == DEFAULTS["cash"]
    assert s["rate_pct"] == 7.25
    assert s["stay"] == 10
    assert "unknown" not in s


def test_scenario_from_settings_down_payment_modes():
    pct = scenario_from_settings(dict(DEFAULTS, dp_mode="%", dp_pct=15.0))
    amt = scenario_from_settings(dict(DEFAULTS, dp_mode="$", dp_amt=60_000.0))
    assert pct.loan.down_payment == pytest.approx(DEFAULTS["price"] * 0.15)
    assert amt.loan.down_payment == 60_000


def test_html_summary_round_trips_and_escapes():
    plan = sample_plan()
    html = report.render_html(plan, "https://example.test/?plan=abc")
    assert "&lt;b&gt;offer&lt;/b&gt;" in html and "<b>offer</b>" not in html.split("<script")[0]
    assert "Elm Ave" in html
    assert plan_from_file(html.encode()) == plan


def test_text_summary_contains_key_numbers():
    plan = sample_plan()
    sc = scenario_from_settings(plan["settings"])
    text = report.render_text(plan, "https://example.test/?plan=abc")
    assert f"${sc.monthly_total:,.0f}" in text
    assert f"${sc.cash_to_close:,.0f}" in text
    assert "Ask about rate lock." in text
    assert "https://example.test/?plan=abc" in text


def test_plain_json_file_loads():
    import json
    plan = sample_plan()
    assert plan_from_file(json.dumps(plan).encode()) == plan


def test_bad_file_raises():
    with pytest.raises(PlanError):
        plan_from_file(b"<html>nothing here</html>")
