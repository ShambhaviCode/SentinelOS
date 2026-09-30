# Final review: skeptical-judge pass

Written before the laptop evidence exists. Update the risks and checklist after running the
runbook.

## Answers to the judge's questions

| # | Question | Honest answer today |
|---|---|---|
| 1 | Different from a generic chatbot? | Yes. There is no chat. It is a decision point on agent inputs **and tool actions**, with policy and audit. |
| 2 | Is Snapdragon genuinely relevant? | The argument is real (private, on-device decisions on sensitive content). The proof depends on `npu-verification.md`. |
| 3 | Can we prove local inference? | Yes once the model is installed: the provider and load time are read at runtime, and the analysis path makes no network calls. |
| 4 | Can we prove NPU inference? | **Not yet.** The method is strong (fallback disabled, profiler node counts, CPU comparison) but it has not run. |
| 5 | Are model claims accurate? | We claim only what the model is and its license; no detection rate is claimed. |
| 6 | Are benchmark values real? | Only script-generated values are shown; none exist yet. |
| 7 | Can a judge reproduce the demo? | Yes for the deterministic engine on any OS (`python -m sentinel.server --no-ml`). The ML path needs the export step. |
| 8 | Is the architecture understandable? | Yes: one diagram, one scoring formula, and rule IDs visible in every piece of evidence. |
| 9 | Are we overclaiming? | Documents use "detects known patterns" and "designed to". Offline is not claimed until verified. |
| 10 | Is the UI professional? | Dark console, consistent decision colors, real data only. Reviewed via screenshots. |
| 11 | Is the problem clear in 20 seconds? | The script states it by 0:20 with concrete examples. |
| 12 | Does the demo visibly prove it? | Yes: evidence lines, a Blocked badge and the trust graph path. |
| 13 | All four criteria? | See the README alignment section. The Snapdragon evidence is the gap. |
| 14 | What could fail live? | See Risks. |

## Strengths

- A hybrid detector with a principled safety property (the model cannot block alone), backed by tests.
- It covers **actions**, not only text, which is where agent risk actually becomes harm.
- Explainability: rule IDs, redacted evidence, the policy that decided, and a recommended action.
- Unusually honest runtime reporting: fallback-disabled QNN sessions and "Not detected" everywhere else.
- The zero-dependency core removes the most common ARM64 installation failure.

## Weaknesses

- The prompt-injection rules are English-only and pattern-based; paraphrases outside the patterns rely on the model.
- The classifier's real-world accuracy has not been measured. The quantization calibration set is small.
- The agent is simulated. There is no integration with a real agent framework yet.
- Three presets score CRITICAL, so the demo shows less gradation between HIGH and CRITICAL.

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| QNN rejects an op or int64 inputs | Medium | `--int32-inputs` re-export; diagnostic node counts; honest CPU fallback |
| PyTorch will not install on ARM64 Python | Medium | Export with x64 Python under emulation, or on another machine |
| The model scores the Safe preset as injection | Low–medium | Its effect is capped at review; check and record in `risk-model.md` |
| Laptop sleeps or the server stops mid-demo | Low | Start the server just before presenting; the UI shows "Server unreachable" |
| Network probe shows "Online" on stage Wi-Fi | High | The label reads "Online (analysis stays local)"; turn Wi-Fi off for the demo if offline was verified |

## Fixes before submission

1. Run the laptop runbook, steps 0–8.
2. Fill the ⟦FILL⟧ slots in `submission/` from the evidence files.
3. Build the pitch PPTX and PDF and the description PDF from the verified values.
4. Re-check the model license on its model card.
5. Record the preset results with the model loaded in `risk-model.md`.

## Final checklist

- [x] App launches (sandbox, deterministic engine)
- [x] Agent simulator and five presets work
- [x] Prompt injection, sensitive data, tool-risk and safe scenarios work
- [x] Risk score, allow/approve/block and approve/deny work
- [x] Audit timeline works
- [x] Tests pass (37)
- [x] Synthetic data only; no secrets committed
- [x] README, architecture, security, risk model, model, deployment and runbook docs
- [ ] Local AI running on the laptop
- [ ] NPU execution verified, or its absence documented
- [ ] Benchmarks measured on the laptop
- [ ] Offline verified
- [ ] Screenshots from the laptop
- [ ] Deck (PPTX, PDF) and description PDF with real values
