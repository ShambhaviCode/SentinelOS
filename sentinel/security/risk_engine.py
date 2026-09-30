"""Risk engine: turns signals into an explainable score and level.

Scoring (documented in docs/risk-model.md):

1. Per scanner, signals combine with noisy-OR:  s = 1 - Π(1 - w_i)
   Several weak signals add up, but no score can exceed 1.
2. The local ML classifier contributes to the prompt-injection score only:
       s_inj = 1 - (1 - s_rules) * (1 - ml_weight * p_injection)
   With ml_weight = 0.55, the model alone can reach at most 0.55 (the MEDIUM band,
   REQUIRE_APPROVAL). A BLOCK on injection needs deterministic evidence too,
   which limits the damage from model false positives.
3. Overall = max(scanner scores) + combination_bonus for every *other* scanner
   scoring at least combination_min_score, capped at 1.0.
4. Level from thresholds: LOW < MEDIUM ≤ … < HIGH ≤ … < CRITICAL.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sentinel.models import MLResult, Signal


def noisy_or(weights: list[float]) -> float:
    p = 1.0
    for w in weights:
        p *= 1.0 - max(0.0, min(1.0, w))
    return 1.0 - p


@dataclass
class RiskAssessment:
    scores: dict[str, float]
    overall: float
    level: str
    primary_category: str
    contributions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scores": {k: round(v, 3) for k, v in self.scores.items()},
            "overall": round(self.overall, 3),
            "score_100": round(self.overall * 100),
            "level": self.level,
            "primary_category": self.primary_category,
            "contributions": self.contributions,
        }


def level_for(score: float, thresholds: dict[str, float]) -> str:
    if score >= thresholds["CRITICAL"]:
        return "CRITICAL"
    if score >= thresholds["HIGH"]:
        return "HIGH"
    if score >= thresholds["MEDIUM"]:
        return "MEDIUM"
    return "LOW"


def assess(signals: list[Signal], ml: Optional[MLResult], risk_cfg: dict[str, Any]) -> RiskAssessment:
    by_scanner: dict[str, list[Signal]] = {"prompt": [], "data": [], "tool": []}
    for s in signals:
        by_scanner.setdefault(s.scanner, []).append(s)

    scores = {k: noisy_or([s.weight for s in v]) for k, v in by_scanner.items()}
    contributions = [{"source": "rules", "scanner": k, "score": round(v, 3)} for k, v in scores.items()]

    if ml and ml.available and ml.injection_probability is not None:
        w = float(risk_cfg.get("ml_weight", 0.55))
        rules_only = scores["prompt"]
        scores["prompt"] = 1.0 - (1.0 - rules_only) * (1.0 - w * ml.injection_probability)
        contributions.append({"source": "ml", "scanner": "prompt",
                              "probability": round(ml.injection_probability, 4), "weight": w,
                              "score_after": round(scores["prompt"], 3)})

    top_scanner = max(scores, key=scores.get)
    overall = scores[top_scanner]
    bonus = float(risk_cfg.get("combination_bonus", 0.1))
    min_score = float(risk_cfg.get("combination_min_score", 0.3))
    extra = [k for k, v in scores.items() if k != top_scanner and v >= min_score]
    if extra:
        overall = min(1.0, overall + bonus * len(extra))
        contributions.append({"source": "combination", "scanners": extra, "bonus": bonus * len(extra)})

    level = level_for(overall, risk_cfg["thresholds"])

    primary = "NONE"
    if overall >= risk_cfg["thresholds"]["MEDIUM"]:
        pool = by_scanner.get(top_scanner) or []
        if pool:
            primary = max(pool, key=lambda s: s.weight).category
        elif top_scanner == "prompt":
            primary = "PROMPT_INJECTION"  # ML-only finding
    return RiskAssessment(scores=scores, overall=overall, level=level,
                          primary_category=primary, contributions=contributions)
