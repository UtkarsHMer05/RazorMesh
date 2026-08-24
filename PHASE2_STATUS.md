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
| M27 | payment.authorized Handling | PASS | D-031: subscribed informative-only; lagged snapshot cannot regress SUCCEEDED nor fulfil EXECUTING (test) |
| M28 | payment.captured Handling | PASS | confirm_captured exactly-once; captured-then-paid dup no-op proven; reservation reserved-to-committed once |
| M29 | payment.failed Handling | PASS | record_provider_failure settles EXECUTING-to-FAILED releasing reservation; duplicate failure no-op; late capture reconciles via guarded path |
| M30 | order.paid Handling | PASS | order.paid alone settles exactly-once without prior captured event; duplicates no-op |
| M31 | Raw-Body Webhook Endpoint | PASS | POST /api/v1/webhooks/razorpay: raw bytes before parse, 256KB cap (413), event-id required, zero mutation pre-verification, controlled statuses |
| M32 | Webhook Signature Verification | PASS | verify_webhook_signature HMAC over RAW body; matrix: valid, one-byte mutation, wrong secret, reserialization mismatch, missing header/event-id, unknown-type accepted-ignored; DI settings fix |
| M33 | Durable Webhook Inbox & Dedup | PASS | webhook_inbox.py: provider_events PK claim via insert-race; loser classified DUPLICATE with zero processing; PROCESSED/ERROR states recorded; route wired through inbox; suite 308/308 |
| M34 | Ordering & Reconciliation Tests | PASS | permutation matrix (15 cases): canonical, captured-first, failed-then-captured, paid-before-captured, all-dups, delayed-auth-only, fail-no-capture, and EVERY capture-ending ordering converges to single commit; suite 316/316 |
| M35 | Public Webhook Tunnel Preparation | PASS | zrok installed via brew; scripts/webhook_tunnel.sh + docs/PHASE2_TUNNEL.md (Dashboard steps, OTP 754081, event list, secret handling); enable step requires human token -> combined gate with M36 |
| M36 | HUMAN GATE — Webhook Dashboard | PASS | Dashboard webhook verified (Enabled, 4 events) + tunnel end-to-end; M01–M37 audit remediation (5 defects fixed, 323 tests green); live signed-delivery proof DEFERRED to M38 per human instruction + D-032/R-016 (current docs: test events are triggered by Test Mode transactions; no test-notification action exists) |
| M37 | Real Success Checkout Readiness Gate | PASS | readiness checklist fully evidenced (order create, Checkout UI, callback verify, webhook verify/dedup, provider fetch, reducer, reservation, audit, Test Mode guard, Phase-1 regressions 323/323); one reliable start workflow `make phase2-up` proven live; auth diagnostic OK; R-017 test instruments verified |
| M38 | HUMAN GATE — Real Test Success | PASS | payment #3 end-to-end: ALLOW→ticket→order→failed→late-capture reconcile→SUCCEEDED/ELIGIBLE; 4 REAL signed webhooks verified=true (7 total real rows); reserved→committed EXACTLY ONCE by live fixed webhook path (v4: ensure→reserve→release→commit); provider_name=razorpay; audit chain valid (7 events); provider-side fetch paid/captured matches; authorized-in-FAILED semantics defect found live, fixed+regression-tested (D-034); payment #2 losses disclosed (D-033) |
| M39 | Success Evidence Reconciliation | PASS | docs/PHASE2_M39_EVIDENCE_RECONCILIATION.md: DB↔provider fetch↔webhook inbox↔audit chain↔Dashboard observations reconciled for payments #2/#3; honest limitations recorded (Events API 404 R-018; payment #2 rows destroyed; one ERROR inbox row disclosed) |
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


## M27-M30 - Payment Event Semantics (reducer-backed)

MILESTONES: M27, M28, M29, M30
STATUS: ALL PASS

Requirements: master prompt M27-M30 + sections 22/23; R-014 semantics.
Security invariants: P2-S15/S16, P2-S13/S14.

