# PRE_V2_CORRECTED_BASELINE (PVB019)

**Status:** `PRE_V2_CORRECTED_BASELINE_PASS / FINAL_PHASE4_ACCEPTANCE_BLOCKED_UNTIL_AGENTPAY_IR_V2`
**Recorded:** 2026-08-29 · HEAD at correction: `6c378d3` (+ this correction's commits)

## 1. Orientation diagnostic

Reproduced live from disk (docs/PHASE3_ORIENTATION_DIAGNOSTIC.{md,json}): 293 paired dev-only
cases; legacy macro-F1 0.9832 vs canonical 0.9764 (Δ −0.0068); contradiction recall 0.9896 →
0.9792; unsafe contradiction→entailment flips 1 → 2; **RETRAIN_REQUIRED=YES**. Scope guards prove
only development data influenced the recommendation (no OOD/test contamination). The correction
already shipped (D-053): frozen_v2 corpus + `phase3-finetuned-v2` checkpoint wired as the runtime
default (`SEMANTIC_VERIFIER_BACKEND=deberta`, thresholds `semantic-thresholds-v3`).

## 2. Current model hash (frozen)

`PRE_V2_LEGACY_CORRECTED_BASELINE` = `artifacts/models/incoming/phase3-finetuned-v2`
— all 9 files hashed in docs/agentpay_ir_v2/PRE_V2_LEGACY_CORRECTED_BASELINE.json
(model.safetensors `163864e0…`; tokenizer/config/label_map included). Old paths/weights preserved;
the future AgentPay-IR v2 artifact lives at a different path (no naming collision).

## 3. Runtime fixes applied during this correction

- `deberta_v2` backend option added to Settings + semantic_runtime (INACTIVE; missing artifact
  fails CLOSED to CHALLENGE, never a keyword substitution) — pinned by tests.
- deberta_v2 success path records the REAL model version + artifact sha256 (previously would have
  fallen into the stub-metadata branch).
- Fail-closed model errors preserve the ACTUAL pair_count (was 0).
- accelerate added to the semantic uv group (HF Trainer dependency for the smoke fine-tune).

## 4. Template robustness (disclosed, quantified)

QUALITY_GATES.json: 325 distinct hypothesis templates (80-char normalized), top-10 concentration
41.1% of train; 143 lexical-shortcut tokens (≥12 occurrences, single label); near-duplicate
(Jaccard≥0.85) density within split/family buckets: train 187 / val 454 / test 528. These are
recorded as TEMPLATE_OVERFIT_RISK indicators for the v2 training read — not hidden.

## 5. Test counts (this session, real runs)

- Backend: 755 collected, exit 0 (live DeBERTa in loop); semantic_runtime file 17/17 after fixes.
- Frontend: tsc 0 errors; eslint 0 errors (1 pre-existing warning); vitest 15/15; next build OK.
- Playwright: 13/13 green after isolating the retired v1-reviewer spec (root cause documented);
  NEW reviewer-v2.spec.ts 3/3 (keyboard labels, autosave round-trip, deterministic export,
  suggestion-leakage absence).
- Clean-room (isolated DB/Redis/mock provider): scripts/acceptance.py 10/10.

## 6. Remaining limitations (explicit)

1. **Pre-v2 payment smoke completion is BLOCKED_EXTERNAL**: the Razorpay Test sandbox checkout
   fails every automated instrument (domestic card declined; international disabled; netbanking/
   wallet simulator pages never load). The captured→commit lineage evidence therefore remains
   deferred; failure paths and reconciliation were verified. A manual checkout completion (or
   account settings fix) closes this.
2. Real-data AgentPay-IR v2 is **not yet trained**. The current corpus (13,843/2,312/2,261) and
   Colab bundle are PRE-REVIEW artifacts; final freeze happens after human review via
   scripts/rzp_finalize_review_v2.py.
3. Historical debts unchanged: 4 stale E2E tests isolated (not deleted); services/api/scripts
   ruff drift; ESLint 9 dev-only exception.

## 7. Explicit statement

**The real-data AgentPay-IR v2 model is not yet trained.** Nothing in this report claims v2
training, v2 evaluation, or final Phase-4 acceptance.
