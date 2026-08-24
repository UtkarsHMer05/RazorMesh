# PHASE2_STATUS.md — Razorpay Test Mode Integration Evidence

## Status rules

- Valid states: `NOT_STARTED`, `IN_PROGRESS`, `PASS`, `BLOCKED`.
- PASS only with recorded acceptance evidence below.
- Real Razorpay interaction classes: `NONE | READ_ONLY | TEST_ORDER | TEST_CHECKOUT | WEBHOOK`.
- Secrets are never recorded here — only `PRESENT/ABSENT` for the three
  credential variables, which live solely in the gitignored root `.env`.

| # | Milestone | Status | Evidence summary |
|---|---|---|---|
| M01 | Repository & Governance Integrity Re-read | PASS | hygiene sweep clean; scaffold created; hardening commit cef5a6f absorbed; .env ignored w/ credentials PRESENT |
| M02 | Phase-1 Full Quality Revalidation | PASS | ruff+mypy strict clean; pytest 225/225 (cov 96% TOTAL under current flags); eslint/tsc/vitest3/build OK; Playwright 2/2; security-check PASS (pip+pnpm audits clean); benchmark smoke 14 pairs P=R=F1=1.0 |
| M03 | Phase-1 Security Invariant Revalidation | PASS | focused runs: 45 core security + 14 buyer/audit/lifecycle + 33 targeted (race/replay/forged/tamper/superseded/stale/unknown) all PASS; replay = idempotent collapse, never 500 |
| M04 | Phase-1 Clean-Room Acceptance Re-run | PASS | fresh volume→3 migrations→50 products→live API: acceptance 10/10 PASS, lab 16/16 families, benchmark 14 pairs, tamper non-mutating |
| M05 | Freeze Phase-2 Baseline | PASS | docs/PHASE2_BASELINE.md: HEAD 5186cca, pytest 225/225 cov 96%, migration head d8b412f091c3, versions recorded; zero Razorpay calls so far (declared) |
| M06 | Live Razorpay Documentation Research | PASS | R-013/R-014/R-015 appended to RESEARCH.md: Orders limits (receipt≤40, notes≤15×256), checkout.js handler contract, HMAC formulas (callback uses SERVER-stored order id; webhook over RAW body), x-razorpay-event-id dedup, ordering not guaranteed, failed→captured expected, captured+order.paid both fire once, zrok guidance, OTP 754081, SDK razorpay 2.0.1 |
| M07 | Provider Client & Dependency Decision | PASS | D-030: one thin httpx 0.28.1 wrapper (latest stable, 0 advisories, already locked); razorpay SDK 2.0.1 declined (Beta classifier, opt-in auto-retry foot-gun, extra requests dep); HMAC via stdlib |
| M08 | Root `.env` / Typed Config Reconciliation | PASS | .env reconciled (14 nonsecret keys appended; 3 secrets untouched/never printed); typed Settings w/ SecretStr + Literal guards; 6 new tests; suite 231/231; secret scan clean |
| M09 | Razorpay Test-Mode Fail-Safe | PASS | validate_payment_provider_config(): live prefix rejected in any mode; real provider requires test+3 creds (names only, never values); mock needs nothing; 5 new tests; suite 236/236 |
| M10 | Phase-2 Governance Transition | PASS | PHASES marked ACTIVE; PRD §11 PRD-RZP-001..012; ARCHITECTURE §14 provider flow + state dimensions; SECURITY P2-S01..S24 + T19..T24; TESTING §13 gates; D-030; R-013..R-015 |
| M11 | Razorpay Provider Skeleton | PASS | providers/razorpay.py: typed client+errors (auth/rejection/unknown/config), order create/fetch, no-retry proven via MockTransport call counts; DI factory keeps mock default; buyer layer untouched; 9 tests; suite 245/245 |
| M12 | Safe Auth Diagnostic | PASS | scripts/rzp_auth_check.py vs REAL Test keys: read-only GET /orders?count=1 → 200 OK, credentials accepted, 677ms; zero secrets printed; mock-transport tests for ok/401/timeout; suite 246/246 |
| M13 | DB Schema for Razorpay Correlation | PASS | migration a93c7d5e21f0: 8 correlation columns on attempts + partial unique idx (order/payment id) + provider_events inbox (event_id PK, verified, payload_sha256); up/down round-trip; dedup tests; suite 248/248 |
| M14 | Internal→Razorpay Order Mapping | PASS | build_order_correlation(): receipt=r_{attempt_id} (≤40), notes=4 opaque refs+generation (≤15×256), no PII/secrets; parse_order_correlation() round-trip; 4 tests; suite 252/252 |
| M15 | Server-Side Order Creation | PASS | executor Razorpay path: order created via trusted prelude, correlation persisted, attempt EXECUTING; timeout→UNKNOWN+REQUIRED+reservation held; 400→FAILED+release; idempotent re-entry (1 call); strict-mypy config gap found & closed (30 latent errors fixed); suite 255/255 |
| M16 | Razorpay Error Taxonomy | PASS | exhaustive matrix test (21 cases): 401/403→AUTH; 400/404/422/429/3xx/4xx-residual→REJECTED(definitive, no-effect); 5xx/timeout/connect/malformed/bad-entity→UNKNOWN(never retried, calls==1); suite 276/276 |
| M17 | First Real Test Order | PASS | scripts/rzp_first_order.py: real ALLOW→reserve→ticket→nonce→attempt→order_TTaTD5sEvimzoD (created, 64890 INR minor); fetch matches amount/currency/receipt; security regressions green post-mutation |
| M18 | Order Fetch & Reconciliation | PASS | reconcile_attempt(): amount/currency/receipt validated vs durable authority; conflicts raise AMOUNT/CURRENCY/CONTEXT_MISMATCH; paid classified as capture evidence WITHOUT settling (reducer owns that); 6 mock tests + REAL reconcile of order_TTagLmM6FL6oB4 consistent=True; suite 282/282 |
| M19 | Checkout Launch Contract | PASS | CheckoutLaunchPayload frozen dataclass (public key id, order id, amount, currency, safe correlation); issued ONLY for EXECUTING attempts with order claim; secret-leak tests; buyer route returns launch on razorpay path; suite 282/282 |
| M20 | Checkout Script Integration | PASS | src/lib/razorpay.ts: idempotent official checkout.js loader (once per page, typed states, retry-on-error, no secrets); 3 vitest cases; lint/tsc clean; suite 287 backend + 6 web |
| M21 | Real Checkout UI | PASS | buyer page: TEST MODE banner, Pay→backend launch→official modal (server fields only), VERIFYING/CAPTURED/FAILED/PROVIDER_UNKNOWN states, no dangerous re-pay on unknown; typecheck/lint/vitest/build green |
| M22 | Client Success Handler | PASS | buyer UI forwards ONLY payment_id/order_id/signature to POST /buyer/callback; VERIFYING phase with do-not-close notice; no browser finality |
| M23 | Server Checkout Signature Verification | PASS | verify_checkout_signature(): HMAC-SHA256(SERVER-stored order|payment_id, key_secret), constant-time compare; POST /buyer/callback verifies BEFORE any mutation; 403 codes SIGNATURE_INVALID/CONTEXT_MISMATCH; DI settings fix |
| M24 | Callback Adversarial Tests | PASS | 5 adversarial cases: valid signature marks verified; forged → 403 no mutation; swapped browser order → CONTEXT_MISMATCH; duplicate verified callback idempotent; wrong-secret signature rejected; suite 292/292 |
| M25 | Post-Callback Provider Verification | PASS | valid signature ≠ fulfilment: callback fetches provider order; `paid` → confirm_captured() settles SUCCEEDED exactly-once (reserved→committed, razorpay_payment_id claim, fulfilment ELIGIBLE, RAZORPAY_PAYMENT_VERIFIED event); otherwise EXECUTING + NOT_CAPTURED; duplicate-after-settlement idempotent; suite 294/294 |
| M26 | Provider State Reducer | PASS | reducer.py: single idempotent applier for verified events; dimensions separated; captured/order.paid exactly-once; authorized informative-only; failed→FAILED(release) with guarded FAILED→SUCCEEDED late-capture reconcile (capacity-checked, audited); 4 permutation tests; suite 298/298 |
| M27 | payment.authorized Handling | NOT_STARTED | — |
| M28 | payment.captured Handling | NOT_STARTED | — |
| M29 | payment.failed Handling | NOT_STARTED | — |
| M30 | order.paid Handling | NOT_STARTED | — |
| M31 | Raw-Body Webhook Endpoint | NOT_STARTED | — |
| M32 | Webhook Signature Verification | NOT_STARTED | — |
| M33 | Durable Webhook Inbox & Dedup | NOT_STARTED | — |
| M34 | Ordering & Reconciliation Tests | NOT_STARTED | — |
| M35 | Public Webhook Tunnel Preparation | NOT_STARTED | — |
| M36 | HUMAN GATE — Webhook Dashboard | NOT_STARTED | — |
| M37 | Real Success Checkout Readiness Gate | NOT_STARTED | — |
| M38 | HUMAN GATE — Real Test Success | NOT_STARTED | — |
| M39 | Success Evidence Reconciliation | NOT_STARTED | — |
| M40 | HUMAN GATE — Real Test Failure | NOT_STARTED | — |
| M41 | Provider-Unknown / Timeout Reconciliation | NOT_STARTED | — |
| M42 | Real-Provider Concurrency & Replay Regression | NOT_STARTED | — |
| M43 | Security Lab Phase-2 Expansion | NOT_STARTED | — |
| M44 | Audit & Evidence Ledger Upgrade | NOT_STARTED | — |
| M45 | Buyer UI Trust-State Polish | NOT_STARTED | — |
| M46 | Automated E2E w/ External Checkout Boundary | NOT_STARTED | — |
| M47 | Phase-2 Performance & Network Baseline | NOT_STARTED | — |
| M48 | Full Phase-2 Security & Dependency Gate | NOT_STARTED | — |
| M49 | Phase-2 Clean-Room Acceptance | NOT_STARTED | — |
| M50 | Completion Report & STOP | NOT_STARTED | — |