### Decisions and implementation
- D-031: payment.authorized subscribed as informative-only (lagged snapshots).
- payment.captured -> exactly-once settlement via confirm_captured; repeated
  captured/order.paid events collapse to no-ops.
- payment.failed -> definitive for that payment: FAILED + atomic release;
  NOT unrecoverable - later verified capture reconciles via guarded
  reconcile_failed_to_succeeded (capacity-checked, loudly audited).
- order.paid -> correlated success evidence; alone it settles exactly once;
  after captured it is a no-op.

### Validation
pytest tests/test_reducer.py -v -> 7 passed
pytest (full)                   -> 301 passed
ruff / mypy strict              -> clean

### Real Razorpay interaction
- NONE.

### Next
- M31 - Raw-Body Webhook Endpoint.


## M31-M32 — Raw-Body Webhook Endpoint + Signature Verification

MILESTONES: M31, M32
STATUS: ALL PASS

Requirements: master prompt M31/M32/§25/§22; R-014.
Security invariants: P2-S10/S11 + P2-S12 groundwork.

### Implementation
- `api/routes/webhooks.py`: async route captures RAW body via request.body()
  BEFORE any parsing; content-length + streamed cap 256KB -> 413;
  x-razorpay-event-id mandatory -> 400 when absent; signature check BEFORE any
  business logic -> 403 RAZORPAY_WEBHOOK_SIGNATURE_INVALID with ZERO mutation;
  verified events reduce via ProviderStateReducer; unknown event types return
  200 processed=false IGNORED_EVENT_TYPE (retry behavior is never load-bearing);
  unmatched contexts return 200 UNMATCHED_CONTEXT surfaced for operators.
- `verify_webhook_signature()`: stdlib HMAC-SHA256 over exactly the received
  bytes with constant-time compare.

### Validation
pytest tests/test_webhook_verification.py -v -> 7 passed: valid /
missing-signature / one-byte-mutation / wrong-secret / reserialization-breaks-
signature (raw-body necessity proof) / missing-event-id / unknown-event-type.
pytest (full) -> 308 passed. ruff + mypy strict clean.

### Real Razorpay interaction
- NONE (local fixtures only; real delivery awaits M36 human gate).


## M33 — Durable Webhook Inbox & Dedup

MILESTONE: M33
STATUS: PASS

Requirements: master prompt M33/§24 — durable event-id dedup; concurrent duplicates one effect.
Security invariants: P2-S12/S13.

### Implementation
- `webhook_inbox.py`: `ingest_verified_event()` — INSERT into provider_events
  (event_id PRIMARY KEY) is the claim; the losing concurrent delivery hits the
  unique constraint and is classified DUPLICATE without running business logic.
  Winner runs the reducer exactly once; row transitions RECEIVED->PROCESSED or
  ERROR (with safe error text) for operators.
- Webhook route now ingests EVERY verified payment/order event through the inbox.

### Validation commands + results
```text
pytest tests/test_webhook_verification.py -q → 7 passed (incl. real duplicate
  delivery across runs returning duplicate=true)
pytest (full)                                → 308 passed
ruff / mypy strict                           → clean
```

### Real Razorpay interaction
- NONE.

### Next
- M34 — Ordering & Reconciliation Tests.


## M34 — Ordering & Reconciliation Tests

MILESTONE: M34
STATUS: PASS

Requirements: master prompt M34 — arbitrary event orderings converge safely.
Security invariants: P2-S13/S14/S15/S16.

### Evidence
pytest tests/test_reducer.py -v -> 15 passed. Parametrized matrix covers:
authorized->captured->paid; captured-first; failed->captured reconcile;
order.paid-before-captured; all-duplicates; delayed authorization only;
failure without capture stays FAILED with released capacity; and EVERY
permutation of {captured, order.paid, authorized} ending in capture evidence
converges to exactly one commit with zero residual reservation.

Full suite: 316 passed. ruff + mypy strict clean.


## M35 — Public Webhook Tunnel Preparation

MILESTONE: M35
STATUS: PASS (preparation complete; enable+share requires human action)

