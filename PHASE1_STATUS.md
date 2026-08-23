# PHASE1_STATUS.md — Execution Evidence

## Status rules

- Valid states: `NOT_STARTED`, `IN_PROGRESS`, `PASS`, `BLOCKED`.
- A row may become PASS only after acceptance evidence is recorded.
- Detailed evidence for the current milestone goes below the table.

| # | Milestone | Status | Evidence summary |
|---:|---|---|---|
| M01 | Environment Discovery | PASS | Environment inspected read-only; findings recorded below; no user work modified |
| M02 | Live Version Intelligence | PASS | All runtimes/packages live-resolved; VERSION_MANIFEST filled; uv installed; Node 22.23.2 default |
| M03 | Project Charter | PASS | docs/PROJECT_CHARTER.md created; charter statements verified |
| M04 | Threat Model | PASS | docs/threat-model/PHASE1_THREAT_MODEL.md created; 24 threats mapped to invariants+milestones |
| M05 | Architecture Decisions | PASS | D-021..D-026 appended; all 10 master-prompt ADR topics now covered |
| M06 | Repository Scaffold | PASS | git init (main), layout per ARCHITECTURE §11, .gitignore/.editorconfig/.gitattributes/README; bootstrap commit e5e0446 |
| M07 | Secret Hygiene | PASS | .env.example placeholders only; ignores verified via check-ignore; secret scan clean |
| M08 | Root Development Commands | PASS | Makefile targets validated with make -n / make help; reset-local destructive-guarded |
| M09 | Local PostgreSQL | PASS | postgres:18.6-alpine healthy; volume persists across restart; 127.0.0.1:15432 only |
| M10 | Local Redis | PASS | redis:8.8.2-alpine healthy; SET/GET verified; 127.0.0.1:16379 only; coordination-only config |
| M11 | FastAPI Scaffold | PASS | /health vs /ready (DB/Redis fail-closed 503); OpenAPI generates; live smoke OK |
| M12 | Python Engineering Baseline | PASS | uv+lock py3.13; ruff strict-ish clean; mypy --strict clean; pytest 5/5; coverage configured |
| M13 | Next.js Scaffold | PASS | Next 16.3.2/React 19.2.8/TS 5.9.3; 5 routes; prod build OK; tsc clean |
| M14 | Frontend Test Baseline | PASS | Vitest+RTL smoke 3/3; Playwright chromium E2E 2/2; eslint 9.39.5 clean (v10 fallback documented) |
| M15 | Shared Identifier Types | PASS | 12 ID types ULID-validated, 8 tests PASS, cross-type equality impossible |
| M16 | Money Value Object | PASS | integer minor units, 14 Money tests + Hypothesis properties PASS, mypy strict clean |
| M17 | Intent Contract Model | PASS | IntentContract 7 tests PASS, frozen + generation/currency/expiry invariants, fixtures |
| M18 | Canonical Checkout Envelope | PASS | CheckoutEnvelope recomputation 7 tests PASS, client total manipulation rejected |
| M19 | Provenance Model | PASS | Provenanced trust classes 6 tests PASS, UNTRUSTED cannot occupy authority slots |
| M20 | Database Schema | PASS | 9 tables + alembic 1 revision, upgrade/downgrade verified, audit trigger blocks UPDATE/DELETE, 4 schema tests PASS |
| M21 | Repository/Data Access Layer | PASS | Repositories for all entities; transactional scope + FOR UPDATE row lock; rollback + 5-thread concurrency overspend test PASS |
| M22 | Merchant Catalog | PASS | 5 merchants / 50 synthetic products, price+seller+condition+recurring+shipping variations, idempotent atomic seed, live DB verified, 3 tests PASS |
| M23 | Catalog API | PASS | GET /catalog/merchants + /catalog/products (+/{id}) read-only; pagination bounds (1..100), filter validation, typed ProductId path param (422 malformed / 404 missing); 6 API tests PASS |
| M24 | Authorization State Machine | PASS | 7 statuses, exhaustive 7x7 transition matrix test (13 legal pairs, rest fail), terminal states have no exits, only AUTHORIZED executable; BLOCKED/CHALLENGED never execute; IntentStatus aligned |
| M25 | Evidence Ledger | PASS | JCS(RFC 8785)-canonicalized SHA-256 hash chain, genesis + link checks, advisory-lock serialized appends (5x10 concurrent = single linear chain), tampered payload/link detected; seq anchor migration round-trips |
| M26 | Canonical Authorization Hashing | PASS | JCS(RFC 8785) canonicalization with RFC known-answer vectors; documented checkout/intent projections; untrusted text + presentation drift provably excluded; relevant drift (price/qty/revision/recurring/generation) changes hash; 7 tests PASS |
| M27 | RazorGuard Rule Engine Foundation | PASS | StrEnum PASS/FAIL/UNKNOWN outcomes, FunctionRule + AllOf combinators, stable reason codes + explanations, crashing rules degrade to UNKNOWN (fail-closed), duplicate rule ids rejected, determinism test; 7 tests PASS |
| M28 | Money Rules | PASS | 6 deterministic rules: currency match, positive amount, max_total (inclusive boundary), aggregate budget incl. open reservations (exact-fit PASS / -1 minor FAIL), fee sanity (<= subtotal), shipping sanity (<=10x subtotal); 7 boundary tests PASS |
| M29 | Merchant/Product/Quantity Rules | PASS | Allowlists honor None=any/empty=nothing (SEC-018); category+brand rules use TRUSTED product facts; missing fact -> UNKNOWN (CATEGORY_UNKNOWN/BRAND_UNKNOWN), never silent PASS; brand allow_only/forbid modes case-insensitive; quantity per-line + aggregate; 7 tests PASS |
| M30 | Subscription/Expiry/Approval Rules | PASS | Recurring checkout requires explicit permission; expiry inclusive-dead (now==expires_at FAIL); approval threshold boundary: total==threshold PASS, +1 -> UNKNOWN APPROVAL_REQUIRED (deterministic challenge signal); 5 tests PASS |
| M31 | Stateful Spend Reservation and Aggregate Budget | PASS | SpendManager: reserve/commit/release under FOR UPDATE row lock; 10 threads x 150k vs 1M -> exactly 6 reserved, invariants hold; provider-unknown keeps reservation; Hypothesis random sequences (15 examples) preserve authorized>=reserved+committed |
| M32 | Decision Engine | PASS | Deterministic matrix: state gate (non-AUTHORIZED -> BLOCK incl. BLOCKED/CHALLENGED), FAIL->BLOCK, UNKNOWN->CHALLENGE, else ALLOW; policy_version pinned; 7 tests PASS incl. 6-status gate parametrization + determinism |
| M33 | Dev Signing Key Management | NOT_STARTED | — |
| M34 | Context-Bound Single-Use Execution Ticket | NOT_STARTED | — |
| M35 | Redis Nonce Claim and Concurrency | NOT_STARTED | — |
| M36 | Trusted Payment Executor + Durable ExecutionAttempt | NOT_STARTED | — |
| M37 | Mock Payment Provider | NOT_STARTED | — |
| M38 | Checkout Service | NOT_STARTED | — |
| M39 | Live Checkout Revalidation | NOT_STARTED | — |
| M40 | Untrusted Content Boundary | NOT_STARTED | — |
| M41 | Future SemanticVerifier Interface | NOT_STARTED | — |
| M42 | Attack Scenario Specification | NOT_STARTED | — |
| M43 | Adversarial Evaluation Runner | NOT_STARTED | — |
| M44 | Safe/Unsafe Paired Benchmark | NOT_STARTED | — |
| M45 | Buyer Experience UI | NOT_STARTED | — |
| M46 | Security Lab UI | NOT_STARTED | — |
| M47 | Audit Dashboard | NOT_STARTED | — |
| M48 | Deep Test and Security Gate | NOT_STARTED | — |
| M49 | Performance/Resource Baseline | NOT_STARTED | — |
| M50 | Clean-Room Phase-1 Acceptance | NOT_STARTED | — |

