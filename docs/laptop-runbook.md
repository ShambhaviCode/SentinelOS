# Laptop runbook: Snapdragon HP PC

Run these in order from the repository root in PowerShell. Every step that produces
evidence writes it to `docs/` automatically. Do not edit generated numbers by hand.

## 0. Inspect the machine (read-only, 1 min)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\inspect_env.ps1
```

This writes `sentinel_env.txt` and `docs/environment.md`. Check them for:
- Processor: the Snapdragon model name
- Python `machine = ARM64` (native). If you see `AMD64`, install the **ARM64** Python
  installer from python.org.
- The NPU listed under compute accelerators

## 1. Runtime environment (5 min)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
.\.venv\Scripts\Activate.ps1
python -c "import onnxruntime as o; print(o.get_available_providers())"
```

You need `QNNExecutionProvider` in that list for the NPU path.

## 2. Tests (1 min)

```powershell
python -m unittest discover -s tests -t . -v
```

## 3. Export and quantize the model (10–20 min, one time)

Use a separate environment with PyTorch. If PyTorch will not install in ARM64 Python,
use x64 Python (it runs under emulation) **only for this step**:

```powershell
py -3.12-64 -m venv .venv-export
.\.venv-export\Scripts\python.exe -m pip install -r requirements-export.txt
.\.venv-export\Scripts\python.exe tools\export_model.py
.\.venv-export\Scripts\python.exe tools\quantize_qnn.py
```

Check the printed tokenizer parity (should be 4/4), logit difference (should be tiny) and
QDQ label flips (should be 0). An alternative is to run this step on any other computer and
copy `models/prompt-injection/` across.

## 4. Verify NPU execution (2 min)

```powershell
.\.venv\Scripts\Activate.ps1
python tools\verify_npu.py
```

Read the verdict in `docs/npu-verification.md`:
- **NPU EXECUTION VERIFIED**: you may say the classifier runs on the Snapdragon NPU.
- **NOT VERIFIED**: the error and diagnostic node counts show why. Try
  `tools\export_model.py --int32-inputs`, re-quantize, and re-verify. If it still fails,
  present the CPU path honestly (still local, still offline).

## 5. Benchmark (3 min)

```powershell
python -m benchmark                    # auto: NPU if verified-capable
python -m benchmark --provider cpu     # CPU comparison, saved separately in data/benchmarks/
python -m benchmark                    # re-run auto last so the UI shows the main result
```

The last run writes `docs/benchmark-results.md/.json`, which the Benchmarks page reads.
Both raw runs are kept in `data/benchmarks/` for the NPU-vs-CPU comparison.

## 6. Run the app

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run.ps1
# open http://127.0.0.1:8765
```

Run all five presets in the Agent console. Record each preset's decision and model
probability in the table at the end of `docs/risk-model.md`.

## 7. Offline check (5 min)

Turn off Wi-Fi (and unplug Ethernet), restart the server, open the UI, run all five
presets, and fill in `docs/offline-verification.md`.

## 8. Screenshots (10 min)

With the model loaded and after running the presets, capture (Win+Shift+S) into
`submission/screenshots/`:

1. `01-overview.png`: Overview after all presets
2. `02-agent-console.png`: Agent console with the Prompt injection preset loaded
3. `03-threat-detection.png`: The threat detail after running Prompt injection
4. `04-trust-graph.png`: The trust graph for Excessive file access
5. `05-benchmarks.png`: Benchmarks page
6. `06-local-ai-status.png`: Local AI status panel (Benchmarks page)

## 9. Send back for the final package

Paste these into the chat: `docs/environment.md`, `docs/npu-verification.md`,
`docs/benchmark-results.md`, the preset results table, and `docs/offline-verification.md`.
The pitch deck, PDFs and final submission text will be completed with those real values.