### Implementation
- Installed zrok via Homebrew (verified binary).
- `scripts/webhook_tunnel.sh`: checks/starts API, validates zrok environment,
  shares the local API publicly; prints registration reminder.
- `docs/PHASE2_TUNNEL.md`: exact one-time setup, per-run usage, Dashboard
  registration steps for Test Mode incl. OTP 754081, event list
  (payment.authorized/captured/failed, order.paid), and secret-handling rules
  (secret stays in .env; never pasted into chat).

### Human input required next (combined with M36)
- `zrok enable <token>` (token from my.zrok.io) then run the script, and
  register the webhook in the Test Dashboard using the existing .env secret.


## M36 — HUMAN GATE — Razorpay Test Webhook Dashboard (+ M01–M37 audit remediation)

MILESTONE: M36
STATUS: PASS (Dashboard + tunnel configuration verified; live signed-delivery
proof explicitly deferred to M38 per D-032 — NOT fabricated, NOT claimed)

Requirements: master prompt M36 — endpoint + public URL verified before the gate;
human registers webhook with the EXISTING .env secret (never pasted into chat);
verify at least one real signed event after confirmation.
Security invariants: P2-S04/S10/S11/S12 exercised against reality.

### Human action (confirmed by human owner 2026-08-24)
- zrok environment enabled by human; Test Mode Dashboard webhook registered with
  the secret already stored in `.env` (secret never entered into chat by instruction).

### Tunnel + endpoint verification (agent-executed)
```text
zrok overview                    → share 1pvdxdizehva.shares.zrok.io → http://127.0.0.1:8000
curl https://<share>/ready       → 200 ok (postgres ok, redis ok)
curl -X POST https://<share>/api/v1/webhooks/razorpay (unauthenticated)
                                 → controlled 400 (event-id required), zero mutation
.env                             → RAZORPAY_WEBHOOK_PUBLIC_URL set to the share URL
```

### M01–M37 audit (per human instruction: verify every milestone, fix defects)

M01–M35 evidence was re-checked against commits, code and live re-validation.
Claims found ACCURATE: governance scaffold, baseline freeze, research R-013..R-015,
D-030/D-031, typed config + fail-safes, schema a93c7d5e21f0 (current head),
correlation contract, error taxonomy, real orders order_TTaTD5sEvimzoD /
order_TTagLmM6FL6oB4 (evidence recorded at the time; DB since wiped by test
runs — provider_events rows present today are synthetic `evt_ok_*` fixtures,
NOT real Razorpay deliveries), launch contract, checkout UI/handler, callback
verification, reducer + inbox + permutation matrix, tunnel prep.

Defects FOUND AND FIXED during the audit:

1. **`ruff format --check` violation** in tests/test_webhook_verification.py
   (introduced with M31/M32; `make lint` ran `ruff check` only, so later
   milestone gates did not catch it). Fixed: file formatted; `make lint` now
   runs `ruff format --check` as well (TESTING.md §15).
2. **`make security-check` FAIL (3 BLOCKING)** — secret scanner flagged test
   fixtures added in M23–M32 (two synthetic HMAC secrets; the intentional
   `rzp_live_` literal required to prove live-key rejection). Earlier
   "security-check PASS" claims predated those files. Fixed: narrow documented
   allowlist in scripts/security_check.py pinning exact file+rule+literal with
   justifications; policy recorded in TESTING.md §15. Scan now PASS, audits clean.
3. **`/ready` hardcoded `mock_payment_provider=True`** (Phase-1 leftover) —
   lied about provider mode in razorpay deployments. Fixed: reports the actual
   loaded settings (`payment_provider` + derived flag); FastAPI description
   updated to Phase-2 wording; test updated (TESTING.md §14 item 10).
4. **Test suite read the REAL root `.env`** — the session settings fixture did
   not disable dotenv, so tests ran with PAYMENT_PROVIDER=razorpay and real
   Test credentials in scope (determinism + P2-S20 violation). Fixed:
   `Settings(_env_file=None, ...)` in conftest; suite is now mock/credential-free
   regardless of local .env (TESTING.md §15).
