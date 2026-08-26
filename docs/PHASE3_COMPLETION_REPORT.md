# RazorMesh Trust — Phase 3 Completion Report (AI/ML Trust Layer)

Status: **ALL AUTOMATABLE SCOPE COMPLETE — PHASE-4 APPROVAL PENDING (HUMAN GATE)**
(per master prompt §15: after M50 the only remaining human gate is Phase-4 approval).

## What was built

### Intent Compiler path (Qwen via TokenRouter)
- Backend-only client (`intent_compiler.py`): OpenAI-compatible transport,
  typed error taxonomy (AUTH/REJECTED/UNKNOWN), no-retry discipline,
  request-id correlation, SecretStr credentials (P3-S01).
- Versioned+hashed prompt v2 (`intent_compiler_prompt.py`, D-038): compact
  schema-forward rules — never invent, hard-vs-semantic split, ambiguities
  surfaced, minor-unit money, negation preserved, human text is sole source.
- `IntentCompilationService`: strict extraction → Pydantic validation →
  exactly ONE bounded repair → fail-closed outcomes.
- REAL probe evidence: auth OK on api.tokenrouter.com; planner model visible;
  thinking-model behavior captured; JSON-by-instruction AND
  response_format=json_object both produce parseable output.

### Human confirmation gate (the authority boundary)
- Durable draft states DRAFT/NEEDS_CLARIFICATION/CONFIRMED/REJECTED
  (migration e7a1c4f9b2d5); raw human text NEVER stored.
- Only confirm_draft creates/supersedes authorization generations; exactly-once
  arbitrated by unique index + true FOR UPDATE locking; same-nonce replay is
  idempotent; differing nonce → CONFIRMATION_REPLAY_MISMATCH; stale drafts
  refuse; new caps below committed spend refused.
- UI: NL input → structured proposal review → Confirm/Reject with honest
  states; semantic verdicts surfaced when present. Zero secrets client-side.

### Semantic layer (DeBERTa NLI — **FINE-TUNED as production, baseline B retained as fallback**)
- AgentPay-IR v0.1 records with provenance + content-hash integrity.
- Data: seed 915 template-truth + adversarial 38 hard cases + Qwen candidates
  (provisional labels only) → frozen_v1: **1021 records**, whole-group splits
  train/val/test = 723/171/127, leakage gate PASSED.
- Baselines on identical harness: A acc 0.474 val / B **0.637** val
  (test 0.606), contradiction recall **0.704** vs 0.389 →
  **D-044: baseline B selected** (PROVISIONAL_BASELINE).
- **M34**: human ran the canonical training notebook on T4 GPU for 3 epochs;
  artifact `phase3-finetuned.zip` (654 MB, sha256 `54d0fa01…f1e24`) returned
  with `eval_macro_f1=0.9826`, `eval_accuracy=0.9825`, base
  `cross-encoder/nli-deberta-v3-base` (Apache-2.0), label map
  `{0: contradiction, 1: entailment, 2: neutral}`.
- **M35**: artifact verified (`rzp_verify_training.py artifact` PASS).
- **M36**: fine-tuned vs baseline B apples-to-apples. Closed the M26 gap:
  on the 79-card human-gold heldout (cards in val/test, never seen in
  training), unsafe entailments on human contradictions went **8 → 0**;
  contradiction recall went **0.645 → 1.000**; accuracy 0.595 → 0.937.
  D-046 selects the fine-tuned model as production; baseline B retained
  as documented fallback for parity regression checks.
- **M37 (re-frozen v2)**: thresholds re-derived against fine-tuned
  softmax on val: τ_block=0.30, τ_entail=0.40 → contra recall 0.9815,
  block precision 0.9636, F2 0.9779, 2/61=0.033 false blocks on val
  entailment (within 0.05 cap). `gold_validation_status` flipped
  PENDING_GOLD_VALIDATION → **GOLD_VALIDATED**. Heldout validation:
  31/31 human contradictions correctly BLOCKED.
- **M38**: `DebertaNLISemanticVerifier` reads `label_map.json` from the
  artifact dir (or from the policy manifest, with legacy fallback) so
  the index→label projection is data-driven, never hard-coded.
- **M39/M40/M41/M42/M43/M44**: SemanticEvidenceBuilder (authority-only
  hypotheses), conservative fusion (D-039: semantics can only STRICTEN),
  security lab (5 scenarios incl. injection/renewal/supremacy), wire-
  level isolation tests, UI semantic verdict integration, audit events
  (SEMANTIC_VERIFICATION_RUN + POLICY_FUSION_DECIDED) with NO text or
  secrets persisted.