---

# Current milestone evidence

## M01 — Repository and Governance Integrity Re-read

MILESTONE: M01
STATUS: IN_PROGRESS

Requirements: master prompt §1/§6/§13 (governance integrity, .env reconciliation prep, scaffold).
Security invariants: S10/S11/S30 (secret hygiene), P2-S01..S04 groundwork.

### Implementation / findings
- Git state inspected: working tree clean at user's hardening commit `cef5a6f`
  ("fix: harden and validate phase 1 trust core") on top of Phase-1 final `debfea4`.
  No unrelated or unexplained changes.
- User hardening commit absorbed before any Phase-2 work: executor re-reads durable
  authority before reservation (D-027), reservation/settlement follow provider-effect
  boundary with DB constraints + migration `d8b412f091c3` (D-028), audit tamper demo is
  non-mutating (D-029), scenario registry grew to 16 families / 14 benchmark pairs,
  suite grew to 225 tests @ 93.25% coverage. These are later human decisions — treated
  as authoritative baseline.
- Governance re-read: AGENTS.md (system prompt), RULES.md, PRD.md, PHASES.md,
  SECURITY.md, ARCHITECTURE.md, TESTING.md, DECISIONS.md (D-001–D-029),
  VERSION_MANIFEST.md, TESTING gates, updated MEMORY.md.
- Human authorization for Phase 2 received this session (explicit instruction +
  credentials provision). Per master prompt M05, MEMORY will declare "Phase 2 active"
  only after M01–M04 pass.
- Root `.env` verified git-ignored via `git check-ignore -v` (`.gitignore:6`) WITHOUT
  printing contents; human-provided Test credentials written to it this session at
  human request; file mode 600; only variable NAMES ever echoed (`PRESENCE` check).
  Contents now: RAZORPAY_MODE=test, RAZORPAY_KEY_ID=PRESENT (test prefix validated),
  RAZORPAY_KEY_SECRET=PRESENT, RAZORPAY_WEBHOOK_SECRET=PRESENT. Phase-1 nonsecret
  settings intentionally not duplicated yet — settings.py defaults cover them;
  reconciliation happens in M08 as planned.
