# Deployment

## Target

A Snapdragon-powered Windows 11 PC (ARM64). The deterministic engine and UI also run on
any Windows, macOS or Linux machine with Python 3.10 or newer.

## Runtime layout

| Piece | Needs | Notes |
|---|---|---|
| Security engine + server | Python 3.10+ standard library | Binds to 127.0.0.1:8765 |
| UI | Prebuilt in `app/frontend/dist` | Node is only needed to rebuild the UI |
| ML classifier, NPU | Native ARM64 Python, `onnxruntime-qnn`, `numpy`, QDQ model | x64 Python under emulation cannot load the QNN provider |
| ML classifier, CPU | `onnxruntime`, `numpy`, ONNX model | Any platform |
| Model export (one time) | `torch`, `transformers`, internet | Any machine; x64 Python under emulation on the laptop works |

## Quick start (deterministic engine only; any OS)

```bash
python -m sentinel.server --no-ml
# open http://127.0.0.1:8765
```

## Full setup on the Snapdragon laptop

Follow [laptop-runbook.md](laptop-runbook.md) step by step.

## Execution provider selection

Set `SENTINEL_EP` before starting the server or benchmark:

| Value | Behaviour |
|---|---|
| `auto` (default) | QNN HTP if the provider and `model.qdq.onnx` exist and a session can be created with CPU fallback disabled; otherwise CPU |
| `qnn` | Same as auto, but records an error if QNN is unavailable |
| `cpu` | CPU provider with `model.onnx` |

## Offline operation

Once the model files are in `models/prompt-injection/`, nothing in the analysis path needs
the network, and the UI's fonts are bundled. Offline operation is **designed** in; it
becomes a **claim** only after `offline-verification.md` has been filled in on the laptop.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `QNNExecutionProvider` missing from providers | x64 Python, or `onnxruntime` installed instead of `onnxruntime-qnn` | Use ARM64 Python; `pip uninstall onnxruntime` then `pip install onnxruntime-qnn` |
| QNN session fails with fallback disabled | An op or data type HTP does not support | Read the error in `npu-verification.md` and the diagnostic node counts; try `tools/export_model.py --int32-inputs`, then re-quantize |
| QNN session fails: backend could not load | `QnnHtp.dll` not found | Reinstall `onnxruntime-qnn`; check that the NPU driver is present in `docs/environment.md` |
| UI says "UI not built" | `app/frontend/dist` missing | `cd app/frontend && npm install && npm run build` |
| "ML classifier unavailable" | Model files missing | Run the export and quantize steps |
