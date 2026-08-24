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
| M07 | Provider Client & Dependency Decision | NOT_STARTED | — |
| M08 | Root `.env` / Typed Config Reconciliation | NOT_STARTED | — |
| M09 | Razorpay Test-Mode Fail-Safe | NOT_STARTED | — |
| M10 | Phase-2 Governance Transition | NOT_STARTED | — |
| M11 | Razorpay Provider Skeleton | NOT_STARTED | — |
| M12 | Safe Auth Diagnostic | NOT_STARTED | — |
| M13 | DB Schema for Razorpay Correlation | NOT_STARTED | — |
| M14 | Internal→Razorpay Order Mapping | NOT_STARTED | — |
| M15 | Server-Side Order Creation | NOT_STARTED | — |
| M16 | Razorpay Error Taxonomy | NOT_STARTED | — |
| M17 | First Real Test Order | NOT_STARTED | — |
| M18 | Order Fetch & Reconciliation | NOT_STARTED | — |
| M19 | Checkout Launch Contract | NOT_STARTED | — |
| M20 | Checkout Script Integration | NOT_STARTED | — |
| M21 | Real Checkout UI | NOT_STARTED | — |
| M22 | Client Success Handler | NOT_STARTED | — |
| M23 | Server Checkout Signature Verification | NOT_STARTED | — |
| M24 | Callback Adversarial Tests | NOT_STARTED | — |
| M25 | Post-Callback Provider Verification | NOT_STARTED | — |
| M26 | Provider State Reducer | NOT_STARTED | — |
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
