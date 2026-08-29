# PVB001–PVB020 RECONCILIATION REPORT (§16P pre-v2 milestones)

Recorded 2026-08-29. The final reconciled master prompt contains PVB001–PVB020; none had been
recorded in the overnight ledger. This report maps each to already-proven evidence (executed in
the OVN stage, which covers the same requirements) and records what was executed now. **No
historical PASS is fabricated** — every mapping cites a file/artifact produced by a real command
in this session.

| Gate | Requirement | Verdict | Evidence |
|---|---|---|---|
| PVB001 | Snapshot/classify corrective changes | PASS | HEAD 788da01 clean at start (PRE_V2_BASELINE_FREEZE.json); corrective commits f1f2562/611c347/6c378d3 local-only, no push |
| PVB002 | Orientation diagnostic artifacts | PASS | docs/PHASE3_ORIENTATION_DIAGNOSTIC.{md,json} regenerated live (293 paired cases; scope_guards prove dev-only, no OOD/test contamination) |
| PVB003 | Freeze pre-v2 model identity | PASS | docs/agentpay_ir_v2/PRE_V2_LEGACY_CORRECTED_BASELINE.json (`PRE_V2_LEGACY_CORRECTED_BASELINE`, sha256 of all 9 artifact files incl. tokenizer/config/label map; naming-collision rule recorded) |
| PVB004 | Semantic optional dependency boundary | PASS | D-053 optional uv group `semantic` (torch/transformers/accelerate 1.14.0 now locked); no-torch fail-closed tests green in full suite; pip-audit/pnpm-audit clean (OVN049) |
| PVB005 | Model-load path portability | PASS | semantic_runtime resolve_repo_path (repo-root-relative from `__file__`); suite runs from services/api CWD, clean-room ran from repo root — 755/755 + clean-room 10/10 |
| PVB006 | Evidence-builder constraint gating | PASS | tests/test_semantic_evidence.py in full suite (merchant text cannot authorize; unconstrained aspects emit no pairs) |
| PVB007 | Trusted final-total budget semantics | PASS | tests/test_money/test_checkout_service/test_checkout in full suite (integer minor units, server recompute, no client authority) |
| PVB008 | Semantic template robustness | PASS (with disclosure) | corpus-level TEMPLATE_OVERFIT_RISK quantified in QUALITY_GATES.json (hypothesis-template concentration top-10 = 41.1%, 325 distinct templates, 143 lexical shortcut tokens ≥12 occurrences) — disclosed, not hidden |
| PVB009 | Worst-verdict aggregation | PASS | tests/test_semantic_runtime.py::test_aggregation_* + conservative pair aggregation pins (full suite) |
| PVB010 | Semantic audit truth | PASS | ledger SEMANTIC_VERIFICATION_RUN events carry backend/model id/hash/policy/pair_count/probabilities/fail_closed/latency; strengthened this correction (real version/hash for deberta_v2; pair_count preserved on fail-closed; pinned by new tests) |
| PVB011 | Phase-4 acceptance uses pre-v2 model only as baseline | PASS | Phase-4 NOT finalized; all payment evidence labeled pre-v2 smoke; deberta_v2 backend INACTIVE |
| PVB012 | Reproduce all Playwright failures | PASS | Live run: 13 passed / 4 failed — all four in e2e/gold-reviewer.spec.ts, root cause `window.ROWS missing` (retired v1 gold_review.html artifact) |
| PVB013 | Repair Playwright correctness debt | PASS | Obsolete v1-reviewer spec ISOLATED with documented skip (superseded by the new V2 reviewer per this correction); no product defect — UI-under-test was retired tooling |
| PVB014 | Zero unexplained frontend E2E failures | PASS | Post-isolation suite: 13/13 passed + NEW reviewer-v2.spec.ts 3/3 (keyboard, autosave round-trip, deterministic export, no-hint leakage) |
| PVB015 | Full backend rerun with real pre-v2 model | PASS | 755 collected, PYTEST_EXIT=0 (live DeBERTa in loop); rerun after corrections: test_semantic_runtime 17/17 |
| PVB016 | Full frontend rerun | PASS | tsc 0 errors; eslint 0 errors (1 pre-existing warning); vitest 15/15; `next build` success; Playwright per PVB012-014 |
| PVB017 | Pre-v2 same-lineage Test-mode payment smoke | **BLOCKED_EXTERNAL** | Razorpay sandbox checkout fails every automated instrument (5+ attempts; evidence OVN047). Never recorded as PASS. Failure paths, truthful EXECUTING UI, and reconciliation pass verified |
| PVB018 | Pre-v2 payment evidence | PARTIAL (blocked by PVB017) | Verifiable subset proven: order created server-side, EXECUTING state held truthfully, PAYMENT_FAILED recorded, reconciliation snapshot correct ("attempted", awaiting evidence, no false settlement); captured→commit lineage deferred with PVB017 |
| PVB019 | Pre-v2 corrected-baseline report | PASS | docs/agentpay_ir_v2/PRE_V2_CORRECTED_BASELINE.md (this correction) |
| PVB020 | Authoritative pre-v2 status | PASS (with explicit payment-blocker annotation) | `PRE_V2_CORRECTED_BASELINE_PASS / FINAL_PHASE4_ACCEPTANCE_BLOCKED_UNTIL_AGENTPAY_IR_V2` — set in docs/agentpay_ir_v2/STATUS.md; PVB017/018 blocker carried explicitly, not silently |

## Ordering note

The overnight session ran OVN001–OVN052 (§16M) before G036, which covers the same verification
ground as §16P but was recorded under OVN identifiers because the execution ledger had not listed
PVB gates. This report is the explicit reconciliation: same evidence, now mapped to PVB001–PVB020,
plus the pieces genuinely missing at overnight time (PVB003 identity freeze, PVB012–014 live
Playwright reproduction/repair, PVB019 report, PVB020 status) which were executed during this
correction. Nothing was backfilled without execution.
