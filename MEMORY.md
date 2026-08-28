# MEMORY.md — Compact Working Memory

## Purpose

This is a **rolling handoff file**, not a source of product requirements.

It exists so an AI coding agent can resume work without reconstructing the entire repository history.

It MUST stay compact, current and evidence-based.

It may never override `AGENTS.md`, `RULES.md`, `PRD.md`, `PHASES.md`, `SECURITY.md`, `ARCHITECTURE.md`, `DESIGN.md` or accepted decisions.

---

# Update policy

Update after every milestone.

Do not append forever.

Rewrite/compact stale operational details while preserving current facts.

Target: generally under 200 lines.

Never claim something passed unless `PHASE1_STATUS.md` contains the corresponding evidence.

---

# Current snapshot

**Project:** RazorMesh Trust
**Active phase:** Phase 4 ACTIVE (M01–M50 AUTONOMOUS PASS, awaiting human acceptance)
**Current milestone:** Phase-3 dataset + semantic-runtime correction COMPLETE (2026-08-28).
**Last updated:** 2026-08-28 (Phase-3 correction: frozen_v2 dataset, v2 checkpoint,
DeBERTa wired as the live runtime semantic verifier; backend 755 passed incl.
13/13 live-ingress E2E with the real model; ruff/mypy clean; frontend gates green).
**Gate (Phase 4 final M49, historical):** `services/api` ruff clean / mypy clean / pytest
718/718 PASS; `apps/web` typecheck 0 errors / lint 0 errors / vitest 76 PASS /
`next build` 6 static routes. AgentPay-X 191/191 with 100% safe-pass, 100%
attack-block, 0 false-allow, 0 false-block.
**Evidence pack (correction):** `docs/PHASE3_DATASET_AND_RUNTIME_FINAL_AUDIT.md`.
**Autonomous flag:** `AUTONOMOUS_50_OF_50_PASS / AWAITING_FINAL_HUMAN_ACCEPTANCE`.

Phase-3 correction essentials (D-053):
- frozen_v2 AgentPay-IR v0.2 = canonical orientation (premise=evidence,
  hypothesis=authorization), 648/143/126 splits + untouched OOD 129, leakage
  gate PASS, 35/35 families.
- Runtime artifact `artifacts/models/incoming/phase3-finetuned-v2`
  (sha256 163864e0…, base cross-encoder/nli-deberta-v3-base, label map
  0=contradiction/1=entailment/2=neutral), policy `semantic-thresholds-v3`
  (tau_block=0.05, tau_entail=0.9; calibrated on frozen_v2 val ONLY).
- `SEMANTIC_VERIFIER_BACKEND=deberta` is the production/default backend;
  torch 2.13.0 + transformers 5.15.1 live in the OPTIONAL uv group
  `semantic`; no-torch envs fail CLOSED to CHALLENGE (never keyword fallback).
  Per-process singleton load + manifest-hash enforcement; keyword verifier is
  only the labeled `deterministic_test_stub`.
- `make test-backend` / `make dev-api` / `make setup` use `--group semantic`.
- Orientation diagnostic (RETRAIN_REQUIRED=YES) and v1-vs-v2 revalidation
  numbers live in docs/PHASE3_ORIENTATION_DIAGNOSTIC.md and
  docs/PHASE3_MODEL_REVALIDATION.md; perf in docs/PHASE3_RUNTIME_PERFORMANCE.md
  (cold 0.61s, p50 51.9ms, p95 65.1ms, RSS 792MiB).

Historical Phase-3 re-audit facts (2026-08-27) are preserved above and
remain valid — they describe the prior Phase-3 state and are not
overwritten by Phase-4 completion.

---

# Environment facts (verified M01/M02)

