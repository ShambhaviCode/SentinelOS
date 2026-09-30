"""Core data types shared by every SentinelOS component."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional

LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
DECISIONS = ["ALLOW", "REQUIRE_APPROVAL", "BLOCK"]  # ordered by severity


@dataclass
class ToolRequest:
    tool: str = ""            # e.g. file.read, file.list, shell.exec, network.request, email.send
    target: str = ""          # path, URL, command or recipient
    scope: str = ""           # file | directory | recursive | profile | drive
    reason: str = ""
    payload: str = ""         # data the tool would carry out (e.g. request body)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional["ToolRequest"]:
        if not d or not d.get("tool"):
            return None
        return cls(**{k: str(d.get(k, "") or "") for k in ("tool", "target", "scope", "reason", "payload")})


@dataclass
class AgentRequest:
    prompt: str = ""
    context: str = ""
    context_source: str = "untrusted"   # untrusted | trusted
    tool_request: Optional[ToolRequest] = None
    preset_id: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "AgentRequest":
        return cls(
            prompt=str(d.get("prompt", "") or ""),
            context=str(d.get("context", "") or ""),
            context_source=str(d.get("context_source", "untrusted") or "untrusted"),
            tool_request=ToolRequest.from_dict(d.get("tool_request")),
            preset_id=d.get("preset_id"),
        )


@dataclass
class Signal:
    scanner: str          # prompt | data | tool
    category: str         # threat taxonomy category
    rule_id: str
    description: str
    weight: float         # 0..1 contribution to the scanner's risk
    source: str = ""      # prompt | context | tool_request
    evidence: str = ""    # redacted where the match is a secret

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PolicyVerdict:
    rule_id: str
    effect: str           # ALLOW | REQUIRE_APPROVAL | BLOCK
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MLResult:
    available: bool
    label: Optional[str] = None
    injection_probability: Optional[float] = None
    provider: Optional[str] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
