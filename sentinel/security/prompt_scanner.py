"""Layer 1 prompt-injection detection: weighted, categorized patterns.

Patterns allow a few intervening words between key terms, so "ignore all of the
previous instructions" and "please disregard your earlier rules" both match the
same rule. This detects known patterns; it does not claim to catch every attack.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sentinel.models import Signal

GAP = r"(?:\W+\w+){0,5}?\W+"  # up to five intervening words

TARGET_WORDS = r"(?:instructions?|rules|directives|guidelines|prompts?|constraints|programming|guardrails)"


@dataclass(frozen=True)
class Rule:
    rule_id: str
    signal: str
    description: str
    weight: float
    pattern: re.Pattern


def _r(p: str) -> re.Pattern:
    return re.compile(p, re.IGNORECASE | re.MULTILINE)


RULES: list[Rule] = [
    Rule("PI-01", "instruction_override",
         "Attempts to override or discard the agent's existing instructions", 0.85,
         _r(rf"\b(?:ignore|disregard|forget|override|overrule|discard)\b{GAP}{TARGET_WORDS}\b")),
    Rule("PI-02", "system_prompt_extraction",
         "Asks the agent to reveal hidden or system-level instructions", 0.80,
         _r(rf"\b(?:reveal|print|show|display|repeat|output|leak|expose|dump)\b{GAP}"
            r"(?:system\s+prompt|hidden\s+instructions?|initial\s+instructions?|developer\s+(?:message|instructions?)|"
            r"your\s+instructions|confidential\s+(?:instructions?|information|data))")),
    Rule("PI-03", "role_hijack",
         "Tries to give the agent a new, unrestricted identity", 0.70,
         _r(r"\b(?:you\s+are\s+now|from\s+now\s+on,?\s+you\s+are|act\s+as|pretend\s+(?:to\s+be|you\s+are)|roleplay\s+as)\b"
            r"(?:\W+\w+){0,5}?\W+(?:unrestricted|unfiltered|jailbroken|dan|developer\s+mode|admin(?:istrator)?|root|"
            r"a\s+different\s+(?:system|assistant)|without\s+(?:limits|restrictions))")),
    Rule("PI-04", "guardrail_bypass",
         "Asks the agent to bypass or disable safety controls", 0.80,
         _r(rf"\b(?:bypass|disable|circumvent|turn\s+off|deactivate|evade|get\s+around)\b{GAP}"
            r"(?:safety|security|restrictions?|filters?|guardrails?|polic(?:y|ies)|monitoring|sentinel\w*|controls?)")),
    Rule("PI-05", "instruction_smuggling",
         "Embeds a new instruction block inside content", 0.60,
         _r(r"(?:\b(?:new|updated|real|actual|revised)\s+(?:instructions?|task|objective)\s*:|"
            r"\bfollow\s+these\s+instructions\s+instead\b|\[\s*(?:system|admin|developer)\s*\]|"
            r"^\s*#{1,6}\s*system\b|<\s*/?\s*system\s*>)")),
    Rule("PI-06", "covert_action",
         "Asks the agent to hide its actions from the user", 0.60,
         _r(r"(?:\b(?:do\s+not|don't|never)\s+(?:tell|inform|alert|notify|mention\s+(?:this\s+)?to)\b(?:\W+\w+){0,3}?\W+"
            r"(?:user|anyone|operator|human|owner)|\bwithout\s+(?:telling|informing|notifying)\s+(?:the\s+)?(?:user|anyone)|"
            r"\b(?:secretly|silently|covertly)\b)")),
    Rule("PI-07", "exfiltration_directive",
         "Directs the agent to send data to an outside destination", 0.70,
         _r(rf"\b(?:send|upload|post|forward|email|transmit|exfiltrate|copy)\b{GAP}(?:to|at)\b(?:\W+\w+){{0,3}}?\W*"
            r"(?:https?://\S+|\S+@\S+\.\w+|external|attacker|this\s+(?:address|url|server|endpoint))")),
    Rule("PI-08", "scope_escalation",
         "Pushes the agent to access resources outside its task", 0.60,
         _r(r"(?:\b(?:access|read|open|list|scan|search|collect)\b(?:\W+\w+){0,3}?\W+(?:all|every|entire|any|other)\s+"
            r"(?:files?|folders?|directories|documents|drives?|emails?)\b|\boutside\s+(?:of\s+)?(?:your|the)\s+"
            r"(?:current\s+)?(?:task|scope|workspace|project))")),
]

SOURCE_MULTIPLIER = {"context:untrusted": 1.0, "context:trusted": 0.7, "prompt": 0.9}


def _evidence(text: str, start: int, end: int, limit: int = 180) -> str:
    """Return the sentence containing the match, trimmed to `limit` characters."""
    left = max(text.rfind(".", 0, start), text.rfind("\n", 0, start)) + 1
    right_candidates = [i for i in (text.find(".", end), text.find("\n", end)) if i != -1]
    right = min(right_candidates) + 1 if right_candidates else len(text)
    snippet = text[left:right].strip()
    return snippet if len(snippet) <= limit else snippet[: limit - 1] + "…"


def scan(prompt: str, context: str, context_source: str = "untrusted") -> list[Signal]:
    signals: list[Signal] = []
    fields = [("prompt", prompt, SOURCE_MULTIPLIER["prompt"]),
              ("context", context, SOURCE_MULTIPLIER.get(f"context:{context_source}", 1.0))]
    for source, text, mult in fields:
        if not text:
            continue
        for rule in RULES:
            m = rule.pattern.search(text)
            if m:
                signals.append(Signal(
                    scanner="prompt", category="PROMPT_INJECTION", rule_id=rule.rule_id,
                    description=rule.description, weight=round(rule.weight * mult, 3),
                    source=source, evidence=_evidence(text, m.start(), m.end()),
                ))
    return signals
