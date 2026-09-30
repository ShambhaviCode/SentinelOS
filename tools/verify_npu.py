"""Isolated NPU verification for the SentinelOS classifier.

Run on the Snapdragon laptop with native ARM64 Python and onnxruntime-qnn:

    python tools/verify_npu.py

Evidence written to docs/npu-verification.md and docs/npu-verification.json.

Verdict rules (all must hold for "NPU execution verified"):
  1. QNNExecutionProvider is available in this ONNX Runtime build.
  2. A session on the QNN HTP backend is created with
     session.disable_cpu_ep_fallback = 1 (ORT refuses to create it if any node
     would need the CPU).
  3. Inference runs and returns finite outputs.
  4. The ORT profile shows zero graph nodes executed by CPUExecutionProvider.
"""
from __future__ import annotations

import getpass
import glob
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DOCS = ROOT / "docs"
PROFILE_DIR = ROOT / "data" / "profiles"


def sanitize(s: str) -> str:
    try:
        user = getpass.getuser()
        return s.replace(user, "<user>") if user else s
    except Exception:
        return s


def provider_counts(profile_path: str) -> dict[str, int]:
    with open(profile_path, encoding="utf-8") as f:
        events = json.load(f)
    counts: dict[str, int] = {}
    for ev in events:
        if ev.get("cat") == "Node" and ev.get("name", "").endswith("_kernel_time"):
            p = ev.get("args", {}).get("provider", "unknown")
            counts[p] = counts.get(p, 0) + 1
    return counts


