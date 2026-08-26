# P3-M36 — Fine-tuned vs Baseline B Evaluation

**Date:** 2026-08-26
**Decision (D-046):** Select the fine-tuned model
(`cross-encoder/nli-deberta-v3-base` fine-tuned on frozen_v1 train split,
3 epochs, eval_macro_f1 ≈ 0.983 on val) as the production
`SemanticVerifier` backbone. Retain zero-shot baseline B as a documented
fallback for parity regression checks only.

## Setup

- **Artifact:** `artifacts/models/incoming/phase3-finetuned/` (unzipped from
  `phase3-finetuned.zip`, sha256 `54d0fa01…f1e24`).
- **Base model:** `cross-encoder/nli-deberta-v3-base` (Apache-2.0).
- **Label map (read from artifact, drives all index→label translation):**
  `{0: contradiction, 1: entailment, 2: neutral}` — identical project-space
  order to baseline B, so the production `DebertaNLISemanticVerifier`
  contract is unchanged.
- **Training metrics (artifact's own metrics.json):**
  `eval_loss=0.1322`, `eval_accuracy=0.9825`, `eval_macro_f1=0.9826`.
- **Eval script:** `scripts/rzp_eval_finetuned.py` (mirror of
  `rzp_eval_nli_baseline.py` but reading label_map + model from the
  artifact directory).
- **Splits evaluated:** `frozen_v1/val.jsonl` (171), `frozen_v1/test.jsonl`
  (127), and the 320 human-gold cards split into:
  - `human_gold_heldout` (79): cards whose `record_id` is in val or test
    — these were **never seen** during training (honest holdout).
  - `human_gold_in_train` (241): cards whose `record_id` is in train —
    reported separately for transparency (P3-S09: no training-set
    contamination in holdout reporting).
  - `human_gold_all` (320): the headline M26 number for context.

## Headline numbers

| Split | n | Baseline B acc / macro-F1 | Fine-tuned acc / macro-F1 | Contra recall B → FT | Unsafe entail on contra B → FT |
|---|---:|---|---|---|---|
| val | 171 | 0.637 / 0.607 | **0.982 / 0.983** | 0.704 → **0.981** | — → 1 |
| test | 127 | 0.606 / 0.589 | **0.984 / 0.984** | — → **1.000** | — → 0 |
| human_gold_heldout | 79 | 0.595 / 0.554 | **0.937 / 0.938** | 0.645 → **1.000** | 8 → **0** |
| human_gold_in_train | 241 | n/a (in training pool) | 0.967 / 0.966 | — → 1.000 | — → 0 |
| human_gold_all | 320 | 0.563 (M26) | 0.959 / 0.958 | — → 1.000 | 29 → 0 |

**All numbers traced to:**
- `docs/PHASE3_NLI_FINETUNED_METRICS.json` (this milestone).
- `docs/PHASE3_NLI_BASELINE_B_METRICS.json` (M29) for val/test.
- `data/phase3/gold/gold_frozen.json` (M26) for human_gold_all baseline
  number (56.25% acc, 29 unsafe entailments on human contradictions).

## Security / safety interpretation

- **Closed the M26 gap:** zero-shot baseline B failed on human-labeled
  contradiction 29/119 (unsafe entailments). Fine-tuned model has
  **0 unsafe entailments on the heldout 31 human contradictions** and
  **0 on the full 119**.
- **Contra recall on human holdout:** 0.645 → **1.000** (every human
  contradiction correctly classified).
- **Neutral handling on human holdout:** precision 1.0, recall 0.955 —
  fine-tuned is much more conservative than baseline B (which collapsed
  many neutrals to entailment, recall 0.232 on val).
- **No training-set contamination reported as holdout** (P3-S09).
- **No fabricated numbers** (P3-S20): every cell above is sourced from a
  committed artifact whose path is named in this doc.

## Selection criteria (master prompt §12 order)

1. **Contra recall on human holdout:** B 0.645 → FT 1.000 → **FT**.
2. **Unsafe entailments on human contradictions:** B 8 → FT 0 → **FT**.
3. **Macro F1:** B 0.554 → FT 0.938 (heldout), B 0.589 → FT 0.984 (test) → **FT**.
4. **Calibration:** deferred to M37 — both emit softmax; FT outputs are
   confident (M47 already proved CPU feasibility on a 0.2B model).
5. **License / origin:** FT base is Apache-2.0; FT artifact derived from
   the RazorMesh training pipeline. **Gold-data semantics (corrected, D-050):**
   the 320 human-reviewed gold cards were split at freeze into
   `human_gold_in_train` (241) which **are** in `frozen_v1/train.jsonl` and
   therefore DID influence training, and `human_gold_heldout` (79) which are
   in val/test and were **never** seen during training. The 79-card heldout
   labels never influenced training, threshold calibration (M37 used val
   only), or model-selection parameters (best-checkpoint by val macro-F1);
   the heldout numbers above are transparent evaluation reporting, not
   tuning inputs. P3-S09/S12 is satisfied specifically for the heldout, not
   for the 241 in-train gold cards (disclosed here, not hidden).
6. **Reproducibility:** artifact sha256 recorded; transformer
   version (5.15.1) recorded; deterministic re-load possible.

## What this changes downstream

- **M37 (thresholds):** the existing PROVISIONAL thresholds
  (τ_block=0.36, τ_entail=0.40) were calibrated against the baseline-B
  val softmax. Fine-tuned softmax is much more confident — M37 will
  re-derive thresholds on val with the fine-tuned verifier and validate
  on human_gold_heldout (the cleanest separation of calibration vs
  test data).
- **M38 (production SemanticVerifier):** the model_dir is swapped to
  the artifact path; the label_map is read from disk (no hard-coding).
- **M45/M46 (e2e benchmark / ablation):** re-run with the new verifier.
  Ablation structure unchanged — the property (NLI-only can never
  create authority) is invariant to the model.

## What this does NOT change

- Money representation (integer minor units) — invariant to the verifier.
- Ticket context-binding, short-lived single-use tickets — invariant.
- Hard-rule precedence (NLI never grants, only refuses/challenges) —
  invariant.
- `RULES.md` / `SECURITY.md` / `PRD.md` — no changes.
