# Risk model

The same inputs always give the same score (tests assert this for every preset).

## 1. Signals

Each scanner emits signals with a weight between 0 and 1 (listed in the scanner source files
and shown in the UI evidence list with their rule IDs).

## 2. Scanner scores: noisy-OR

    score = 1 − Π (1 − wᵢ)

Several weak signals add up, one strong signal dominates, and the score can never exceed 1.
Example: weights 0.85 and 0.35 give 1 − (0.15 × 0.65) = 0.9025.

## 3. ML contribution (prompt-injection score only)

    injection = 1 − (1 − rules) × (1 − ml_weight × p_injection)

With `ml_weight = 0.55`, a model probability of 1.0 with no rule evidence gives 0.55, which is
in the MEDIUM band (REQUIRE_APPROVAL). **The model alone can hold a request for review but
cannot block it.** When rule evidence exists, the model raises the score further.

`ml_weight` must stay below the HIGH threshold (0.60); `tests/test_security_engine.py`
enforces the resulting behaviour.

## 4. Overall score

    overall = max(prompt, data, tool) + 0.10 × (number of other scanners scoring ≥ 0.30)

capped at 1.0. Findings in several dimensions at once (for example, injection plus data
exposure) are more serious than either alone.

## 5. Levels and decisions

| Level | Overall score | Default decision |
|---|---|---|
| Low | below 0.30 | Allow |
| Medium | 0.30 to 0.59 | Require approval |
| High | 0.60 to 0.84 | Block |
| Critical | 0.85 and above | Block |

## 6. Policy verdicts

Tool and cross-cutting policies return their own effects. The final decision is the most
severe of the level-mapped decision and every verdict. When a policy forces a stricter
decision, the reported level is raised to match (BLOCK → at least High) so the level and
decision never contradict each other.

All thresholds and weights are in `config/policies.json`.

## 7. What "confidence" means in the UI

The UI shows **Model confidence (injection)**: the classifier's softmax probability for the
injection class, computed at request time. When the model is not loaded, the UI says "ML
classifier unavailable". The risk score (0–100) is a separate, rule-based number. SentinelOS
does not present a synthetic "confidence" for rule matches.

## Current preset results (deterministic engine, verified by tests)

| Preset | Level | Decision | Main drivers |
|---|---|---|---|
| Safe request | Low | Allow | none |
| Command needs review | Medium | Require approval | TR-08 shell command |
| Prompt injection | Critical | Block | PI-01, PI-02, PI-06, PI-08 |
| Sensitive data exposure | Critical | Block | DS-03, DS-04, XC-02 secrets leaving the device |
| Excessive file access | Critical | Block | TR-01 recursive scope, TR-02 vague reason |

With the ML classifier loaded, the prompt-injection score can only rise. The three Block
presets are already at their strictest outcome, so their decisions cannot change. The Safe
and Command-review presets could escalate if the model scores their benign text as injection
(for example, a probability of 0.55 or more on the Safe preset would move it to Require
approval). After installing the model on the laptop, run all five presets and record the
observed results and probabilities in this table.
