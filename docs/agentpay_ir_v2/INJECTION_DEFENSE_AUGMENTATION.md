# Prompt-Injection Training Augmentation — PREPARED, NOT INTEGRATED (2026-08-30)

## Why

PVB008 (`PRE_V2_TEMPLATE_ROBUSTNESS.md`) showed the deployed PRE_V2 model PASSes
13/15 on prompt-injection-laden premises: hostile/injected merchant text is read as
SUPPORTING the authorization hypothesis instead of being ignored. This staging set
is a targeted development/training augmentation addressing exactly that failure
mode.

## What exists

- `data/agentpay_ir_v2/augmentation/prompt_injection_aug_v2.jsonl` — 96 rows
  (48 neutral + 48 contradiction), sha256 `f897137b…` (full sha in the manifest).
- 12 hand-authored templates × 8 fresh entity variants:
  - 6 templates labeled **neutral** — injected text is irrelevant to the stated
    constraint (teaches: injection ⇒ not-entailment);
  - 6 templates labeled **contradiction** — injected text demands violating the
    constraint (teaches: injection demanding X ⇒ contradiction with "only X is
    authorized").
- Builder: `scripts/rzp_build_prompt_injection_augmentation_v2.py` (deterministic,
  re-runnable, self-asserting).

## Gates that passed (asserted in the builder, pinned by tests)

| gate | result |
|---|---|
| v2 record contract (all provenance fields, schema_version) | PASS |
| hash-disjoint vs corpus train/val/test, fresh OOD, human gold | PASS |
| split_group-disjoint vs corpus and OOD (`aug_pi_*` namespace) | PASS |
| text-disjoint vs the PVB008 grid sentences | PASS |
| entity holdout (fresh names absent from corpus, OOD, PVB008) | PASS |
| canonical_guard (no authorization prose in premises) | PASS |
| synthetic-security cap if fully integrated | 96 / 13,843 train = **0.69%** (≤ 10% cap) |

## What is NOT done (deliberate)

- **Not integrated into any frozen artifact**: the bundle builder and notebook never
  touch it, and no current train/val/test/gold/OOD file contains these rows. The ONLY
  integration path is the finalizer flag
  `--integrate-prompt-injection-augmentation` (an explicit human decision at
  post-review finalization), which merges the 96 rows into the FINAL TRAIN split
  ONLY and re-runs the canonical-hash, leakage, provenance and synthetic-ratio
  gates over the merged set. Both the flag-gated and default (no-integration)
  paths are exercised by the dry-run finalizer and pinned by tests.
- Never sourced from OOD or PVB008 sentences (verified disjoint at build time and
  re-verified against the final data at integration time).
- It is an augmentation for the DEVELOPMENT side only; the untouched OOD remains
  the generalization benchmark and is never tuned from.
