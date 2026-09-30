"""Layer 2: local ML prompt-injection classifier on ONNX Runtime.

Provider selection (env SENTINEL_EP = auto | qnn | cpu, default auto):

* qnn/auto: if QNNExecutionProvider is available and a QDQ-quantized model
  exists, create the session on the QNN HTP (NPU) backend with
  session.disable_cpu_ep_fallback = 1. If that session is created, every node
  in the graph was accepted by QNN — this is the evidence behind reporting
  "NPU". If creation fails, the error is recorded and we fall back to CPU.
* cpu: CPUExecutionProvider with the fp32 model (or the QDQ model if that is
  the only one present).

If onnxruntime or the model files are missing, the classifier reports itself as
unavailable and SentinelOS continues with the deterministic engine only.
"""
from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Any, Optional

from sentinel.inference.tokenizer import WordPieceTokenizer
from sentinel.models import MLResult

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = Path(os.environ.get("SENTINEL_MODEL_DIR", ROOT / "models" / "prompt-injection"))


class Classifier:
    def __init__(self, model_dir: Path = MODEL_DIR, provider_pref: Optional[str] = None):
        self.model_dir = Path(model_dir)
        self.provider_pref = (provider_pref or os.environ.get("SENTINEL_EP", "auto")).lower()
        self.session = None
        self.tokenizer: Optional[WordPieceTokenizer] = None
        self.meta: dict[str, Any] = {}
        self.status: dict[str, Any] = {
            "available": False, "model": None, "model_file": None, "runtime": None,
            "runtime_version": None, "provider": None, "accelerator": None,
            "cpu_fallback_disabled": False, "load_time_ms": None, "errors": [],
        }
        self._load()

    # ---------------------------------------------------------------- loading
    def _load(self) -> None:
        try:
            import numpy  # noqa: F401
            import onnxruntime as ort
        except Exception as e:  # pragma: no cover - depends on install
            self.status["errors"].append(f"onnxruntime not importable: {e}")
            return
        self.status["runtime"] = "ONNX Runtime"
        self.status["runtime_version"] = ort.__version__

        labels_path = self.model_dir / "labels.json"
        vocab_path = self.model_dir / "vocab.txt"
        fp32 = self.model_dir / "model.onnx"
        qdq = self.model_dir / "model.qdq.onnx"
        if not labels_path.exists() or not vocab_path.exists() or not (fp32.exists() or qdq.exists()):
            self.status["errors"].append(
                f"Model files not found in {self.model_dir.relative_to(ROOT) if self.model_dir.is_relative_to(ROOT) else self.model_dir}. "
                "Run tools/export_model.py (see docs/model.md).")
            return

        self.meta = json.loads(labels_path.read_text(encoding="utf-8"))
        self.tokenizer = WordPieceTokenizer(vocab_path, max_length=int(self.meta.get("max_length", 128)))
        self.status["model"] = self.meta.get("source_model")

        available = ort.get_available_providers()
        want_qnn = self.provider_pref in ("auto", "qnn") and "QNNExecutionProvider" in available and qdq.exists()
        if self.provider_pref == "qnn" and not want_qnn:
            self.status["errors"].append(
                "QNN requested but unavailable "
                f"(QNNExecutionProvider available: {'QNNExecutionProvider' in available}, QDQ model present: {qdq.exists()}).")

        if want_qnn:
            try:
                so = ort.SessionOptions()
                so.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
                t0 = time.perf_counter()
                self.session = ort.InferenceSession(
                    str(qdq), sess_options=so,
                    providers=[("QNNExecutionProvider", {"backend_path": "QnnHtp.dll"})])
                self.status["load_time_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                self.status.update(provider="QNNExecutionProvider", accelerator="NPU (Qualcomm Hexagon, HTP backend)",
                                   cpu_fallback_disabled=True, model_file=qdq.name)
            except Exception as e:
                self.status["errors"].append(f"QNN HTP session failed with CPU fallback disabled: {e}")
                self.session = None

        if self.session is None:
            path = fp32 if fp32.exists() else qdq
            t0 = time.perf_counter()
            self.session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
            self.status["load_time_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            self.status.update(provider="CPUExecutionProvider", accelerator="CPU", model_file=path.name)

        self.status["available"] = True
        self._inputs = {i.name: i.type for i in self.session.get_inputs()}

    # -------------------------------------------------------------- inference
    def _feed(self, text: str) -> dict[str, Any]:
        import numpy as np
        ids, mask = self.tokenizer.encode(text)
        feed = {}
        for name, typ in self._inputs.items():
            dtype = np.int32 if "int32" in typ else np.int64
            if "mask" in name:
                feed[name] = np.array([mask], dtype=dtype)
            elif "type" in name:
                feed[name] = np.zeros((1, len(ids)), dtype=dtype)
            else:
                feed[name] = np.array([ids], dtype=dtype)
        return feed

    def raw_logits(self, text: str) -> list[float]:
        out = self.session.run(None, self._feed(text))[0]
        return [float(x) for x in out.reshape(-1)]

    def classify(self, text: str) -> MLResult:
        if not self.status["available"]:
            return MLResult(available=False, error="; ".join(self.status["errors"]) or "ML classifier unavailable")
        t0 = time.perf_counter()
        logits = self.raw_logits(text)
        m = max(logits)
        exps = [math.exp(x - m) for x in logits]
        probs = [e / sum(exps) for e in exps]
        idx = int(self.meta["injection_index"])
        p = probs[idx]
        id2label = self.meta.get("id2label", {})
        top = max(range(len(probs)), key=probs.__getitem__)
        return MLResult(available=True, label=id2label.get(str(top), str(top)), injection_probability=p,
                        provider=self.status["provider"], latency_ms=round((time.perf_counter() - t0) * 1000, 2))

    def classify_fields(self, prompt: str, context: str) -> MLResult:
        """Classify prompt and context separately; report the riskier one."""
        results = [(f, self.classify(t)) for f, t in (("prompt", prompt), ("context", context)) if t.strip()]
        if not results:
            return MLResult(available=self.status["available"], injection_probability=0.0 if self.status["available"] else None,
                            provider=self.status["provider"], latency_ms=0.0)
        if not results[0][1].available:
            return results[0][1]
        field, best = max(results, key=lambda r: r[1].injection_probability)
        best.latency_ms = round(sum(r.latency_ms for _, r in results), 2)
        best.label = f"{best.label} ({field})"
        return best
