"""Layer 1 tool-risk analysis.

Evaluates the tool, target, scope and stated reason of an agent's proposed
action against the policy file. Returns risk signals plus the policy verdicts
they imply. Nothing is executed here: tools in SentinelOS are simulated.
"""
from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlparse

from sentinel.models import PolicyVerdict, Signal, ToolRequest

EFFECT_WEIGHT = {"ALLOW": 0.05, "REQUIRE_APPROVAL": 0.40, "BLOCK": 0.85}

VAGUE_REASONS = re.compile(
    r"\b(additional|more|extra|broader|general)\s+context\b|\bjust\s+in\s+case\b|\bmight\s+be\s+(useful|helpful)\b|"
    r"\bto\s+be\s+safe\b|\bexplore\b|\bfor\s+completeness\b", re.IGNORECASE)

PROFILE_PATTERNS = re.compile(
    r"^(?:[a-z]:)?[\\/]+users[\\/]+[^\\/]+[\\/]?$|^~[\\/]?$|^%userprofile%[\\/]?$|^/home/[^/]+/?$", re.IGNORECASE)
DRIVE_PATTERNS = re.compile(r"^(?:[a-z]:[\\/]?|/)$", re.IGNORECASE)


def _norm(path: str) -> str:
    return path.strip().replace("\\", "/")


def infer_scope(tool: ToolRequest) -> str:
    if tool.scope:
        return tool.scope.lower()
    target = _norm(tool.target)
    if DRIVE_PATTERNS.match(target):
        return "drive"
    if PROFILE_PATTERNS.match(target):
        return "profile"
    if "**" in target:
        return "recursive"
    last = target.rstrip("/").split("/")[-1]
    if target.endswith("/") or "." not in last or "*" in last:
        return "directory"
    return "file"


def _in_workspace(target: str, roots: list[str]) -> bool:
    t = _norm(target).lower()
    return any(t.startswith(_norm(r).lower().rstrip("/")) for r in roots)


def _signal(category: str, rule_id: str, description: str, effect: str, evidence: str,
            weight: Optional[float] = None) -> Signal:
    return Signal(scanner="tool", category=category, rule_id=rule_id, description=description,
                  weight=EFFECT_WEIGHT[effect] if weight is None else weight,
                  source="tool_request", evidence=evidence)


def scan(tool: Optional[ToolRequest], policies: dict[str, Any]) -> tuple[list[Signal], list[PolicyVerdict]]:
    signals: list[Signal] = []
    verdicts: list[PolicyVerdict] = []
    if tool is None:
        return signals, verdicts

    name = tool.tool.lower()
    evidence = f"{tool.tool} → {tool.target}" + (f" (scope: {tool.scope})" if tool.scope else "")

    if name.startswith("file."):
        cfg = policies["file_access"]
        scope = infer_scope(tool)
        effect = cfg["scope_effects"].get(scope, "REQUIRE_APPROVAL")
        if scope != "file":
            signals.append(_signal("EXCESSIVE_PRIVILEGE", "TR-01",
                                   f"Requests {scope}-level file access", effect, evidence))
            verdicts.append(PolicyVerdict("FA-SCOPE", effect,
                                          f"File access policy: '{scope}' scope → {effect}."))
            if VAGUE_REASONS.search(tool.reason or "") or not tool.reason.strip():
                signals.append(_signal("EXCESSIVE_PRIVILEGE", "TR-02",
                                       "Broad access is justified with a vague or missing reason",
                                       "REQUIRE_APPROVAL", f"Reason given: “{tool.reason or 'none'}”", weight=0.35))
        lowered = _norm(tool.target).lower()
        hit = next((m for m in cfg["sensitive_path_markers"] if m.lower() in lowered), None)
        if hit:
            signals.append(_signal("POLICY_VIOLATION", "TR-03",
                                   f"Targets a sensitive location ({hit})", "BLOCK", evidence, weight=0.9))
            verdicts.append(PolicyVerdict("FA-SENSITIVE", "BLOCK",
                                          f"File access policy: paths containing '{hit}' are blocked."))
        if not _in_workspace(tool.target, cfg["workspace_roots"]) and scope == "file" and not hit:
            eff = cfg["outside_workspace_effect"]
            signals.append(_signal("EXCESSIVE_PRIVILEGE", "TR-04",
                                   "Targets a file outside the task workspace", eff, evidence))
            verdicts.append(PolicyVerdict("FA-WORKSPACE", eff,
                                          f"File access policy: files outside the workspace → {eff}."))
        if name in {"file.write", "file.move"}:
            eff = cfg["write_effect"]
            signals.append(_signal("UNSAFE_TOOL_USE", "TR-05", "Modifies files", eff, evidence, weight=0.3))
            verdicts.append(PolicyVerdict("FA-WRITE", eff, f"File write policy → {eff}."))
        if name == "file.delete":
            eff = "BLOCK" if scope in {"recursive", "profile", "drive"} else cfg["delete_effect"]
            signals.append(_signal("UNSAFE_TOOL_USE", "TR-06", "Deletes files", eff, evidence))
            verdicts.append(PolicyVerdict("FA-DELETE", eff, f"File delete policy → {eff}."))

    elif name == "shell.exec":
        cfg = policies["command_execution"]
        cmd = tool.target.lower()
        blocked = next((p for p in cfg["blocked_patterns"] if p in cmd), None)
        if blocked:
            signals.append(_signal("UNSAFE_TOOL_USE", "TR-07",
                                   f"Command matches a blocked pattern ({blocked.strip()})", "BLOCK", evidence, weight=0.95))
            verdicts.append(PolicyVerdict("CMD-BLOCKED", "BLOCK", "Command execution policy: blocked pattern."))
        else:
            eff = cfg["default_effect"]
            signals.append(_signal("UNSAFE_TOOL_USE", "TR-08", "Runs a shell command", eff, evidence, weight=0.45))
            verdicts.append(PolicyVerdict("CMD-DEFAULT", eff, f"Command execution policy: default → {eff}."))

    elif name in {"network.request", "network.upload", "http.post"}:
        cfg = policies["network"]
        host = (urlparse(tool.target).hostname or tool.target).lower()
        if host not in [d.lower() for d in cfg["allowed_domains"]]:
            eff = cfg["unknown_destination_effect"]
            signals.append(_signal("SUSPICIOUS_DESTINATION", "TR-09",
                                   f"Destination {host} is not on the allowlist", eff, evidence))
            verdicts.append(PolicyVerdict("NET-UNKNOWN", eff, f"Network policy: unknown destination → {eff}."))

    elif name == "email.send":
        cfg = policies["email"]
        domain = tool.target.rsplit("@", 1)[-1].lower() if "@" in tool.target else ""
        if domain not in [d.lower() for d in cfg["internal_domains"]]:
            eff = cfg["external_effect"]
            signals.append(_signal("SUSPICIOUS_DESTINATION", "TR-10",
                                   f"Email to external domain {domain or '(unknown)'}", eff, evidence))
            verdicts.append(PolicyVerdict("MAIL-EXTERNAL", eff, f"Email policy: external recipient → {eff}."))

    return signals, verdicts
