# RazorMesh Trust — Phase 3 Completion Report (AI/ML Trust Layer)

Status: **ALL AUTOMATABLE SCOPE COMPLETE — 2 HUMAN GATES PENDING**
(P26 gold review, M34 Colab training). Phase-4 approval required after.

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

### Semantic layer (DeBERTa NLI, provisional baseline B)
- AgentPay-IR v0.1 records with provenance + content-hash integrity.
- Data: seed 915 template-truth + adversarial 38 hard cases + Qwen candidates
  (provisional labels only) → frozen_v1: **1021 records**, whole-group splits
  train/val/test = 723/171/127, leakage gate PASSED.
- Baselines on identical harness: A acc 0.474 val / B **0.637** val
  (test 0.606), contradiction recall **0.704** vs 0.389 →
  **D-044: baseline B selected** (PROVISIONAL_BASELINE).
- Thresholds calibrated on VAL ONLY: τ_block 0.36 / τ_entail 0.40 → BLOCK
  precision 0.927, recall 0.704, F2 0.739, false-blocks 2/171.
- Conservative fusion (D-039): exhaustive matrix + Hypothesis property prove
  semantics can ONLY tighten; verifier failure ⇒ CHALLENGE fail-closed.

### Audit & lab
- Ledger events INTENT_COMPILED/CONFIRMED/REJECTED/SUPERSEDED/COMPILE_FAILED +
  SEMANTIC_VERIFICATION_RUN + POLICY_FUSION_DECIDED — no text, no secrets.
- Security Lab: 5 semantic scenarios (injection/renewal/supremacy) all pass;
  wire-level isolation proofs for compile requests.

## Final numbers

| Gate | Result |
|---|---|
| pytest | **516 passed** |
| ruff / mypy strict | clean / 71 files both roots |
| frontend tsc/eslint/vitest/build | clean / clean / 12 / OK |
| Playwright | 5 passed |
| security-check | PASS (0 findings) |
| compiler eval (N=90 sample, D-041) | schema-validity 100%, case-pass 78.9%, zero invented money |
| fusion on frozen test | BLOCK P=0.936 R=0.674 F1=0.784, unsafe-allows=1 |
| local inference | CPU ≈50 ms/pair; MPS similar → Modal NOT_NEEDED |

## Honest limitations
- Absolute zero-shot scores are low by design (adversarial-flavored set);
  fine-tuned comparison awaits Colab artifact (M34→M36).
- All quality metrics are PENDING_GOLD_VALIDATION until the 320-case pack is
  human-reviewed (M26 pack ready).
- Full 307-case compiler eval continuation is a recorded pre-M48-obligation;
  sampled N=90 results are the current measured truth.
- Qwen candidate volume reduced per overnight policy; counts in manifests are
  actual, never padded.
- NLI-only paths can never create payment authority — structural, tested.

## Reproduction
```bash
docker compose down -v && docker compose up -d
make migrate && make seed && make test-db
cd services/api && uv run pytest          # 516 passed
uv run --project services/api python scripts/rzp_build_seed_dataset.py
uv run --project services/api python scripts/rzp_build_adversarial.py
uv run --project services/api python scripts/rzp_freeze_dataset_v1.py
uv run --project services/api python scripts/rzp_build_gold_pack.py
services/ml-venv/bin/python scripts/rzp_eval_nli_baseline.py --model B --split test
```

## Commits
Phase-3 milestone commits are local-only (never pushed): ce55ba0 … HEAD
(see `git log --oneline | grep P3-`). Starting point fc0422e (Phase-2 close).
