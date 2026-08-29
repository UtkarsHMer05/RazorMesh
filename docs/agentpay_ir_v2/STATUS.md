# AUTHORITATIVE STATUS (PVB020 + PRE-REVIEW FINAL CORRECTION)

# PRE_REVIEW_FINAL_CORRECTION_PASS /
# SAFE_TO_BEGIN_HUMAN_LABELING_AND_COLAB_PIPELINE_VERIFIED (pre-label correction, 2026-08-30)

**Recorded:** 2026-08-29 · This file is the SINGLE current handoff document. Older
handoff text in TRANSFORMATION_REPORT.md §"OVERNIGHT" is superseded history; the
workflow below is the only current one.

## What changed in the PRE-REVIEW FINAL CORRECTION (all enforced by tests)

- **V3 review pack rebuilt** (`data/agentpay_ir_v2/review/REVIEW_PACK_V3.jsonl`,
  sha256 `c88b7817…`): **635 cards** across **21 observed strata**, **zero duplicate
  normalized pairs**, **zero duplicate underlying record_ids**, new card-id namespace
  `rc2_*`. The V2 pack and its label-bearing linkage/role manifest are REMOVED from
  tracking (git history retains only the label-free card file). The obsolete
  700-card artifacts (`corpus/review_candidates*.jsonl`, `corpus/review_role_manifest.json`)
  are likewise untracked. **Design note:** the `currency` and `delivery_constraint`
  families are intentionally held OUT of human-review/training and are represented
  only in the untouched OOD's withheld-family component — they were never strata in
  the V3 pack (21 observed, not 25).
- **Group-level roles, never card-random** (301 gold / 334 supervised across 319
  split groups): record_id, split_group, generator_parent_id, entity_family_id AND
  internal template families can never span GOLD and SUPERVISED (union-find over
  internal template families; contractnli/esci fixed-hypothesis exception disclosed
  in the freeze manifest). Group isolation outranked the exact 300 target (301).
- **Reviewer surface minimal**: reviewer JSON + UI expose ONLY card_id, premise,
  hypothesis. Tests catch label-bearing metadata (`*_contradiction`, `*_entailment`,
  `*_neutral`, stratum, source_class, …) at both vitest and Playwright level.
- **Private stays private**: linkage (`REVIEW_LINKAGE_V3.json`), roles
  (`REVIEW_ROLE_MANIFEST_V3.json`), `decisions_working.json`, `GOLD_FROZEN_V3.jsonl`
  and decision exports are gitignored; only hashes/counts/provenance are committed.
- **Canonical role-manifest hash**: sha256 over the assignments object ONLY, stored
  exclusively in `REVIEW_PACK_FREEZE_V3.json` (`37a59cf4…`); the role manifest never
  hashes itself; round-trip verify + tamper + self-hash rejection pinned by tests.
- **Finalizer upgraded** (`scripts/rzp_finalize_review_v2.py`): V3 targets, canonical
  hash verify, conflict rejection (same record/pair decided two ways), **group-level
  gold isolation** (every corpus row sharing a gold card's split_group is excluded;
  only the human-reviewed card itself becomes a gold row), gold rows carry the HUMAN
  label with `source_kind=human_reviewed` (never the source label; only a boolean
  agreement flag), `content_sha256` recomputed on every relabel and re-validated on
  EVERY final row, and the final bundle is built from `corpus/final` via an explicit
  `--corpus-dir` (final ZIP train/val hashes are proven equal to the final corpus
  files by tests). `--root` enables full dry runs in a temporary workspace.
- **Colab bundle + notebook fixed**: bundle builder accepts `--corpus-dir` /
  `--train/--val` / `--out-zip`; the archive is byte-deterministic (fixed member
  order/timestamps, sha256 `6292deb6…` for the PRE-REVIEW bundle); the notebook is
  generated OUTSIDE the zip with `EXPECTED_BUNDLE_SHA256` (the nonexistent
  `manifest['bundle_sha256']` design is gone) and still verifies every internal file
  from `bundle_manifest.json`; dependencies install from the bundle's
  `requirements-frozen.txt` (transformers 5.15.1 / torch 2.13.0 / accelerate 1.14.0 —
  ONE version source), no torch import before install, actual versions asserted
  before training. A no-training local preflight test executes the full verification
  logic against the generated ZIP.
