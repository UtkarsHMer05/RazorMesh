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
**Active phase:** Phase 3 ACTIVE (human-approved 2026-08-25; M01 PASS)
**Current milestone:** P2 complete (50/50 + D-037 final audit); P3-M01 PASS
**Phase-2 milestones passed:** P2-M01..P2-M50 (all 50)
**Last updated:** 2026-08-25
**Gate:** Independent master-prompt audit (2026-08-25) found and repaired gaps hidden by the prior green suite: provider create/fetch authority validation; exact callback attempt and cross-principal-session binding; current authorization/checkout revalidation at captured settlement; webhook amount/currency correlation; conservative failed-payment reservation hold preventing late-capture overspend; and strict `rzp_test_`/official-endpoint configuration. Final battery: Ruff + mypy clean; pytest 375/375; frontend lint/tsc, Vitest 11/11, build, Playwright 5/5; security-check zero findings; benchmark 20 pairs F1=1.0; migration down/up; live mock acceptance 10/10 with Security Lab 22/22; current Test auth diagnostic; trusted Test order create/fetch exact match, no checkout/payment. D-037 + PHASE2_STATUS final addendum are authoritative. Changes remain uncommitted; no push. Phase 3 still requires explicit human approval.

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

None recorded.

---

# Human-owned inputs

- No external API keys should be needed in Phase 1.
- Git push/remote changes require explicit human authorization.

---

# Active decisions

See `DECISIONS.md`, currently D-001 through D-037 (D-032: M36 signed-webhook
proof deferred to M38 — satisfied by 7 real deliveries; D-033: M38
spend-commit defect remediation + hard test/dev DB separation +
UNMATCHED_CONTEXT classification; D-034: payment.authorized informative-only
in every attempt state; D-035: UI re-syncs payment truth via read-only
GET /buyer/status — browser is never a source of payment truth).
D-037 supersedes release-on-provider-failure: provider failure retains the
reservation until verified late capture or explicit terminal resolution, and
all callback/provider evidence is correlated to current durable authority.

---

# Known technical debt

- ESLint 9.39.5 is EOL but retained as a dev-only compatibility exception because the current Next 16.3.2 plugin stack crashes under ESLint 10.9.0. Re-test when upstream peers add v10 support.
- Benchmark safe controls are synthetic fixture twins; metrics must never be generalized beyond the recorded suite.
- Failed Razorpay payments conservatively retain reservation capacity while a late capture remains possible; Phase 2 has no automated terminal-release workflow because elapsed time alone is not provider truth.

---

# Next action

PHASE 3 RUNNING — next milestone: **P3-M09** (TokenRouter client abstraction: backend-only
httpx client, typed errors, timeout, DI seam, fixtures; NO authority yet).
P3-M08 done: governance fully extended (PRD §12, SECURITY §16 P3-S01..S20,
TESTING §15, D-038/D-039/D-040, ARCHITECTURE §15, PHASE3_MILESTONES.md). P3-M07 done: credentials merged into .env
(names-only output), Phase-1/2 vars preserved, .env.example placeholders
added; PRIVATE FILE STILL EXISTS until M10 probe success. P3-M06 done: R-019..R-021 recorded — TokenRouter docs base
URL is .io not .com (probe decides at M10); DeBERTa label maps DIVERGE
(A:[E,N,C] vs B:[C,E,N]) and must be pinned+tested; datasets >=5.0.1 floor
from PYSEC-2026-3716. P3-M05 done:
baseline frozen at d457661 in docs/PHASE3_BASELINE.md.
P3-M04 done: phase-2 integrity re-proven (focused suites 67, live-key
rejection runtime-proven, dev audit chain valid=True, read-only diagnostic OK,
no new payments). P3-M03 done: frontend battery
green — lint/tsc/vitest 11/build/Playwright 5; zero secret refs in src/e2e/.next. P3-M02 done: battery
green (375 stable); FIXED latent strict-mypy violation in D-037 settlement-
authority validator (stale .mypy_cache had masked it — always purge caches
when counts diverge between roots); race test made load-robust WITHOUT
weakening exactly-once (CoordinationUnavailable = inconclusive no-effect;
idempotent-reentry rows may be many but must share ONE attempt identity).
P3-M01 evidence: master prompt read fully; governance read in precedence;
bootstrap file untracked + excluded via .git/info/exclude:49 with ZERO history
entries and values still UNREAD (merge at M07, probe+delete after M10);
backend regression 375/375.

Standing notes: `make test-db` must re-provision
razormesh_test after any `docker compose down -v` (migrate alone does NOT
create it). If the zrok share dies, re-run `make phase2-up` and UPDATE the
Dashboard webhook URL + `.env` RAZORPAY_WEBHOOK_PUBLIC_URL (share is not
reserved); stale-secret retry 403s are zero-mutation by design. Known UI
debt: page reload resets buyer component state — no cross-session attempt
redisplay yet. Per-milestone detail (M41–M50) lives in PHASE2_STATUS.md.

---

# Resume protocol

On resume:

1. read `AGENTS.md`;
2. read current source-of-truth docs;
3. inspect `PHASE1_STATUS.md`;
4. verify the latest PASS gate if any;
5. continue the first NOT_STARTED/BLOCKED milestone only after understanding the blocker.
