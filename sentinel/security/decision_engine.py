"""Decision engine: the final ALLOW / REQUIRE_APPROVAL / BLOCK call.

final = most severe of (decision_map[risk level], every policy verdict)

A policy verdict can only make a decision stricter, never looser. The level
reported alongside a policy-driven BLOCK is raised to at least HIGH so the
level and decision never contradict each other.
"""
from __future__ import annotations

from typing import Any

from sentinel.models import PolicyVerdict
from sentinel.security.policy_engine import PolicyEngine, most_severe
from sentinel.security.risk_engine import RiskAssessment

MIN_LEVEL_FOR = {"BLOCK": "HIGH", "REQUIRE_APPROVAL": "MEDIUM", "ALLOW": "LOW"}
LEVEL_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def decide(risk: RiskAssessment, verdicts: list[PolicyVerdict], engine: PolicyEngine) -> dict[str, Any]:
    from_level = engine.decision_for_level(risk.level)
    decision = most_severe([from_level] + [v.effect for v in verdicts])

    level = risk.level
    floor = MIN_LEVEL_FOR[decision]
    if LEVEL_ORDER.index(level) < LEVEL_ORDER.index(floor):
        level = floor

    drivers = [v.to_dict() for v in verdicts if v.effect == decision and decision != "ALLOW"]
    if from_level == decision and decision != "ALLOW":
        drivers.insert(0, {"rule_id": "RISK-LEVEL", "effect": decision,
                           "reason": f"Risk level {risk.level} maps to {decision}."})
    return {
        "decision": decision,
        "level": level,
        "level_from_score": risk.level,
        "decision_from_level": from_level,
        "drivers": drivers,
        "policy_verdicts": [v.to_dict() for v in verdicts],
    }