- **Frozen selection rule preserved** (min unsafe C→E → max macro-F1 → max
  contradiction recall; neutral recall + safe false-block reported, never selection
  inputs) — unit-tested over fake candidate metrics, in the generator module AND in
  the notebook's embedded copy.
- **`semantic_model_path_v2` now actually honored**: `deberta_v2` resolves the
  configured path (Settings → orchestrator → runtime); temp-path tests prove the
  configured artifact is loaded and an absent configured path fails closed naming
  THAT path (no constant fallback).
- **PVB008 executed for real** (`docs/agentpay_ir_v2/PRE_V2_TEMPLATE_ROBUSTNESS.md`):
  10 families x 5 premise x 3 hypothesis hand-authored paraphrases run through the
  deployed PRE_V2 model (150 inferences). Findings: 8/10 families ≥0.87 action
  stability and full expected-action agreement; **prompt-injection premises PASS
  13/15 (unsafe)** — a recorded template-overfit/robustness defect the v2 training
  must repair; semantic_fees 0.87, seller_authorization 0.80 stability.
- **OOD expanded + refrozen BEFORE training** (`eval/fresh_ood_v2.jsonl`, 401 →
  **665 rows**, sha256 `8948a8e3…`): the real ContractNLI/ESCI entity-heldout
  component is kept; 264 untouched RazorMesh-security rows added
  (recurring/trial/membership/fee/seller/quantity/condition/prompt-injection/
  lookalike/negation; 136 contradictions = 53% of the expansion; fresh synthetic
  entities proven corpus-absent; all rows v2-normalized; idempotent self-healing
  refreeze pinned by tests).
- **Cross-split near-duplicate analysis** (`NEAR_DUP_CROSS_SPLIT_REPORT.md`):
  exact pair overlap = **0** in train↔val, train↔test, val↔test; near-dup (Jaccard
  ≥0.85 within shared template families) 389/414/44 pairs disclosed;
  same-hypothesis overlap (134–144 per direction) quantified and attributed to the
  ContractNLI fixed-hypothesis exception — human gold + OOD are the stronger
  generalization benchmarks.
- **/reviewer is local/dev-only**: every reviewer route returns 403 unless
  `RAZORMESH_REVIEWER_ENABLED=1`; a deployed application never exposes the pack.
- Agent-control documents (master prompts, paste-to-agent files, overnight
  ledgers, AI operating contracts) are untracked and gitignored; local copies kept.
- **Pre-label Colab-methodology corrections (2026-08-30):**
  (a) the notebook SAVES both candidate checkpoints with their exact validation
  metrics bound to them (`cand_2ep/`, `cand_3ep/` + validation_metrics.json), and
  packaging COPIES the frozen-rule-selected checkpoint to
  `agentpay-ir-v2-finetuned/` — never a third unevaluated retrain from base;
  model_manifest.json records `selected_checkpoint_source_dir`,
  `selected_candidate_metrics` (== the packaged checkpoint's own
  validation_metrics.json, asserted at run time) and `artifact_files_sha256` of
  those exact files;
  (b) the clean-environment install-order test executes the verify+install cells
  with the post-install import/version block cut entirely — pure stdlib, no
  dependency on accelerate/torch/transformers;
  (c) the 96-row injection-defense augmentation is integration-READY: the
  finalizer flag `--integrate-prompt-injection-augmentation` merges it into the
  FINAL TRAIN split only (never val/test/gold/OOD) and re-runs hash, leakage,
  provenance and synthetic-ratio gates (cap 10%, real share ~0.7%); the dry run
  exercises both the default (no integration) and flag-gated paths.
- **Pre-label correction (2026-08-30):** notebook now extracts the bundle BEFORE
  the pip-install step (fresh-runtime order fixed; exercised in a clean temp dir
  by a test); gold-adequacy guard stops the finalizer when the usable human-gold
  set falls below min(250, 85% of the frozen gold allocation) and warns below
  95%; obsolete 700-card artifacts (corpus/review_candidates*, review_role_manifest)
  untracked + ignored; a PREPARED-but-NOT-INTEGRATED prompt-injection augmentation
  staging set (96 rows, hash/group/text-disjoint from corpus, OOD, gold and the
  PVB008 grid; 0.69% of train vs the 10% cap) awaits an explicit integration
  decision — see INJECTION_DEFENSE_AUGMENTATION.md. V3 pack SHA, roles, card IDs
  and allocation are UNCHANGED.

