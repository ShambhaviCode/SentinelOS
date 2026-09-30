"""SentinelOS local server (Python standard library only).

    python -m sentinel.server            # http://127.0.0.1:8765
    python -m sentinel.server --no-ml    # deterministic engine only

Binds to 127.0.0.1 by default: the security console is not exposed to the network.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from sentinel.audit import AuditLog
from sentinel.gateway import Gateway
from sentinel.inference.runtime_info import machine_info, network_status
from sentinel.security.policy_engine import PolicyEngine
from sentinel.simulator.presets import PRESETS

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "frontend" / "dist"
BENCH = ROOT / "docs" / "benchmark-results.json"
NPU_EVIDENCE = ROOT / "docs" / "npu-verification.json"
MAX_BODY = 256 * 1024

STATE: dict = {}


def build_state(use_ml: bool) -> None:
    classifier = None
    if use_ml:
        from sentinel.inference.classifier import Classifier
        classifier = Classifier()
    STATE["classifier"] = classifier
    STATE["gateway"] = Gateway(PolicyEngine(), classifier, AuditLog())
    STATE["machine"] = machine_info()
    STATE["started"] = time.time()


def status_payload() -> dict:
    c = STATE["classifier"]
    ml = c.status if c else {"available": False, "errors": ["Started with --no-ml"]}
    npu = json.loads(NPU_EVIDENCE.read_text(encoding="utf-8")) if NPU_EVIDENCE.exists() else None
    return {"ml": ml, "machine": STATE["machine"], "network": network_status(),
            "analysis_path": "local", "npu_verification": npu}


class Handler(BaseHTTPRequestHandler):
    server_version = "SentinelOS"

    def log_message(self, fmt, *args):  # quieter console
        sys.stderr.write("  %s %s\n" % (self.command, self.path))

    def _json(self, obj, status=HTTPStatus.OK):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("Request body too large")
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        path = urlparse(self.path).path
        gw: Gateway = STATE["gateway"]
        if path == "/api/status":
            return self._json(status_payload())
        if path == "/api/presets":
            return self._json(PRESETS)
        if path == "/api/events":
            return self._json({"events": gw.audit.list(), "stats": gw.audit.stats()})
        if path == "/api/policies":
            return self._json(gw.policy.summary())
        if path == "/api/benchmark":
            return self._json(json.loads(BENCH.read_text(encoding="utf-8")) if BENCH.exists() else None)
        return self._static(path)

    def do_POST(self):
        path = urlparse(self.path).path
        gw: Gateway = STATE["gateway"]
        try:
            body = self._body()
        except (ValueError, json.JSONDecodeError) as e:
            return self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
        if path == "/api/analyze":
            return self._json(gw.analyze(body))
        if path.startswith("/api/events/") and path.endswith("/resolve"):
            event_id = path.split("/")[3]
            action = body.get("action")
            if action not in ("approve", "deny"):
                return self._json({"error": "action must be approve or deny"}, HTTPStatus.BAD_REQUEST)
            ev = gw.audit.resolve(event_id, action)
            return self._json(ev) if ev else self._json({"error": "event not found"}, HTTPStatus.NOT_FOUND)
        return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def _static(self, path: str):
        if not STATIC.exists():
            return self._json({"error": "UI not built. Run: cd app/frontend && npm install && npm run build"},
                              HTTPStatus.NOT_FOUND)
        target = (STATIC / path.lstrip("/")).resolve()
        if not str(target).startswith(str(STATIC.resolve())) or not target.is_file():
            target = STATIC / "index.html"   # single-page app fallback
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    ap = argparse.ArgumentParser(description="SentinelOS local server")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-ml", action="store_true", help="run the deterministic engine only")
    args = ap.parse_args()
    build_state(use_ml=not args.no_ml)
    ml = STATE["classifier"].status if STATE["classifier"] else None
    print("SentinelOS — Local AI Security for Autonomous Agents")
    if ml and ml["available"]:
        print(f"  ML classifier: {ml['model']} on {ml['provider']} ({ml['accelerator']}), load {ml['load_time_ms']} ms")
    else:
        print("  ML classifier unavailable — deterministic engine only.")
        for e in (ml or {}).get("errors", []):
            print(f"    · {e}")
    print(f"  Open http://{args.host}:{args.port}")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
