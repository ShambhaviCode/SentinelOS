# SentinelOS

## Local AI Security for Autonomous Agents

SentinelOS is a security boundary that runs on the device. It checks what an AI agent reads
and what it wants to do, and returns **allow**, **require approval** or **block**, with the
evidence behind the decision.

> **Verification status.** Anything that depends on the Snapdragon hardware (processor,
> execution provider, NPU execution, latency) is filled in by scripts that write evidence to
> `docs/`. Where those files say *NOT YET RUN*, no claim is made.
>
> | Evidence | File | Status |
> |---|---|---|
> | Machine inspection | [docs/environment.md](docs/environment.md) | see file |
> | NPU execution | [docs/npu-verification.md](docs/npu-verification.md) | see file |
> | Benchmarks | [docs/benchmark-results.md](docs/benchmark-results.md) | see file |
> | Offline operation | [docs/offline-verification.md](docs/offline-verification.md) | see file |

## The Problem

AI agents no longer only answer questions. They read documents, open files, call tools and
send messages using the permissions of the person who launched them. Anything the agent reads
can contain instructions, and anything in its context can leak through a tool call.

## Why Agentic AI Changes Security

| Before | Now |
|---|---|
| User → application → model → answer | User → agent → reads data → calls tools → takes actions |
| The model's output is shown to a person | The model's output becomes an action |
| Untrusted text is displayed | Untrusted text can steer behaviour |

The dangerous moment is **between the agent deciding and the agent acting.** Traditional
application security checks users and endpoints; it does not look at a document telling an
agent to "ignore your previous instructions" or at an agent asking for the whole Documents
folder to answer a one-line question.

## Our Solution

Every agent request (prompt, context and proposed tool action) goes through one gateway:

```
Agent ──► SentinelOS gateway
            ├─ Prompt scanner      (injection patterns)
            ├─ Data scanner        (secrets, personal data)
            ├─ Tool scanner        (scope, paths, commands, destinations)
            └─ Local ML classifier (injection probability, on device)
                    │
               Risk engine ──► Policy engine ──► Decision: Allow / Require approval / Block
                                                      │
                                                 Audit timeline
```

## Key Capabilities

- **Prompt-injection detection.** Eight weighted rule categories that tolerate paraphrasing,
  plus a local DistilBERT classifier as a second signal.
- **Sensitive-data detection.** API tokens, private keys, passwords, Luhn-checked card
  numbers, ID formats, email and phone. Secrets are redacted before display or logging.
- **Tool-risk analysis.** Least-privilege checks on file scope, sensitive paths, commands,
  network destinations and email recipients, including broad requests with vague reasons.
- **Explainable decisions.** A risk score, severity, model probability, rule-by-rule evidence,
  the policy that decided, why it matters, and a recommended action.
- **Human in the loop.** Medium-risk requests wait for approve or deny, recorded in the audit
  log.
- **Agent trust graph.** A diagram of each request's path through the boundary, drawn from
  that request's real scores.
- **Honest runtime panel.** Model, runtime, execution provider, accelerator, load time and
  network state are all read from the machine.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the component diagram and API. Scoring
is documented in [docs/risk-model.md](docs/risk-model.md), and the threat model and
limitations in [docs/security.md](docs/security.md).

## Local AI

| | |
|---|---|
| Model | `acuvity/distilbert-base-uncased-prompt-injection-v0.1` (Apache-2.0, see [docs/model.md](docs/model.md)) |
| Format | ONNX, static `[1,128]` input; QDQ-quantized (uint16 activations, uint8 weights) for the NPU |
| Runtime | ONNX Runtime |
| Tokenizer | Pure-Python WordPiece, parity-checked against Hugging Face |
| Role | Second signal for prompt injection. It can hold a request for review; blocking needs rule evidence too |

## Snapdragon Optimization

The execution path targets the Snapdragon NPU through ONNX Runtime's **QNN Execution
Provider** on the **HTP backend**:

1. The model is exported with static shapes and QDQ-quantized with ONNX Runtime's QNN
   quantization helpers, because the HTP backend runs quantized graphs.
2. The session is created with `session.disable_cpu_ep_fallback = 1`. ONNX Runtime then
   refuses to create the session unless **every** node runs on QNN, so a successful session
   is itself evidence that nothing silently fell back to the CPU.
3. `tools/verify_npu.py` adds ORT profiling (counting nodes per execution provider), compares
   outputs with a CPU reference, and writes the verdict to `docs/npu-verification.md`.
4. If any step fails, SentinelOS runs the same model on the CPU, still locally, and the UI
   says so.