- `.env.example` confirmed tracked and placeholder-only.
- Secret-leak sweep: no frontend `.env*`, no tracked logs/screenshots/HAR/artifacts,
  no `rzp_live_` anywhere, no test dumps in `apps/web/test-results`.
- Created minimal scaffold: `PHASE2_MILESTONES.md` (50 gated milestones, Phase-1
  history untouched) + this file.

### Files changed
- `PHASE2_MILESTONES.md` (new), `PHASE2_STATUS.md` (new), `MEMORY.md` (bootstrap note)

### Validation commands
```bash
git status --short                       # clean except intended new files
git check-ignore -v .env                 # ignored (no contents printed)
git ls-files | grep -i env               # .env.example tracked only
find apps -name ".env*" -not -path "*node_modules*"   # none
grep -rn "rzp_live_" . --include="*.py" --include="*.ts" --include="*.tsx"  # none
```

### Results
- Working tree understood; Phase-1 history preserved; no secret leak; scaffold in place.

### Security regression
- N/A (no runtime code changed in M01). Secret hygiene checks above are the security gate.

### Human gate
- NONE (Phase-2 start authorized by human this session).

### Known limitations
- `.env` currently holds ONLY the four Razorpay variables; typed-config reconciliation
  is M08 per plan.

### Next
- M02 — Phase-1 Full Quality Revalidation.

## M02 — Phase-1 Full Quality Revalidation

MILESTONE: M02
STATUS: PASS

Requirements: master prompt §2 (independent revalidation, no shortened substitutes).
Security invariants: all Phase-1 invariants re-proven by suite; S30 audits.

### Implementation / findings
- No repair needed: every gate passed on first run against the user's hardened
  baseline (`cef5a6f`).
- Test-count reconciliation vs reported evidence: 225/225 matches the reported
  Phase-1 final count exactly (the earlier 213 was pre-hardening). Coverage under
  current flags measures TOTAL 96% (5310 stmts / 196 miss); the reported 93.25%
  figure used a different flag set — both are honest local measurements, not a
  regression.
- Benchmark smoke regenerated `docs/PHASE1_BENCHMARK.json`: 14 pairs, TP=14 FP=0
  TN=14 FN=0, P=R=F1=1.0, unsafe_execution_rate 0.0 — matches hardened pipeline.

### Validation commands + results
```text
docker compose ps                       → postgres+redis healthy
ruff check .                            → All checks passed
mypy -p razormesh_api                   → no issues in 48 files
pytest -q --cov                         → 225 passed; TOTAL 96%
pnpm lint / typecheck / test            → clean / clean / 3 passed
pnpm build                              → OK (static prerender)
playwright test                         → 2 passed
make security-check                     → secret scan 0; pip-audit clean; pnpm audit clean
make benchmark                          → 14 pairs P=R=F1=1.0
```

### Real Razorpay interaction
- NONE.

### Security regression
- Full pytest suite includes the permanent execution-integrity regressions added by
  the human hardening commit; all pass. Secret scan clean; no secrets logged.

### Known limitations
- None new.

### Next
- M03 — Phase-1 Security Invariant Revalidation (focused security run).

## M03 — Phase-1 Security Invariant Revalidation

MILESTONE: M03
STATUS: PASS

Requirements: master prompt M03 list (forged signature, wrong principal/agent/merchant,
BLOCK/CHALLENGE bypass, replay, 20-worker race, aggregate race, stale checkout,
superseded authorization, provider-unknown mock path, audit tamper).
Security invariants: S2/S4/S8/S9/S11/S12/S15/S16/S21/S24/S26/S28 re-proven.

### Validation commands + results
```text
pytest tests/{tickets,nonce,spend,revalidation,executor,state_machine,ledger}.py -v
    → 45 passed
pytest tests/{buyer_api,audit_dashboard,stateful_lifecycle}.py -v
    → 14 passed
pytest tests -k "race or replay or forged or tamper or superseded or stale or unknown" -v
    → 33 selected, 33 passed
```

### Findings
- Forged ticket → SIGNATURE_INVALID before any durable effect (test_tickets).
- Wrong principal/agent/merchant bindings rejected in ordered fail-closed verify.
- BLOCKED/CHALLENGED never executable via exhaustive state-machine matrix.
- Replay: hardened executor collapses replays to the SAME durable attempt
  (`test_replay_does_not_leak_a_second_reservation`: two executes → 1 attempt,
  committed once, reserved 0). Controlled outcome — never HTTP 500. The hardening
  commit's ticket-ID-derived idempotency supersedes the earlier 409 approach
  (D-027); both prove no second effect.
- 20-worker same-ticket nonce race: exactly one winner (test_nonce).
- Aggregate-spend race cannot exceed authorization (test_spend + Hypothesis sequences).
- Stale checkout + superseded generation rejected at executor boundary (test_revalidation).
- PROVIDER_UNKNOWN retains reservation; reconciliation applies authoritative outcome;
  no fresh financial operation (test_executor).
- Audit tamper detection + non-mutating public demo (test_ledger/test_audit_dashboard, D-029).

### Real Razorpay interaction
- NONE.

### Known limitations
- None new.

### Next
- M04 — Phase-1 Clean-Room Acceptance Re-run.

## M04 — Phase-1 Clean-Room Acceptance Re-run

MILESTONE: M04
STATUS: PASS

Requirements: master prompt M04 (disposable-state reproduction; never touch host :5432).
Security invariants: full Phase-1 set re-demonstrated live.

### Commands + results
```text
docker compose down -v && up -d      → razormesh-postgres/redis recreated healthy (15432/16379 only)
make migrate                          → 3 revisions: b31a01dd94f2 → c5f21a9d3e10 → d8b412f091c3
make seed                             → 50 synthetic products
uvicorn (127.0.0.1:8000) + /ready     → ok, postgres+redis ok, mock provider true
python scripts/acceptance.py          → 10/10 PASS
```

