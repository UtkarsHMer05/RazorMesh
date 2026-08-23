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
**Active phase:** Phase 1 — Local Trust Core  
**Current milestone:** M33 — Dev Signing Key Management (next)  
**Milestones passed:** M01–M32  
**Last updated:** 2026-08-24
**Gate:** ruff clean, mypy 34 files clean, pytest 127/127

---

# Environment facts (verified M01/M02)

- macOS 26.5, arm64, Apple M2, 8 GB RAM, 168 GiB free disk.
- Node v22.23.2 LTS installed + default via nvm (v20 EOL). npm 10.9.8, pnpm 10.18.2.
- uv 0.12.5 installed (~/.local/bin/uv). Python 3.13 line will be uv-managed (3.13.15 current).
- Docker 29.7.2 + Compose v5.4.0; daemon launched on demand at M09 (approved).
- User's own non-Docker PostgreSQL occupies 127.0.0.1:5432 — DO NOT TOUCH. Our Docker PG binds 127.0.0.1:15432.
- Infra live: razormesh-postgres (18.6-alpine @127.0.0.1:15432, vol pgdata, PG18 mounts /var/lib/postgresql) + razormesh-redis (8.8.2-alpine @127.0.0.1:16379, no persistence by design — coordination only).
- Ports 3000/8000 free. All host bindings loopback-only.
- Repo: governance pack only; git init happens at M06 with .gitignore in place.

# Version decisions (M02, full detail in VERSION_MANIFEST.md)

- fastapi 0.141.1 / pydantic 2.13.4 / sqlalchemy 2.0.52 / alembic 1.19.1 / psycopg[binary] 3.3.4
- redis-py 8.1.0 / cryptography 50.0.0 (Ed25519) / rfc8785 0.1.4 (JCS) / httpx 0.28.1
- pytest 9.1.1 + asyncio 1.4.0 + hypothesis 6.165.10 + ruff 0.16.4 + mypy 2.3.1
- next 16.3.2 / react 19.2.8 / typescript 5.9.3 (NOT 7.0 — maturity) / eslint 10.9.0
- vitest 4.1.11 + RTL 16.3.2 + jsdom 30.0.1 + @playwright/test 1.62.1
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
- DB: 9 tables, alembic upgrade/downgrade, audit trigger blocks mutation (M20)
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

---

# Active blockers

None recorded.

---

# Human-owned inputs

- No external API keys should be needed in Phase 1.
- Git push/remote changes require explicit human authorization.

---

# Active decisions

See `DECISIONS.md`, currently D-001 through D-020.

---

# Known technical debt

None yet; do not invent.

---

# Next action

M33 — Dev Signing Keys: local Ed25519 keygen, gitignored private keys.

---

# Resume protocol

On resume:

1. read `AGENTS.md`;
2. read current source-of-truth docs;
3. inspect `PHASE1_STATUS.md`;
4. verify the latest PASS gate if any;
5. continue the first NOT_STARTED/BLOCKED milestone only after understanding the blocker.
