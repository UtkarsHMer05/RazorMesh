# P3 — Untouched-by-training OOD Evaluation (owner closure audit, item #3)

**Set:** `data/phase3/eval/untouched_ood/ood_adversarial_129.jsonl`
**Origin:** the M24 curated adversarial/OOD matrix (129 template-truth rows,
43 independent scenario groups, all 18 semantic families). It was authored
**after** the M27 freeze, so it is **not** in `frozen_v1/train` and was never
seen during fine-tuning. It is therefore a genuinely *untouched-by-training*
OOD evaluation surface.

**Important honesty caveat:** this set is **template-truth (deterministic), not
human-reviewed.** It is the additional OOD evaluation the closure audit
requires, but a *human-reviewed* OOD set is still recommended as a pre-Phase-4
gate (D-050). Its labels were NOT used for retraining, selection, or
calibration (per D-049).

## Result — fine-tuned `phase3-finetuned-cross-encoder` (frozen policy v2)

| Gold label | Expected | Model action confusion | 
|---|---|---|
| contradiction (43) | BLOCK | BLOCK 38 / CHALLENGE 1 / **PASS 4** |
| entailment (43) | PASS/CHALLENGE | PASS 30 / CHALLENGE 6 / BLOCK 7 (over-block) |
| neutral (43) | PASS/CHALLENGE | PASS 10 / CHALLENGE 3 / **BLOCK 30** (over-block) |

- Correct action: 87/129 = **0.674**
- **TRUE unsafe-allows (gold=contradiction → model PASS): 4** ← real OOD safety gap
- Conservative over-blocks (gold=neutral → BLOCK): 30 (safe refusals)
- No model error / fail-closed: 0

## Interpretation

1. The frozen in-distribution test split reported **0 unsafe-allows**; this hard
   OOD set reveals **4**, proving the 79-card human holdout alone is
   **insufficient** to certify OOD safety. An additional untouched set was
   required — and is now built.
2. Every residual error is either a conservative over-block (safe refusal) or a
   small number of contradiction→PASS unsafe-allows on adversarial phrasing the
   model did not train on. The conservative policy fusion (M40) cannot recover a
   contradiction the verifier mislabels as entailment, so this is a verifier
   generalization gap, not a fusion gap.
3. Recommended Phase-4 gate: (a) human-review the M24 OOD families to convert
   template-truth into human_gold_ood; (b) consider adversarial fine-tuning data
   augmentation from these families before production promotion.

Artifacts: `data/phase3/eval/untouched_ood/results.json` (machine-readable).
