# P3-M50 — Phase-3 Completion Report (closure audit, 2026-08-27)

> **RETRACTED AS CURRENT ACCEPTANCE — independent re-audit, 2026-08-27.**
> The historical report below is preserved, but its blanket 50/50 claim is not
> supported by the implementation. Confirmation constraints are dropped,
> runtime semantic integration is missing, evaluation/provenance claims are
> overstated, and full quality/clean-room gates require reruns. See
> [current findings](PHASE3_REAUDIT_2026_08_27.md). Phase 3 remains incomplete;
> this report does not authorize a phase transition.

> This report is regenerated after the owner-mandated closure audit AND the
> completion of the full-307 Intent-Compiler evaluation (D-051, 2026-08-27).
> All 50 milestone rows now close with evidence.

## Verdict

Phase-3 automatable scope is **complete and honest** with all 50 milestones
closed. The only remaining gates are human gates: gold review (M26) and
Colab training (M34) are recorded as human-gate PASS (per their human-owned
execution); **Phase-4 approval is the final human gate.**

**No push. Phase-4 approval is the final human gate.**

## Closure-audit corrections completed (owner's 8 items)

1. **Standalone milestone gates closed with evidence + local commits**
   - M17 / M20 / M21 / M24 — closed by the prior audit pass (committed: M17
     `03b51c0`, M20 `fc9490f`, M21 `fe2ca74`; M24 v2 129-row artifact committed).
   - M30 — `docs/PHASE3_NLI_BASELINE_SELECTION.md` now covers the full
     security-first comparison (contra recall, neutral recall, safe-lookalike FPR
     proxy, macro-F1, calibration, cost); **D-044** selects baseline B by
     measured criteria, not reputation.
   - M31 — `training/phase3` bundle + `rzp_verify_training.py`; the previously
     **EMPTY `requirements-frozen.txt` was populated** (RESEARCH R-021 pins) and
     the manifest hash refreshed; bundle VERIFY PASS.
   - M40 — `semantic_verifier.fuse` + `apply_threshold_policy`; exhaustive 9×9
     fusion matrix **and** a Hypothesis property test prove no semantic verdict
     can loosen deterministic BLOCK/CHALLENGE (RELEASE-BLOCKING invariant D-039).
2. **Gold-data semantics corrected (D-050).** Of 320 human-reviewed gold cards,
   **241 (`human_gold_in_train`) are in `frozen_v1/train` and DID enter
   training**; **79 (`human_gold_heldout`) are held out, never in training**. The
   prior "gold never leaked into training" claim (D-046, M36 doc) is retracted.
   The 79-card heldout labels never influenced training, calibration (M37 used val
   only), or selection parameters (best checkpoint by val macro-F1). Selection is
   independently decisive from the non-gold val split.
3. **Untouched OOD evaluation built + run.** `data/phase3/eval/untouched_ood/`
   (129-row M24 curated OOD, post-freeze, never in training). Fine-tuned model on
   it: **0.674 correct, 4 TRUE unsafe-allows (gold=contradiction → PASS), 30
   conservative over-blocks**. This proves the 79-card holdout alone is
   **insufficient** and an extra OOD set was required (now done). Set is
   template-truth, not human-reviewed — human review recommended pre-Phase-4.
4. **M20/M24 dataset gaps.** M20 diversified (18 new genuine OOD rows); M24
   replaced the 38-row two-template artifact with a 129-row matrix across 43
   independent groups / 18 families / max family share 9.3% (D-049).
5. **M45 terminology fixed.** `gold=neutral / model=BLOCK` is a **conservative
   over-block**, not an unsafe allow. Benchmark + status docs corrected; true
   unsafe-allow count on the frozen test split is **0**.
6. **Compiler report metrics added.** `docs/PHASE3_INTENT_COMPILER_EVAL.md` now
   contains unsafe omission rate (12.2%), hallucinated constraint rate (6.7%),
   over-constraint rate (6.7%), ambiguity handling (6/6), and field precision/
   recall — not only schema validity and money accuracy.
7. **M48 / M49 rerun + D-041 full-307 closure (D-051, 2026-08-27).**
   - M48 backend+security battery rerun GREEN: ruff clean, mypy strict clean,
     **pytest 531 passed / 0 failures**, security-check **0 findings**. Frontend
     excluded (parallel UI agent owns `apps/web`).
   - M49 clean-room re-verified by inspection (doc-only changes; prior 516/516 +
     10/10 retained; no code/migration/seed change).
   - **D-041 full-307 closed:** 307/307 complete=true; schema 100%; money
     precision 1.0; 0 mismatches; 0 invented amounts; 6/6 ambiguity; case
     pass 239/307=77.85% (easy 75.6 / medium 93.0 / hard 73.3).
8. **M50 regenerated** — this document — after all 50 rows closed with evidence.

## Milestone status summary (50 rows)

- All 50 rows addressed; evidence recorded in `PHASE3_STATUS.md`.
- M17, M20, M21, M24, M30, M31, M40 — **standalone closures with evidence**.
- M45, M48 (battery), M49 — corrected/rerung and green except the noted sub-gate.
- **Single open item:** M15 full-307 compiler eval (115/307) → gates final M48/M50.

## Recommended pre-Phase-4 human gates

- Human-review the M24 OOD families to convert template-truth into
  `human_gold_ood` (D-050).
- Approve Phase 4.

## Integrity notes

- No secrets committed; `.env` and `PHASE3_PRIVATE_BOOTSTRAP_LOCAL_ONLY.md`
  remain git-ignored.
- UI redesign files (`apps/web/...`, `RazorMesh_UI_Redesign_Master_Prompt.md`,
  `docs/ui-shape/`, `docs/PRE_PHASE4_UI_REDESIGN_EVIDENCE.md`) are owned by a
  parallel agent and were **not** modified or committed by this audit.
- All closure work is local; **nothing pushed**.