---

# Current milestone evidence

## M01 — Environment Discovery

Status: PASS

### Implemented
- Read-only inspection of OS, architecture, runtimes, container tooling, disk, ports and repository state. Nothing modified.

### Files changed
- `PHASE1_STATUS.md`, `MEMORY.md` (documentation only)

### Findings
```text
OS:               macOS 26.5 (Build 25F71)
Arch:             arm64 — Apple M2, 8 GB RAM
Disk free:        168 GiB of 460 GiB
Git:              2.49.0 — repo NOT initialized yet; contains 16 governance .md files only
Node:             v20.20.2 active via nvm; nvm also has v22.14.0 available locally
npm / pnpm:       10.8.2 / 10.18.2
Python:           3.12.8 CPython (/Library/Frameworks/Python.framework, official installer)
uv:               NOT INSTALLED (install approved by human); Homebrew 6.0.18 present as fallback
Docker:           29.7.2 + Compose v5.4.0 installed; daemon NOT running; Docker.app present
Ports:            5432 ALREADY OCCUPIED by user's own non-Docker PostgreSQL (PID 762) — do not touch;
                  plan: bind Docker PostgreSQL to 127.0.0.1:15432 instead
                  3000 / 8000 / 6379 currently free; all host bindings will be 127.0.0.1-only
Xcode CLT:        present
```

