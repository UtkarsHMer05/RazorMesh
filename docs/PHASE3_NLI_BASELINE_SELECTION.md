# P3-M30 — NLI Baseline Selection (PROVISIONAL pending gold review)

Frozen data: `data/phase3/dataset/frozen_v1` (1021 records; leakage gate PASSED).
Identical harness for both candidates (`scripts/rzp_eval_nli_baseline.py`,
same tokenizer settings, same split files, card-pinned label maps unit-tested).

| Model | License | Val acc | Val macro-F1 | Val contra recall | Test acc | Test macro-F1 |
|---|---|---|---|---|---|---|
| A MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli | MIT | 0.474 | 0.397 | 0.389 | 0.417 | 0.349 |
| B cross-encoder/nli-deberta-v3-base | Apache-2.0 | 0.637 | 0.607 | 0.704 | 0.606 | 0.589 |

Security-first criteria (master prompt §12 order):
1. contradiction recall: B 0.704 vs A 0.389 -> B
2. neutral handling: B macro-F1 gap (+0.21), balanced classes
3. safe-lookalike FPR: no pathological FP class for either; B ahead on aggregate precision (contra prec 0.927)
4. macro F1: B +0.210
5. calibration: deferred to M37 thresholds; both emit usable softmax
6. cost: both ~0.2B base, CPU-feasible; B ships official ONNX exports (M47 option)

DECISION (D-044): select B - cross-encoder/nli-deberta-v3-base as the
provisional SemanticVerifier backbone.

Status: PROVISIONAL_BASELINE / PENDING_GOLD_VALIDATION.
Fine-tuned comparison (M36) may replace it only with held-out evidence after
the human-run Colab training (M34).