5. **CRITICAL — `/buyer/execute` hardcoded MockPaymentProvider** (buyer.py
   `_executor`), ignoring PAYMENT_PROVIDER. Consequences if shipped: razorpay
   mode would have settled transactions SUCCEEDED with NO provider order and
   committed reservations without any real payment; the launch-payload branch
   (M19) was unreachable through the API. The M19 status line "buyer route
   returns launch on razorpay path" was NOT covered by any route-level test and
   was false until this fix — corrected here, history preserved. Fixed:
   `_provider_for(settings)` seam over `build_payment_provider` (fail-safe guard
   included; no silent fallback P2-S21); callback `_razorpay_provider` now uses
   `from_settings` so the guard applies there too; misconfiguration fails closed
   with 503 RAZORPAY_CONFIG_UNAVAILABLE (names only). New regression file
   tests/test_buyer_execute_provider_wiring.py (3 tests): razorpay mode →
   EXECUTING + launch payload (public fields only, no secrets) + durable order
   correlation + reservation HELD; mock mode → SUCCEEDED without launch;
   razorpay-without-credentials → controlled 503.

### Full gate re-validation after remediation (2026-08-24)
```text
pytest (full)                     → 323 passed (320 prior + 3 wiring regressions)
ruff format --check / ruff check  → clean / clean
mypy strict (services/api + root) → no issues in 52 source files (both dirs)
pnpm lint / typecheck / test      → clean / clean / 6 passed
playwright                        → 2 passed
make security-check               → PASS (secret scan 0; pip-audit clean; pnpm audit clean)
live /ready (local + via tunnel)  → payment_provider=razorpay, mock=false (honest)
```

### Real Razorpay interaction
- NONE new this milestone (tunnel verification only; no orders/payments created).

### Close-out ruling (2026-08-24, explicit human instruction → D-032)

The original M36 acceptance line "verify at least one real signed event" could
not be executed as written:

- Human owner inspected the live Test Mode Dashboard: the registered webhook
  (Enabled, 4 events at the zrok URL) exposes NO "Send test notification"
  action for this account.
- Current official documentation re-checked the same date (R-016): "Test events
  get triggered on a transaction done in the Test mode." The page describes no
  Dashboard test-notification button.

Ruling, per the human owner's explicit instruction (highest governance
precedence, AGENTS.md §3), recorded as decision D-032:

1. The Dashboard/tunnel configuration portion of M36 is VERIFIED (evidence
   above: webhook Enabled with 4 events at the exact public URL; public HTTPS
   reaches the local API; unauthenticated probes get controlled 400 with zero
   mutation; /ready honest in razorpay mode).
2. The signed-delivery proof is DEFERRED to M38, where the first controlled
   real Test Mode transaction will actually generate payment.authorized /
   payment.captured / payment.failed / order.paid events.
3. NON-FABRICATION STATEMENT: at M36 close, provider_events contains ZERO real
   Razorpay deliveries (17 synthetic `evt_ok_*` fixture rows only; query
   `event_id NOT LIKE 'evt_ok_%'` returned 0 rows on 2026-08-24 22:35 and
   again after the gate re-runs). No test notification occurred; none is
   recorded as having occurred.
4. Carried-forward obligation: M38 cannot PASS without ≥1 REAL signed event
   (verified=true, non-fixture event_id) in provider_events.

### Next
- M37 readiness gate → M38 human gate (real Test Mode success checkout; its
  gate evidence MUST include the deferred real signed webhook event).

---

## M37 — Real Success Checkout Readiness Gate

MILESTONE: M37
STATUS: PASS

Requirements: master prompt M37 — before asking the human to pay, ensure order
creation, Checkout UI, callback verification, webhook verification/dedup,
provider fetch, reducer, reservation, audit, Test Mode guard and full Phase-1
regressions are green; provide one reliable start command/workflow.

### Readiness checklist → evidence