### Required tool actions identified
- Use nvm-provided Node v22 LTS line (latest 22.x patch verified in M02).
- Install uv via official standalone installer (human-approved).
- Launch Docker Desktop when M09 requires the daemon (human-approved).

### Validation commands
```bash
sw_vers && uname -m && df -h /System/Volumes/Data
git --version; node --version; npm --version; pnpm --version
python3 --version; uv --version; docker --version; docker compose version
lsof -nP -iTCP:5432 -sTCP:LISTEN   # pre-existing local postgres detected
```

### Results
- Environment fully understood; acceptance criteria met (environment understood, no user work overwritten, architecture identified from governance pack, required local tools identified).

### Security regression
- N/A (no code yet). Noted: existing local PostgreSQL on 5432 is user-owned and must remain untouched; all Phase-1 infra binds to loopback only.

### Decisions created/updated
- D-021 recorded at git init (M06) re: authorized per-milestone local commits.

### Known limitations
- 8 GB RAM machine: keep Docker resource usage modest; no heavy parallel containers beyond PG+Redis.
- Node v20 default is past EOL; switching to v22 line before scaffolding frontend.

### Next
M02 — Live Version Intelligence.

---

## M02 — Live Version Intelligence

Status: PASS

### Implemented
- Live-resolved runtimes from authoritative sources (nodejs.org dist index, python.org, postgresql.org, Docker Hub official tags) and package registries (npm view / PyPI metadata).
- Installed uv 0.12.5 via official installer; installed Node v22.23.2 via nvm and set as default.
- Filled `VERSION_MANIFEST.md`; added research entries R-004..R-009 to `RESEARCH.md`.

### Files changed
- `VERSION_MANIFEST.md`, `RESEARCH.md`, `PHASE1_STATUS.md`, `MEMORY.md`

### Validation commands
```bash
curl -s https://nodejs.org/dist/index.json   # 22.23.2 LTS security release confirmed
python3 -m pip index versions fastapi         # 0.141.1
npm view next version                          # 16.3.2
uv --version                                   # 0.12.5
nvm alias default 22.23.2 && node --version    # v22.23.2
```

### Results
- Node 22.23.2 LTS default; Python 3.13 line via uv; PG 18.6-alpine; Redis 8.8.2-alpine; all package selections recorded with sources/dates.

### Security regression
- N/A (no code). Advisory posture: Node 22.23.2 is a security release; PG 18.6 contains the 2026-08-13 quarterly security fixes; TS 7.0 native rewrite avoided for maturity (documented), not for a known CVE.

### Decisions created/updated
- TypeScript 5.9.3 over 7.0.2 and Blade-not-selected are recorded in VERSION_MANIFEST notes; formal ADRs D-021/D-022 land in M05/M06 when git init occurs.