### Live evidence highlights
- Normal purchase ALLOW→SUCCEEDED (total 64890 minor); replay collapses to same attempt.
- Forged signature 403 SIGNATURE_INVALID pre-provider.
- 20-worker race: distinct_attempts=1, durable=1, succeeded=1.
- Security Lab 16/16 families incl. CROSS_PRINCIPAL/AGENT/MERCHANT, AUTHORIZATION_SUPERSESSION,
  SUBSCRIPTION_INSERTION, UNTRUSTED_INSTRUCTION, SAFE_LOOKALIKE.
- Audit chain valid before AND after non-mutating tamper simulation (76 events unchanged).
- Benchmark artifact: 14 pairs TP14 FP0 TN14 FN0 F1=1.0.

### Real Razorpay interaction
- NONE.

### Next
- M05 — Freeze Phase-2 Baseline.

## M05 — Freeze Phase-2 Baseline

MILESTONE: M05
STATUS: PASS

Requirements: master prompt M05 (baseline document; MEMORY declares Phase 2 active).

### Implementation
- Created `docs/PHASE2_BASELINE.md` freezing: HEAD `5186cca`, pytest 225/225
  (TOTAL cov 96% under current flags), migration head `d8b412f091c3`, runtime versions,
  Phase-1 performance reference (`docs/PHASE1_PERFORMANCE.json`), known limitations,
  and the explicit statement that NO Razorpay network call of any kind has been made yet.
- `MEMORY.md` now declares Phase 2 active (per master prompt: allowed once M01–M04 pass).

### Real Razorpay interaction
- NONE (explicitly asserted in the baseline doc).

### Next
- M06 — Live Razorpay Documentation Research.

## M06 — Live Razorpay Documentation Research

MILESTONE: M06
STATUS: PASS

Requirements: master prompt M06/§5 (live re-verification; official docs override snapshot).
Research checked: RESEARCH.md R-013, R-014, R-015 (all official Razorpay sources + PyPI registry).

### Confirmed against live docs (deltas vs prompt snapshot: none material)
1. Basic Auth Key_ID:Key_Secret for all API calls.
2. Orders create: POST /v1/orders; amount integer subunit; currency 3 chars;
   receipt ≤40 chars; notes ≤15 pairs × ≤256 chars — binds M14 correlation design.
3. Standard Checkout web uses handler functions (callback_url is redirect-only);
   success handler yields payment_id/order_id/signature.
4. Callback verification formula HMAC-SHA256(order_id|payment_id, key_secret) with the
   SERVER-stored order id — "Do not use the razorpay_order_id returned by Checkout"
   (P2-S08 exactly).
5. Webhook: HMAC-SHA256 over RAW body with webhook secret vs X-Razorpay-Signature;
   never parse/cast before verifying (P2-S10/S11).
6. Dedup via x-razorpay-event-id (P2-S12); delivery order NOT guaranteed (P2-S14).
7. payment.failed → payment.captured same transaction = documented expected behaviour
   (late auth / UPI TPAP retry); payloads are snapshots that may lag (P2-S16).
8. payment.captured and order.paid both fire on capture → exactly-once effect needed
   (P2-S15).
9. authorized ≠ settled; uncaptured auto-refund; fulfil only after captured (M25).
10. Test UPI success@razorpay / failure@razorpay still current; test webhook setup OTP
    754081; zrok recommended tunnel (ngrok blacklisted).
11. razorpay PyPI 2.0.1 (2026-03-09), requests dep, opt-in enable_retry, no known vulns.

### Real Razorpay interaction
- NONE (documentation only).

### Next
- M07 — Provider Client & Dependency Decision.

## M07 — Provider Client & Dependency Decision

MILESTONE: M07
STATUS: PASS

Requirements: master prompt §10/M07 — choose exactly one client; record version,
timeout policy, retry policy, error mapping, test approach, ExecutionAttempt impact.
Decision ID: D-030.

### Choice
Project-standard HTTP client: **httpx 0.28.1** (live-verified latest stable, zero
known vulnerabilities, already in uv.lock). Official razorpay SDK 2.0.1 evaluated
and declined: Beta trove classifier; opt-in `enable_retry` automatic retries are a
mutating-call foot-gun; adds `requests` dependency for two endpoints.

### Policies established by D-030
- Timeout: explicit per-call timeout on every Razorpay request (typed config, M08).
- Retry: NONE at transport level. Mutating calls are never retried automatically;
  read-only fetch may later get a bounded, explicitly-coded retry if justified.
- Error mapping: httpx.TimeoutException/ConnectError → PROVIDER_UNKNOWN class;
  401 → RAZORPAY_AUTH_FAILED; 400/422 → definitive rejection; 5xx → provider
  degraded (unknown unless disproven); malformed body → unknown + audit.
- Test approach: httpx.MockTransport fixtures incl. timeout-before-response and
  timeout-after-send.
- ExecutionAttempt impact: wrapper returns typed results only; the executor keeps
  sole authority over attempt state/reservation — identical to mock semantics.


## M08 — Root `.env` and Typed Config Reconciliation

MILESTONE: M08
STATUS: PASS

Requirements: master prompt §6/M08 — reconcile env, preserve human secrets, typed config.
Security invariants: S30, P2-S01..S04 groundwork, secret-logging prevention.

### Implementation
- `settings.py`: added `payment_provider` (Literal mock|razorpay), `razorpay_mode`
  (Literal test ONLY — 'live' is unrepresentable at the type level),
  key_id + SecretStr key_secret/webhook_secret, api base URL, bounded timeout
  (0 < t <= 60s), webhook path/public URL; `razorpay_credentials_present` helper.
  SecretStr ensures repr/model_dump never leaks secrets (test-proven).
- Root `.env`: appended 14 missing NONSECRET Phase-1/Phase-2 keys (DATABASE_URL,
  REDIS_URL, key paths, API_HOST/PORT, WEB_ORIGIN, POLICY_VERSION,
  PAYMENT_PROVIDER=razorpay, MOCK_PAYMENT_PROVIDER=false, RAZORPAY_API_BASE_URL,
  RAZORPAY_REQUEST_TIMEOUT_SECONDS=10, RAZORPAY_WEBHOOK_PATH, empty PUBLIC_URL).
  The three human Razorpay values were preserved byte-for-byte without display.
- `.env.example`: Phase-2 section with BLANK secret placeholders + comments.