Measured latency on the target laptop: **see [docs/benchmark-results.md](docs/benchmark-results.md)**.

## Security Model

Untrusted context is weighted highest. Tool requests in the same turn as a likely injection
are blocked. Secrets leaving the device are blocked. Policies in `config/policies.json` can
only make a decision stricter. Full details and limitations are in
[docs/security.md](docs/security.md).

## Demo

Five synthetic, deterministic scenarios in the **Agent console**:

| Scenario | Result |
|---|---|
| Safe request: read one workspace file | Low, **Allow** |
| Command needs review: `git status` | Medium, **Require approval** |
| Prompt injection hidden in a vendor document | Critical, **Block** |
| Credentials about to be emailed outside the organization | Critical, **Block** |
| Recursive access to the whole Documents folder, "Need additional context." | Critical, **Block** |

These are results from the deterministic engine, asserted by the tests. All demo data is
synthetic ([demo/README.md](demo/README.md)).

## Benchmark

```powershell
python -m benchmark                  # auto provider
python -m benchmark --provider cpu   # CPU comparison
```

This records the model, provider, accelerator, warmup, iterations, median, p95, mean,
throughput and memory, and writes `docs/benchmark-results.md` and `.json` (read by the
Benchmarks page) plus raw JSON in `data/benchmarks/`.

## Installation

Prerequisites: Python 3.10+ (**native ARM64** Python for the NPU path). Node 18+ only if you
rebuild the UI.

```powershell
git clone <repo-url> sentinelos
cd sentinelos
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1       # add -Cpu for CPU-only
```

Model export (one time): see [docs/laptop-runbook.md](docs/laptop-runbook.md), step 3.

## Running

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run.ps1
# or, on any OS without the model:
python -m sentinel.server --no-ml
```

Open http://127.0.0.1:8765, go to **Agent console**, choose **Prompt injection**, and select
**Run security check**.

To rebuild the UI: `cd app/frontend && npm install && npm run build`.

## Tests

```powershell
python -m unittest discover -s tests -t . -v
```

The 37 tests cover the safe prompt, injection prompts (including paraphrases), sensitive
data and redaction, safe data, excessive file scope, allowed and blocked tools, network and
command policies, risk calculation, the ML cap, policy evaluation, final decisions, preset
determinism, and the ML code path (with a synthetic fixture model; skipped without
onnxruntime).

## Limitations

- Rule-based detection finds known patterns. Novel, encoded, multilingual or multi-turn
  attacks can evade it, and the classifier's accuracy on real-world traffic has not been
  measured here.
- Sensitive-data detection depends on recognizable formats.
- The agent is a deterministic test environment, not a production agent framework.
- The classifier scores the first 128 tokens of each field.
- The local API has no authentication (single-user, localhost only).
- NPU execution, latency and offline operation are claimed only as far as the files in `docs/`
  show.

## Future Roadmap

- Integrations with agent frameworks and MCP tool servers through the same gateway contract
- Central policy management for teams, with signed policy bundles
- Continuous behavioural monitoring across a whole agent session, not single turns
- Stronger model-based detection: multilingual, encoded payloads, larger evaluation sets
- More tool connectors (browsers, cloud storage, calendars)

## Technology Stack

Python (standard library) · ONNX Runtime (QNN Execution Provider / CPU) · DistilBERT ·
React 18 + TypeScript + Vite · IBM Plex (bundled)

## Snapdragon AI Lab Challenge Alignment

### Technical Implementation
A working hybrid detector (deterministic rules plus a local transformer classifier), an
explainable risk model, a policy engine and an audit trail, with 37 automated tests. The
Snapdragon path uses ONNX Runtime's QNN HTP backend with CPU fallback disabled and
profiler-based verification. The evidence lives in `docs/npu-verification.md` and
`docs/benchmark-results.md`.

### Application Use Case & Innovation
Security for autonomous agents: checking what an agent reads and does *before* it acts,
covering prompt injection, data exposure and least-privilege tool use, with a person in the
loop for uncertain cases.

### Deployment & Accessibility
Runs entirely on the laptop. The core has zero third-party Python dependencies, the UI is
prebuilt with bundled fonts, and there are setup, run and inspection scripts for Windows on
ARM plus a CPU fallback for any machine. No cloud accounts or API keys.

### Presentation & Documentation
Architecture, security, risk model, model, deployment and a step-by-step runbook. Evidence
files are machine-generated. Five repeatable demo scenarios, plus a pitch script and deck
content in `submission/`.