- **Colab runtime-correctness fix (2026-08-30):** the generated FINAL packaging
  cell no longer contains doubled braces (it is inserted verbatim, so `{{...}}`
  would have executed as set-literals-of-dicts and crashed with
  `TypeError: unhashable type: 'dict'`). A new execution test runs the actual
  generated final cell against fake cand_2ep/cand_3ep checkpoints with mocked
  `colab_files.download` and proves: agentpay-ir-v2-finetuned/ is the EXACT
  selected candidate's files, valid training_metrics.json/model_manifest.json
  with correct provenance, valid artifact hashes, and the final ZIP — with no
  training. Package-version verification now gates on
  `importlib.metadata.version()` for every pinned distribution, while
  `torch.__version__` and the CUDA build are recorded as evidence.

## Fresh-clone reproduction (run BEFORE trusting the dry-run finalizer)

The private linkage/role files are gitignored; a fresh clone reproduces them
deterministically from the tracked corpus and verifies the frozen hashes:

```bash
# 1. regenerate in a temp dir and verify against the tracked frozen artifacts
#    (pack bytes, role-assignment sha, freeze manifest; writes NOTHING)
services/api/.venv/bin/python scripts/rzp_build_review_pack_v3.py --verify-only
# 2. write the private linkage/roles locally (pack/freeze bytes identical)
services/api/.venv/bin/python scripts/rzp_build_review_pack_v3.py
# 3. run the committed integrity gates (pack, roles, finalizer, bundle, notebook)
cd services/api && .venv/bin/python -m pytest tests/agentpay_v2/
# 4. full dry-run finalization (default AND opt-in augmentation paths)
cd .. && services/api/.venv/bin/python scripts/rzp_dryrun_finalize_review.py
```
`--verify-only` must print `VERIFY-ONLY PASS` (all four checks true) before any
finalization is trusted.

## THE one current handoff workflow (only these steps, in order)

1. **Human review** — open `http://localhost:3000/reviewer` with the dev server
   started with `RAZORMESH_REVIEWER_ENABLED=1` (already set in the local `.env`).
   Label ALL 635 cards (1=contradiction, 2=entailment, 3=neutral, 4=ambiguous/bad).
   Progress autosaves; roles are hidden; no suggestions are shown.
2. **Export** — click "Export decisions JSON" (`/api/reviewer/export`,
   deterministic, sorted by card_id).
3. **Finalize** — `services/api/.venv/bin/python scripts/rzp_finalize_review_v2.py
   --decisions <exported.json>` → validates, rejects conflicts, applies
   group-level gold isolation, integrates supervised labels, re-runs leakage gates,
   freezes `corpus/final/{train,val,test}.jsonl` + `GOLD_FROZEN_V3.jsonl`, and
   rebuilds the FINAL Colab bundle + notebook with the final archive hash.
4. **Colab** — upload `artifacts/agentpay_ir_v2_colab_training_bundle.zip` (the
   FINAL one produced by step 3) to `notebooks/RazorGuard_NLI_AgentPayIR_v2_Training.ipynb`,
   run top-to-bottom on T4/L4.
5. **Return** — place `agentpay-ir-v2-finetuned.zip` in `artifacts/models/incoming/`,
   then tell the agent "v2 artifact uploaded" → POST_COLAB_RESUME (validation-only
   calibration, one-shot test/gold/OOD eval, `deberta_v2` wiring, full regression).

## Still blocked / not started (carried, not hidden)

- OVN047/PVB017 pre-v2 payment completion: BLOCKED_EXTERNAL (Razorpay sandbox
  checkout blocks automation; failure paths + reconciliation proven).
- Full v2 fine-tuning: NOT started — begins only after human review + Colab run.
- No training, and no evaluation of frozen test/gold/OOD with any model, happened
  in this correction.
- **Remote state (recorded 2026-08-30, human-confirmed): GitHub `main` already
  contains the pre-review correction and privacy commits (through `cbcfab9` and
  the agent-control-untracking commit). This agent never pushes; remote syncing
  happens outside the agent. See docs/agentpay_ir_v2/REMOTE_STATE.md.**