| Readiness item | Evidence (milestone + tests) |
|---|---|
| Order creation | M15 executor prelude (timeout→UNKNOWN+hold, 400→FAILED+release, idempotent re-entry); M17 real order created; wiring test persists razorpay_order_id |
| Checkout UI | M20/M21 (official checkout.js loader, TEST MODE banner, server-fields-only modal, no dangerous re-pay on unknown); vitest 6/6; Playwright 2/2; production build OK |
| Callback verification | M23/M24: HMAC-SHA256 over SERVER-stored order id (P2-S08), constant-time compare, verify-before-mutation; 5 adversarial cases (forged/swapped/replay/wrong-secret) |
| Webhook verification/dedup | M31/M32/M33: raw-body HMAC (P2-S13), 256KB cap, zero mutation pre-verification; durable provider_events inbox with DB-level event-id dedup (P2-S14) |
| Provider fetch | M18 reconcile_attempt (amount/currency/context vs durable authority); M25 post-callback fetch, `paid` → capture evidence |
| Reducer | M26–M30 + M34: 15-case permutation matrix; every capture-ending ordering converges to exactly one commit; authorized informative-only (D-031) |
| Reservation | SpendManager atomic reserve/commit/release (row-locked, concurrency-proven); wiring test: EXECUTING holds reserved_minor>0 with committed_minor=0 |
| Audit | Evidence ledger JCS+SHA256 chain (tamper-evident); RAZORPAY_PAYMENT_VERIFIED event on settlement (M25) |
| Test Mode guard | M09 fail-safe (live prefix rejected in any mode; names-only error reporting); live auth diagnostic 2026-08-24: `mode: test (guard passed)`, credentials accepted read-only |
| Full Phase-1 regressions | Full suite re-run at this gate: 323/323 |

### One reliable start workflow (new)

`make phase2-up` → `scripts/phase2_start.sh` (idempotent, non-destructive,
never prints secrets): infra up → wait postgres/redis → alembic head →
idempotent seed → config guard (names only) → API :8000 → web :3000 → zrok
tunnel (reuses live share or starts a new one with explicit Dashboard/.env
update instructions) → local+public `/ready` verification. Proven live this
milestone: all 7 steps green, `payment_provider=razorpay`, `mock=false`,
tunnel live at the registered share URL.

### Gate run (2026-08-24, this milestone)
```text
pytest (full)                      → 323 passed
make lint (ruff format+check+eslint) → clean
mypy strict (root + services/api)  → no issues in 52 source files (both)
pnpm typecheck / test / build      → clean / 6 passed / OK (6 routes)
playwright                         → 2 passed
make security-check                → PASS (secret scan 0; pip-audit clean; pnpm audit clean)
scripts/phase2_start.sh            → all steps green; local+public /ready honest (razorpay)
scripts/rzp_auth_check.py          → ok, credentials accepted (read-only), test guard passed, 1 order listed
```

### Real Razorpay interaction
- READ_ONLY only (auth diagnostic GET /orders?count=1). No orders/payments
  created this milestone.

### Carried into M38 (per D-032)
- M38 gate evidence MUST include ≥1 REAL signed webhook event in
  provider_events (verified=true, event_id not matching `evt_ok_*`).

### Next
- M38 HUMAN GATE: one official Test Mode success checkout (R-017 instruments:
  `success@razorpay` UPI), then end-to-end verification incl. the deferred
  signed-delivery proof.

---

## M38 — HUMAN GATE — Real Test Success