### Validation commands + results
```text
git check-ignore -v .env                        → ignored (.gitignore:6)
awk key-names only                              → 3 secret lines present, untouched
ruff/mypy                                       → clean
pytest tests/test_settings_phase2.py            → 6 passed
pytest (full)                                   → 231 passed
make security-check                             → PASS, no blocking findings
```

### Real Razorpay interaction
- NONE.

### Next
- M09 — Razorpay Test-Mode Fail-Safe.


## M09 — Razorpay Test-Mode Fail-Safe

MILESTONE: M09
STATUS: PASS

Requirements: master prompt M09/§7 — require test mode, reject live keys, refuse
real-provider start without credentials, keep mock credential-free, name-only errors.
Security invariants: P2-S01, P2-S02, P2-S03 (groundwork), P2-S20, P2-S21.

### Implementation
- `settings.py`: `ProviderConfigError` + `validate_payment_provider_config()`.
  - `rzp_live_` prefix → `RAZORPAY_LIVE_KEY_REJECTED` in ANY provider mode.
  - `PAYMENT_PROVIDER=razorpay` requires RAZORPAY_KEY_ID + RAZORPAY_KEY_SECRET +
    RAZORPAY_WEBHOOK_SECRET; missing vars reported by NAME only.
  - `RAZORPAY_MODE` is a Literal['test'] at the type level — 'live' cannot even
    construct Settings; defensive runtime check retained.
  - Mock mode requires no Razorpay credentials (P2-S20).

### Validation commands + results
```text
pytest tests/test_settings_phase2.py -q   → 11 passed (5 new fail-safe tests)
pytest (full)                             → 236 passed
ruff/mypy strict                          → clean
```
Tests prove: mock-without-creds OK; real-provider-missing names all three variables;
live prefix rejected even under mock; valid test config passes guard; secret VALUES
never appear in error strings.

### Real Razorpay interaction
- NONE.

### Next
- M10 — Phase-2 Governance Transition.


## M10 — Phase-2 Governance Transition

MILESTONE: M10
STATUS: PASS

Requirements: master prompt §13/M10 — full governance sync without erasing Phase-1 history.

### Updated
- `PHASES.md`: Phase 2 marked ACTIVE with pointers.
- `PRD.md`: §11 added (PRD-RZP-001..012) incl. non-goals.
- `ARCHITECTURE.md`: §14 provider architecture, separated state dimensions,
  configuration model, D-030 reference.
- `SECURITY.md`: P2-S01..S24 invariants + defensive scenarios T19..T24.
- `TESTING.md`: §13 Phase-2 release-blocking gates.
- `DECISIONS.md`: D-030 (M07). `VERSION_MANIFEST.md`: razorpay client note.
- `RESEARCH.md`: R-013..R-015 (M06). `MEMORY.md`: Phase 2 active since P2-M05.

### Validation
- Documentation-only milestone; suite re-run green (236/236 at last code change).
- A fresh session can reconstruct scope/state from these files alone.

### Real Razorpay interaction
- NONE.

### Next
- M11 — Razorpay Provider Skeleton.


## M11 — Razorpay Provider Skeleton

MILESTONE: M11
STATUS: PASS

Requirements: master prompt M11/§8/§10; D-030.
Security invariants: SEC-001, P2-S05/S06 groundwork, P2-S17..S21.

### Implementation
- `providers/razorpay.py`:
  - `RazorpayClient` — single httpx wrapper (Basic auth, bounded timeout,
    optional MockTransport seam). Error mapping per M16 taxonomy:
    401/403→AUTH_FAILED; 400/404/422→ORDER_CREATE_REJECTED (definitive);
    timeouts/connect errors/5xx/malformed→UNKNOWN (truth not disproven).
  - `RazorpayPaymentProvider` — order lifecycle (create_order/fetch_order) with
    `from_settings` guard (requires PAYMENT_PROVIDER=razorpay + test mode);
    Standard Checkout is an async-confirmation model so the provider exposes the
    order lifecycle rather than a synchronous charge(); executor authority over
    attempt/reservation state is unchanged.
  - `build_payment_provider(settings)` DI factory: mock default credential-free;
    razorpay construction runs fail-safe guard; NO silent fallback to mock (P2-S21).
- Buyer/agent layers unchanged; they still construct only through trusted paths.

### Validation commands + results
```text
pytest tests/test_provider_razorpay.py -v → 9 passed
pytest (full)                             → 245 passed
ruff / mypy strict (49 files)             → clean
```
Fault-injection proofs: timeout → UNKNOWN + calls==1 (no transport retry);
503 → UNKNOWN + calls==1; 400 → definitive rejection; 401 → auth error;
malformed JSON → unknown; Basic auth header present; request body carries exactly
the server-authoritative amount.

### Real Razorpay interaction
- NONE (MockTransport only).

### Next
- M12 — Safe Razorpay Authentication Diagnostic (first permitted real interaction).


## M12 — Safe Razorpay Authentication Diagnostic

MILESTONE: M12
STATUS: PASS
REAL RAZORPAY INTERACTION: READ_ONLY (first permitted real interaction)

Requirements: master prompt M12/§7 — verify real Test credentials without printing
secrets; read-only bounded operation; timeout + structured errors.
Security invariants: P2-S01..S03 exercised against reality.

### Implementation
- `providers/razorpay.py`: `RazorpayAuthDiagnostic` (read-only GET /orders?count=1;
  401/403→RAZORPAY_AUTH_FAILED; timeout/network→UNKNOWN; non-200→STATE_CONFLICT)
  and `razorpay_auth_diagnostic_from_settings` fail-safe entry.
- `scripts/rzp_auth_check.py`: prints variable NAMES + PRESENT markers only.

### Real validation (executed this milestone)
```text
uv run --project services/api python scripts/rzp_auth_check.py
  → ok: True, code: OK, credentials accepted by provider (read-only),
    latency_ms: 677.08, listed_orders: 0
```
Human-provided Test keys authenticated successfully. No secret value ever printed,
logged, or stored outside the gitignored `.env`.

### Validation commands + results
```text
pytest tests/test_provider_razorpay.py   → 10 passed (diagnostic ok/401/timeout cases)
pytest (full)                            → 246 passed
ruff / mypy strict                       → clean
```