def main() -> None:
    import numpy as np
    import onnxruntime as ort

    from sentinel.inference.runtime_info import machine_info
    from sentinel.inference.tokenizer import WordPieceTokenizer
    from sentinel.simulator.presets import PRESETS_BY_ID

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    mdir = ROOT / "models" / "prompt-injection"
    qdq = mdir / "model.qdq.onnx"
    meta = json.loads((mdir / "labels.json").read_text(encoding="utf-8")) if (mdir / "labels.json").exists() else {}
    report: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "machine": machine_info(),
        "model": meta.get("source_model"),
        "model_file": qdq.name,
        "session_options": {"session.disable_cpu_ep_fallback": "1", "enable_profiling": True},
        "provider_options": {"backend_path": "QnnHtp.dll"},
        "steps": [],
        "verdict": "NOT VERIFIED",
    }

    def step(name, ok, detail=""):
        report["steps"].append({"step": name, "ok": ok, "detail": sanitize(str(detail))})
        print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")
        return ok

    ok = step("QNNExecutionProvider available", "QNNExecutionProvider" in ort.get_available_providers(),
              ort.get_available_providers())
    ok = ok and step("Quantized QDQ model present", qdq.exists(), qdq.relative_to(ROOT))

    if ok:
        tok = WordPieceTokenizer(mdir / "vocab.txt", max_length=int(meta.get("max_length", 128)))
        text = PRESETS_BY_ID["injection"]["request"]["context"]
        ids, mask = tok.encode(text)

        so = ort.SessionOptions()
        so.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
        so.enable_profiling = True
        so.profile_file_prefix = str(PROFILE_DIR / "npu_verify")
        try:
            t0 = time.perf_counter()
            sess = ort.InferenceSession(str(qdq), sess_options=so,
                                        providers=[("QNNExecutionProvider", {"backend_path": "QnnHtp.dll"})])
            load_ms = (time.perf_counter() - t0) * 1000
            ok = step("Session created on QNN HTP with CPU fallback disabled", True,
                      f"providers={sess.get_providers()} load={load_ms:.1f} ms")
            report["session_load_ms"] = round(load_ms, 1)
        except Exception as e:
            ok = step("Session created on QNN HTP with CPU fallback disabled", False, e)

        if ok:
            inputs = sess.get_inputs()
            feed = {}
            for i in inputs:
                dt = np.int32 if "int32" in i.type else np.int64
                feed[i.name] = np.array([mask if "mask" in i.name else ids], dtype=dt)
            report["inputs"] = [{"name": i.name, "type": i.type, "shape": i.shape} for i in inputs]
            for _ in range(10):
                sess.run(None, feed)
            lat = []
            for _ in range(100):
                t0 = time.perf_counter()
                out = sess.run(None, feed)[0]
                lat.append((time.perf_counter() - t0) * 1000)
            logits = out.reshape(-1).astype(float)
            ok = step("Inference returned finite outputs", bool(np.all(np.isfinite(logits))), logits.tolist())
            e = np.exp(logits - logits.max())
            report["output"] = {"logits": logits.tolist(),
                                "injection_probability": float(e[int(meta.get('injection_index', 1))] / e.sum())}
            lat.sort()
            report["latency_ms"] = {"iterations": 100, "warmup": 10, "median": round(statistics.median(lat), 3),
                                    "p95": round(lat[94], 3), "min": round(lat[0], 3), "max": round(lat[-1], 3)}

            prof = sess.end_profiling()
            counts = provider_counts(prof)
            report["profile_node_providers"] = counts
            report["profile_file"] = sanitize(os.path.relpath(prof, ROOT))
            cpu_nodes = counts.get("CPUExecutionProvider", 0)
            ok = step("Profile shows no CPU-executed nodes", cpu_nodes == 0 and bool(counts), counts) and ok

            # Reference: same QDQ model on CPU, to confirm the NPU output is sane.
            cpu = ort.InferenceSession(str(qdq), providers=["CPUExecutionProvider"])
            ref = cpu.run(None, feed)[0].reshape(-1).astype(float)
            report["cpu_reference_logits"] = ref.tolist()
            report["max_abs_logit_diff_vs_cpu"] = float(np.abs(ref - logits).max())

    if ok:
        report["verdict"] = "NPU EXECUTION VERIFIED"
    else:
        # Diagnostic: which nodes would fall back to CPU if fallback were allowed?
        try:
            so = ort.SessionOptions()
            so.enable_profiling = True
            so.profile_file_prefix = str(PROFILE_DIR / "npu_diag")
            s2 = ort.InferenceSession(str(qdq), sess_options=so,
                                      providers=[("QNNExecutionProvider", {"backend_path": "QnnHtp.dll"}),
                                                 "CPUExecutionProvider"])
            i = s2.get_inputs()
            s2.run(None, {x.name: np.zeros(x.shape, dtype=np.int32 if "int32" in x.type else np.int64) for x in i})
            report["diagnostic_with_fallback"] = provider_counts(s2.end_profiling())
        except Exception as e:
            report["diagnostic_with_fallback"] = f"failed: {sanitize(str(e))}"

    DOCS.mkdir(exist_ok=True)
    (DOCS / "npu-verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report)
    print(f"\nVerdict: {report['verdict']}  → docs/npu-verification.md")


def write_markdown(r: dict) -> None:
    m = r["machine"]
    lines = [
        "# NPU verification", "",
        f"Generated by `tools/verify_npu.py` on {r['timestamp']}. This file is machine-written evidence; "
        "do not edit the results by hand.", "",
        f"**Verdict: {r['verdict']}**", "",
        "## Machine", "",
        f"- Processor: {m['processor']}", f"- OS: {m['os']}",
        f"- Python: {m['python']} ({m['python_arch']})", f"- ONNX Runtime: {m['onnxruntime']}",
        f"- Available providers: {', '.join(m['available_providers'])}", "",
        "## Configuration", "",
        f"- Model: {r['model']} (`{r['model_file']}`)",
        "- Session option: `session.disable_cpu_ep_fallback = 1`",
        "- Provider: `QNNExecutionProvider` with `backend_path = QnnHtp.dll` (Hexagon NPU backend)", "",
        "## Steps", "", "| Step | Result | Detail |", "|---|---|---|",
    ]
    lines += [f"| {s['step']} | {'PASS' if s['ok'] else 'FAIL'} | {s['detail'][:160].replace('|', '/')} |" for s in r["steps"]]
    if "latency_ms" in r:
        l = r["latency_ms"]
        lines += ["", "## Inference latency (NPU session)", "",
                  f"{l['iterations']} iterations after {l['warmup']} warmup runs: median {l['median']} ms, "
                  f"p95 {l['p95']} ms, min {l['min']} ms, max {l['max']} ms.",
                  "", f"Session creation: {r.get('session_load_ms')} ms."]
    if "profile_node_providers" in r:
        lines += ["", "## Profile: nodes by execution provider", "", f"`{r['profile_node_providers']}`",
                  "", f"Max absolute logit difference vs the same model on CPU: {r.get('max_abs_logit_diff_vs_cpu')}"]
    if "diagnostic_with_fallback" in r:
        lines += ["", "## Diagnostic (CPU fallback allowed)", "", f"`{r['diagnostic_with_fallback']}`"]
    (DOCS / "npu-verification.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