MILESTONE: M38
STATUS: PASS (payment #3 end-to-end exactly-once proven; D-032 obligation met
by payments #2 + #3 — 7 REAL signed deliveries verified=true)
REAL RAZORPAY INTERACTION: TEST_CHECKOUT (human, payments #2/#3) + WEBHOOK
(7 real signed deliveries accepted) + READ_ONLY (order/payment fetches)

Full working evidence record: `docs/PHASE2_M38_EVIDENCE.md`; final
reconciliation: `docs/PHASE2_M39_EVIDENCE_RECONCILIATION.md` (M39).

### What payment #2 proved (durable, captured BEFORE any test run)

- Human success checkout ~18:10 UTC (Test Mode, success@razorpay):
  attempt `exa_01M0TFCS608MSJ59GHHVJ5NP8E`, order `order_TThUuhmUinebAX`,
  payment `pay_TThVaPlcLqu4XE`, 239800 INR minor.
- THREE real signed webhook deliveries accepted (first ever — D-032
  obligation content), all verified=true, PROCESSED, correlated to the
  order/payment:
  - `TThVgbHU0l5E7y` payment.authorized 18:10:03.115688+00
  - `TThVhMzdj2zNfo` payment.captured  18:10:03.274933+00
  - `TThVilsyhg1VWm` order.paid        18:10:04.994904+00
  (payload_sha256 recorded in the evidence doc; event ids do not match the
  `evt_ok_*` fixture pattern and share the ULID time-prefix of the provider
  entities created at transaction time.)
- Human-observed: three webhook POSTs → HTTP 200 immediately after
  `/buyer/execute`; `/buyer/callback` → 200.
- Provider-side READ-ONLY fetch (new typed `fetch_payment`/`fetch_event`):
  order status=`paid`, payment status=`captured`, both 239800 INR; receipt
  `r_exa_01M0TFCS608MSJ59GHHVJ5NP8E` ties the provider order to the attempt.
  Events API 404 for this account (R-018) — event reality rests on HMAC +
  correlation + Dashboard delivery logs.
- Older payment-#1 retry deliveries still 403 SIGNATURE_INVALID (signed with
  the pre-correction Dashboard secret): pre-verification rejection, zero
  mutation, as designed.

### Defects found and fixed this milestone (D-033)

1. CRITICAL — webhook reducer built WITHOUT SpendManager: the captured event
   settled the attempt SUCCEEDED but skipped reserved→committed
   (reservation stranded at 239800/0). Fixed: `_reducer()` wires
   SpendManager; regression `test_webhook_route_wiring_commits_reservation`
   drives the REAL route + wiring and pins committed exactly once.
2. Audit truthfulness — attempts recorded provider_name 'mock' (column
   default) for real Razorpay runs. Fixed: `PaymentProvider.name` protocol
   member; wiring test asserts 'razorpay'.
3. CRITICAL (process) — ~12 test files reach the dev DB through
   `get_settings()` (reads root `.env`); the post-payment gate run
   (18:26–27 UTC) wiped the dev business tables and destroyed payment #2's
   attempt/spend/audit rows BEFORE capture — same class of loss as payment
   #1. Fixed permanently: conftest env pinning (env vars beat dotenv;
   credentials pinned EMPTY), dedicated `razormesh_test` DB, session-scoped
   autouse isolation guard (TESTING.md §15). Verified: full 329-test suite
   left the dev DB byte-identical; fixture residue only in razormesh_test.
4. Classification — verified-but-unmatched events surfaced as generic
   PROCESSING_ERROR; restored M31-documented UNMATCHED_CONTEXT + inbox state
   UNMATCHED (regression-tested; live-proven by signed probe).

### Non-fabrication statement (payment #2 spend leg)

The exactly-once reserved→committed transition for payment #2 is UNPROVEN:
the commit never ran (Defect 1), and the stranded reservation row was
destroyed by the pre-isolation test run before the guarded one-time repair
(`scripts/repair_m38_spend_commit.py`) could be applied — the script now
refuses (target row absent; exit 1, recorded). No financial state has been
or will be reconstructed manually; the loss is disclosed, not patched over.

### Gate run on fixed + isolated stack (2026-08-24)

```text
ruff format --check / ruff check       → clean / clean
mypy strict (root + services/api)      → no issues in 52 source files (both)
pytest (full)                          → 329 passed; dev DB byte-identical
pnpm lint / typecheck / test           → clean / clean / 6 passed
playwright                             → 2 passed
make security-check                    → PASS (one new documented allowlist entry)
scripts/webhook_live_probe.py (public) → 200 UNMATCHED_CONTEXT, zero mutation
                                         (also proves live process reloaded fixes)
scripts/rzp_m38_evidence.py            → order paid / payment captured (READ_ONLY)
```

### Payment #3 close-out (2026-08-24 19:08–19:11 UTC, evidence captured BEFORE any test run)

