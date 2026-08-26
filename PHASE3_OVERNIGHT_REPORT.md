# PHASE3_OVERNIGHT_REPORT — read me first

Starting commit: `4f7c05c` (P3-M26 PASS in last turn) · Ending commit: see
`git log --oneline -1` after this turn's commits. Nothing pushed. Working
tree clean at the next commit.

## Milestone outcomes (final)

| M | Status | Note |
|---|---|---|
| M01–M15 | PASS | verified/committed earlier this phase (see PHASE3_STATUS) |
| M16 | PASS | confirmation flow + 17 tests + hardening (identity-map lock fix, unique-index exactly-once) |
| M17 | PASS | drafts API + IntentDraftPanel UI; harness clock fix (FRESH_NOW) |
| M18 | PASS | AgentPay-IR v0.1 schema |
| M19 | PASS | seed dataset 915 records, deterministic |
| M20 | PASS* | generator robust+running; candidates: see manifest (volume reduced per your policy; resumable to target) |
| M21 | PASS | candidate validation gates |
| M22 | PASS | exact+near dedup |
| M23 | PASS | group splits + leakage gate |
| M24 | PASS | adversarial expansion 38 hard records (quality-over-quota) |
| M25 | PASS | gold pack 320 ready |
| M26 | **PASS** (HUMAN GATE 1) | 320/320 human-reviewed, 0 invalid exclusions, GOLD_VALIDATED |
| M27 | PASS | frozen_v1: 1021 records, leakage-free |
| M28/M29 | PASS | baseline A/B evals (B wins) |
| M30 | PASS | D-044 select B (PROVISIONAL_BASELINE) |
| M31–M33 | PASS | training bundle + Colab notebook + preflight zip |
| M34 | **PASS** (HUMAN GATE 2) | 3-epoch T4 run; `phase3-finetuned.zip` returned; eval_macro_f1=0.9826 |
| M35 | PASS | `rzp_verify_training.py artifact` PASS on the real artifact |
| M36 | **PASS** | fine-tuned vs baseline B; **D-046** selects fine-tuned as production; baseline B retained as fallback |
| M37 | PASS (RE-FROZEN v2) | τ_block=0.30, τ_entail=0.40, F2=0.978, status GOLD_VALIDATED |
| M38 | PASS | DebertaNLISemanticVerifier, label_map read from artifact (data-driven) |
| M39 | PASS | SemanticEvidenceBuilder (authority-only hypotheses) |
| M40 | PASS | fusion matrix + property test (RELEASE-BLOCKING) |
| M41 | PASS | semantic lab scenarios |
| M42 | PASS | wire-level isolation proofs |
| M43 | PASS | UI verdict rendering |
| M44 | PASS | AI audit events in hash chain |
| M45–M47 | PASS | e2e benchmark re-run with fine-tuned verifier; ablation unchanged; Modal NOT_NEEDED |
| M48 | PASS | full battery green (522 tests after M35–M38) |
| M49 | PASS | clean-room acceptance: docker down -v, migrate to e7a1c4f9b2d5, test-db provisioned, **522/522** on clean room |
| M50 | PASS (report) | completion report finalized; **STOP for Phase-4 approval** |

## TokenRouter reality (honest)
- attempts/succeeded/failed counts live in
  `data/phase3/dataset/candidates/last_run.json` +
  `/tmp/rzm_gen.log`; dead windows caused multiple clean exits (by design).
- rejected_invalid and duplicates recorded per run in the same files.

## Dataset actuals
- frozen_v1 total 1021 (train 723 / val 171 / test 127); labels balanced;
  leakage PASSED.

## Headline numbers (every cell → a committed artifact)
- Fine-tuned NLI val (171): acc **0.982** / macroF1 **0.983**
- Fine-tuned NLI test (127): acc **0.984** / macroF1 **0.984**
- Fine-tuned NLI human_gold_heldout (79): acc **0.937** / macroF1 **0.938**
- Human contradiction recall (heldout 31): baseline B **0.645** → fine-tuned **1.000**
- Unsafe entail on human contradictions: baseline B **8/31** (heldout) / **29/119** (all) → fine-tuned **0 / 0**
- Thresholds (semantic-thresholds-v2): τ_block=**0.30**, τ_entail=**0.40**, F2 **0.978**, false-block rate **0.033**
- E2E fusion on test (127): block P=**0.977** R=**1.000** F1=**0.989**, 1 conservative unsafe-allow
- Local inference: CPU **69.8 ms/pair**, MPS 16.99s → Modal **NOT_NEEDED**
- Full backend test battery: **522 passed** (clean-room)
- ruff / mypy strict: clean / 71 files both roots
- frontend tsc/eslint/vitest/build/Playwright: clean / clean / 12 / OK / 5
- security-check: PASS (0 findings)

## YOUR MORNING ACTIONS
- **Phase-4 approval** is the only remaining human gate. No further
  milestone work will be started autonomously.
- Review `docs/PHASE3_COMPLETION_REPORT.md` and the new artifacts:
  `docs/PHASE3_NLI_FINETUNED_METRICS.json`,
  `docs/PHASE3_NLI_FINETUNE_EVAL.md`,
  `docs/PHASE3_END_TO_END_BENCHMARK.{json,md}` (all re-generated
  with the fine-tuned verifier this turn).
- Optional: review `DECISIONS.md` D-046 (fine-tuned model selection).

## Reruns required after Phase-4 approval (NOT for this turn)
- Full-307 compiler eval (D-041 carry-forward)
- Any threshold recalibration if heldout false-block rate shifts on
  future human-gold data

## Known limitations
- Heldout false-block rate (4/26=0.154) is above the 0.05 calibration
  cap; recorded transparently. These are conservative refusals, not
  unsafe allows. The 0.05 cap is the CALIBRATION constraint (satisfied
  on val); the heldout is reported for transparency.
- Compiler eval sampled N=90/307 (D-041). Full-307 is a recorded
  pre-M48 obligation that the human owner chose to defer.
- NLI-only paths never create payment authority — structural
  guarantee, tested in M41 + M42.
- Phase 3 is a local prototype. Never mark production-ready.

No results were fabricated. Every number above traces to a committed artifact.
