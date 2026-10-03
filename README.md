<div align="center">

# 🛡️ SentinelOS

### On-Device Security for AI Agents

**Checks what an AI agent reads and what it wants to do, before it acts, on the device.**

![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)
![ONNX Runtime](https://img.shields.io/badge/ONNX%20Runtime-QNN%20%7C%20CPU-005CED)
![Target](https://img.shields.io/badge/target-Snapdragon%20NPU-3253DC?logo=qualcomm&logoColor=white)
![Tests](https://img.shields.io/badge/tests-37%20passing-1E9E6A)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

<img src="docs/screenshots/threat-detection.png" alt="SentinelOS blocking a prompt injection hidden in a vendor document" width="860">

<sub>A prompt injection hidden in a vendor document, caught line by line and blocked.</sub>

</div>

---

## ⚡ The short version

AI agents read documents, open files and send messages **with your permissions**.
One poisoned document can tell an agent to *"ignore your previous instructions"*, and it will try.

**SentinelOS sits between the agent and everything it can touch.** Every prompt, every piece of
content the agent reads and every action it proposes passes through one local gateway and comes
out as **Allow**, **Needs approval** or **Block**, with the evidence behind the decision.

No cloud. No API keys. No data leaves the device.

```bash
git clone https://github.com/ShambhaviCode/SentinelOS.git && cd SentinelOS
python -m sentinel.server --no-ml        # zero dependencies: Python standard library only
# open http://127.0.0.1:8765 → Agent console → "Prompt injection" → Run security check
```

---

## 🎯 The problem

| Before | Now |
|---|---|
| User → app → model → answer | User → **agent** → reads data → **calls tools** → **takes actions** |
| Model output is shown to a person | Model output **becomes an action** |
| Untrusted text is displayed | Untrusted text **can steer behaviour** |

Three failures matter most once text turns into action:

- **Prompt injection.** Content the agent reads carries instructions, and the agent follows them.
- **Data exposure.** Credentials in the agent's context leak through an email, an upload or a log.
- **Excessive privilege.** The agent asks for your whole Documents folder to answer a one-line question.

Traditional application security checks *who* is calling. It doesn't check whether a document is
instructing the agent, or whether a file request fits the task. SentinelOS checks both.

---

## 🧭 How it works

```mermaid
flowchart LR
    A[AI agent] --> G[Agent gateway]
    subgraph B["SentinelOS boundary: on the device"]
        G --> P[Injection rules<br/>8 weighted categories]
        G --> M[Local ML classifier<br/>DistilBERT · ONNX Runtime]
        G --> D[Data scan<br/>secrets · personal data]
        G --> T[Tool scan<br/>scope · paths · destinations]
        P & M & D & T --> R[Risk engine<br/>explainable scoring]
        R --> PE[Policy engine<br/>config/policies.json]
    end
    PE --> AL([✅ Allow])
    PE --> AP([⏸️ Needs approval])
    PE --> BL([⛔ Block])
    PE --> AU[(Audit trail)]
```

<div align="center">
<img src="docs/screenshots/trust-graph.png" alt="Agent trust graph showing an excessive file-access request blocked" width="860">

<sub>The agent trust graph, drawn from real event data: a recursive request for the whole Documents folder is stopped at the tool scan.</sub>
</div>

---

## ✨ Design choices

| | |
|---|---|
| 🧠 **Hybrid detection** | Deterministic rules for repeatable, explainable results, plus a local transformer classifier as a second opinion. |
| 🔒 **Model can't block alone** | The ML signal is capped by design: it can hold a request for review, but blocking needs rule evidence too, so a false positive never silently stops real work. |
| 🧰 **Guards actions, not just text** | Least-privilege checks on file scope, sensitive paths, shell commands, network and email destinations. |
| 🔎 **Every decision is explained** | Risk score, severity, model confidence, rule-by-rule evidence, the deciding policy, and a recommended next step. |
| 🙋 **Human in the loop** | Uncertain requests wait for approve or deny, recorded in the audit trail. |
| 🤐 **Secrets stay secret** | Credentials are redacted before they reach the UI or the log. |
| 📏 **Honest telemetry** | Model, provider, accelerator, latency and network state are read from the machine. Anything unknown says *Not detected*. |

---

## ⚙️ Built for Snapdragon

The ML classifier is engineered for the **Qualcomm Hexagon NPU** through ONNX Runtime's
**QNN Execution Provider (HTP backend)**:

1. **Export** to a static-shape ONNX graph (`[1, 128]`), because the NPU needs fixed shapes.
2. **Quantize** to QDQ (16-bit activations, 8-bit weights) with ONNX Runtime's QNN tools, because HTP runs quantized graphs.
3. **Run with CPU fallback disabled** (`session.disable_cpu_ep_fallback = 1`). ONNX Runtime refuses to start the session unless *every* operation runs on the NPU, so nothing can quietly fall back to the CPU.
4. **Prove it.** `tools/verify_npu.py` counts nodes per execution provider with the ORT profiler, checks outputs against a CPU reference, and writes a machine-generated verdict.

If any step isn't supported, SentinelOS runs the same model on the CPU, still fully local, and the UI says so.

| Evidence | Generated by | File |
|---|---|---|
| Machine inspection | `scripts/inspect_env.ps1` | [docs/environment.md](docs/environment.md) |
| NPU verification | `tools/verify_npu.py` | [docs/npu-verification.md](docs/npu-verification.md) |
| Benchmarks | `python -m benchmark` | [docs/benchmark-results.md](docs/benchmark-results.md) |
| Offline check | manual checklist | [docs/offline-verification.md](docs/offline-verification.md) |

> These files are written by scripts on the target laptop and are never edited by hand. Where a file says *NOT YET RUN*, no claim is made.

---

## 🎬 Demo scenarios

All data is synthetic. Every scenario is deterministic, and the tests assert each result.

| Scenario | What the agent attempted | Decision |
|---|---|---|
| Safe request | Read one project file to summarize it | ✅ **Allow** |
| Command review | Run `git status` | ⏸️ **Needs approval** |
| Prompt injection | Follow instructions hidden in a vendor document | ⛔ **Block** |
| Data exposure | Email a service key and password to an outside address | ⛔ **Block** |
| Excessive access | List all of Documents, recursively, for "additional context" | ⛔ **Block** |

<div align="center">
<img src="docs/screenshots/agent-console.png" alt="SentinelOS agent console" width="860">
</div>

---

## 🚀 Quick start

**Rules engine only (any OS, zero dependencies):**
```bash
python -m sentinel.server --no-ml
```

**With the local ML classifier on CPU:**
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-export.txt   # macOS/Linux: .venv/bin/python
.venv/Scripts/python tools/export_model.py
.venv/Scripts/python -m sentinel.server
```

**On a Snapdragon Windows PC (NPU path):** follow [docs/laptop-runbook.md](docs/laptop-runbook.md). It needs native ARM64 Python and `onnxruntime-qnn`, and covers setup, export, quantization, NPU verification and benchmarking step by step.

Then open **http://127.0.0.1:8765**.

---

## 🧪 Tests

```bash
python -m unittest discover -s tests -t . -v
```

The 37 tests cover injection (including paraphrases), sensitive data and redaction, file scope,
blocked and allowed tools, network and command policies, the risk formula, the ML cap, policy
precedence, final decisions, preset determinism, and the ML inference path.

---

## 🗂️ Project structure

```
sentinel/
  gateway.py            one entry point, stage timings, audit
  security/             prompt · data · tool scanners, risk, policy, decision
  inference/            ONNX Runtime classifier, pure-Python WordPiece tokenizer, runtime info
  simulator/            synthetic demo scenarios
  server.py             standard-library HTTP server (localhost only)
app/frontend/           React + TypeScript UI (prebuilt in dist/)
config/policies.json    editable policies
tools/                  export · QNN quantization · NPU verification
benchmark/              python -m benchmark
docs/                   architecture, security, risk model, model, deployment, evidence
tests/                  37 tests
```

---

## 📚 Documentation

[Architecture](docs/architecture.md) ·
[Security model](docs/security.md) ·
[Risk model](docs/risk-model.md) ·
[Model](docs/model.md) ·
[Deployment](docs/deployment.md) ·
[Laptop runbook](docs/laptop-runbook.md)

---

## ⚖️ Limitations

- Rules detect **known patterns**. Novel, encoded, multilingual or multi-turn attacks can evade them, and the classifier's real-world accuracy hasn't been measured yet.
- Sensitive-data detection depends on recognizable formats.
- The agent is a deterministic **test environment**, not a production integration.
- The classifier scores the first 128 tokens of each field; the rules scan the full text.
- The local API has no authentication (single user, localhost only).

SentinelOS reduces risk; it does not make an agent secure.

---

## 🛣️ Roadmap

- Agent-framework and MCP tool-server integrations through the same gateway
- Team-wide policy management with signed policy bundles
- Session-level behavioural monitoring across multi-step agent runs
- Multilingual and encoded-payload detection, with larger evaluation sets
- More tool connectors: browsers, cloud storage, calendars

---

## 🏆 Snapdragon AI Lab Challenge alignment

| Criterion | Evidence |
|---|---|
| **Technical implementation** | Hybrid detector, explainable risk model, policy engine and audit trail. QNN HTP path with fallback disabled and profiler verification. 37 tests. |
| **Use case & innovation** | Security at the moment an agent turns text into action: injection, data exposure and least-privilege tool use, with a person in the loop. |
| **Deployment & accessibility** | Fully local, zero-dependency core, prebuilt UI with bundled fonts, Windows-on-ARM scripts, CPU fallback everywhere. No accounts or keys. |
| **Presentation & documentation** | Architecture, security, risk and model docs, a step-by-step runbook, machine-generated evidence files, and repeatable demos. |

---

<div align="center">

**Built by Shambhavi **

MIT License

</div>