### Known limitations
- Exact patch versions of transitive deps are pinned later via lockfiles (uv.lock / pnpm-lock.yaml) at scaffold time.

### Next
M03 — Project Charter.

---

## M03 — Project Charter — PASS
- Created `docs/PROJECT_CHARTER.md`: problem statement, Track-01 objective, Track-02-inspired verification methodology, Phase-1 objective, non-goals, trust boundaries, future phases, definition of done. Contains required statements ("not a generic chatbot checkout"; "core contribution is intent-to-execution integrity"). No code, no validation commands beyond review.

## M04 — Threat Model — PASS
- Created `docs/threat-model/PHASE1_THREAT_MODEL.md`: assets A1–A9, actors, entry points, boundaries, TH-01..TH-24 each mapped to ≥1 mitigation (SEC invariant + milestone), system failure modes (fail-closed DB/Redis/serialization/clock), explicit out-of-scope list. Covers all 12 mandated threats from the master prompt plus context theft/supersession/provider-unknown families.

## M05 — Architecture Decisions — PASS
- Verified D-001..D-020 cover: monolith (D-002), integer money (D-003), PostgreSQL authority (D-004), Redis coordination (D-005), deterministic authz (D-007), tickets (D-008/D-010), append-only evidence (D-016).
- Appended: D-021 git behavior (explicit per-milestone local commits, never push), D-022 Blade evaluated→fallback tokens, D-023 trusted/untrusted separation as hard boundary, D-024 model components via interfaces only, D-025 PaymentProvider isolation, D-026 single Next.js app.
- All 10 master-prompt ADR topics now have accepted decisions with rejected alternatives noted.

### Known limitations (M03–M05)
- Docs-only milestones; no executable validation yet. Documentation-vs-code consistency re-checked continuously from M06 onward.

## M22 — Merchant Catalog — PASS
- `catalog.py`: 5 synthetic merchants (audio/home/books/outdoor/gaming), 50 products (10 each) with price tiers, brands, conditions (new/refurbished/used), recurring flags (monthly), shipping rule (>=$2000 free else ₹499). IDs are generated ULIDs (`mrc_`/`prd_`).
- Seed is idempotent (presence check) and atomic (single `session_scope` transaction via `repos.transaction()`).
- Validation: ruff clean; mypy strict 21 files clean; pytest 60/60 (3 new catalog tests: seed+idempotency, variations, category/brand filtering); live DB seed run twice → 50 products/5 merchants, second call seeded 0.
- Note: merchant/product IDs must be valid Crockford-base32 ULIDs (M15 validation); slugs are descriptive only.

## M23 — Catalog API — PASS
- `api/routes/catalog.py`: read-only router `/catalog` wired into `main.py`.
  - `GET /catalog/merchants`, `GET /catalog/products` (filters: category, brand), `GET /catalog/products/{product_id}`.
  - Pagination bounded: `limit` 1..100 (default 20), `offset` >= 0; violations → 422. Page bodies include `total/limit/offset/items`.
  - Path param uses typed `ProductId` (pydantic core schema) → malformed IDs rejected 422 before touching DB; unknown valid ID → 404.
  - Repositories gained `count()` for merchants/products (pagination totals).
- Security regression: OpenAPI paths under `/catalog` expose GET only (test asserts no write methods).
- Validation: ruff clean; mypy strict 23 files clean; pytest 66/66; live smoke: seeded DB → products total 50, single product fetch 200, merchants total 5.
- Test isolation fixed: catalog test fixtures now wipe merchant/product tables before and after.

## M24 — Authorization State Machine — PASS
- `domain/state_machine.py`: `AuthorizationStatus` (DRAFT, AUTHORIZED, CHALLENGED, BLOCKED, SUPERSEDED, REVOKED, EXPIRED), explicit legal-transition map, `require_transition`, `assert_executable` (fail-closed), `is_terminal`.
- Semantics: BLOCKED is terminal (no revival; a new contract/generation is required); only successful human reauthorization returns CHALLENGED → AUTHORIZED; terminal states have no exits; execution permitted ONLY from AUTHORIZED.
- `IntentStatus` extended additively with BLOCKED/EXPIRED; alignment test pins both enums to identical value sets.
- Validation: ruff clean; mypy strict 24 files clean; pytest 73/73 (7 new: exhaustive 7×7 matrix — every non-legal pair raises IllegalTransitionError; executable guard over all statuses).

