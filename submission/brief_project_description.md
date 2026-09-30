# SentinelOS: Local AI Security for Autonomous Agents

*Draft. Values marked ⟦FILL⟧ are taken from the machine-generated evidence files in `docs/`
before submission. No hardware or performance claim is made until those files exist.*

## 1. Problem

AI agents now read documents, open files, call tools and send messages on a person's
behalf, using that person's permissions. This creates a class of risk that answer-only
chatbots did not have. A document can contain instructions aimed at the agent. A working
context can hold credentials that end up in an outbound email. An agent can ask for far more
access than its task requires, and a single mistaken or manipulated step becomes an action
with real consequences.

## 2. Why now

Agent frameworks and tool protocols are making it routine to connect language models to
file systems, browsers, email and business applications. Prompt injection through retrieved
content is a widely documented weakness of these systems. The security question has moved
from "what did the model say?" to "what is the agent about to do, and should it?"

## 3. Solution

SentinelOS is a security boundary that runs on the device. Every agent request (the user's
prompt, the content the agent has read, and the tool action it proposes) passes through one
gateway and receives one of three decisions: **allow**, **require approval** or **block**.
Each decision comes with a risk score, a severity level, the rule-by-rule evidence, the policy
that decided it, and a recommended next step.

## 4. Technical architecture

The gateway runs four analyses:

- **Prompt scanner.** Eight weighted categories of injection behaviour, including instruction
  override, system-prompt extraction, role hijack, guardrail bypass, covert action and
  exfiltration directives. Content from untrusted sources is weighted highest.
- **Data scanner.** Ten rules for credentials, tokens, private keys, card numbers
  (Luhn-validated), identity-number formats, email and phone. Secrets are redacted before
  display or logging.
- **Tool scanner.** Least-privilege checks on file scope, sensitive paths, workspace
  boundaries, shell commands, network destinations and email recipients.
- **Local ML classifier.** A DistilBERT prompt-injection model running on ONNX Runtime.

A **risk engine** combines signals with a documented noisy-OR function. A **policy engine**
applies editable rules, such as blocking tool calls made in the same turn as a detected
injection and blocking secrets that would leave the device. A **decision engine** takes the
strictest outcome, and every decision is written to an **audit timeline** where held requests
can be approved or denied.

## 5. AI implementation

Detection is deliberately hybrid. Deterministic rules give explainable, repeatable results
and cover data and tool risk, which a text classifier cannot see. The classifier adds a
second opinion on injection wording. Its influence is capped: the model alone can hold a
request for review but cannot block it. This keeps model false positives from interrupting
legitimate work while still using the model's signal. The UI reports the model's real softmax
probability, or says plainly that the classifier is unavailable.

## 6. Snapdragon optimization

The classifier is exported with static input shapes, QDQ-quantized using ONNX Runtime's QNN
quantization tools, and run through the **QNN Execution Provider on the HTP (NPU) backend**.
The session is created with CPU fallback disabled, so ONNX Runtime refuses to start it unless
every operation runs on QNN. A verification script adds profiler-based node counts and a CPU
reference comparison.

- Processor: ⟦FILL: docs/environment.md⟧
- NPU verification verdict: ⟦FILL: docs/npu-verification.md⟧
- Model inference latency, median / p95: ⟦FILL: docs/benchmark-results.md⟧
- Full security check latency, median / p95: ⟦FILL: docs/benchmark-results.md⟧
- CPU comparison on the same laptop: ⟦FILL: data/benchmarks/*-cpu.json⟧

## 7. Privacy and local processing

Analysis happens entirely on the device. SentinelOS needs no cloud account and no API key,
and it sends no document content anywhere. The server listens only on the local machine, and
the interface's fonts are bundled. Offline operation: ⟦FILL: docs/offline-verification.md⟧.

## 8. Use cases

- A knowledge worker's agent summarizing vendor documents that may contain hidden instructions
- A coding agent proposing shell commands that should be reviewed before running
- An operations agent drafting emails from notes that contain credentials
- A research agent requesting file access broader than its question needs

## 9. Deployment

SentinelOS targets Snapdragon-powered Windows 11 PCs. The security engine and server use only
the Python standard library, which avoids common installation failures on ARM64. The ML path
needs native ARM64 Python with `onnxruntime-qnn`. Setup, run and machine-inspection scripts
are included, and the same software runs on the CPU on any machine.

## 10. Innovation

Most AI security tools sit in the cloud and filter model inputs or outputs. SentinelOS is
aimed at the point where an agent turns text into action, and it makes that decision on the
device. This matters for privacy (the content being checked is often the sensitive content),
for availability (the boundary works without a connection), and for trust (every decision is
explained and auditable).

## 11. Current results

- A working MVP with five repeatable scenarios. Safe requests are allowed, a shell command is
  held for approval, and prompt injection, credential exfiltration and excessive file access
  are blocked.
- 37 automated tests covering the scanners, risk scoring, policies, decisions and preset
  determinism.
- On-device inference results: ⟦FILL⟧.

## 12. Limitations and future work

Rule-based detection finds known patterns. Novel, encoded, multilingual or multi-turn attacks
can evade it, and the classifier's real-world accuracy has not been measured here. The agent
is a deterministic test environment rather than a production integration. Next steps are
integrations with agent frameworks and tool servers, central policy management, session-level
behavioural monitoring, broader model-based detection, and more tool connectors.