- **M45/M46/M47**: e2e benchmark re-run with fine-tuned verifier →
  block P=0.977 R=1.000 F1=0.989; ablation rules-only/never-fires/full-
  fusion unchanged (fusion is a property of the policy, not the model);
  CPU 69.8 ms/pair, MPS 16.99s → Modal **NOT_NEEDED**.

## Final numbers (every cell → a committed artifact)

| Gate | Result | Source |
|---|---|---|
| pytest | **522 passed** | clean-room run after M35–M38 |
| ruff / mypy strict | clean / 71 files both roots | `uv run --project services/api ruff check` + `mypy -p razormesh_api` |
| frontend tsc/eslint/vitest/build | clean / clean / 12 / OK | `apps/web` battery |
| Playwright | 5 passed | `npx playwright test` |
| security-check | PASS (0 findings) | `make security-check` |
| compiler eval (N=90 sample, D-041) | schema-validity 100%, case-pass 78.9%, zero invented money | `docs/PHASE3_INTENT_COMPILER_EVAL.md` |
| fine-tuned NLI val 171 | acc 0.982, macroF1 0.983 | `docs/PHASE3_NLI_FINETUNED_METRICS.json` |
| fine-tuned NLI test 127 | acc 0.984, macroF1 0.984 | `docs/PHASE3_NLI_FINETUNED_METRICS.json` |
| fine-tuned NLI human_gold_heldout 79 | acc 0.937, macroF1 0.938 | `docs/PHASE3_NLI_FINETUNED_METRICS.json` |
| human contradiction recall (heldout 31) | 0.645 (B) → **1.000 (FT)** | `docs/PHASE3_NLI_FINETUNE_EVAL.md` |
| unsafe entail on human contradictions | 8 (B heldout) / 29 (B all) → **0 / 0 (FT)** | `docs/PHASE3_NLI_FINETUNE_EVAL.md` |
| fusion on frozen test (e2e) | BLOCK P=0.977 R=1.000 F1=0.989, 1 conservative unsafe-allow | `docs/PHASE3_END_TO_END_BENCHMARK.json` |
| local inference | CPU 69.8 ms/pair; MPS 16.99s → Modal NOT_NEEDED | `docs/PHASE3_END_TO_END_BENCHMARK.json` |
| thresholds (semantic-thresholds-v2) | τ_block=0.30, τ_entail=0.40, F2 0.978, false-block 0.033 | `data/phase3/policy/semantic_thresholds.json` |
| gold validation status | **GOLD_VALIDATED** (320/320 reviewed, 0 invalid exclusions) | `data/phase3/gold/manifest.json` + `gold_frozen.json` |

## Honest limitations
- Heldout false-block rate (4/26 = 0.154) is above the 0.05 calibration
  cap. This is a conservative refusal, not an unsafe allow (P3-S08).
  Recorded per P3-S20. The 0.05 cap is the CALIBRATION constraint
  (satisfied on val); the heldout is reported for transparency. If
  future human-gold data shifts this rate above the cap, a follow-up
  recalibration is the correct response.
- Compiler eval sampled N=90/307 (D-041). Full-307 is a recorded
  pre-M48 obligation that the human owner chose to defer.
- NLI-only paths can never create payment authority — structural,
  tested in M41 + M42.
- Phase 3 is a local prototype. Never mark production-ready.

## Reproduction
```bash
docker compose down -v && docker compose up -d
make migrate && make seed && make test-db
cd services/api && uv run pytest          # 522 passed
# Fine-tuned NLI eval (M36):
services/ml-venv/bin/python scripts/rzp_eval_finetuned.py --batch 16
# Threshold re-calibration (M37 v2):
services/ml-venv/bin/python scripts/rzp_calibrate_thresholds_finetuned.py
# E2E benchmark + ablation (M45/M46/M47):
services/ml-venv/bin/python scripts/rzp_run_e2e_benchmark.py
# Real-artifact smoke (M38):
services/ml-venv/bin/python -c "
import sys; sys.path.insert(0, 'services/api/src')
from pathlib import Path
from razormesh_api.semantic_verifier import DebertaNLISemanticVerifier
v = DebertaNLISemanticVerifier(
    model_dir=Path('artifacts/models/incoming/phase3-finetuned'),
    policy_path=Path('data/phase3/policy/semantic_thresholds.json'),
)
print(v.verify(premise='used', hypothesis='new').action)
"
```

## Commits
Phase-3 milestone commits are local-only (never pushed): ce55ba0 … HEAD
(see `git log --oneline | grep P3-`). Starting point fc0422e (Phase-2 close).

## STOP — Phase-4 approval required

Per master prompt §15, after M50 lands the only remaining gate is human
Phase-4 approval. No further milestone work will be started autonomously.
