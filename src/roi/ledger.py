"""Phase 6: intervention ledger validation and the ROI arithmetic behind GET /roi/summary.

Everything here is pure (no DB) so it is unit-testable; src/api/routes.py and
scripts/simulate_interventions.py do the I/O. The policy in config/interventions.yaml is a set of
ASSUMPTIONS -- see docs/uplift-method.md for why this is a simulation, not measured uplift.
"""
from __future__ import annotations

from pathlib import Path

import yaml

DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[2] / "config" / "interventions.yaml"
SIMULATION_LABEL = ("SIMULATION: effect sizes and costs are assumptions from config/interventions.yaml, "
                    "not measured uplift. Nothing here was estimated from a randomized experiment.")


class InterventionValidationError(ValueError):
    pass


def load_policy(path: str | Path = DEFAULT_POLICY_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text())


def validate_intervention(payload: dict, policy: dict) -> dict:
    """Returns the normalised row to insert or raises InterventionValidationError."""
    types = policy["types"]
    itype = payload.get("intervention_type") or policy["default_type"]
    if itype not in types:
        raise InterventionValidationError(f"unknown intervention_type '{itype}'; valid: {sorted(types)}")
    if not str(payload.get("case_id") or "").strip():
        raise InterventionValidationError("case_id is required")
    risk = payload.get("risk_at_intervention")
    if risk is None or isinstance(risk, bool) or not 0 <= float(risk) <= 1:
        raise InterventionValidationError("risk_at_intervention must be a number between 0 and 1")
    cost = types[itype]["cost"] if payload.get("cost") is None else payload["cost"]
    if isinstance(cost, bool) or float(cost) < 0:
        raise InterventionValidationError("cost must be >= 0")
    return {"case_id": str(payload["case_id"]).strip(), "intervention_type": itype,
            "risk_at_intervention": float(risk), "cost": float(cost),
            "breached_after": payload.get("breached_after"), "notes": payload.get("notes")}


def _bucket(rows: list[dict], policy: dict) -> dict:
    """ROI for one group of ledger rows. Avoided breaches use the policy's assumed relative effect:
    by model risk (sum of risk * effect) and, where outcomes are known, by observed breaches
    (count of breached treated cases * effect -- the counterfactual is still assumed)."""
    n = len(rows)
    cost = sum(float(r["cost"]) for r in rows)
    by_risk = sum(float(r["risk_at_intervention"]) * policy["types"].get(r["intervention_type"], {"effect": 0})["effect"]
                  for r in rows)
    known = [r for r in rows if r.get("breached_after") is not None]
    by_outcome = sum(policy["types"].get(r["intervention_type"], {"effect": 0})["effect"]
                     for r in known if r["breached_after"])
    value = lambda avoided: avoided * policy["breach_cost"]
    return {
        "interventions": n, "total_cost": round(cost, 2),
        "avoided_breaches_by_model_risk": round(by_risk, 2),
        "net_value_by_model_risk": round(value(by_risk) - cost, 2),
        "outcomes_known": len(known),
        "avoided_breaches_by_observed_outcomes": round(by_outcome, 2),
        "net_value_by_observed_outcomes": round(value(by_outcome) - sum(float(r["cost"]) for r in known), 2),
    }


def break_even_effect(rows: list[dict], policy: dict) -> float | None:
    """Uniform relative effect at which model-risk net value is zero: cost / (breach_cost * sum(risk))."""
    total_risk = sum(float(r["risk_at_intervention"]) for r in rows)
    if not rows or total_risk == 0:
        return None
    return round(sum(float(r["cost"]) for r in rows) / (policy["breach_cost"] * total_risk), 4)


def roi_summary(rows: list[dict], policy: dict) -> dict:
    sim = [r for r in rows if r.get("is_simulated")]
    real = [r for r in rows if not r.get("is_simulated")]
    return {
        "label": SIMULATION_LABEL,
        "assumptions": {"breach_cost": policy["breach_cost"], "capacity_pct": policy["capacity_pct"],
                        "types": policy["types"]},
        "simulated": _bucket(sim, policy),
        "logged": _bucket(real, policy),
        "break_even_effect_simulated": break_even_effect(sim, policy),
    }