- macOS 26.5, arm64, Apple M2, 8 GB RAM, 168 GiB free disk.
- Node v22.23.2 LTS installed + default via nvm (v20 EOL). npm 10.9.8, pnpm 10.18.2.
- uv 0.12.5 installed (~/.local/bin/uv). Python 3.13.15 is uv-managed and pinned in `services/api/.python-version`.
- Docker 29.7.2 + Compose v5.4.0; daemon launched on demand at M09 (approved).
- User's own non-Docker PostgreSQL occupies 127.0.0.1:5432 — DO NOT TOUCH. Our Docker PG binds 127.0.0.1:15432.
- Infra live: razormesh-postgres (18.6-alpine @127.0.0.1:15432, vol pgdata, PG18 mounts /var/lib/postgresql) + razormesh-redis (8.8.2-alpine @127.0.0.1:16379, no persistence by design — coordination only).
- Ports 3000/8000 free. All host bindings loopback-only.
- Repo: complete Phase-1 modular monolith on `main`; no push authorization.

# Version decisions (M02, full detail in VERSION_MANIFEST.md)

- fastapi 0.141.1 / pydantic 2.13.4 / sqlalchemy 2.0.52 / alembic 1.19.1 / psycopg[binary] 3.3.4
- redis-py 8.1.0 / cryptography 50.0.0 (Ed25519) / rfc8785 0.1.4 (JCS) / httpx 0.28.1 / httpx2 2.12.0
- pytest 9.1.1 + asyncio 1.4.0 + hypothesis 6.165.10 + ruff 0.16.4 + mypy 2.3.1
- next 16.3.2 / react 19.2.8 / typescript 5.9.3 / eslint 9.39.5 (dev-only compatibility exception)
- vitest 4.1.11 + RTL 16.3.2 + jsdom 26.1.0 compatibility pin + @playwright/test 1.62.1
- postgres:18.6-alpine, redis:8.8.2-alpine; Blade NOT selected (D-022) → fallback tokens

---

# Product in one sentence

RazorMesh Trust verifies that a proposed agentic-commerce transaction still matches the human's confirmed authorization before a trusted executor may perform a payment-like side effect.

---

# Core invariants to remember

- AI/buyer proposes; RazorGuard authorizes; trusted executor executes.
- No valid ticket → no provider execution.
- PostgreSQL durable authority; Redis coordination only.
- Money = integer minor units.
- ALLOW / CHALLENGE / BLOCK.
- Execution tickets are context-bound and single-use.
- Spend = authorized/reserved/committed.
- Unknown provider outcome is not blindly retried.
- Checkout is revalidated before execution.
- Audit is append-oriented and tamper-evident.
- Phase 1 uses a mock provider only; Phase 2 permits Razorpay Test Mode only.

---

# Proven state