### Known limitations
- The diagnostic proves credential validity only — not capture settings or webhook
  configuration (later milestones).

### Next
- M13 — Database Schema for Razorpay Correlation.


## M13 — Database Schema for Razorpay Correlation

MILESTONE: M13
STATUS: PASS

Requirements: master prompt M13/§24 — durable provider correlation + event inbox.
Security invariants: P2-S12 (durable event dedup), P2-S22 (ids stored, never secrets).

### Implementation
- Migration `a93c7d5e21f0` (revises d8b412f091c3):
  - execution_attempts += provider_name, razorpay_order_id, razorpay_payment_id,
    razorpay_order_status, razorpay_payment_status, callback_verified_at,
    fulfilment_state (NOT_ELIGIBLE default), reconcile_state (NONE default).
  - Partial UNIQUE indexes: uq_attempt_razorpay_order / uq_attempt_razorpay_payment
    (WHERE NOT NULL) — one attempt may claim a given provider order/payment id.
  - New table `provider_events`: x-razorpay-event-id as PRIMARY KEY (durable dedup),
    event_type, received_at, verified, processing_state, payload_sha256 (safe
    evidence hash — no raw payloads), intent/order/payment refs, error.
- `models.py`: ExecutionAttempt extended + ProviderEvent model.

### Validation commands + results
```text
make migrate                                  → upgrade to a93c7d5e21f0 (head)
alembic downgrade -1 && alembic upgrade head   → round-trip OK; idempotent re-run clean
pytest tests/test_schema_phase2.py -v          → 2 passed:
  • two attempts claiming same razorpay_order_id → second insert IntegrityError,
    exactly one attempt survives
  • duplicate provider event_id → IntegrityError at flush (durable constraint)
pytest (full)                                  → 248 passed
ruff / mypy strict                             → clean
```

### Real Razorpay interaction
- NONE.

### Next
- M14 — Internal→Razorpay Order Mapping.


## M14 — Internal→Razorpay Order Mapping

MILESTONE: M14
STATUS: PASS

Requirements: master prompt M14 — exact correlation within official limits; opaque refs only.
Security invariants: P2-S05 (one order per trusted execution context), P2-S22.

### Contract (implemented in providers/razorpay.py)
- receipt = `r_{execution_attempt_id}` → ≤40 chars (official limit); embeds the
  durable execution identity so any provider row traces back to ONE attempt.
- notes = {intent_id, checkout_id, decision_id, ticket_id, authorization_generation}
  → 5 pairs × ≤256 chars (official ≤15×256). Opaque ULID tokens only; no secrets,
  no contact/PII fields, no free text.
- parse_order_correlation() recovers references from provider notes for reconciliation.

### Validation commands + results
```text
pytest tests/test_order_mapping.py -v   → 4 passed (limits, no-secret scan, round-trip, oversize rejection)
pytest (full)                           → 252 passed
ruff / mypy strict                      → clean
```

### Real Razorpay interaction
- NONE.

### Next
- M15 — Server-Side Razorpay Order Creation.


## M15 — Server-Side Razorpay Order Creation

MILESTONE: M15
STATUS: PASS

Requirements: master prompt M15 — trusted-path order creation only; server-authoritative
amount/currency; unknown mapping; durable correlation; audit.
Security invariants: SEC-001/S14/S15 preserved; P2-S05/S06/S17/S18/S19 proven.

### Implementation
- `executor.py`: provider-type branch after the existing trust prelude
  (ticket verify → durable revalidation D-027 → nonce → reservation D-028).
  `_execute_razorpay_order()`:
    - builds bounded receipt/notes (M14) and calls create_order with amounts taken
      ONLY from verified durable claims;
    - success → attempt stays EXECUTING, razorpay_order_id/status persisted under
      partial-unique claim, RAZORPAY_ORDER_CREATED ledger event;
    - UNKNOWN (timeout/connect/5xx/malformed) → PROVIDER_UNKNOWN +
      reconcile_state=REQUIRED + reservation KEPT + RAZORPAY_ORDER_UNKNOWN event;
    - definitive rejection/auth failure → FAILED via atomic settle (reservation
      released) + RAZORPAY_ORDER_REJECTED event.
  - Re-entry remains ticket-derived idempotent: same attempt returned, no second
    order call (proven by transport call-count == 1).

### Gate strengthening discovered & repaired
`make typecheck` ran `mypy -p razormesh_api` from repo ROOT where pyproject's
[tool.mypy] strict section is NOT discovered — so earlier "strict clean" claims were
effectively default-config runs. Fixed at the source: made the package genuinely
clean under TRUE strict settings (parameterized JSONB generics in models.py, typed
route returns, removed a dead-unreachable branch in settings guard) — verified clean
from BOTH root and services/api. Suite count grew 252→255 with new tests.

### Validation commands + results
```text
pytest tests/test_executor_razorpay.py -v   → 3 passed (created/unknown/rejected paths)
pytest (full)                               → 255 passed
ruff check .                                → clean
mypy -p razormesh_api (from BOTH dirs)      → Success: no issues in 49 source files
```

### Real Razorpay interaction
- NONE (MockTransport fault injection).

### Next
- M16 — Razorpay Error Taxonomy (largely realized in skeleton; formalize remaining mappings).


## M16 — Razorpay Error Taxonomy

MILESTONE: M16
STATUS: PASS

Requirements: master prompt M16/§18 — explicit classes; no blanket 500; unknown keeps identity+reservation.
Security invariants: P2-S17..S19 formalized at client level.

### Final mapping (implemented + tested)
| Provider signal | Internal class | Effect semantics |
|---|---|---|
| 401/403 | RAZORPAY_AUTH_FAILED | definitive no-effect |
| 400/404/422 | RAZORPAY_ORDER_CREATE_REJECTED | definitive no-effect |
| 429 | RAZORPAY_ORDER_CREATE_REJECTED (rate-limited) | no resource created; still NO auto-retry |
| other 3xx / residual 4xx | RAZORPAY_ORDER_CREATE_REJECTED | definitive refusal |
| 500/502/503/504 | UNKNOWN | truth not disproven → PROVIDER_UNKNOWN path |
| timeout / connect errors | UNKNOWN | may have reached provider |
| malformed JSON / invalid entity | UNKNOWN | cannot trust partial state |

