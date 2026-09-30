"""Agent Gateway: the single entry point every agent request passes through.

request → prompt / data / tool scanners → local ML classifier → risk engine
        → policy engine → decision engine → audit timeline
"""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Optional

from sentinel.audit import AuditLog
from sentinel.models import AgentRequest, MLResult
from sentinel.security import data_scanner, prompt_scanner, tool_scanner
from sentinel.security.decision_engine import decide
from sentinel.security.policy_engine import PolicyEngine
from sentinel.security.risk_engine import assess, noisy_or
from sentinel.security.taxonomy import TAXONOMY


class Gateway:
    def __init__(self, policy: Optional[PolicyEngine] = None, classifier: Any = None,
                 audit: Optional[AuditLog] = None):
        self.policy = policy or PolicyEngine()
        self.classifier = classifier          # None → deterministic engine only
        self.audit = audit

    def analyze(self, req: AgentRequest | dict) -> dict[str, Any]:
        if isinstance(req, dict):
            req = AgentRequest.from_dict(req)
        timings: dict[str, float] = {}
        t_start = time.perf_counter()

        def lap(name: str, t0: float) -> float:
            now = time.perf_counter()
            timings[name] = round((now - t0) * 1000, 3)
            return now

        t = time.perf_counter()
        prompt_signals = prompt_scanner.scan(req.prompt, req.context, req.context_source)
        t = lap("prompt_scan", t)
        payload = req.tool_request.payload if req.tool_request else ""
        data_signals = data_scanner.scan(req.prompt, req.context, payload)
        t = lap("data_scan", t)
        tool_signals, tool_verdicts = tool_scanner.scan(req.tool_request, self.policy.policies)
        t = lap("tool_scan", t)

        if self.classifier is not None:
            ml = self.classifier.classify_fields(req.prompt, req.context)
        else:
            ml = MLResult(available=False, error="ML classifier not loaded")
        t = lap("ml_inference", t)

        signals = prompt_signals + data_signals + tool_signals
        risk = assess(signals, ml, self.policy.risk)
        t = lap("risk_engine", t)

        secret_score = noisy_or([s.weight for s in data_signals if s.weight >= 0.5])
        verdicts = tool_verdicts + self.policy.cross_cutting(req.tool_request, risk.scores["prompt"], secret_score)
        decision = decide(risk, verdicts, self.policy)
        lap("policy_and_decision", t)
        timings["total"] = round((time.perf_counter() - t_start) * 1000, 3)
        timings["total_excluding_ml"] = round(timings["total"] - timings["ml_inference"], 3)

        category = risk.primary_category
        if category == "NONE" and decision["decision"] != "ALLOW":
            category = next((s.category for s in sorted(signals, key=lambda s: -s.weight)), "POLICY_VIOLATION")
        info = TAXONOMY[category]
        reasoning = [s.description for s in sorted(signals, key=lambda s: -s.weight)[:4]]
        reasoning += [d["reason"] for d in decision["drivers"] if d["rule_id"] != "RISK-LEVEL"]

        event = {
            "id": uuid.uuid4().hex[:12],
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "preset_id": req.preset_id,
            "request": {
                "prompt": req.prompt, "context": req.context, "context_source": req.context_source,
                "tool_request": asdict(req.tool_request) if req.tool_request else None,
            },
            "signals": [s.to_dict() for s in signals],
            "ml": ml.to_dict(),
            "risk": risk.to_dict(),
            "decision": decision,
            "threat": {"category": category, **info},
            "reasoning": list(dict.fromkeys(reasoning)),
            "timings_ms": timings,
        }
        if self.audit is not None:
            self.audit.record(event)
        return event