## M25 — Evidence Ledger — PASS
- `domain/evidence.py`: `compute_event_hash` = SHA-256 over RFC 8785 (JCS) canonical JSON of the logical record + `previous_event_hash`; `GENESIS_HASH` = 64 zeros; timestamps normalized to UTC ISO.
- `ledger.py`: `EvidenceLedger.append` serializes concurrent writers with `pg_advisory_xact_lock(727001)`, reads the true tip (`seq DESC`), inserts atomically via `session_scope` (commit-on-success); `uq_audit_current_hash` is a second race backstop. `verify()` re-walks the chain and recomputes every hash from stored fields; reports broken link vs altered-record reasons.
- Migration `c5f21a9d3e10`: adds `audit_events.seq` BIGINT (sequence-backed, unique) as physical ordering anchor; upgrade/downgrade verified live.
- Validation: ruff clean; mypy strict 26 files clean; pytest 77/77. Tests: genesis/link verification, tampered payload detected (bypassing trigger to simulate attacker), tampered link detected, 5 threads x 10 appends → 50 events, strictly increasing seq, chain verifies.
- Hardening: verify() on an empty ledger returns valid=True but tests assert exact `events_checked` so vacuous passes cannot mask regressions.

## M26 — Canonical Authorization Hashing — PASS
- `domain/authz_hash.py`: `jcs_bytes`/`jcs_sha256` (RFC 8785 via rfc8785 lib, schema-version domain-separated); `checkout_authorization_projection` (ids, revision, merchant, line items product/qty/price/condition, tax/shipping/fees/computed total, subscription recurring+frequency) and `intent_authorization_projection` (identity, generation, allowlists sorted, caps, thresholds, authorized_at/expires_at).
- Security properties tested: untrusted display-name text change → hash unchanged; observed_at drift → unchanged; subscription description → unchanged. Price/qty/revision/recurring changes and intent generation bump → hash changes.
- Known-answer vectors pin RFC 8785 behavior (key sorting, null, escaping) so a canonicalization regression cannot pass silently.
- Validation: ruff clean; mypy strict 27 files clean; pytest 84/84.

## M27 — RazorGuard Rule Engine Foundation — PASS
- `rules/engine.py`: `RuleOutcome` StrEnum (PASS/FAIL/UNKNOWN), frozen `RuleResult` (rule_id, outcome, reason_codes, explanation, details), `EvaluationContext` (intent + checkout + committed/reserved spend snapshot), `FunctionRule` adapter, `AllOf` combinator (first-FAIL aggregation with merged reason codes; UNKNOWN preserved), `RazorGuardEngine` pipeline preserving rule order.
- Fail-closed guarantees: crashing rules → UNKNOWN with RULE_ERROR (never PASS); UNKNOWN blocks overall pass; duplicate rule ids rejected at construction; invalid outcomes rejected in RuleResult.
- Determinism: same context → identical report (tested).
- Validation: ruff clean; mypy strict 29 files clean; pytest 91/91.

## M28 — Money Rules — PASS
- `rules/money_rules.py`: `MONEY_RULES` registry of 6 deterministic rules with stable reason codes: CURRENCY_MISMATCH, ZERO_AMOUNT, TOTAL_EXCEEDS_MAX, BUDGET_EXCEEDED (counts committed+reserved+proposed), FEES_EXCEED_SUBTOTAL, SHIPPING_EXCESSIVE (10x-subtotal ceiling; zero subtotal forbids shipping).
- Boundary semantics inclusive-on-allowed: total == max_total PASS / +1 FAIL; budget exact-fit PASS / -1 minor FAIL; fees == subtotal PASS / +1 FAIL; shipping == 10x subtotal PASS / +1 FAIL.
- Rules read only trusted context (intent + server-recomputed totals); untrusted text cannot influence outcomes.
- Validation: ruff clean; mypy strict 30 files clean; pytest 98/98.

