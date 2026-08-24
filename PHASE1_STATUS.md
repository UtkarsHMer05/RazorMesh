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
| M33 | Dev Signing Key Management | PASS | Ed25519 pair via cryptography lib at settings-driven paths (infra/keys/, gitignored); 0o600 private perms; missing key -> actionable DevKeyError; sign/verify + cross-key rejection + idempotent ensure tested (6 tests); live keygen verified untracked |
| M34 | Context-Bound Single-Use Execution Ticket | PASS | Signed JCS-canonical claims bind principal/agent/gen/intent+checkout hashes/merchant/amount/currency/decision/policy/nonce/window; ordered fail-closed verify: SIGNATURE_INVALID -> TICKET_EXPIRED -> 11 binding codes; 8 tests PASS |
| M35 | Redis Nonce Claim and Concurrency | PASS | SET NX EX atomic claim; replay rejected; TTL bounded; holder-only Lua release; 20-worker same-nonce race -> exactly 1 winner; Redis down -> CoordinationUnavailable fail-closed; 5 tests PASS |
| M36 | Trusted Payment Executor + Durable ExecutionAttempt | PASS | Only executor calls PaymentProvider; durable attempts CREATED->EXECUTING->SUCCEEDED/FAILED/PROVIDER_UNKNOWN (transition-guarded); idempotency-key re-entry returns same attempt (never fresh op); unknown keeps reservation, failure releases, success commits; ticket persisted for FK/audit; 6 tests PASS |
| M37 | Mock Payment Provider | PASS | 7 modes (success/failure/timeout-before/timeout-after-success/duplicate/delayed/out-of-order) driving REAL executor: provider-side effects ledger proves money-moved-vs-not; unknown+reconciliation resolves to SUCCEEDED; duplicate delivery keeps 1 effect; 7 tests PASS |
| M38 | Checkout Service | PASS | Server recomputes ALL amounts from trusted catalog (client total mismatch rejected loudly); blocked intents refused pre-rules; propose persists checkout + ledger event; authorize runs full rule set -> durable decision + hashes; ALLOW-only ticket issuance; 7 tests PASS |
| M39 | Live Checkout Revalidation | PASS | Revalidator re-reads durable checkout, rebuilds exact authz projection (condition/currency persisted), recomputes hash: relevant drift -> STALE_CHECKOUT; generation/status drift -> AUTHORIZATION_SUPERSEDED/STALE; untrusted title changes proven NOT to invalidate; 5 tests PASS |
| M40 | Untrusted Content Boundary | PASS | Hostile payloads (SQLi/prompt-injection/forged authority JSON) stored verbatim as UNTRUSTED_CONTENT; authorization hashes + decisions unaffected; smuggled policy/nonce strings stay inert; authority-slot attempt -> TrustViolation; ledger chain intact with hostile rows; 5 tests PASS |
| M41 | Future SemanticVerifier Interface | PASS | Protocol + NullSemanticVerifier (UNDECIDED default) + DeterministicKeywordVerifier test double; rule adapter maps SAFE/UNSAFE/UNDECIDED -> PASS/FAIL/UNKNOWN fail-closed; zero ML deps asserted; 6 tests PASS |
| M42 | Attack Scenario Specification | PASS | Pydantic-validated ScenarioSpec (id pattern, family-specific invariants: swap/replay>=2/drift-field/split>=2); registry covers all 7 required families exactly once; expected labels isolated from decision inputs; 5 tests PASS |
| M43 | Adversarial Evaluation Runner | PASS | All 7 scenarios executed through REAL pipeline (service+engine+ledger+ticket+nonce+executor+mock): expected==actual for every family incl. split prevention via durable aggregate budget and provider-unknown no-fresh-op; labels never enter decision inputs; 5 tests PASS |
| M44 | Safe/Unsafe Paired Benchmark | PASS | 6 attack/safe-twin pairs through real pipeline: TP=6 FP=0 TN=6 FN=0, P=R=F1=1.0, false-block 0%, safe-completion 100%; synthetic GMV completed 389340 + protected 324450 minor units (explicitly labelled); artifact docs/PHASE1_BENCHMARK.json; 4 tests PASS |
| M45 | Buyer Experience UI | PASS | 4-step buyer flow (fixture authz -> catalog -> propose/decision -> mock execution) on real backend endpoints POST /buyer/*; live E2E: ALLOW->SUCCEEDED; forged signature 403 SIGNATURE_INVALID; replay collapses to same attempt (1 effect); CORS now GET+POST; tsc+build+vitest clean |
| M46 | Security Lab UI | PASS | GET /security-lab/scenarios + POST /security-lab/run (server executes all 7 real-pipeline scenarios, 7/7 as-designed) with hash-chained evidence tail; lab page renders scenario list + outcomes table + evidence; tsc+build clean; 2 tests PASS |
| M47 | Audit Dashboard | PASS | GET /audit/timeline (chronological + hash heads + reason codes), /audit/verify, /audit/state/{intent} (spend/decisions/tickets/attempts), POST /audit/tamper-test (simulates trigger bypass -> DETECTED -> self-restores); dashboard page renders all views; 5 tests PASS; tsc+build clean |
| M48 | Deep Test and Security Gate | PASS | pytest 213/213 incl. new Hypothesis stateful lifecycle; secret scan 0; pip-audit 2.10.1 clean; pnpm audit clean; eslint/tsc/vitest 3/3/build OK; Playwright E2E 2/2; Makefile entry points repaired; benchmark CLI writes artifact |
| M49 | Performance/Resource Baseline | PASS | scripts/perf_baseline.py -> docs/PHASE1_PERFORMANCE.json: micro (hash ~0.03ms, sign 0.11ms, verify 0.20ms, decide 0.035ms), e2e happy path mean 31.0ms, benchmark suite 0.54s, in-process API latencies; hardware+version context recorded; LOCAL ONLY |
| M50 | Clean-Room Phase-1 Acceptance | PASS | Fresh volume -> migrate -> seed -> live API: scripts/acceptance.py 10/10 PASS (purchase, replay collapse, forged sig 403, 20-worker race =1 effect, lab 7/7, audit verify+tamper detect, benchmark artifact); pytest 213/213; build+E2E green; completion report written |

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

## M33 — Dev Signing Key Management — PASS
- `keys.py`: `DevSigningKeys` (load / generate / ensure) over `cryptography` Ed25519; PEM PKCS8 private + SubjectPublicKeyInfo public; private file chmod 0o600; paths from settings (`dev_ticket_*_key_path`, default `./infra/keys/`).
- Missing/unreadable/wrong-type keys raise `DevKeyError` with actionable regeneration instructions — no silent key substitution.
- Security: `infra/keys/` + `*.pem` gitignored (verified via check-ignore); live generation run, files untracked; sign/verify roundtrip, tamper rejection, cross-pair rejection tested.
- Validation: ruff clean; mypy strict 35 files clean; pytest 133/133.

## M34 — Context-Bound Single-Use Execution Ticket — PASS
- `tickets.py`: `ExecutionTicketClaims` (frozen pydantic: ticket/decision/checkout/intent ids, principal, agent, generation, intent_hash, checkout_hash+revision, merchant, amount, currency, policy_version, nonce, issued/expires), `TicketIssuer` (Ed25519 over RFC 8785 canonical claim bytes with schema domain-separation), `TicketVerifier` with ordered fail-closed checks: signature → expiry → 11 binding comparisons against `CurrentBinding` (the CURRENT authoritative values).
- Distinct machine-readable codes: SIGNATURE_INVALID, MALFORMED_TICKET, TICKET_EXPIRED, PRINCIPAL_MISMATCH, AGENT_MISMATCH, INTENT_MISMATCH, AUTHORIZATION_SUPERSEDED (hash or generation), CHECKOUT_MISMATCH, CHECKOUT_CHANGED (hash or revision), MERCHANT_MISMATCH, AMOUNT_MISMATCH, CURRENCY_MISMATCH.
- Tests prove: happy path; amount tampering → signature failure; expired-but-valid-binding rejected; wrong principal/agent/merchant rejected; superseded authorization (generation bump + new intent hash) rejected; changed checkout (hash or revision) rejected; nonce mandatory.
- Validation: ruff clean; mypy strict 36 files clean; pytest 141/141.

## M35 — Redis Nonce Claim and Concurrency — PASS
- `nonce.py`: `NonceRegistry` over Redis `SET key value NX EX ttl` (single atomic compare-and-set); holder-only compensating release via Lua compare-and-delete; TTL bounded (default 300s); `holder_of`/`ttl_of` inspection.
- Fail-closed: Redis unreachable → `CoordinationUnavailable` on every operation, so no side effect proceeds without dedup capability. PostgreSQL remains durable authority; Redis holds only ephemeral claims.
- Race proof: 20 real threads claim the SAME nonce → exactly 1 winner, 19 rejected. Replay after first use always rejected; distinct nonces independent.
- Validation: ruff clean; mypy strict 37 files clean; pytest 146/146.

## M36 — Trusted Payment Executor + Durable ExecutionAttempt — PASS
- `executor.py`: `PaymentProvider` protocol + `ChargeCommand`/`ChargeResult`; `AttemptState` machine (CREATED→EXECUTING→{SUCCEEDED,FAILED,PROVIDER_UNKNOWN}, terminal states locked, `require_transition` guard); `TrustedPaymentExecutor.execute`: idempotency-key re-entry FIRST (returns same durable attempt → provider-unknown can never spawn a fresh financial op), ticket verification (M34), Redis nonce claim (M35), durable ticket row + CREATED attempt BEFORE provider call, single `charge()` per attempt.
- Spend integration: SUCCEEDED → `spend.commit`; FAILED → `spend.release`; PROVIDER_UNKNOWN → reservation intentionally KEPT (tested). `resolve_unknown()` provides explicit ops resolution of unknown attempts.
- Tests cover: success+commit, definitive failure+release (+error_code persisted), provider exception→UNKNOWN+reservation kept, retry-same-idempotency never recharges (provider.calls==1), tampered ticket blocks before any side effect (zero attempts), nonce replay rejected.
- Note: test chain helper uses incremental flushes between parent/child merges — SQLAlchemy UOW did not derive FK order without relationship(); flagged for later normalization.
- Validation: ruff clean; mypy strict 38 files clean; pytest 152/152.

## M37 — Mock Payment Provider — PASS
- `providers/mock.py`: `MockPaymentProvider` with thread-safe effects ledger + event queue; modes SUCCESS, DEFINITIVE_FAILURE, TIMEOUT_BEFORE_EFFECT (no provider-side effect), TIMEOUT_AFTER_SUCCESS (effect recorded THEN raise — proves "unknown" can mean paid), DUPLICATE_EVENT (replay returns same reference, single effect), DELAYED_EVENT (UNKNOWN now, SUCCEEDED delivered later), OUT_OF_ORDER_EVENT (terminal before creation with sequence proof).
- Tests drive the REAL TrustedPaymentExecutor: success→SUCCEEDED+commit; failure→FAILED+release+zero effects; timeout-before→UNKNOWN+held reservation+NO money moved; timeout-after→UNKNOWN but reconciliation via pending_events resolves to SUCCEEDED.
- Test infra: shared FK-safe `wipe_business_tables` in conftest used by all integration fixtures (fixes cross-fixture pollution).
- Validation: ruff clean; mypy strict 39 files clean; pytest 159/159.

## M38 — Checkout Service — PASS
- `checkout_service.py`: `CheckoutService.propose` (clients name product_id+quantity ONLY; prices/shipping from trusted catalog rows; single-merchant enforcement; quantity caps; client_total disagreement → ClientTotalMismatch; durable Checkout projection + CHECKOUT_PROPOSED ledger event) and `authorize` (full rule set via DecisionEngine over trusted facts; durable Decision row with intent/checkout hashes + reason codes + per-rule outcomes; DECISION_RECORDED + TICKET_ISSUED ledger events; ALLOW-only ticket issuance with 120s validity).
- Security: BLOCKED/CHALLENGED intents refused before rule evaluation; untrusted merchant text never enters rule inputs; amount manipulation cannot pass because totals are server-recomputed.
- Validation: ruff clean; mypy strict 40 files clean; pytest 166/166.

## M39 — Live Checkout Revalidation — PASS
- `revalidation.py`: `Revalidator.revalidate` re-reads the durable checkout row, rebuilds the envelope EXACTLY from stored authorization-relevant fields (proposal now persists product_id/quantity/unit_price_minor/currency/condition per line), recomputes the JCS hash and compares to the ticket binding; independently re-checks intent status/generation/terms hash.
- Verdicts: STALE_CHECKOUT (hash or revision drift), AUTHORIZATION_SUPERSEDED (generation), AUTHORIZATION_STALE (status/terms), CHECKOUT_MISSING, AUTHORIZATION_MISSING.
- Proven both ways: server-side quantity drift invalidates; untrusted catalog title/image changes do NOT invalidate.
- Validation: ruff clean; mypy strict 41 files clean; pytest 171/171.

## M40 — Untrusted Content Boundary — PASS
- Poisoned every product title + merchant description with hostile payloads (SQL injection, prompt injection, forged policy_version/decision/nonce/ticket JSON) and proved end-to-end:
  1. Storage keeps text VERBATIM (no interpretation);
  2. Different hostile texts → identical intent hashes and identical ALLOW decisions;
  3. Durable decision row carries only OUR policy version; forged nonce string absent from issued tickets;
  4. Untrusted content attempting an authority slot raises TrustViolation;
  5. Evidence ledger chain verifies with hostile rows stored.
- Validation: ruff clean; mypy strict 41 files clean; pytest 176/176.

## M41 — Future SemanticVerifier Interface — PASS
- `semantic.py`: `SemanticVerifier` protocol, `SemanticAssessment` (SAFE/UNSAFE/UNDECIDED), `NullSemanticVerifier` (Phase-1 default), `DeterministicKeywordVerifier` (case-insensitive banned-phrase double), and `semantic_rule` adapter into the RazorGuard matrix: SAFE→PASS, UNSAFE→FAIL SEMANTIC_UNSAFE, UNDECIDED→UNKNOWN SEMANTIC_UNDECIDED (fail-closed).
- Phase boundary enforced by test: transformers/torch/onnxruntime must not appear in sys.modules.
- Validation: ruff clean; mypy strict 42 files clean; pytest 182/182.

## M42 — Attack Scenario Specification — PASS
- `scenarios.py`: `ScenarioSpec` (pydantic, frozen) with family-specific invariants (CONTEXT_SWAP needs swap_principal_to; REPLAY needs replay_count>=2; CHECKOUT_DRIFT needs drift_field; APPROVAL_SPLIT needs split_parts>=2); `ExpectedOutcome` enum keeps EXPECTED labels separate from runner inputs.
- Registry: 7 scenarios covering every required family exactly once — safe baseline, context swap, 5x replay, checkout drift, 3-way approval split, provider-unknown retry, expired authorization. `validate_registry()` guards duplicates + coverage.
- Validation: ruff clean; mypy strict 43 files clean; pytest 190/190.

## M43 — Adversarial Evaluation Runner — PASS
- `evaluation.py`: `AdversarialRunner` wipes+seeds per scenario, wires the full stack (CheckoutService + 17-rule DecisionEngine + EvidenceLedger + TicketIssuer + Redis nonce + TrustedPaymentExecutor + MockPaymentProvider), applies only structured spec mutations, records ACTUAL outcomes; expected labels used solely for post-hoc scoring.
- Key hardening discovered by the runner: `authorize()` now reads durable committed/reserved spend into the rule context, so aggregate budgets bind across checkouts (approval-split defense is enforced at authorization time once part 1 has committed).
- Results: safe→ALLOW_EXECUTE_ONCE; context swap→PRINCIPAL_MISMATCH rejection; 5x replay→SINGLE_EFFECT_ONLY (4 nonce rejections); drift→STALE_DETECTED; split→parts 2-3 BLOCK BUDGET_EXCEEDED; provider-unknown retry→same attempt reused (1 provider call); expired→BLOCK.
- Validation: ruff clean; mypy strict 44 files clean; pytest 195/195.

## M44 — Safe/Unsafe Paired Benchmark — PASS
- `benchmark.py`: `build_pairs()` creates a SAFE control twin per attack family (differs only by the malicious dimension); `PairedBenchmark.run()` classifies via ground-truth pair labels vs system behaviour (money moved?); confusion matrix + precision/recall/F1/false-block/safe-completion; GMV figures explicitly labelled SYNTHETIC and exported to `docs/PHASE1_BENCHMARK.json`.
- Current-pipeline result: TP=6, FP=0, TN=6, FN=0 → P=R=F1=1.0, false-block 0%, safe-completion 100%. Synthetic completed GMV 389340 minor; protected (stopped fraud) 324340+minor as recorded in artifact. NO production claims — fixture prices only.
- Validation: ruff clean; mypy strict 45 files clean; pytest 199/199.

## M45 — Buyer Experience UI — PASS
- Backend: `api/routes/buyer.py` — POST /buyer/fixture-intent (permissive demo authorization), POST /buyer/propose (server-authoritative totals -> full RazorGuard decision -> ticket on ALLOW), POST /buyer/execute (rebuilds binding ONLY from durable rows, full ticket verification, nonce claim, executor). CORS updated to GET+POST.
- Frontend: `buyer/page.tsx` 4-step flow with decision banner (ALLOW/CHALLENGE/BLOCK + reason codes) and execution state; UI holds no privileges — bypass note explains backend re-verification.
- Live E2E: fixture intent → propose → ALLOW (total 64890 minor) → execute SUCCEEDED; forged signature → 403 SIGNATURE_INVALID; replay → collapses to SAME durable attempt (exactly 1 effect; provider called once) — idempotent by design.
- Validation: ruff clean; mypy strict 46 files clean; pytest 204/204; tsc clean; next build OK; vitest 3/3.

## M46 — Security Lab UI — PASS
- Backend: `api/routes/security_lab.py` — GET /security-lab/scenarios (registry listing) + POST /security-lab/run (wipes, seeds, executes all 7 scenarios through the REAL pipeline via AdversarialRunner; returns actual outcomes + hash-chained ledger evidence tail). Explicitly framed as synthetic/local/mock-only.
- Frontend: security-lab page lists registered scenarios, executes the suite server-side on click, renders outcome table (scenario/family/actual/as-designed) and evidence tail with truncated SHA-256 heads. No offensive tooling; nothing touches third parties.
- Validation: ruff clean; mypy strict 47 files clean; pytest 206/206; tsc clean; next build OK.

## M47 — Audit Dashboard — PASS
- Backend: `api/routes/audit.py` — GET /audit/timeline (chronological events with seq, hashes (16-hex heads), reason codes), GET /audit/verify (chain verdict), GET /audit/state/{intent_id} (intent status/generation + spend authorized/reserved/committed/available + decisions + tickets incl. nonce presence + execution attempts), POST /audit/tamper-test (simulates attacker bypassing the append-only trigger by rewriting the newest event's actor, runs verify -> DETECTED, then self-restores with correct sequence continuation).
- Frontend: audit page renders timeline (newest-first with hash heads), verify banner, intent state inspector (spend/decisions/tickets/attempts) and tamper-test result.
- Validation: ruff clean; mypy strict 48 files clean; pytest 211/211; tsc clean; next build OK.

## M48 — Deep Test and Security Gate — PASS
- New: `tests/test_stateful_lifecycle.py` — Hypothesis `RuleBasedStateMachine` over the authorization lifecycle (random legal+illegal transitions; invariants: terminal states never revive, execution only from AUTHORIZED) + property test that random reserve/commit/release sequences keep reserved>=0, committed>=0, reserved+committed<=authorized.
- Repaired gate wiring discovered by the deep gate: root `scripts/` was empty while Makefile targets pointed at nonexistent files (M08 was validated via dry-run only). Now real: `make keys` → `python -m razormesh_api.keys`; `make seed` → `python -m razormesh_api.catalog`; `make benchmark` → `python -m razormesh_api.benchmark` (new CLI entry writing docs/PHASE1_BENCHMARK.json); `make dev-api` → `razormesh_api.api.main:app`; `make security-check` → new `scripts/security_check.py`.
- New `scripts/security_check.py`: git-tracked-file secret scan (full private-key BLOCK detection incl. base64 body — bare PEM header strings in assertions are not findings; AWS/GitHub/Razorpay key shapes; credential assignments with .env.example placeholder exemption) + Python dep audit via pip-audit 2.10.1 against the locked uv venv + frontend `pnpm audit --prod`, classified per TESTING.md §10.
- Frontend React hooks compliance: replaced synchronous effect-invoked loaders on buyer/security-lab/audit pages with the documented async-IIFE + cancellation-flag pattern (fixes eslint react-hooks/set-state-in-effect errors without suppression).
- Ruff config: documented per-file-ignores for alembic template conventions (E402/I001/UP007/UP035/BLE001).
- Deep-gate results: ruff clean; mypy strict 48 files clean; **pytest 213/213** (incl. stateful lifecycle, 20-worker nonce race C1, spend concurrency C2, duplicate-event idempotency C3, wrong-context tickets T8–T10, stale checkout T11, superseded generation T12, provider-unknown T15, audit tamper detection); secret scan 0 findings; pip-audit "No known vulnerabilities found" (only local razormesh-api itself skipped as non-PyPI); pnpm audit --prod clean; eslint clean; tsc clean; vitest 3/3; next build OK (6 routes); Playwright chromium E2E 2/2; make benchmark regenerated docs/PHASE1_BENCHMARK.json with identical metrics (TP6 FP0 TN6 FN0, P=R=F1=1.0).

## M49 — Performance/Resource Baseline — PASS
- New `scripts/perf_baseline.py` (+ `make perf`): measures with real components and writes `docs/PHASE1_PERFORMANCE.json` labelled "LOCAL-ONLY Phase-1 baseline; NOT production capacity".
- Context recorded: macOS 26.5, arm64 Apple M2, 8 GB RAM, 8 logical CPUs, Python 3.13.11, fastapi 0.141.1 / pydantic 2.13.4 / sqlalchemy 2.0.52 / cryptography 50.0.0 / rfc8785 0.1.4.
- Micro (pure CPU, n=2000–3000): checkout authz hash mean 0.0294 ms; intent authz hash 0.0269 ms; ticket issue (JCS+Ed25519 sign) 0.1089 ms; ordered fail-closed ticket verify 0.1956 ms; RazorGuard decide over ALL rule groups 0.0352 ms.
- End-to-end trusted core happy path (propose→authorize→reserve→nonce claim→mock execute incl. PostgreSQL+Redis, n=25): mean 31.00 ms, p50 30.09 ms, p95 32.56 ms.
- Paired benchmark suite wall-clock: 0.542 s for 12 real-pipeline scenarios (6 pairs, P=R=F1=1.0).
- In-process ASGI API latency: GET /health mean 0.415 ms; GET /catalog/products?limit=100 mean 16.10 ms (DB read of 100 rows); POST /buyer/fixture-intent mean 14.08 ms (durable write). Network stack explicitly excluded.
- Validation: ruff clean; mypy strict clean; pytest 213/213 regression after harness addition.
- Known limits: single-machine local numbers only; no load generation beyond stated n; ASGI transport for API figures; no production capacity claims.

## M50 — Clean-Room Phase-1 Acceptance — PASS
- Clean-room reproduction: `docker compose down -v` (razormesh volume only) → `up -d` healthy → `make migrate` (2 revisions on empty DB) → `make seed` (50 products) → API started fresh on 127.0.0.1:8000, /ready ok.
- New `scripts/acceptance.py` runs PRD §9 demonstrations over live HTTP; result **10/10 PASS**: readiness+mock banner; normal purchase ALLOW→SUCCEEDED (total 64890 minor); replay collapses to same durable attempt (1 effect); forged signature → 403 SIGNATURE_INVALID pre-provider; 20-worker same-ticket race → distinct_attempts=1, durable=1, succeeded=1; security-lab real-pipeline suite 7/7 (CONTEXT_SWAP, REPLAY, CHECKOUT_DRIFT, APPROVAL_SPLIT, PROVIDER_UNKNOWN, EXPIRED_AUTHORIZATION + safe baseline); audit verify valid before AND after tamper-test; tamper DETECTED (hash mismatch) then self-restored; benchmark artifact present with computed confusion metrics.
- Repair surfaced by acceptance: concurrent/replayed nonce use returned HTTP 500 via uncaught NonceAlreadyClaimed; now returns 409 NONCE_REPLAY_REJECTED per error taxonomy (replay is a business denial, not a server fault). Lint/mypy re-verified.
- Final gates on clean deployment: pytest 213/213; next production build OK; Playwright chromium E2E 2/2; ruff+mypy clean.
- `docs/PHASE1_COMPLETION_REPORT.md` written: architecture summary, live demonstration table, benchmark metrics (labelled synthetic), LOCAL-ONLY performance baseline, honest limitations, phase-transition request.

---

# Final Phase-1 exit checklist

- [x] 50/50 milestones PASS
- [x] normal authorized flow works
- [x] BLOCK cannot execute
- [x] CHALLENGE cannot execute before reauthorization
- [x] 20-worker same-ticket provider effect count = 1
- [x] aggregate budget concurrency invariant passes
- [x] wrong principal/agent/merchant ticket fails
- [x] stale/superseded authorization fails
- [x] provider-unknown path does not blindly duplicate
- [x] audit tamper test detected
- [x] benchmark metrics generated from actual runner
- [x] dependency/security findings classified
- [x] clean-room setup succeeds
- [x] `docs/PHASE1_COMPLETION_REPORT.md` exists
