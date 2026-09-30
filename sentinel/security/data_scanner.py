"""Layer 1 sensitive-data detection.

Deterministic patterns for secrets, credentials and personal identifiers.
Evidence for secret-class matches is redacted so the UI and audit log never
store the full value.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sentinel.models import Signal


@dataclass(frozen=True)
class DataRule:
    rule_id: str
    kind: str
    description: str
    weight: float
    pattern: re.Pattern
    secret: bool = False          # redact evidence
    validator: object = None      # optional callable(str) -> bool


def _luhn(value: str) -> bool:
    digits = [int(c) for c in value if c.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


RULES: list[DataRule] = [
    DataRule("DS-01", "private_key", "Private key material", 0.95,
             re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"), secret=True),
    DataRule("DS-02", "cloud_access_key", "Cloud access key identifier", 0.85,
             re.compile(r"\bAKIA[0-9A-Z]{16}\b"), secret=True),
    DataRule("DS-03", "api_token", "API token with a known provider prefix", 0.85,
             re.compile(r"\b(?:sk|pk|rk)[-_](?:live|test|proj)?[-_]?[A-Za-z0-9]{20,}\b|\bgh[pousr]_[A-Za-z0-9]{30,}\b|"
                        r"\bxox[abpr]-[A-Za-z0-9-]{10,}\b"), secret=True),
    DataRule("DS-04", "credential_assignment", "Password or secret assigned in text", 0.80,
             re.compile(r"\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)\b\s*[:=]\s*[\"']?[^\s\"']{6,}",
                        re.IGNORECASE), secret=True),
    DataRule("DS-05", "payment_card", "Payment-card-like number (Luhn valid)", 0.70,
             re.compile(r"\b(?:\d[ -]?){13,19}\b"), secret=True, validator=_luhn),
    DataRule("DS-06", "national_id", "National-ID-like identifier (SSN / Aadhaar / PAN format)", 0.60,
             re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b\d{4}\s\d{4}\s\d{4}\b|\b[A-Z]{5}\d{4}[A-Z]\b"), secret=True),
    DataRule("DS-07", "bank_account", "IBAN-like bank account identifier", 0.55,
             re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}\b"), secret=True),
    DataRule("DS-08", "email_address", "Email address", 0.25,
             re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    DataRule("DS-09", "phone_number", "Phone number", 0.25,
             re.compile(r"\+\d{1,3}[\s-]?\d{2,5}[\s-]?\d{3,5}(?:[\s-]?\d{3,4})?\b|\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")),
    DataRule("DS-10", "confidential_marker", "Document is marked confidential", 0.30,
             re.compile(r"\b(?:confidential|internal\s+only|do\s+not\s+distribute|trade\s+secret|restricted\s+distribution)\b",
                        re.IGNORECASE)),
]


def redact(value: str) -> str:
    value = value.strip()
    if len(value) <= 8:
        return value[:2] + "•" * max(len(value) - 2, 3)
    return value[:4] + "•" * 8 + value[-2:]


def scan_text(text: str, source: str) -> list[Signal]:
    signals: list[Signal] = []
    if not text:
        return signals
    seen_spans: list[tuple[int, int]] = []
    for rule in RULES:
        for m in rule.pattern.finditer(text):
            if rule.validator and not rule.validator(m.group(0)):
                continue
            # Don't double-count a span already claimed by a stronger rule (e.g. a card number read as a phone number).
            if any(m.start() < e and s < m.end() for s, e in seen_spans):
                continue
            seen_spans.append((m.start(), m.end()))
            evidence = redact(m.group(0)) if rule.secret else m.group(0)
            signals.append(Signal(scanner="data", category="DATA_EXPOSURE", rule_id=rule.rule_id,
                                  description=rule.description, weight=rule.weight,
                                  source=source, evidence=evidence))
            break  # one signal per rule per field keeps scores stable
    return signals


def scan(prompt: str, context: str, payload: str = "") -> list[Signal]:
    return scan_text(prompt, "prompt") + scan_text(context, "context") + scan_text(payload, "tool_request")