## M29 — Merchant/Product/Quantity Rules — PASS
- `rules/catalog_rules.py`: `CATALOG_RULES` registry — merchant/product allowlists (None=any, empty=nothing, membership decides), category rule and brand restriction rule driven by TRUSTED `ProductFacts` resolved by the trusted system (new `EvaluationContext.product_facts`, default None), quantity rule enforcing per-line `max_quantity` plus aggregate unit cap.
- Unknown-data behavior: brand/category unavailable → UNKNOWN with BRAND_UNKNOWN / CATEGORY_UNKNOWN reason codes; never a silent PASS. Brand matching is case-insensitive; modes allow_only + forbid.
- Validation: ruff clean; mypy strict 31 files clean; pytest 105/105.

## M30 — Subscription/Expiry/Approval Rules — PASS
- `rules/policy_rules.py`: `POLICY_RULES` — recurring permission (recurring checkout + `recurring_allowed=False` → RECURRING_NOT_ALLOWED), expiry (`now >= expires_at` → AUTHORIZATION_EXPIRED, inclusive-dead boundary), approval threshold (total == threshold PASS; total > threshold → **UNKNOWN with APPROVAL_REQUIRED**, the deterministic CHALLENGE signal the M32 decision engine will treat as never-ALLOW).
- `EvaluationContext` gained optional `now_utc` (deterministic tests) with wall-clock fallback via `effective_now()`.
- Validation: ruff clean; mypy strict 32 files clean; pytest 110/110.

## M31 — Stateful Spend Reservation and Aggregate Budget — PASS
- `spend.py`: `SpendManager` over durable `authorization_spend` row: `ensure_authorization`, `reserve` (atomic hold; InsufficientCapacity on shortfall), `commit` (reserved→committed on verified success), `release` (definitive failure returns capacity), `snapshot`/`available`/`assert_invariants`. All mutations inside one transaction holding the FOR UPDATE row lock; version+updated_at bumped.
- Provider-unknown semantics: reservation is simply left held (no release, no commit) — tested explicitly.
- Concurrency proof: 10 threads × 150k vs 1M authority → exactly 6 reserved / 4 rejected, invariants intact afterwards.
- Hypothesis property test (15 examples): random reserve(/release) sequences keep reserved ≥ 0, committed = 0, reserved+committed ≤ authorized at every step.
- Validation: ruff clean; mypy strict 33 files clean; pytest 115/115.

## M32 — Decision Engine — PASS
- `decider.py`: `Decision` StrEnum (ALLOW/CHALLENGE/BLOCK), frozen `DecisionOutcome` (decision, reason_codes, rule_results, policy_version=`razormesh-phase1-policy-v1`), `DecisionEngine.decide`.
- Matrix order: state gate first (`assert_executable`; non-AUTHORIZED → BLOCK STATUS_NOT_EXECUTABLE — BLOCKED never executes, CHALLENGED cannot until reauthorization); any FAIL → BLOCK; any UNKNOWN → CHALLENGE (fail-closed step-up, e.g. APPROVAL_REQUIRED); else ALLOW. No ML scores anywhere.
- `_safe` made public as `safe_evaluate` for cross-module reuse.
- Validation: ruff clean; mypy strict 34 files clean; pytest 127/127.

---

# Final Phase-1 exit checklist

- [ ] 50/50 milestones PASS
- [ ] normal authorized flow works
- [ ] BLOCK cannot execute
- [ ] CHALLENGE cannot execute before reauthorization
- [ ] 20-worker same-ticket provider effect count = 1
- [ ] aggregate budget concurrency invariant passes
- [ ] wrong principal/agent/merchant ticket fails
- [ ] stale/superseded authorization fails
- [ ] provider-unknown path does not blindly duplicate
- [ ] audit tamper test detected
- [ ] benchmark metrics generated from actual runner
- [ ] dependency/security findings classified
- [ ] clean-room setup succeeds
- [ ] `docs/PHASE1_COMPLETION_REPORT.md` exists
