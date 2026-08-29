# AUTHORITATIVE STATUS (PVB020)

# PRE_V2_CORRECTED_BASELINE_PASS / FINAL_PHASE4_ACCEPTANCE_BLOCKED_UNTIL_AGENTPAY_IR_V2

## PRE-TRAINING-READY (2026-08-29, PVB correction complete)

All pre-training correction items are green:
- PVB001–PVB020 reconciled with real evidence (PVB_RECONCILIATION_REPORT.md); nothing fabricated.
- V2 review pack REBUILT: 701 stratified cards, 25 strata, C/E/N spanned, no hints
  (data/agentpay_ir_v2/review/REVIEW_PACK_V2.jsonl, sha256 80896091…);
  roles pre-frozen (300 gold / 401 supervised, sha256 53914772…); old 700-card pack INVALID.
- Reviewer UI live at http://localhost:3000/reviewer (keyboard 1/2/3/4, arrows, progress,
  autosave, deterministic export; zero suggestions; Playwright 3/3 + full E2E green).
- Post-review finalization pipeline ready (scripts/rzp_finalize_review_v2.py): validation, role
  join, ambiguous routing, gold separation, supervised integration, leakage re-run, final hashes,
  final bundle rebuild.
- Colab notebook corrected: non-self-referential bundle verification, FROZEN selection rule
  (min unsafe C→E → max macro-F1 → max contradiction recall), full model_manifest.json in the
  returned artifact, Colab pins aligned with the API semantic runtime (5.15.1/2.13.0/1.14.0).
- Runtime: deberta_v2 permitted in Settings; real model version/hash recorded; pair_count
  preserved on fail-closed; all pinned by tests (17/17).
- Fresh OOD refrozen: 401 rows, every row normalized to the v2 provenance contract
  (13% internal / 45% ContractNLI / 42% ESCI), hash/group-disjoint from corpus and gold.
- Quality gates run and disclosed (QUALITY_GATES.{json,md}): honest composition 95.3%
  real/human-derived + 4.7% targeted deterministic internal; 143 lexical-shortcut tokens;
  hypothesis-template concentration; premise-source concentration; near-dup density; 34-family
  coverage.
- Phase-4 status: AWAITING_FINAL_HUMAN_ACCEPTANCE preserved as history; dated addendum records
  the deferral. Remote state recorded honestly (REMOTE_STATE.md); no push from this agent.

## Human review entry point

- URL: http://localhost:3000/reviewer (dev server) — cards served from
  data/agentpay_ir_v2/review/REVIEW_PACK_V2.jsonl (701 cards).
- Decisions autosave to data/agentpay_ir_v2/review/decisions_working.json;
  deterministic export at http://localhost:3000/api/reviewer/export.
- After labeling every card: export the JSON, then run
  `services/api/.venv/bin/python scripts/rzp_finalize_review_v2.py --decisions <exported.json>`
  (rebuilds the FINAL Colab bundle with supervised labels integrated).

## Still blocked (carried, not hidden)

- OVN047/PVB017 pre-v2 payment completion: BLOCKED_EXTERNAL (Razorpay sandbox checkout).
- Full v2 fine-tuning: NOT started (per instruction) — begins only after human review + Colab run.
