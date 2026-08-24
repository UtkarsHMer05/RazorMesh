# PHASE2_MILESTONES.md — Phase-2 Gated Plan (Razorpay Test Mode)

## Rule

Exactly one milestone active at a time. Every milestone follows the universal
gate in the Phase-2 master prompt (§14) and updates `PHASE2_STATUS.md` +
`MEMORY.md` before the next. Local commit only after PASS. Phase-1 history in
`MILESTONES.md` / `PHASE1_STATUS.md` is preserved untouched.

Source: human-approved Phase-2 master prompt (2026-08-24). Test Mode only;
Live Mode forbidden (P2-S01/S02).

| # | Milestone | Summary |
|---|---|---|
| M01 | Repository & Governance Integrity Re-read | Git/governance inspection, `.env` ignored, secret-hygiene sweep, Phase-2 status scaffold |
| M02 | Phase-1 Full Quality Revalidation | Ruff/mypy/pytest/frontend/vitest/playwright/security-check/benchmark smoke re-run |
| M03 | Phase-1 Security Invariant Revalidation | Focused security suite incl. races, forged tickets, tamper |
| M04 | Phase-1 Clean-Room Acceptance Re-run | Fresh volumes → migrate → seed → API → acceptance script |
| M05 | Freeze Phase-2 Baseline | Baseline doc: HEAD, counts, versions, migration head, no-Razorpay-yet statement |
| M06 | Live Razorpay Documentation Research | Auth, Orders, Standard Checkout, signatures, webhooks, event semantics, SDK; RESEARCH.md |
| M07 | Provider Client & Dependency Decision | SDK vs project HTTP client; pin; retry policy; DECISIONS entry |
| M08 | Root `.env` / Typed Config Reconciliation | Provider selector + typed Razorpay settings; `.env.example` placeholders |
| M09 | Razorpay Test-Mode Fail-Safe | Require test mode, reject live keys, refuse missing creds, keep mock usable |
| M10 | Phase-2 Governance Transition | PHASES/PRD/ARCHITECTURE/SECURITY/TESTING/DECISIONS/VERSION_MANIFEST/RESEARCH/MEMORY updated |
| M11 | Razorpay Provider Skeleton | RazorpayPaymentProvider behind PaymentProvider; DI seams; no creds to buyer layer |
| M12 | Safe Auth Diagnostic | Read-only credential check against real Test keys; redacted logging |
| M13 | DB Schema for Razorpay Correlation | Migration: provider fields, order/payment/event IDs, verification state; up/down tested |
| M14 | Internal→Razorpay Order Mapping | receipt/notes correlation rules within documented limits; no secrets/PII |
| M15 | Server-Side Order Creation | Trusted-path order create; server-authoritative amount/currency; unknown mapping |
| M16 | Razorpay Error Taxonomy | Explicit error classes/states; no blanket 500; timeout ≠ failure |
| M17 | First Real Test Order | One low-value real order via trusted path; verify correlation + fetch; regression after |
| M18 | Order Fetch & Reconciliation | Fetch-by-order-ID validation vs internal authority; conflicts fail loudly |
| M19 | Checkout Launch Contract | Backend payload: public key ID + order ID + amount/currency; never secrets |
| M20 | Checkout Script Integration | Official Checkout script loading strategy in Next.js; no secrets in bundle |
| M21 | Real Checkout UI | Trust-first TEST MODE screen; Pay asks backend for launch payload |
| M22 | Client Success Handler | Forward payment/order/signature only; VERIFYING state; no browser finality |
| M23 | Server Checkout Signature Verification | HMAC via server-stored order ID; established util or correct HMAC |
| M24 | Callback Adversarial Tests | Forged/mutated/replayed/wrong-context callbacks never commit |
| M25 | Post-Callback Provider Verification | Fetch/captured evidence before fulfilment eligibility |
| M26 | Provider State Reducer | One idempotent reducer over callback/fetch/webhook; separated state dimensions |
| M27 | payment.authorized Handling | Informative-only or justified exclusion per current docs |
| M28 | payment.captured Handling | Exactly-once reservation commit; dedup; audit |
| M29 | payment.failed Handling | Verified failure without foreclosing later capture reconciliation |
| M30 | order.paid Handling | Correlated success evidence; never a second fulfilment trigger |
| M31 | Raw-Body Webhook Endpoint | Raw bytes before parse; size limits; zero mutation pre-verification |
| M32 | Webhook Signature Verification | HMAC-SHA256 raw-body; mutation/reserialization/wrong-secret tests |
| M33 | Durable Webhook Inbox & Dedup | Unique provider event ID; concurrent duplicates = one effect |
| M34 | Ordering & Reconciliation Tests | All permutations converge safely; no double commit/fulfilment |
| M35 | Public Webhook Tunnel Preparation | zrok/current guidance config; scripts/docs; gate if install/login needed |
| M36 | HUMAN GATE — Webhook Dashboard | Human configures webhook with existing secret; one real signed event verified |
| M37 | Real Success Checkout Readiness Gate | Full readiness checklist green before asking human to pay |
| M38 | HUMAN GATE — Real Test Success | Guided success checkout; end-to-end exactly-once verification |
| M39 | Success Evidence Reconciliation | Safe evidence doc reconciling DB/audit/fetch/webhook/Dashboard |
| M40 | HUMAN GATE — Real Test Failure | Guided failure checkout; no fulfilment; reservation semantics correct |
| M41 | Provider-Unknown / Timeout Reconciliation | Local fault injection; identity+reservation held; reconciliation path |
| M42 | Real-Provider Concurrency & Replay Regression | Races via mock/fake at volume; real-provider semantics unchanged |
| M43 | Security Lab Phase-2 Expansion | Defensive callback/webhook/dedup/out-of-order scenarios, labeled synthetic |
| M44 | Audit & Evidence Ledger Upgrade | Safe provider IDs/events into hash-chained ledger; no secrets |
| M45 | Buyer UI Trust-State Polish | TEST MODE labeling; VERIFYING/CAPTURED/FAILED/PROVIDER_UNKNOWN states |
| M46 | Automated E2E w/ External Checkout Boundary | Stubbed Checkout for CI; real M38/M40 evidence preserved |
| M47 | Phase-2 Performance & Network Baseline | Local vs provider/network latency separation; samples + caveats |
| M48 | Full Phase-2 Security & Dependency Gate | Everything: suites, audits, leak checks, Live refusal, .env ignore |
| M49 | Phase-2 Clean-Room Acceptance | Disposable-state reproduction incl. mock suite + safe real auth/order checks |
| M50 | Completion Report, Phase-3/4 Prep, STOP | docs/PHASE2_COMPLETION_REPORT.md; interfaces only for P3/P4; stop for approval |

Human gates embedded: M36 (webhook dashboard), M38 (real success), M40 (real
failure), conditional D (capture settings) / E (tunnel install) as encountered.
