"""App settings: the flat set of user inputs, how they map to a Scenario, and
how a whole plan (settings + name + notes + saved scenarios) is packed into a
URL-safe string or a file and read back.

No Streamlit here, so it can be tested on its own.
"""

from __future__ import annotations

import base64
import json
import re
import zlib
from typing import Any

from .models import Buyer, ClosingCosts, Loan, Property, Scenario

FORMAT_VERSION = 1

# Every sidebar input, with its default. Types here are the types we coerce to.
DEFAULTS: dict[str, Any] = dict(
    price=450_000.0, tax=5_400.0, insurance=1_800.0, hoa=0.0, maint_pct=1.0,
    dp_mode="%", dp_pct=10.0, dp_amt=45_000.0,
    rate_pct=6.5, term=30, points=0.0, cut_pct=0.25, point_cost_pct=1.0, pmi_pct=0.5,
    lender_fees=3_500.0, title=2_000.0, appraisal=650.0, inspection=500.0,
    prepaid_escrow=2_500.0, moving=3_000.0,
    cash=80_000.0, target=3_200.0, income=12_500.0, debt=600.0, max_dti_pct=36.0, stay=7,
    hold="percent",
)

CHOICES: dict[str, tuple] = {
    "dp_mode": ("%", "$"),
    "term": (10, 15, 20, 25, 30),
    "hold": ("percent", "amount"),
}

MAX_SAVED = 3
MAX_NAME = 80
MAX_NOTES = 2_000


class PlanError(ValueError):
    """A shared plan couldn't be read."""


def clean_settings(raw: dict) -> dict[str, Any]:
    """Known keys only, coerced to the default's type; anything missing or
    unreadable falls back to the default. Range checks are left to the models."""
    out = dict(DEFAULTS)
    if not isinstance(raw, dict):
        return out
    for key, default in DEFAULTS.items():
        if key not in raw:
            continue
        try:
            if isinstance(default, str):
                value = str(raw[key])
            elif isinstance(default, int):
                value = int(raw[key])
            else:
                value = float(raw[key])
                if value != value or value in (float("inf"), float("-inf")):
                    continue
        except (TypeError, ValueError):
            continue
        if key in CHOICES and value not in CHOICES[key]:
            continue
        if isinstance(value, (int, float)) and value < 0:
            continue
        out[key] = value
    return out


def down_payment(s: dict) -> float:
    return s["price"] * s["dp_pct"] / 100 if s["dp_mode"] == "%" else s["dp_amt"]


def scenario_from_settings(s: dict) -> Scenario:
    """Build a Scenario from flat settings. Raises pydantic.ValidationError."""
    return Scenario(
        property=Property(price=s["price"], annual_property_tax=s["tax"],
                          annual_insurance=s["insurance"], monthly_hoa=s["hoa"],
                          maintenance_rate=s["maint_pct"] / 100),
        loan=Loan(down_payment=down_payment(s), base_rate=s["rate_pct"] / 100,
                  term_years=s["term"], points=s["points"],
                  rate_cut_per_point=s["cut_pct"] / 100,
                  point_cost_pct=s["point_cost_pct"] / 100, pmi_rate=s["pmi_pct"] / 100),
        closing=ClosingCosts(lender_fees=s["lender_fees"], title=s["title"],
                             appraisal=s["appraisal"], inspection=s["inspection"],
                             prepaid_escrow=s["prepaid_escrow"], moving_and_repairs=s["moving"]),
        buyer=Buyer(cash_available=s["cash"], target_monthly_payment=s["target"],
                    gross_monthly_income=s["income"], other_monthly_debt=s["debt"],
                    max_dti=s["max_dti_pct"] / 100, years_expected_to_stay=s["stay"]),
    )


# --- whole-plan payload -------------------------------------------------------

def make_plan(settings: dict, name: str = "", notes: str = "",
              saved: list[dict] | None = None) -> dict:
    """A plan payload. `saved` is a list of {"name", "inputs"}."""
    return {
        "v": FORMAT_VERSION,
        "name": name[:MAX_NAME],
        "notes": notes[:MAX_NOTES],
        "settings": clean_settings(settings),
        "saved": [
            {"name": str(e.get("name", ""))[:MAX_NAME], "inputs": clean_settings(e.get("inputs", {}))}
            for e in (saved or [])[-MAX_SAVED:]
        ],
    }


def clean_plan(raw: Any) -> dict:
    if not isinstance(raw, dict) or "settings" not in raw:
        raise PlanError("This doesn't look like a saved plan.")
    saved = raw.get("saved") if isinstance(raw.get("saved"), list) else []
    return make_plan(
        raw["settings"],
        str(raw.get("name") or ""),
        str(raw.get("notes") or ""),
        [e for e in saved if isinstance(e, dict)],
    )


def encode_plan(plan: dict) -> str:
    """Compact, URL-safe string for a plan (JSON, deflated, base64url)."""
    data = json.dumps(plan, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(zlib.compress(data, 9)).decode().rstrip("=")


def decode_plan(token: str) -> dict:
    try:
        padded = token + "=" * (-len(token) % 4)
        data = zlib.decompress(base64.urlsafe_b64decode(padded.encode()), bufsize=1 << 16)
        if len(data) > 200_000:
            raise ValueError("too large")
        return clean_plan(json.loads(data))
    except PlanError:
        raise
    except Exception as e:
        raise PlanError("This plan link is damaged or incomplete.") from e


_EMBED_RE = re.compile(
    r'<script type="application/json" id="house-plan">(.*?)</script>', re.S
)


def embed_plan(plan: dict) -> str:
    """A <script> block carrying the plan, safe to drop into HTML."""
    body = json.dumps(plan, indent=1).replace("</", "<\\/")
    return f'<script type="application/json" id="house-plan">{body}</script>'


def plan_from_file(content: bytes) -> dict:
    """Read a plan from a downloaded summary (.html) or a plain .json file."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as e:
        raise PlanError("Couldn't read that file.") from e
    match = _EMBED_RE.search(text)
    try:
        raw = json.loads(match.group(1) if match else text)
    except json.JSONDecodeError as e:
        raise PlanError("That file doesn't contain a saved plan. "
                        "Upload a summary downloaded from this app.") from e
    return clean_plan(raw)