Executor settlement per class: REJECTED→FAILED (reservation released atomically);
UNKNOWN→PROVIDER_UNKNOWN + reconcile_state=REQUIRED (reservation held); re-entry
stays ticket-idempotent with zero extra network calls.

### Validation commands + results
```text
pytest tests/test_razorpay_error_taxonomy.py -v → 21 passed (parametrized matrix incl. calls==1 assertions)
pytest (full)                                   → 276 passed
ruff / mypy strict                              → clean
```

### Real Razorpay interaction
- NONE.

### Next
- M17 — First Real Razorpay Test Order.


## M17 — First Real Razorpay Test Order

MILESTONE: M17
STATUS: PASS
REAL RAZORPAY INTERACTION: TEST_ORDER (+ read-only fetch)

### Execution evidence (safe identifiers only)
```text
intent_id:            intent_01M0SQSH0KPD76GNP48YA2ABQ4
checkout_id:          chk_01M0SQSH0ZFA5608KGJTJMBCKQ
execution_attempt_id: exa_01M0SQSH4NTZP0T5M1YJN4MBKW
state:                EXECUTING            (awaiting capture evidence by design)
amount/currency:      64890 INR minor      (server-authoritative)
razorpay_order_id:    order_TTaTD5sEvimzoD
order status:         created
receipt:              r_exa_01M0SQSH4NTZP0T5M1YJN4MBKW   (≤40 chars, opaque)
fetch reconciliation: amount✓ currency✓ receipt✓
```
No payment/checkout performed. Reservation HELD (not committed) — fulfilment
requires captured/paid evidence per P2-S15/M25.

### Post-mutation security regression
- Focused security keyword suite: 66 passed.
- Full pytest: 276 passed. Auth diagnostic re-run: ok.

### Files changed
- `scripts/rzp_first_order.py` (new, safe-evidence CLI), PHASE2_STATUS.md.

### Next
- M18 — Razorpay Order Fetch and Reconciliation.


## M18 — Razorpay Order Fetch & Reconciliation

MILESTONE: M18
STATUS: PASS
REAL RAZORPAY INTERACTION: READ_ONLY (fetch of the M17 test order)

### Implementation
- `providers/razorpay.py`: `RazorpayProviderStateConflict` + `reconcile_attempt()`:
  - requires an attempt with a correlated razorpay_order_id;
  - validates fetched amount/currency/receipt against DURABLE authority —
    mismatches raise RAZORPAY_AMOUNT_MISMATCH / RAZORPAY_CURRENCY_MISMATCH /
    RAZORPAY_ORDER_CONTEXT_MISMATCH and are never silently rewritten (P2-S06);
  - snapshots razorpay_order_status onto the attempt; classifies `paid` as
    capture EVIDENCE but performs NO settlement (reducer owns transitions, M26+);
  - read-only/idempotent: repeated calls cause no business mutation.

### Validation commands + results
```text
pytest tests/test_razorpay_reconcile.py -v → 6 passed (created/paid classification,
  amount+currency+receipt conflicts, unknown attempt, double-call idempotency)
pytest (full)                              → 282 passed
ruff / mypy strict                         → clean
REAL reconcile (repo-root cwd):
  {attempt: exa_01M0SRGA007VXHVB9Z9DM9K1SH,
   order_id: order_TTagLmM6FL6oB4, status: created, consistent: True}
```

### Known limitations
- pydantic-settings resolves `.env` relative to CWD; scripts must run from repo
  root. Noted for M19+ launch tooling; typed-config hardening can pin an absolute
  default path later.

### Next
- M19 — Checkout Launch Contract.


## M19 — Checkout Launch Contract

MILESTONE: M19
STATUS: PASS

Requirements: master prompt M19 — backend-defined launch payload; public data only;
issued only after trust/execution checks.
Security invariants: P2-S03/S04 (secrets never to browser), P2-S05/S06.

### Implementation
- `CheckoutLaunchPayload` (frozen): public_key_id, razorpay_order_id, amount_minor,
  currency, execution_attempt_id, intent_id, checkout_id.
- `build_launch_payload()`: refuses non-EXECUTING attempts and order-less attempts;
  amount/currency come from the DURABLE attempt, not the browser.
- `POST /buyer/execute`: when the trusted executor returns an EXECUTING attempt with
  an order claim (razorpay path only), the response now carries `launch`; mock mode
  responses unchanged.

### Validation commands + results
```text
pytest tests/test_launch_contract.py -v → 5 passed (field whitelist, secret-absence
  scan against populated Key/Webhook secrets, terminal-attempt refusal,
  missing-correlation refusal, immutability)
pytest (full)                            → 282 passed
ruff / mypy strict                       → clean
```

### Real Razorpay interaction
- NONE (contract + wiring; live browser flow arrives at M21+ with the human gates).

### Next
- M20 — Checkout Script Integration.


## M20 — Checkout Script Integration

MILESTONE: M20
STATUS: PASS

Requirements: master prompt M20 — stable, testable loading of the OFFICIAL script.
Security invariants: P2-S03/S04 (no secret anywhere near the bundle).

### Implementation
- `apps/web/src/lib/razorpay.ts`: `loadRazorpayCheckout()` injects
  https://checkout.razorpay.com/v1/checkout.js once (id-deduped, shared inflight
  promise), resolves true/false on load/error, removes a failed tag so a later
  user action can retry. No API version pinning beyond the documented v1 URL;
  Key ID arrives ONLY via backend launch payload (M19/M21).

### Validation commands + results
```text
pnpm test        → 6 passed (single-injection, idempotency-under-concurrency, error+retry path)
pnpm typecheck   → clean
pnpm lint        → clean
```

### Real Razorpay interaction
- NONE (script load only; no payment initiated).

### Next
- M21 — Real Checkout UI.


## M21 — Real Checkout UI

MILESTONE: M21
STATUS: PASS

Requirements: master prompt M21/§29 — trust-first Test Mode checkout screen.
Security invariants: P2-S03/S04/S06, §29 labeling.

