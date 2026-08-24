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
**Active phase:** Phase 2 — Razorpay Test Mode Integration (ACTIVE since P2-M05)  
**Current milestone:** P2-M40 — NOT_STARTED (HUMAN GATE: real Test Mode FAILURE checkout)  
**Phase-2 milestones passed:** P2-M01..P2-M39  
**Last updated:** 2026-08-25  
**Gate:** M40 needs ONE human failure checkout at http://localhost:3000/buyer — failure@razorpay UPI or sub-4-digit OTP (R-017). Expected: no fulfilment, attempt FAILED, reservation RELEASED (reserved=0, committed unchanged), PAYMENT_FAILED audited, payment.failed webhook verified=true PROCESSED. Agent captures evidence BEFORE any pytest run (belt and braces; suite is isolated from dev DB since M38/D-033). M38 closed on payment #3 (order_TTiVopXKuCg5ol / pay_TTiY0Ny3rAEN9H, 479900 INR): ALLOW→ticket→order→payment.failed(release)→late-capture reconcile→SUCCEEDED/ELIGIBLE; spend v4 ensure→reserve→release→commit exactly once; 4 REAL signed webhooks verified=true (7 real rows total); provider_name=razorpay; audit chain valid (7 events); provider-side fetch paid/captured/failed all match; commit performed by the live FIXED webhook path (no repair script). Also live-proven: P2-S16 guarded FAILED→SUCCEEDED reconciliation; authorized-in-FAILED semantics defect found→fixed→tested (D-034). Evidence: docs/PHASE2_M38_EVIDENCE.md + docs/PHASE2_M39_EVIDENCE_RECONCILIATION.md. Suite 330/330; dev DB business rows survive test runs (isolation guard autouse).

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
- Phase 1 uses a mock provider only.

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

See `DECISIONS.md`, currently D-001 through D-034 (D-032: M36 signed-webhook
proof deferred to M38 — satisfied by 7 real deliveries; D-033: M38
spend-commit defect remediation + hard test/dev DB separation +
UNMATCHED_CONTEXT classification; D-034: payment.authorized informative-only
in every attempt state).

---

# Known technical debt

- ESLint 9.39.5 is EOL but retained as a dev-only compatibility exception because the current Next 16.3.2 plugin stack crashes under ESLint 10.9.0. Re-test when upstream peers add v10 support.
- Benchmark safe controls are synthetic fixture twins; metrics must never be generalized beyond the recorded suite.

---

# Next action

M40 (HUMAN GATE — Real Test Failure): (1) human performs ONE failure
checkout at http://localhost:3000/buyer — failure@razorpay UPI or any card
with an OTP of fewer than 4 digits (R-017). (2) Agent CAPTURES EVIDENCE
FIRST (attempt/spend/audit/provider_events queries) BEFORE any pytest run.
(3) Require: attempt FAILED (NOT_ELIGIBLE), reservation RELEASED
(reserved=0, committed unchanged), PAYMENT_FAILED audited, payment.failed
webhook verified=true PROCESSED, provider-side fetch shows the failed
payment; no fulfilment anywhere. Then M40 PASS → M41 (provider-unknown /
timeout reconciliation via local fault injection). Tunnel/share: if the zrok
share dies, re-run make phase2-up and UPDATE the Dashboard URL + .env
RAZORPAY_WEBHOOK_PUBLIC_URL (share is not reserved). Payment-#1 retry 403s
(old secret) may still tail off; zero-mutation by design.

---

# Resume protocol

On resume:

1. read `AGENTS.md`;
2. read current source-of-truth docs;
3. inspect `PHASE1_STATUS.md`;
4. verify the latest PASS gate if any;
5. continue the first NOT_STARTED/BLOCKED milestone only after understanding the blocker.
