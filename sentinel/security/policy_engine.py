"""Policy engine: loads the policy file and evaluates cross-cutting rules.

Tool-specific rules live in tool_scanner.py (they need the same parsing of the
tool request). This module owns the configuration and the rules that combine
findings from several scanners.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Optional

from sentinel.models import DECISIONS, PolicyVerdict, ToolRequest

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = ROOT / "config" / "policies.json"

EGRESS_TOOLS = {"network.request", "network.upload", "email.send", "file.upload", "http.post"}


def load_policies(path: Optional[Path] = None) -> dict[str, Any]:
    with open(path or DEFAULT_POLICY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def most_severe(effects: list[str]) -> str:
    if not effects:
        return "ALLOW"
    return max(effects, key=DECISIONS.index)


class PolicyEngine:
    def __init__(self, policies: Optional[dict[str, Any]] = None):
        self.policies = copy.deepcopy(policies) if policies else load_policies()

    @property
    def risk(self) -> dict[str, Any]:
        return self.policies["risk"]

    def cross_cutting(self, tool: Optional[ToolRequest], injection_score: float,
                      secret_score: float) -> list[PolicyVerdict]:
        cfg = self.policies["cross_cutting"]
        verdicts: list[PolicyVerdict] = []
        medium = self.risk["thresholds"]["MEDIUM"]
        if tool and cfg.get("block_tool_after_injection") and injection_score >= medium:
            verdicts.append(PolicyVerdict(
                "XC-01", "BLOCK",
                "A tool request arrived in the same turn as a likely prompt injection, so it is treated "
                "as potentially attacker-influenced."))
        is_egress = bool(tool and tool.tool in EGRESS_TOOLS)
        threshold = cfg.get("secret_score_threshold", 0.6)
        if is_egress and cfg.get("block_sensitive_egress") and secret_score >= threshold:
            verdicts.append(PolicyVerdict(
                "XC-02", "BLOCK",
                "Secrets or personal identifiers would leave the machine through an outbound tool."))
        elif cfg.get("review_secrets_in_context") and secret_score >= threshold:
            verdicts.append(PolicyVerdict(
                "XC-03", "REQUIRE_APPROVAL",
                "Credential-class data is present in the agent's working context; a person should "
                "review it before the agent continues."))
        return verdicts

    def decision_for_level(self, level: str) -> str:
        return self.risk["decision_map"][level]

    def summary(self) -> dict[str, Any]:
        """A read-only view for the Policies screen."""
        return copy.deepcopy(self.policies)
