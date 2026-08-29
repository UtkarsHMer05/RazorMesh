# AUTHORITATIVE STATUS (PVB020 + PRE-REVIEW FINAL CORRECTION)

# PRE_REVIEW_FINAL_CORRECTION_PASS / SAFE_TO_BEGIN_HUMAN_LABELING

**Recorded:** 2026-08-29 · This file is the SINGLE current handoff document. Older
handoff text in TRANSFORMATION_REPORT.md §"OVERNIGHT" is superseded history; the
workflow below is the only current one.

## What changed in the PRE-REVIEW FINAL CORRECTION (all enforced by tests)

- **V3 review pack rebuilt** (`data/agentpay_ir_v2/review/REVIEW_PACK_V3.jsonl`,
  sha256 `c88b7817…`): **635 cards**, **zero duplicate normalized pairs**, **zero
  duplicate underlying record_ids**, new card-id namespace `rc2_*`. The V2 pack and
  its label-bearing linkage/role manifest are REMOVED from tracking (git history
  retains only the label-free card file).
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
- No training, no evaluation of frozen test/gold/OOD with any model happened in
  this correction. Nothing has been pushed.