- IDs: 12 typed ULIDs validated (M15)
- Money: minor-unit invariants, no float, Hypothesis properties (M16)
- Intent: frozen contract with generation/expiry/currency invariants (M17)
- Checkout: server recomputed totals, mixed-currency and tampering rejected (M18)
- Provenance: UNTRUSTED_CONTENT cannot satisfy authority gates (M19)
- DB: 9 tables, 3 Alembic revisions; execution-ticket uniqueness and spend-capacity constraints; latest downgrade/upgrade verified (M20 + final audit)
- DAL: repos + FOR UPDATE row lock, concurrency overspend guard (M21)
- Catalog: 5 merchants/50 products seeded idempotently+atomically; IDs must be ULIDs (M22)
- API: read-only /catalog endpoints, bounded pagination, typed-ID path params (M23)
- State machine: 7 statuses, exhaustive matrix tested, only AUTHORIZED executable (M24)
- Evidence ledger: JCS+SHA256 hash chain, advisory-lock appends, tamper detection (M25)
- Authz hashing: JCS canonical projections; untrusted text provably excluded (M26)
- Rule engine: PASS/FAIL/UNKNOWN rules + combinators; crash -> UNKNOWN fail-closed (M27)
- Money rules: 6 rules, inclusive boundaries, budget counts reserved+committed (M28)
- Catalog rules: allowlists + trusted ProductFacts; unknown fact -> UNKNOWN (M29)
- Policy rules: recurring/expiry hard fails; approval threshold -> APPROVAL_REQUIRED UNKNOWN (M30)
- SpendManager: atomic reserve/commit/release, row-locked, concurrency-proven (M31)
- Decision engine: state gate + FAIL->BLOCK + UNKNOWN->CHALLENGE else ALLOW (M32)
- Dev keys: Ed25519 at infra/keys/ (gitignored), ensure/load/sign/verify (M33)
- Tickets: signed JCS claims; verify sig->expiry->11 bindings fail-closed (M34)
- Nonce: Redis SET NX EX claim, 20-worker race proven 1 winner (M35)
- Executor: sole provider caller; verifies durable intent/checkout/current ALLOW before post-auth reservation; signed-ticket-derived idempotency; atomic settlement; unknown keeps reservation (M36 + D-027/D-028)
- Mock provider: 7 scripted modes incl. timeout-after-success + event replay (M37)
- Checkout service: server-authoritative item/tax/fee/shipping/currency/recurring projection; persisted constraints enforced; propose+authorize+ticket flow (M38)
- Revalidation: full intent constraints and checkout projection rebuild from DB at executor boundary; drift blocks, cosmetics don't (M39)
- Untrusted boundary: hostile text inert end-to-end; authority slots protected (M40)
- Semantic seam: Null + deterministic keyword verifier; UNDECIDED fail-closed (M41)
- Scenarios: 16 families schema-validated; expected labels isolated (M42 + final audit)
- Runner: all 16 isolated real-pipeline scenarios pass; no unrelated-data wipe (M43)
- Benchmark: 14 pairs TP14 FP0 TN14 FN0, unsafe-execution 0, synthetic GMV labelled (M44)
- Buyer API/UI: POST /buyer/* flow live-E2E verified; replay collapses idempotently (M45)
- Security Lab: /security-lab/run executes suite server-side with evidence tail (M46)
- Audit dashboard: timeline/verify/state plus non-mutating tamper simulation; event count/chain remain unchanged (M47 + D-029)
- Deep gate: 225 tests at 93.25% coverage, stateful/concurrency/security properties; security audits clean; frontend build/test/E2E green (M48 + final audit)
- Perf baseline: `docs/PHASE1_PERFORMANCE.json` regenerated on Python 3.13.15 and the 14-pair pipeline (M49)
- Acceptance: documented fresh-volume M50 run plus final live `scripts/acceptance.py` 10/10 PASS; security lab 16/16 and benchmark 14 pairs (M50 + final audit)

---

# Active blockers

Phase 4: none remaining. All M01–M50 gates green at the time of the final
M49 re-run; awaiting human acceptance per `docs/PHASE4_FINAL_COMPLETION_REPORT.md`.

Carried forward (out of Phase-4 scope, unchanged from prior audit):
- `services/api/scripts/*` and `services/api/training/phase3/*` ruff drifts.
- 4 pre-existing E2E failures in `e2e/gold-reviewer.spec.ts` (unchanged;
  2026-08-28 additionally repaired the stale checkout E2E locators for the
  auto-create fixture-intent UI: checkout.spec 3/3; the one-off
  `e2e/snapshot.spec.ts` capture utility (self-described, not a regression
  test) fails on mobile fullPage screenshot in this environment).
- Historical Phase-3 re-audit observations preserved above remain valid
  as prior-state evidence; they are not retroactively retracted by Phase 4.

Historical Phase-3 audit notes (kept intact per existing-file protection):
- Concurrent Phase-4 changes previously broke whole-worktree gates; resolved
  by ruff per-file-ignores for `protocol/*_proof.py`, `agentpay_x.py`,
  `untrusted_agent.py`, and `training/*`.
  - Confirmation discards merchant/semantic/product restrictions; confirmed AI
  authority is not connected to buyer checkout; browser IDs are invalid ULIDs
  (FIXED 2026-08-28: IntentDraftPanel now generates Crockford-base32 ULIDs via
  genUlid() instead of UUIDv4; product list dynamically filtered by confirmed
  draft's max_amount + product_summary constraints with budget-only fallback;
  e2e compile+confirm+checkout+pay verified with real TokenRouter API).
- Production checkout never ran the Phase-3 evidence/verifier/fusion stage
  in the prior state; M43 UI evidence was unreachable. (Phase 4 did not
  modify Phase-3 logic; this remains a prior-state observation.)
- 320 reviewed IDs = 241 train + 43 validation + 36 test. Validation
  influenced training selection/calibration; D-050's untouched-79 assertion
  is historically false. Independent human-reviewed evaluation remains a
  prerequisite for any final claim.
- M37 entailment calibration, M38 artifact/probability validation, M39
  invented condition, M45 real-pipeline/metric semantics and M46 ablations
  historically needed repair.
- Historical distributed training ZIPs disagree with repaired directory deps.

---

# Human-owned inputs

- No external API keys should be needed in Phase 1.
- Git push/remote changes require explicit human authorization.

---

# Active decisions

See `DECISIONS.md`. D-046 cited the examined 79-card subset during selection;
D-050's later claim that this subset was untouched by selection/calibration is
unsupported. D-051's full-307 coverage is real, but its unconditional M48/M50
closure and perfect numeric-precision claim are not established. Audit evidence
supersedes those current-acceptance claims; historical entries remain intact.
Duplicate D-047/D-048 IDs exist for later UI/Phase-4 entries; identify entries
by title as well as ID until the governance collision is separately reconciled.

---

# Known technical debt

- ESLint 9.39.5 is EOL but retained as a dev-only compatibility exception because the current Next 16.3.2 plugin stack crashes under ESLint 10.9.0. Re-test when upstream peers add v10 support.
- Benchmark safe controls are synthetic fixture twins; metrics must never be generalized beyond the recorded suite.
- Failed Razorpay payments conservatively retain reservation capacity while a late capture remains possible; Phase 2 has no automated terminal-release workflow because elapsed time alone is not provider truth.

---

# Next action

Phase-3 correction is COMPLETE and fully gated (2026-08-28). Wait for human
acceptance of Phase 4; the acceptance run will execute the real DeBERTa
semantic stage and record `semantic_backend`/model hash/probabilities. After
acceptance, the next lawful action is to push the existing local milestone
commit(s) (weights stay git-ignored; docs/PHASE3_MODEL_SETUP.md documents the
artifact).

Historical Phase-3 re-audit queue remains preserved above as
prior-state evidence; it is not the current active queue.

Standing notes: `make test-db` must re-provision razormesh_test after
any `docker compose down -v` (migrate alone does NOT create it). The
fine-tuned model lives at `artifacts/models/incoming/phase3-finetuned/`
(zip sha256 54d0fa01…f1e24). Eval scripts: `rzp_eval_finetuned.py`
(M36), `rzp_calibrate_thresholds_finetuned.py` (M37),
`rzp_run_e2e_benchmark.py` (M45 — already swapped to the artifact).
Verifier at `services/api/src/razormesh_api/semantic_verifier.py` —
label_map read from `model_dir/label_map.json` (or policy manifest
fallback, or legacy C/E/N fallback). Policy manifest
`data/phase3/policy/semantic_thresholds.json` is v2 with
gold_validation_status=GOLD_VALIDATED (historical value; validity disputed by
this audit, not a current acceptance assertion).

---

# Resume protocol

On resume:

1. read `AGENTS.md`;
2. read current source-of-truth docs;
3. inspect `PHASE1_STATUS.md`;
4. verify the latest PASS gate if any;
5. continue the first NOT_STARTED/BLOCKED milestone only after understanding the blocker.