### Implementation (apps/web/src/app/buyer/page.tsx)
- Visible banner: "Razorpay Test Mode — simulated payment, no real money."
- ALLOW → single Pay action → POST /buyer/execute → server-issued launch payload
  opens the official modal. Browser NEVER supplies key/order/amount/currency.
- Phases: awaiting_checkout → verifying (POST /buyer/callback) → CAPTURED/PAID |
  FAILED | PROVIDER_UNKNOWN with explicit no-fresh-pay note on unknown.
- Retry only re-opens the SAME order's checkout; unknown outcome intentionally
  offers no new-payment action.

### Validation commands + results
```text
pnpm typecheck / lint / test / build → clean / clean / 6 passed / OK
```

### Next
- M22 — Client Success Handler (callback submission hardening + tests).


## M22 — Client Success Handler

MILESTONE: M22
STATUS: PASS

Requirements: master prompt M22 — forward only Razorpay fields + safe correlation;
VERIFYING state; no browser finality.
Security invariants: P2-S06 (browser never authoritative), P2-S09 groundwork.

### Implementation
- Buyer page `submitCallback()`: posts {intent_id, checkout_id,
  razorpay_payment_id, razorpay_order_id, razorpay_signature} to /buyer/callback;
  sets VERIFYING while awaiting the server; renders CAPTURED/FAILED/
  PROVIDER_UNKNOWN strictly from server response. No client-side fulfilment.

### Validation
- Frontend gates green (tsc/lint/vitest/build); server behavior proven in M23/M24 suites.


## M23 — Server Checkout Signature Verification

MILESTONE: M23
STATUS: PASS

Requirements: master prompt M23 — mandatory verification using SERVER-stored order id.
Security invariants: P2-S07, P2-S08, P2-S09.

### Implementation
- `verify_checkout_signature()` (providers/razorpay.py): stdlib hmac/sha256,
  `compare_digest`, formula exactly per official docs; order id comes from the
  durable attempt row — the browser's order value is compared only for mismatch
  detection and never used for verification.
- `POST /buyer/callback`: resolves the attempt by (intent_id, checkout_id) from
  PostgreSQL; browser-order mismatch → 403 RAZORPAY_PAYMENT_CONTEXT_MISMATCH;
  bad signature → 403 RAZORPAY_PAYMENT_SIGNATURE_INVALID with ZERO mutation;
  success → records callback_verified_at only (settlement waits for captured
  evidence per M25). Route now consumes Settings via FastAPI dependency override
  (fixes an lru_cache bypass that would have leaked real-env values into tests).


## M24 — Callback Adversarial Tests

MILESTONE: M24
STATUS: PASS

Requirements: master prompt M24.
Security invariants: P2-S07..S09, S14 (duplicate delivery), superseded/stale paths
remain covered by the executor's durable revalidation which precedes any order.

### Evidence
`pytest tests/test_callback_verification.py -v` → 5 passed:
1. valid signature → callback_verified_at set; attempt stays EXECUTING;
2. forged signature → 403 SIGNATURE_INVALID, durable snapshot byte-identical;
3. browser swaps order id → 403 CONTEXT_MISMATCH (verification still bound to stored id);
4. duplicate verified callbacks → identical outcome, single effect;
5. attacker-signed with wrong secret → 403, no mutation.

Full suite: 292 passed. ruff/mypy strict clean.


## M25 — Post-Callback Provider State Verification

MILESTONE: M25
STATUS: PASS

Requirements: master prompt M25 — captured/paid evidence required before fulfilment.
Security invariants: P2-S15, P2-S13, authorized-only ≠ fulfilment.

### Implementation
- `TrustedPaymentExecutor.confirm_captured()`: atomic EXECUTING→SUCCEEDED with
  reservation commit, guarded payment-id claim (partial unique), ELIGIBLE synthetic
  fulfilment, tamper-evident RAZORPAY_PAYMENT_VERIFIED ledger event.
- Callback endpoint now: signature verified → record verification → FETCH provider
  order → only `paid` settles; anything else returns EXECUTING +
  RAZORPAY_PAYMENT_NOT_CAPTURED with zero settlement. Double-delivery after
  settlement is an idempotent no-op returning the settled state.

### Validation commands + results
```text
pytest tests/test_callback_verification.py -v → 7 passed (incl. paid→SUCCEEDED+
  committed+ELIGIBLE; created→EXECUTING+NOT_CAPTURED+committed==0;
  duplicate-after-settlement idempotent)
pytest (full)                                 → 294 passed
ruff / mypy strict                            → clean
```

### Real Razorpay interaction
- NONE (MockTransport).

### Next
- M26 — Provider State Reducer.


## M26 — Provider State Reducer

MILESTONE: M26
STATUS: PASS

Requirements: master prompt M26/§23 — ONE idempotent reducer; separate state dimensions.
Security invariants: P2-S13/S14/S15/S16.

### Implementation
- `reducer.py`: `ProviderStateReducer.apply_event(VerifiedProviderEvent)` — the only
  business-mutation path for verified provider events:
  - EXECUTING + captured/order.paid → confirm_captured (exactly-once);
  - EXECUTING + authorized → no-op (informative; M27 semantics);
  - EXECUTING + failed → record_provider_failure (atomic release);
  - PROVIDER_UNKNOWN + captured → resolve_unknown(SUCCEEDED)+ELIGIBLE;
  - PROVIDER_UNKNOWN + failed → resolve_unknown(FAILED);
  - FAILED + captured → `reconcile_failed_to_succeeded` (NEW executor method):
    capacity-guarded commit + ELIGIBLE + RAZORPAY_RECONCILED_LATE_CAPTURE audit;
  - SUCCEEDED + anything → no-op (duplicates can never double-commit).
- Executor gained `record_provider_failure` and the guarded reconciliation method.

### Validation commands + results
```text
pytest tests/test_reducer.py -v → 4 passed (captured→paid dedup to one effect;
  authorized never fulfils; failed→captured reconciles once with capacity guard;
  captured resolves PROVIDER_UNKNOWN)
pytest (full)                   → 298 passed
ruff / mypy strict (50 files)   → clean
```

### Next
- M27 — payment.authorized Handling.
