# P3-M30 — NLI Baseline Selection (PROVISIONAL pending gold review)

Frozen data: `data/phase3/dataset/frozen_v1` (1021 records; leakage gate PASSED).
Identical harness for both candidates (`scripts/rzp_eval_nli_baseline.py`,
same tokenizer settings, same split files, card-pinned label maps unit-tested).
All numbers below are from `docs/PHASE3_NLI_BASELINE_A_METRICS.json` and
`docs/PHASE3_NLI_BASELINE_B_METRICS.json` (val split, 171 rows, MPS device).

## Security-first comparison (master prompt §12 order)

| Criterion | A MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli | B cross-encoder/nli-deberta-v3-base | Winner |
|---|---|---|---|
| License | MIT | Apache-2.0 | — |
| Contradiction recall (blocks unsafe) | 0.389 | **0.704** | B |
| Neutral recall (safe-lookalike / benign pass-through) | 0.0179 | **0.232** | B |
| Neutral precision (false-block proxy for safe-lookalike) | 0.0556 | **0.684** | B |
| Macro F1 | 0.397 | **0.607** | B |
| Val accuracy | 0.474 | **0.637** | B |
| Test macro-F1 | 0.349 | **0.589** | B |
| Calibration | softmax usable; deferred to M37 thresholds | softmax usable; deferred to M37 thresholds | tie |
| Resource cost (MPS, 171 rows) | 30.4 s (≈178 ms/row) | **9.1 s (≈53 ms/row)** | B |

### Safe-lookalike false-positive explanation
`safe_lookalike` cards are a **neutral** family (the model must NOT block them).
On the val split, model A misclassifies 54/56 neutral rows as entailment
(false BLOCK of safe-lookalikes), and model B misclassifies 42/56. Neither is
acceptable for production unmitigated, but B's neutral precision (0.684) leaves
far fewer conservative false blocks than A (0.056). The conservative policy
fusion (M40) + thresholds (M37) further bound this; the fine-tuned verifier
(M36) closes most of the remaining gap.

## Decision
**DECISION (D-044): select B — `cross-encoder/nli-deberta-v3-base`** as the
provisional SemanticVerifier backbone, on contradiction-recall and macro-F1
superiority and ~3.3x lower latency. Selected by measured security/utility
criteria, not by reputation.

Status: PROVISIONAL_BASELINE / PENDING_GOLD_VALIDATION.
Fine-tuned comparison (M36) may replace it only with held-out evidence after
the human-run Colab training (M34). M36 recorded D-046: the fine-tuned
cross-encoder improves security further and is selected for production, with the
baseline-B selection here preserved as the documented A/B baseline gate.