Human success checkout (success@razorpay): intent
`intent_01M0TJSMR51H1GVBDWFYKTDRDQ` → RazorGuard ALLOW → ticket
`tk_01M0TJSRRF59BEPPK1HQTSCM47` (single-use: used_at == attempt creation) →
attempt `exa_01M0TJST9KD53EBCP4WMWNRZ5X` → order `order_TTiVopXKuCg5ol`
(479900 INR minor). Live sequence incl. documented Razorpay semantics
(P2-S16/R-014): first payment `pay_TTiWRlfGgjviWU` FAILED (19:09:28,
reservation released, audited) → retry payment `pay_TTiY0Ny3rAEN9H`
authorized/captured (19:11:02) → guarded FAILED→SUCCEEDED reconciliation
committed the reservation exactly once (spend version 4: ensure→reserve→
release→commit; final reserved=0, committed=479900) →
RAZORPAY_RECONCILED_LATE_CAPTURE audited → order.paid + verified browser
callback (19:11:13) idempotent no-ops. Attempt: SUCCEEDED, ELIGIBLE,
RESOLVED, provider_name=razorpay, callback_verified_at set. Audit chain
verified live: valid=true, 7 events. Provider-side READ-ONLY fetch matches
local state exactly (order paid; failed payment failed; retry payment
captured; receipts bind order→attempt). The commit was performed by the
FIXED live webhook path — no repair script.

Fourth real delivery note: payment #3's authorized event arrived while the
attempt was FAILED and exposed a D-031 semantics gap (authorized only
no-op'd in EXECUTING). Zero mutation / no settlement impact; fixed to
informative-only in EVERY state + regression
`test_authorized_is_informative_in_every_state` (D-034). The ERROR inbox row
is preserved as the append-only record.

### Gate run at PASS

```text
ruff format --check / ruff check → clean / clean
mypy strict (root + services/api)→ no issues in 52 source files (both)
pytest (full)                    → 330 passed; dev business rows unchanged
/audit/verify (live)             → valid=true, events_checked=7
scripts/rzp_m38_evidence.py      → orders paid / payments failed+captured (READ_ONLY)
```

### Next
- M39 success evidence reconciliation (closed immediately after; see below).

---

## M39 — Success Evidence Reconciliation

MILESTONE: M39
STATUS: PASS
REAL RAZORPAY INTERACTION: READ_ONLY (order/payment fetches only)

Deliverable: `docs/PHASE2_M39_EVIDENCE_RECONCILIATION.md` — safe-identifier
reconciliation of DB ↔ read-only provider fetches ↔ webhook inbox ↔ audit
chain ↔ human-observed Dashboard facts for payments #2 and #3.

### Reconciliation highlights

- Provider-side fetches match local durable state on every field for both
  payments (statuses, amounts, order↔payment↔attempt binding via receipts).
- 7 REAL signed deliveries in provider_events (verified=true; payload hashes
  stored); event reality established via raw-body HMAC + ULID time-prefix
  identity + correlation + Dashboard 200s (Events API 404 for this account —
  R-018, documented as honest limitation).
- Audit chain valid (7 events) covering the full payment #3 lifecycle incl.
  failure release and guarded late-capture commit.
- Exactly-once reservation semantics proven end-to-end for payment #3
  (version history 4 steps, single commit); payment #2's destroyed rows and
  skipped commit disclosed, not reconstructed (D-033).
- Callback/webhook race resolved correctly in production (callback after
  webhook settlement = idempotent no-op).

### Validation

```text
scripts/rzp_m38_evidence.py → all fetches consistent (READ_ONLY)
/audit/verify (live)        → valid=true, events_checked=7
pytest (full)               → 330 passed (no code change this milestone
                               beyond M38's authorized fix, already gated)
```

### Known limitations
- Recorded in the reconciliation doc §8 (Events API, payment #2 rows, one
  disclosed ERROR inbox row).

### Next
- M40 HUMAN GATE — Real Test Failure (failure@razorpay or sub-4-digit OTP;
  expect no fulfilment, reservation released, audited).
