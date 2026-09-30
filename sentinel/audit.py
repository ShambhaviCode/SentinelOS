"""Audit timeline: every analyzed event, kept in memory and appended to JSONL."""
from __future__ import annotations

import json
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG = ROOT / "data" / "audit.jsonl"


class AuditLog:
    def __init__(self, path: Optional[Path] = DEFAULT_LOG, capacity: int = 500):
        self.path = path
        self.events: deque[dict[str, Any]] = deque(maxlen=capacity)
        self._lock = threading.Lock()
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def _append_file(self, record: dict[str, Any]) -> None:
        if self.path:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def record(self, event: dict[str, Any]) -> None:
        with self._lock:
            self.events.appendleft(event)
            self._append_file({"type": "analysis", **event})

    def resolve(self, event_id: str, action: str, actor: str = "local-operator") -> Optional[dict[str, Any]]:
        with self._lock:
            for ev in self.events:
                if ev["id"] == event_id:
                    if ev["decision"]["decision"] != "REQUIRE_APPROVAL" or ev.get("resolution"):
                        return ev
                    ev["resolution"] = {
                        "action": "APPROVED" if action == "approve" else "DENIED",
                        "actor": actor,
                        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    }
                    self._append_file({"type": "resolution", "id": event_id, **ev["resolution"]})
                    return ev
        return None

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return list(self.events)[:limit]

    def stats(self) -> dict[str, Any]:
        with self._lock:
            evs = list(self.events)
        count = lambda pred: sum(1 for e in evs if pred(e))  # noqa: E731
        return {
            "events": len(evs),
            "allowed": count(lambda e: e["decision"]["decision"] == "ALLOW"),
            "blocked": count(lambda e: e["decision"]["decision"] == "BLOCK"),
            "approval_required": count(lambda e: e["decision"]["decision"] == "REQUIRE_APPROVAL"),
            "pending_approval": count(lambda e: e["decision"]["decision"] == "REQUIRE_APPROVAL" and not e.get("resolution")),
            "tool_requests": count(lambda e: e["request"].get("tool_request")),
            "prompt_injection": count(lambda e: e["risk"]["scores"]["prompt"] >= 0.3),
            "data_events": count(lambda e: e["risk"]["scores"]["data"] >= 0.3),
        }
