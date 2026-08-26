# DECISIONS.md — RazorMesh Trust Decision Log

## Policy

This file is an append-only decision record.

- Never delete historical accepted decisions.
- Never silently edit a historical decision to make history look cleaner.
- If a decision changes, create a new decision with `Supersedes: D-XXX`.
- Update affected source-of-truth documents in the same milestone.
- Every entry includes context, decision, rationale, consequences and evidence.
- `DECISIONS.md` cannot override `RULES.md`, `PRD.md`, `PHASES.md` or `SECURITY.md` without explicit human approval and synchronized edits.

## Template

```text
## D-XXX — Title
Date:
Milestone:
Status: Proposed | Accepted | Superseded | Rejected
Supersedes:
Affected docs:

Context:
Decision:
Rationale:
Alternatives considered:
Security/product consequences:
Validation/evidence:
Follow-up:
```

---

## D-001 — Phase 1 is credential-free

Date: 2026-08-23  
Milestone: Governance/bootstrap  
Status: Accepted

Context: The trust core should be debugged independently of external accounts.

Decision: Phase 1 uses local fixtures, a mock buyer and `MockPaymentProvider`. No Razorpay/LLM/Modal/Colab credentials are required.

Rationale: Separates trust/security bugs from external integration failures and keeps Phase 1 reproducible.

Consequences: Real Razorpay and AI/ML integrations are deferred to later phases.

---

## D-002 — Modular monolith for Phase 1

Date: 2026-08-23  
Status: Accepted

Decision: Prefer one modular backend/API deployment boundary instead of multiple microservices during Phase 1.

Rationale: Reduces operational complexity while preserving module interfaces for later extraction.

---

## D-003 — Money uses integer minor units

Date: 2026-08-23  
Status: Accepted

Decision: All money is `(amount_minor: integer, currency)`.

Rationale: Avoid floating-point financial errors and make canonical hashing predictable.

---

## D-004 — PostgreSQL is durable financial/security authority

Date: 2026-08-23  
Status: Accepted

Decision: Durable intent, authorization generation, decisions, spend, execution attempts, payment state and audit live in PostgreSQL.

Rationale: Redis coordination must not be the sole durable truth.

---

## D-005 — Redis is ephemeral coordination

Date: 2026-08-23  
Status: Accepted

Decision: Redis is used for nonce claims, short-lived locks and cache/coordination only.

---

## D-006 — Three-way RazorGuard decision

Date: 2026-08-23  
Status: Accepted

Decision: RazorGuard returns ALLOW, CHALLENGE or BLOCK.

Rationale: Ambiguity should not automatically become fraud nor automatically become approval.

---

## D-007 — Deterministic hard authorization

Date: 2026-08-23  
Status: Accepted

Decision: Amount, merchant, currency, quantity, expiry, recurring permission, aggregate budget, ticket/context and replay checks are deterministic.

Rationale: Probabilistic AI must not be the final authority over financial side effects.

---

## D-008 — Execution ticket separates proposal from side effect

Date: 2026-08-23  
Status: Accepted

Decision: The buyer/agent cannot directly invoke `PaymentProvider`. RazorGuard authorization produces a signed execution ticket consumed by a trusted executor.

---

## D-009 — Ed25519 Phase-1 signing

Date: 2026-08-23  
Status: Accepted

Decision: Use Ed25519 via established libraries for local execution-ticket signing.

Rationale: Simple modern asymmetric signing suitable for local issuer/verifier separation.

---

## D-010 — Strong ticket context binding

Date: 2026-08-23  
Status: Accepted

Decision: Tickets bind principal, agent, intent hash, authorization generation, authorization-relevant checkout hash, merchant, amount, currency, decision, policy version, nonce and expiry.

Rationale: Prevent context theft, stale authorization and cross-principal/agent/merchant reuse.

---

## D-011 — Canonical authorization hashing

Date: 2026-08-23  
Status: Accepted

Decision: Use an explicit deterministic canonical JSON strategy, preferably RFC 8785/JCS-compatible semantics where practical.

Rationale: Avoid accidental cross-language hash disagreement.

---

## D-012 — Hash only authorization-relevant checkout projection

Date: 2026-08-23  
Status: Accepted

Decision: Checkout authorization hash excludes purely presentational metadata and includes authority-sensitive product/merchant/financial/recurring terms.

Rationale: Prevent both stale-authority execution and unnecessary invalidation on irrelevant UI metadata changes.

---

## D-013 — Spend reservation lifecycle

Date: 2026-08-23  
Status: Accepted

Decision: Aggregate authorization uses authorized/reserved/committed semantics.

Rationale: A failed provider attempt must not permanently consume budget; an unknown outcome must not release budget too early.

---

## D-014 — Durable execution attempts

Date: 2026-08-23  
Status: Accepted

Decision: A durable `ExecutionAttempt` is created/tracked for provider side-effect attempts with states including CREATED, EXECUTING, PROVIDER_UNKNOWN, SUCCEEDED and FAILED.

Rationale: Timeout-after-success cannot safely be treated as "nothing happened".

---

## D-015 — Unknown provider outcome must reconcile

Date: 2026-08-23  
Status: Accepted

Decision: A provider-unknown outcome is not retried as a fresh payment operation. The original execution identity is preserved and reconciled.

---

## D-016 — Audit is append-oriented and tamper-evident

Date: 2026-08-23  
Status: Accepted

Decision: Application exposes append/create only for audit events; historical content is hash-chained; DB mutation restrictions are applied where practical.

Rationale: Detect and discourage historical tampering without falsely claiming absolute immutability.

---

## D-017 — Stateful/property-based security testing

Date: 2026-08-23  
Status: Accepted

Decision: Hypothesis stateful testing will exercise authorization/payment lifecycle sequences in addition to example-based tests.

---

## D-018 — Real concurrency tests are mandatory

Date: 2026-08-23  
Status: Accepted

Decision: Replay and aggregate-spend guarantees must be tested with actual concurrent attempts, including a many-worker same-ticket case.

---

## D-019 — Design follows RazorSense principles, not a deceptive clone

Date: 2026-08-23  
Status: Accepted

Decision: Use Razorpay's public RazorSense/Blade principles and components/tokens where compatible, while clearly presenting RazorMesh as an unofficial hackathon prototype and not inventing proprietary brand specifications.

Rationale: Strong Razorpay fit without pretending official endorsement.

---

## D-020 — Phase-1 benchmark is synthetic and paired

Date: 2026-08-23  
Status: Accepted

Decision: Use safe/unsafe paired scenarios, compute real metrics, and label all monetary impact as synthetic benchmark GMV.

Rationale: Prevent a "block everything" system from appearing safe and avoid fake merchant-impact claims.

---

## D-021 — Git behavior for this repository

Date: 2026-08-23  
Milestone: M05 (recorded), effective from repo init  
Status: Accepted  
Affected docs: `RULES.md` (Git section), `AI_WORKFLOW.md`

Context: The governance pack says commits require explicit authorization. The human owner explicitly authorized "init git + commit per milestone" in the planning session that postdates the pack.

Decision: Initialize git in the repository root; create one coherent local commit per milestone whose gate has genuinely passed. Never push, force-push, or rewrite history. If the owner revokes this, stop committing immediately and keep evidence in files only.

Rationale: Checkpointed history protects against accidental loss while keeping every commit tied to verified state.

Alternatives considered: no commits at all (weaker protection); commit-per-file (noise).

Security/product consequences: None on runtime; improves auditability of engineering process.

Validation/evidence: `git log` shows one commit per PASS milestone.

Follow-up: Re-confirm at any human gate if ambiguous.

---

## D-022 — Razorpay Blade not selected for Phase 1 UI; fallback tokens used

Date: 2026-08-23  
Milestone: M05  
Status: Accepted  
Supersedes: none (refines D-019)  
Affected docs: `DESIGN.md`, `VERSION_MANIFEST.md`, `RESEARCH.md`

Context: DESIGN.md prefers official @razorpay/blade when compatible/appropriate. Live registry evaluation found blade@12.111.0 with web peers styled-components@^5, framer-motion, react-hot-toast (+ RN peers).

Decision: Phase 1 uses the documented RazorMesh fallback design-token layer (`DESIGN.md` §5) with RazorSense-inspired state principles. Blade is deferred to Phase 5 polish unless a compatibility re-check passes cleanly.

Rationale: styled-components v5 under React 19 / Next 16 App Router RSC plus heavy peer stack = material compatibility risk for a trust-critical prototype; custom trust components (DecisionCard, CheckoutDiff…) are the actual product surface.

Alternatives considered: install Blade anyway (risk + weight); partial token import from Blade (still pulls peer deps).

Security/product consequences: No security impact; UI remains serious fintech aesthetic per DESIGN.md gates.

Validation/evidence: VERSION_MANIFEST frontend table records the evaluation; RESEARCH.md R-008.

Follow-up: Re-evaluate Blade in Phase 5 against final React/Next versions.

---

## D-023 — Trusted/untrusted content separation as a hard architectural boundary

Date: 2026-08-23  
Milestone: M05  
Status: Accepted  
Affected docs: `SECURITY.md`, `ARCHITECTURE.md`, `RULES.md`

Context: Buyer-agent output, merchant text, search results and browser state can influence what is proposed, but must never redefine authority.

Decision: Every authorization-relevant field carries provenance (trust classes USER_AUTHORITY / TRUSTED_SYSTEM / VERIFIED_MERCHANT_DATA / UNTRUSTED_CONTENT / DERIVED). Untrusted sources cannot construct or mutate fields consumed by policy, thresholds, nonce/ticket issuance, or executor permissions; the boundary is enforced by typed models and deterministic code paths, not by prompt hygiene.

Rationale: Prompt-injection-resistant by construction; untrusted content stays data.

Alternatives considered: filtering/sanitizing malicious-looking text (unreliable, arms race); trusting merchant "verified" flags without provenance typing.

Security consequences: Direct mitigation for TH-18; enables M40 boundary tests.

Validation/evidence: Provenance model tests (M19) prove untrusted values cannot occupy authority-typed slots.

---

## D-024 — Future AI/model components enter only through interfaces

Date: 2026-08-23  
Milestone: M05  
Status: Accepted  
Affected docs: `ARCHITECTURE.md`

Context: Later phases add an LLM intent compiler and DeBERTa NLI semantic verifier; Phase 1 must remain credential-free and deterministic.

Decision: Define `IntentCompiler` (Phase 1: FixtureIntentCompiler) and `SemanticVerifier` (Phase 1: NullSemanticVerifier, DeterministicScenarioSemanticVerifier) abstractions now. Model outputs may only advise/challenge; they cannot override hard rules or sign tickets.

Rationale: Dependency inversion keeps the deterministic core stable while ML arrives later.

Alternatives considered: retrofitting interfaces after models exist (higher churn); shipping a fake "AI risk score" (forbidden by PRD honesty rules).

Security consequences: Preserves D-007 determinism at the financial boundary.

Validation/evidence: Interface tests in M41; no Transformer dependency exists in Phase 1.

---

## D-025 — Payment provider access isolated behind PaymentProvider interface

Date: 2026-08-23  
Milestone: M05  
Status: Accepted  
Affected docs: `ARCHITECTURE.md`, `SECURITY.md`

Context: Only the trusted executor may cause payment side effects today (mock) and tomorrow (Razorpay test-mode).

Decision: `PaymentProvider` exposes a narrow surface (create/initiate order-like op, execute/confirm payment, query/reconcile, verify event). Phase 1 implements MockPaymentProvider only. The buyer/agent layer never receives the provider object or credentials; FastAPI dependency wiring enforces this structurally.

Rationale: Phase-2 Razorpay adapter becomes an isolated swap; blast radius of provider bugs/failures stays inside the executor path.

Alternatives considered: letting routes call providers directly (violates SEC-001); abstracting too early over hypothetical Razorpay specifics (overfitting risk — interface kept conceptual).

Security consequences: Structural enforcement of SEC-001/SEC-002; supports TH-06/07 containment.

Validation/evidence: M36/M37 tests; architecture test asserts agent modules hold no provider reference.

---

## D-026 — One Next.js application (apps/web) for all Phase-1 surfaces

Date: 2026-08-23  
Milestone: M05  
Status: Accepted  
Affected docs: `ARCHITECTURE.md` §11

Context: The master prompt's structure sketch shows apps/buyer-web + apps/merchant-web, while Milestone 13 defines a single frontend with routes /, /buyer, /merchant, /security-lab, /audit. Human owner confirmed single-app choice during planning.

Decision: Implement one Next.js app at `apps/web` containing all five route areas, matching ARCHITECTURE.md §11. Route folders group buyer/merchant/security-lab/audit surfaces.

Rationale: One build/test/deploy surface for identical placeholder-grade Phase-1 needs; less resource use on the 8 GB host; no cross-app auth to fake.

Alternatives considered: two separate Next.js apps (heavier, no benefit yet).

Security/product consequences: None — authorization never lives in either variant of the frontend.

Validation/evidence: M13 scaffold and M14 Playwright smoke run against the single app.

---

## D-027 — Provider-boundary authority is re-read from durable state

Date: 2026-08-24
Milestone: Phase-1 final validation audit
Status: Accepted
Affected docs: `ARCHITECTURE.md`, `SECURITY.md`, `TESTING.md`

Decision: The trusted executor verifies the signed ticket first, then immediately re-reads the durable authorization, checkout and decision from PostgreSQL. Execution requires an unexpired `AUTHORIZED` intent whose authorization hash still matches, an exactly rebuildable checkout whose hash still matches, and the ticket's current durable `ALLOW` decision. The idempotency identity is derived from the signed ticket ID, never accepted from a caller.

Rationale: Signature validity alone proves who issued a ticket, not that its underlying authority is still current. Durable revalidation at the provider boundary closes forged-state, supersession and stale-decision paths.

Security consequences: Strengthens SEC-001, SEC-003–016 and Intent-to-Execution Integrity. Invalid or replayed requests cannot create an execution attempt or reserve spend.

Validation/evidence: Executor and buyer-API regression tests cover blocked authority, non-ALLOW durable decisions, forged tickets, replay and current checkout reconstruction; live 20-worker acceptance produces one provider effect.

---

## D-028 — Execution reservation and settlement follow the provider-effect boundary

Date: 2026-08-24
Milestone: Phase-1 final validation audit
Status: Accepted
Affected docs: `ARCHITECTURE.md`, `SECURITY.md`, `TESTING.md`

Decision: Durable capacity is synchronized to the current authorization amount without erasing reserved/committed spend, then reserved only after ticket and PostgreSQL authority validation. A lowered authorization below already consumed/held capacity fails closed. Pre-provider setup failures atomically close any created attempt as `FAILED`, release its reservation and release its nonce. Success/failure reconciliation updates attempt state and spend in one PostgreSQL transaction; `PROVIDER_UNKNOWN` retains the reservation until explicit reconciliation. PostgreSQL constraints enforce `reserved + committed <= authorized`, and each signed ticket may identify only one durable attempt.

Rationale: Reservation before authentication leaked authority on forged/replayed requests, while non-atomic settlement could make attempt and financial state disagree.

Security consequences: Preserves budget authority during failures, replays, concurrency and ambiguous provider outcomes without blind retries.

Validation/evidence: Migration `d8b412f091c3` round-trips; schema, executor, spend, reconciliation and concurrency tests pass.

---

## D-029 — Public audit tamper demonstration is non-mutating

Date: 2026-08-24
Milestone: Phase-1 final validation audit
Status: Accepted
Affected docs: `SECURITY.md`, `DESIGN.md`, `TESTING.md`

Decision: `/audit/tamper-test` computes and verifies a hypothetical changed event hash in memory. It never disables database protections and never updates or deletes the real evidence ledger.

Rationale: A public demonstration endpoint must not contain a privileged path capable of altering financial evidence, even if it attempts to restore the original row afterward.

Security consequences: The demo still proves hash-mismatch detection while the durable audit chain remains unchanged and valid.

Validation/evidence: API tests assert detection, unchanged event count and a valid chain before and after simulation; live acceptance confirms the same.

---

## D-030 — Razorpay access uses the project-standard httpx client, not the official SDK

Date: 2026-08-24
Milestones: Phase-2 M07
Status: Accepted
Affected docs: `ARCHITECTURE.md`, `VERSION_MANIFEST.md`, `RESEARCH.md` (R-015)

Decision: All Razorpay HTTP interaction goes through one thin project wrapper over
httpx 0.28.1 (already locked, latest stable, no known advisories). The official
`razorpay` Python SDK (2.0.1) is deliberately NOT selected. Signature verification
(callback and webhook) uses Python stdlib hmac/hashlib implementing exactly the
officially documented formulas.

Rationale:
1. Exact per-call timeout control is required so a mutating call can never be
   silently re-sent by a library-level retry helper (master prompt §27; P2-S19).
   The SDK exposes opt-in automatic retries (`enable_retry`) which is a standing
   foot-gun for order creation.
2. No new dependency or transitive supply chain: the SDK pulls `requests`;
   httpx is already pinned/audited in this repo.
3. Only two endpoints are needed (create order, fetch order) — documented REST
   semantics fit a small wrapper with typed errors better than a Beta-classified
   general SDK.
4. Verification formulas are fully specified by current docs as plain HMAC-SHA256;
   stdlib implementation keeps the security-critical path inspectable and testable.
5. httpx offers deterministic fault injection (MockTransport) for the failure matrix.

Security consequences: Preserves P2-S17..S19 (timeout≠failure; unknown retains
reservation; no blind retry), SEC-001 boundary unchanged — buyer/agent layers never
receive the client or credentials. Error taxonomy maps httpx exceptions to explicit
internal provider-error classes (M16).

Validation/evidence: R-013/R-014/R-015 research entries; wrapper tests use
httpx.MockTransport fixtures including timeout-before-response and
timeout-after-send cases; blanket-retry absence asserted by code review test.

---

## D-031 — payment.authorized is subscribed as informative-only

Date: 2026-08-24
Milestones: Phase-2 M27
Status: Accepted
Affected docs: `ARCHITECTURE.md`, `TESTING.md`

Decision: The webhook/event subscription INCLUDES `payment.authorized`, but the
reducer treats it strictly as an informative correlation signal. It can never
settle a reservation or set fulfilment eligibility. Rationale from current docs
(R-014): authorized payloads are snapshots that may lag (a payment may already be
captured when the authorized event is processed); Standard Checkout best practices
recommend captured/failed/order.paid for automation.

Security consequences: reinforces P2-S15 (authorized alone never fulfils) and the
M25 rule that only captured/paid evidence settles.

Validation/evidence: reducer tests prove authorized events cannot regress a
SUCCEEDED state nor fulfil an EXECUTING attempt.

---

## D-032 — M36 live signed-webhook delivery proof deferred to M38

Date: 2026-08-24
Milestones: Phase-2 M36, M38
Status: Accepted (explicit human instruction, 2026-08-24)
Affected docs: `PHASE2_STATUS.md`, `MEMORY.md`, `RESEARCH.md` (R-016)

Decision: M36 closes as PASS on the verified Dashboard + tunnel configuration.
The original M36 acceptance line "verify at least one real signed event" is
deferred to M38, where the first controlled real Test Mode transaction will
generate actual payment.authorized / payment.captured / payment.failed /
order.paid deliveries.

Rationale:
1. Human inspection of the live Test Mode Dashboard: the registered webhook
   (Enabled, 4 events) exposes NO "Send test notification" action for this
   account.
2. Current official documentation (R-016, re-checked 2026-08-24): "Test events
   get triggered on a transaction done in the Test mode." The current page
   describes no Dashboard test-notification button.
3. Therefore the only non-fabricated path to a real signed delivery is a real
   Test Mode transaction, which is exactly the content of M38.

Explicit non-fabrication statement: at M36 close, provider_events contains ZERO
real Razorpay deliveries (synthetic `evt_ok_*` fixtures only). Live signed
delivery + raw-body HMAC verification + event-id dedup against a REAL provider
event remains UNPROVEN until M38.

Carried-forward obligation: the M38 gate MUST include, before PASS, at least
one REAL signed event in provider_events (verified=true, event_id not matching
the `evt_ok_*` fixture pattern). If no real signed event arrives during M38,
M38 cannot PASS.

Security consequences: no invariant weakened. P2-S13/P2-S14 (raw-body HMAC,
durable dedup) remain implemented and covered by signed-fixture tests
(M31–M34); only the live-delivery proof moves from M36 to M38. This deferral
changes evidence timing, not product scope or security behavior; it resolves
the conflict between the original M36 wording and the live Dashboard/docs
reality, per the human owner's explicit instruction.

---

## D-033 — M38 spend-commit defect remediation, test/dev DB separation, unmatched-context classification

Date: 2026-08-24
Milestones: Phase-2 M38
Status: Accepted
Affected docs: `PHASE2_STATUS.md`, `MEMORY.md`, `TESTING.md`, `RESEARCH.md` (R-018),
`docs/PHASE2_M38_EVIDENCE.md`

Context: payment #2 (order_TThUuhmUinebAX / pay_TThVaPlcLqu4XE, 239800 INR
minor) succeeded end to end and three REAL signed webhooks were accepted
(verified=true, PROCESSED). Two defects and one process failure were found:

1. DEFECT A (code): `webhooks._reducer()` constructed the ProviderStateReducer
   WITHOUT a SpendManager, so executor `_settle()` silently skipped the spend
   block: the captured event settled the attempt SUCCEEDED while the
   reservation stayed reserved (committed=0). The callback path's executor was
   correctly wired but lost the settlement race to the webhook.
2. DEFECT B (code): attempts recorded the `provider_name` column default
   'mock' for real Razorpay executions (audit truthfulness).
3. PROCESS FAILURE: ~12 test files build engines from `get_settings()`, which
   reads the real root `.env`; the conftest switch to `razormesh_test` did not
   cover them, so the post-payment gate run wiped the dev business tables and
   destroyed payment #2's attempt/spend/audit evidence before capture (same
   class of loss as payment #1).

Decisions:

1. Webhook reducer wiring now always includes SpendManager; regression
   `test_webhook_route_wiring_commits_reservation` drives the REAL route +
   REAL wiring and pins reserved→committed exactly once.
2. `PaymentProvider` protocol gains `name`; attempts persist the real provider
   name at creation; wiring test asserts it.
3. Hard test/dev separation (permanent gate, TESTING.md §15): conftest pins
   DATABASE_URL/REDIS_URL/PAYMENT_PROVIDER before any razormesh_api import
   (env vars beat dotenv), pins the three Razorpay credential variables to
   EMPTY (an absent var would let the .env values through), and a session-scoped
   autouse guard fails the ENTIRE suite if `get_settings()` resolves the dev
   DB, a non-mock provider, or any Razorpay credential. Verified: full suite
   run left the dev DB byte-identical; fixture residue landed only in
   `razormesh_test`.
4. One-time guarded repair (`scripts/repair_m38_spend_commit.py`) was written
   for the stranded reservation; it REFUSES to run now that its exact guarded
   target row was wiped (exit 1, recorded). No manual SQL was or will be used
   to reconstruct destroyed financial state — the destroyed evidence is
   disclosed, not fabricated, and the exactly-once commit for payment #2 is
   recorded as UNPROVEN. M38 PASS therefore requires one further real success
   checkout (payment #3) against the fixed stack.
5. Verified-but-unmatched webhook events are classified UNMATCHED_CONTEXT
   (response) with inbox state UNMATCHED, restoring the M31-documented
   behavior; generic PROCESSING_ERROR is reserved for true processing
   failures. Regression-tested. This is classification-only: both paths were
   already zero-mutation and returned controlled 200s.
6. Read-only provider evidence fetches (`fetch_payment`, `fetch_event`) added
   to the Razorpay client/provider with the M16 error taxonomy unchanged;
   used by `scripts/rzp_m38_evidence.py`. GET /v1/events{,/{id}} 404 for this
   account (R-018) — event reality is established by HMAC + correlation
   instead.

Security consequences: RULES §financial-correctness 8 ("verified success
commits reservation") was violated in production for payment #2 by Defect A
and is now enforced by route-level regression; P2-S20 strengthened (no
credential can reach the suite even via dotenv); no invariant weakened; no
destroyed evidence reconstructed or claimed.

Validation/evidence: docs/PHASE2_M38_EVIDENCE.md (real event rows + payload
hashes; provider-side paid/captured fetch; live signed probe
UNMATCHED_CONTEXT; 329-test suite with dev DB byte-identical).

---

## D-034 — payment.authorized is informative-only in EVERY attempt state

Date: 2026-08-25
Milestones: Phase-2 M38 (close-out), M39
Status: Accepted
Affected docs: `PHASE2_STATUS.md`, `MEMORY.md`

Context: D-031 subscribed payment.authorized as strictly informative-only,
but the reducer implemented the no-op only for EXECUTING attempts (plus the
generic SUCCEEDED short-circuit). Live M38 evidence (order_TTiVopXKuCg5ol,
2026-08-24 19:11 UTC): the authorized event for the retry payment arrived
while the attempt was FAILED (after payment.failed for the first payment)
and fell through to the reducer's `ValueError("unsupported provider event
kind")`, producing an inbox ERROR row.

Decision: `apply_event` treats `payment.authorized` as informative-only in
EVERY attempt state — the kind check precedes all state-specific branches.
Rationale: authorized payloads are lagged snapshots (R-014); the documented
failed→captured same-transaction flow (P2-S16) implies authorized snapshots
for retry payments can arrive against FAILED (or PROVIDER_UNKNOWN/CREATED)
attempts. An informative signal must never raise, settle, or reconcile.

Security consequences: none adverse — the production error caused zero
business mutation (inbox claimed the event, controlled 200 returned) and no
settlement impact; the change removes spurious ERROR rows and aligns the
implementation with D-031. Authorized still can never settle or fulfil in
any state (regression-tested for EXECUTING, FAILED, and
SUCCEEDED-after-reconcile).

Validation/evidence: regression `test_authorized_is_informative_in_every_state`
(FAILED + late-capture-reconciled SUCCEEDED cases); existing M27/M34 tests
unchanged; full suite 330 passed; the live ERROR inbox row
(`TTiY6VwFdJ22xL`) preserved as the append-only record of the occurrence.
The same live sequence also constitutes the first production demonstration
of the guarded FAILED→SUCCEEDED late-capture reconciliation (P2-S16/M26):
release on failure, then exactly one capacity-checked commit, audited as
RAZORPAY_RECONCILED_LATE_CAPTURE.

---

## D-035 — UI re-syncs payment truth via read-only GET /buyer/status

Date: 2026-08-25
Milestones: Phase-2 M40
Status: Accepted
Affected docs: `PHASE2_STATUS.md`, `TESTING.md` (§14.11), `MEMORY.md`,
`docs/PHASE2_M40_EVIDENCE.md`

Context: the live M40 failure checkout settled correctly server-side
(verified payment.failed webhook → FAILED, reservation released exactly
once, audited), but the buyer page kept showing EXECUTING with a Re-open
button. Root cause: on failure, checkout.js never invokes the success
handler, so no `/buyer/callback` occurs, and the page had no path to
re-read server truth after the modal was dismissed — it rendered its last
local phase, not the backend state.

Decision:
1. Add `GET /buyer/status?intent_id&checkout_id` — strictly READ-ONLY,
   zero mutation, returning the authoritative snapshot (state, attempt_id,
   fulfilment_state, razorpay_order_id, razorpay_payment_status,
   error_code); unknown contexts return a controlled `NO_ATTEMPT`.
2. The buyer page re-syncs from this endpoint on modal `ondismiss` and
   offers a manual "Refresh status from server" action while
   EXECUTING/PROVIDER_UNKNOWN. FAILED renders a truthful note (nothing
   fulfilled, reservation released) and hides Re-open; SUCCEEDED renders
   CAPTURED/PAID. Re-open remains available only while the SERVER says
   EXECUTING (same-order retry, consistent with M21 and the live M38
   payment-#3 failed→retry→captured behavior).
3. The callback's not-captured response re-reads the CURRENT attempt state
   instead of returning its initial pre-lock snapshot, so a webhook
   settling mid-request cannot produce a stale EXECUTING response.

Rationale: the browser is never a source of payment truth (RULES UI §1–3);
UI state must be a view over backend state. Modal dismissal without a
success handler is a normal failure-path event, not an error, and the UI
must converge to server truth without requiring a page reload.

Security consequences: none adverse — the new endpoint is read-only and
secret-free (regression-scanned); it creates no mutation surface and no
authority. Settlement remains exclusively the reducer/executor's job.

Validation/evidence: live endpoint returned FAILED for the M40 attempt;
regressions — `test_status_endpoint_reflects_server_truth_and_is_read_only`
(read-only, no-secret, exactly-once release), two callback race regressions
(callback after failure settlement inert; mid-request settlement reported
fresh), three frontend re-sync vitest cases; full suite 333 passed.

## D-036 — Reconciliation service: receipt discovery, guarded claim, RESOLVED marking (P2-M41)

Context: a Razorpay order-create timeout leaves the attempt PROVIDER_UNKNOWN
with reconcile_state=REQUIRED and — critically — NO razorpay_order_id, because
the response was lost before parsing. Before M41 nothing could recover this:
fetch reconciliation required a known order id, and webhooks for the unknown
order raised ORDER_CONTEXT_MISMATCH (UNMATCHED_CONTEXT) forever. Additionally,
resolve_unknown() never marked reconcile_state=RESOLVED, so webhook-settled
unknowns stayed REQUIRED on any ops view.

Decision:
1. Receipt-based discovery: GET /orders?count=100 (read-only, one bounded page)
   scanned for an exact receipt match `r_{execution_attempt_id}`. Zero or one
   match proceeds; multiple matches raise RAZORPAY_ORDER_CONTEXT_MISMATCH.
2. Guarded claim: a discovered order is persisted onto the attempt ONLY after
   amount/currency validation against durable authority (P2-S06), under the
   partial-unique index (races surface as loud conflicts). Claiming binds
   CORRELATION only; settlement still flows exclusively through the reducer.
   After claiming, later webhooks for that order correlate normally.
3. Fetch-proven capture reduces as order.paid through the ONE idempotent
   reducer; every terminal settlement (including resolve_unknown) marks
   reconcile_state=RESOLVED. Non-terminal fetch results snapshot only.
4. Operator surface: GET /ops/reconciliation/required (read-only listing) and
   POST /ops/reconciliation/{attempt_id} (one safe pass; 404/409 controlled).
   No endpoint creates financial operations or retries order creation.

Rationale: the receipt is durable internal identity embedded at create time
(M14); matching it exactly against provider data is authoritative read
evidence, not a guess. Keeping PROVIDER_UNKNOWN until OUTCOME evidence
(captured/failed) preserves P2-S18/S19 semantics while restoring correlation.

Security consequences: positive — closes an indefinite-stuck state and a
correlation hole without adding any mutation authority outside the executor/
reducer; all new provider reads are bounded and read-only; no secrets touched.

Validation/evidence: services/api/tests/test_reconciliation.py (10 tests) —
timeout→UNKNOWN/REQUIRED/held; re-entry calls==1; discovery miss keeps
identity+reservation; created-snapshot keeps waiting; paid settles exactly-once
+ RESOLVED + ELIGIBLE with duplicate-pass no-op; pre-claim orphan webhook cannot
correlate but post-claim settles once; amount/currency mismatch mutate nothing
and never claim; duplicate receipt conflict; failure resolution marks RESOLVED;
ops listing/pass wiring incl. 404/409. Full suite 343 passed; ruff/mypy strict
(54 files, both roots) clean; security-check PASS.

---

## D-037 — Phase-2 exit audit hardens provider authority and late-capture capacity

Date: 2026-08-25
Milestones: Phase-2 post-completion verification
Status: Accepted
Affected docs: `SECURITY.md`, `ARCHITECTURE.md`, `TESTING.md`,
`PHASE2_STATUS.md`, `MEMORY.md`, `docs/PHASE2_COMPLETION_REPORT.md`

Context: the milestone suite was green, but an independent requirement-by-
requirement audit against the Phase-2 master prompt found missing negative
proofs. A successful order-create response was trusted without validating its
returned identity/amount/currency/receipt/status; callback lookup selected the
latest attempt from browser context instead of an exact server-issued attempt;
captured evidence could settle after authorization or checkout drift; webhook
capture evidence did not carry amount/currency; and `payment.failed` released
capacity even though R-014 records that the same transaction may later capture.
The last behavior allowed a fresh use of the authorization to consume capacity
before the late capture arrived. A correctly signed but structurally malformed
webhook envelope could also raise an uncontrolled server error after HMAC
verification.

Decision:
1. Validate every created or fetched order against durable order id (when
   known), amount, currency and receipt. A create mismatch or unexpected create
   status becomes `PROVIDER_UNKNOWN/REQUIRED` with the reservation held; it is
   never launched. Verified financial webhook events must also match their
   payload amount/currency before reduction; malformed signed envelopes are
   controlled no-ops rather than exceptions.
2. The launch contract includes `execution_attempt_id`; callbacks select that
   exact row and independently match its intent, checkout and server-stored
   order. Immediately before captured settlement, revalidate the ticket-bound
   current authorization generation/hash and checkout revision/hash. Captured
   provider truth against stale authority is retained for reconciliation but
   cannot commit spend or grant fulfilment.
3. A provider `payment.failed` state remains `FAILED/NOT_ELIGIBLE`, but its
   reservation stays held with `reconcile_state=REQUIRED`. Verified later
   capture converts that existing hold to committed exactly once. Capacity is
   released only by a separate explicit terminal resolution that proves no
   later provider effect is possible. Pre-provider definitive rejection keeps
   its existing immediate compensation/release behavior.
4. Razorpay execution accepts only `rzp_test_` key IDs and the official HTTPS
   API base URL. The mock provider remains credential-free.

Rationale: provider/browser data is evidence, not authority. Correlating every
provider observation to the durable execution context and preserving capacity
across an explicitly non-final failure closes both intent-to-execution drift and
late-capture overspend windows without adding a new architecture or provider
dependency.

Security consequences: positive. Wrong-context, stale/superseded, mismatched
amount/currency/order, unexpected create response, replay, and failure-then-
capture capacity reuse now fail closed. Captured provider truth is never hidden,
but stale authority never becomes fulfilment authority.

Validation/evidence: backend suite 375 passed; strict Ruff + mypy clean;
frontend lint/typecheck, 11 Vitest tests, build and Playwright 5/5 passed;
security-check reported zero findings; migration downgrade/upgrade passed on
the dedicated test database; mock live acceptance passed all checks including
20-worker single-effect and Security Lab 22/22; current Test Mode auth passed;
one trusted-path Test order create/fetch returned an exact authority match and
performed no checkout/payment.

## D-038 — Phase-3 model architecture; no Qwen fine-tuning (P3-M08)

Decision: two AI components, strictly separated. (1) Intent Compiler: Qwen
3.8 Max Free via TokenRouter's OpenAI-compatible Chat Completions, used ONLY
to convert trusted human text into a versioned IntentDraft behind strict
Pydantic/domain validation with ONE bounded repair and fail-closed fallback.
(2) Semantic Verifier: DeBERTa-v3 NLI (baseline chosen by frozen evidence at
M30) as a pure-inference classifier with no provider/DB privileges. Qwen is
never fine-tuned in Phase 3; DeBERTa is fine-tuned only on AgentPay-IR and
only replaces the baseline if held-out gold evidence justifies it.

Rationale: master prompt §3/§12; keeps probabilistic components out of the
authority path entirely (AI proposes, RazorGuard authorizes).

Security consequences: enforces P3-S02/S03/S06/S16/S18 by construction.

Validation/evidence: contract tests from M09 onward; context-isolation tests
M12/M42; ablation M46.

## D-039 — Conservative fusion invariant is release-blocking (P3-M08)

Decision: final decision = deterministic hard decision ⊕ semantic action per
the master-prompt matrix — semantics may only STRICTEN. Implemented as a pure
function with an exhaustive matrix test PLUS a property/Hypothesis test
proving no semantic output or probability vector can weaken BLOCK/CHALLENGE.
Any change to fusion requires changing these tests first.

Security consequences: P3-S07/P2 hard-rule supremacy made mechanically
unbypassable.

## D-040 — Data/gold/training/inference policy (P3-M08)

Decisions: (1) AgentPay-IR is synthetic + human-reviewed with full provenance;
Qwen labels are provisional only. (2) A human-reviewed gold set of >=300
stratified examples gates all final model/threshold claims; gold never leaks
into training/tuning. (3) Splits are group-based (template/parent/entity/
lookalike); leakage tests release-blocking. (4) Fine-tuning runs in Google
Colab on the selected baseline with a self-contained reproducible notebook and
hashed frozen inputs; artifact import requires hash+manifest verification.
(5) Local inference first (CPU→MPS→ONNX→quantized); Modal only through the
conditional human gate if measured local inference is genuinely inadequate.
(6) Thresholds calibrated on validation data only, frozen with model/hash/
version, evaluated once on frozen gold.

Security consequences: P3-S09..S14, S20 enforcement strategy.

## D-041 — M15 compiler evaluation on a stratified 90-case sample; full-307 continuation is a pre-M48 obligation (P3-M15)

Date: 2026-08-25
Milestone: P3-M15
Status: Accepted (explicit human instruction, 2026-08-25)
Affected docs: `PHASE3_STATUS.md`, `MEMORY.md`, `TESTING.md` (§15 gate note),
`docs/PHASE3_INTENT_COMPILER_EVAL.md`

Context: master prompt M15 says "run the real compiler on the golden set"
(307 manual-truth cases). Measured free-tier TokenRouter reality: qwen3.8-max
is a thinking model at ~30–250s per case with intermittent 503
hard_concurrency_limit windows (~6–8 cases per 10 minutes when open), so a
full 307-case run costs ~5–7 hours of wall time. The human owner explicitly
asked to reduce the recorded evaluation to ~90 cases.

Decision:
1. The recorded P3-M15 evaluation is a DETERMINISTIC STRATIFIED SAMPLE of 90
   cases: round-robin across all 25 golden-set categories preserving the
   difficulty mix (runner `stratified()`; selection is reproducible from the
   frozen golden set — no randomness).
2. Every reported M15 metric states N=90/307 explicitly with the sampling
   method disclosed (P3-S20 honesty; no implied full-set coverage).
3. The remaining 217 cases are a CARRIED-FORWARD OBLIGATION: the resumable
   runner (`scripts/rzp_run_compiler_eval.py`, no argument = full set)
   completes them before the M48 full Phase-3 gate, where the acceptance
   matrix item "Intent compiler evaluation complete" is re-verified on the
   full 307. M48 cannot PASS on the sample alone.
4. Provider-noise rows (COMPILER_UNAVAILABLE) are never counted as results;
   four hard cases measured under a harness-reduced max_output_tokens=2000
   budget were discarded (preserved in
   `data/phase3/compiler_eval/discarded_budget2000_rows.jsonl`) and
   re-measured at the restored 4000 budget per M10 thinking-model evidence.

Rationale: a stratified sample across all categories is a defensible measured
evaluation when disclosed; the human owner owns scope; the resumable runner
makes full coverage a scheduling matter, not a scientific one.

Security consequences: none adverse — no security invariant is affected by
evaluation sample size; no metric is fabricated or generalized beyond the
measured N; the compiler itself (schema, repair, fail-closed, isolation) is
unchanged and fully unit-tested.

Validation/evidence: `docs/PHASE3_INTENT_COMPILER_EVAL.md` (N=90 metrics +
sampling statement), `data/phase3/compiler_eval/summary.json`,
`data/phase3/compiler_eval/results.jsonl`.

Follow-up: full-307 continuation run before M48; update the eval doc with the
full-set numbers when it completes.

Addendum (same milestone, 2026-08-25) — golden-truth corrections found during
M15 failure analysis, applied transparently (truth accuracy, not score
management): (a) F1 budget-only phrases that explicitly state rupees/₹/INR now
carry currency="INR" instead of "UNSPECIFIED" (applied before sample
measurement); (b) F13-002 "subscribe me to the premium tier monthly" is a
subscription REQUEST, so the contradictory recurring_forbidden=true expectation
was removed and that one case re-measured against corrected truth (passes;
stale row preserved in discarded_stale_truth_rows.jsonl). Golden sha256 moved
eef70c9c… → 9164f04c…. Known gap recorded: after (a), zero golden cases
exercise the currency-unstated → unspecified path; add genuinely
currency-unstated cases in a future golden revision (pre-M48, folds into
M18–M25 dataset work). All details in docs/PHASE3_INTENT_COMPILER_EVAL.md §5/§8.

## D-042 — Human confirmation domain flow (P3-M16)

Context: M16 adds durable draft states and makes human confirmation the ONLY
path to authority (P3-S03). A confirmed draft materializes/supersedes an
IntentContract authorization_generation.

Decisions:
1. **Durable draft table** `intent_drafts` stores every compiler outcome that
   produced a valid payload, with state DRAFT / NEEDS_CLARIFICATION /
   CONFIRMED / REJECTED, the full validated payload (JSONB), source-text hash,
   and compiler provenance (model id, prompt version+sha256, schema version,
   attempts, request ids) for P3-S13 auditability. Raw human text is NOT
   stored — only its SHA256 — so the durable store carries no unnecessary
   secret/PII-bearing prose.
2. **State machine.** A fresh compile yields NEEDS_CLARIFICATION when the
   payload has ambiguities, else DRAFT. Only a DRAFT that is not superseded
   may be confirmed. Confirming transitions DRAFT→CONFIRMED and is the single
   code path that creates/supersedes an IntentContract generation. Rejecting
   transitions DRAFT|NEEDS_CLARIFICATION→REJECTED. CONFIRMED and REJECTED are
   terminal. A new compile/revise for the same (principal, agent) supersedes
   any prior non-terminal draft via `superseded_by` (stale drafts can never be
   confirmed).
3. **Fail-closed authority materialization.** A confirmed draft maps to an
   IntentContract deterministically with the most-restrictive non-inventing
   defaults: currency + max_total from the draft's stated money (a draft with
   no stated max_amount cannot create authority — confirmation is refused);
   aggregate_budget = max_total (no invented larger lifetime budget);
   approval_threshold = max_total; max_quantity = stated quantity_max else 1;
   recurring_allowed = true ONLY if the draft explicitly set
   recurring_forbidden=false, else false; brand/condition restrictions carried
   from the draft when stated. Free-text merchant names are NOT yet resolved to
   typed merchant ids (no resolver exists); allowed_merchant_ids stays None and
   merchant-name enforcement is deferred to the semantic-verifier/fusion phase
   (recorded limitation, revisit at M39).
4. **Idempotency + replay.** Confirmation carries a client nonce stored on the
   draft. Re-confirming an already-CONFIRMED draft with the SAME nonce returns
   the original result without bumping the generation again; a DIFFERENT nonce
   on a confirmed draft is a replay conflict and fails closed. The generation
   bump is tied to the one-time DRAFT→CONFIRMED transition inside a single DB
   transaction (PostgreSQL remains durable authority; Redis uninvolved).
5. **Audit.** INTENT_COMPILED / INTENT_CONFIRMED / INTENT_REJECTED /
   INTENT_DRAFT_SUPERSEDED ledger events carry draft_id, intent_id, generation,
   model/prompt/schema versions — never secrets, never raw human text.

Security consequences: enforces P3-S03 (no authority before confirmation),
P3-S14 (a compiler outage yields no draft and therefore no confirmation path —
outage cannot bypass the human), and preserves P3-S13/P3-S20 auditability.

Recorded limitations: merchant-name→id resolution deferred (semantic layer);
aggregate_budget/approval_threshold use conservative equals-max_total defaults
until a later milestone lets the human state them explicitly.


## D-043 — Overnight execution policy for Phase 3 (human-authorized 2026-08-26)

Human authorized: (1) reduced Qwen candidate volume (~600-800 target, quality
over quota) with resumable/idempotent/hash-cached generation, Retry-After
respect, bounded backoff+jitter, dead-window circuit breaker, no paid-model
fallback, no fabricated outputs; (2) full Colab/training PREPARATION tonight
with zero-shot DeBERTa baseline as PROVISIONAL SemanticVerifier and every
trained-artifact-dependent result marked PENDING_COLAB/PENDING_HUMAN; (3)
complete gold-review PACK generated now with actual review deferred to morning
— machine metrics marked PENDING_GOLD_VALIDATION until then, thresholds tuned
on validation data only; (4) dependency-aware deferred-human-gate mode:
automatable parts proceed with honest PENDING/BLOCKED statuses, a dependency
list of reruns maintained, and no milestone ever marked PASS without its
required evidence. Morning report required (PHASE3_OVERNIGHT_REPORT.md).

Security consequences: preserves P3-S03/S09/S10/S12/S14/S20 verbatim.


## D-045 — Gold review INVALID exclusion label (human-requested, 2026-08-26)

The human gold reviewer gained a fourth action: 4=INVALID/BAD EXAMPLE with a
recorded exclusion reason. Rules:
- existing 1=entailment / 2=neutral / 3=contradiction and E=export unchanged;
- invalid cards are EXCLUDED from gold metrics — never force-labeled;
- existing cards/record IDs/order are preserved byte-for-byte (verified by
  content digest before/after the reviewer upgrade);
- downstream ingestion (dataset_quality.ingest_gold_decisions) splits
  decisions into valid labels vs exclusions (reason mandatory-or-defaulted)
  and unknown record ids are quarantined.

Security consequences: none new; strengthens P3-S09/S12 honesty by preventing
garbage pairs from becoming gold truth.


## D-046 — Select fine-tuned cross-encoder as production SemanticVerifier (P3-M36)

Date: 2026-08-26
Milestone: P3-M36 (fine-tuned vs baseline evaluation)
Status: Accepted
Supersedes: D-044 (provisional baseline B selection) — provisional was
correctly held pending this evidence; baseline B is now retained only as a
documented fallback for parity regression checks.
Affected docs: PHASE3_STATUS.md (M36 row), docs/PHASE3_NLI_FINETUNE_EVAL.md
(new), docs/PHASE3_NLI_FINETUNED_METRICS.json (new), data/phase3/policy/
semantic_thresholds.json (v2 re-frozen with fine-tuned softmax + status
flipped to GOLD_VALIDATED), scripts/rzp_run_e2e_benchmark.py (model
swapped), services/api/src/razormesh_api/semantic_verifier.py (label_map
read from artifact).

Context: D-044 selected baseline B (`cross-encoder/nli-deberta-v3-base`,
Apache-2.0) provisionally because the zero-shot numbers on the frozen val
set (acc 0.637, macroF1 0.607, contra recall 0.704) were the strongest
of the two candidates. M26 (gold review) later exposed that on the 320
human-labeled cards baseline B only reached 56.25% accuracy with 29
unsafe entailments on human contradictions — a large gap. M34 ran
3 epochs of fine-tuning on the frozen_v1 train split (723 records) using
the canonical notebook (transformers 5.15.1, AdamW, lr 2e-5, batch 16,
eval_macro_f1-best model selection). M35 verified the artifact
(`phase3-finetuned.zip` sha256 54d0fa01…, unzipped to
artifacts/models/incoming/phase3-finetuned/, label_map = {0: contradiction,
1: entailment, 2: neutral}, metrics.json: eval_macro_f1 = 0.9826). M36
ran the same harness on val/test/human_gold_heldout and got:

| split | baseline B acc/F1 | fine-tuned acc/F1 | contra recall B → FT |
| val 171 | 0.637/0.607 | 0.982/0.983 | 0.704 → 0.981 |
| test 127 | 0.606/0.589 | 0.984/0.984 | — → 1.000 |
| human_gold_heldout 79 | 0.595/0.554 | 0.937/0.938 | 0.645 → 1.000 |
| unsafe_entail on human contradictions | 8 (heldout) / 29 (all) | 0 / 0 | — |

Decision: select the fine-tuned model as the production
`DebertaNLISemanticVerifier`. Recalibrate thresholds on val with the
fine-tuned softmax (τ_block=0.30, τ_entail=0.40, contra recall 0.9815,
block precision 0.9636, F2=0.978, 2/61=0.033 false blocks on val entail
rows, well within the 0.05 cap). Flip gold_validation_status →
GOLD_VALIDATED. Re-run the e2e benchmark + ablation with the new
verifier; M47 CPU/MPS timing recorded.

Rationale: every P3-S20 number above is traceable to a committed
artifact (`docs/PHASE3_NLI_FINETUNED_METRICS.json`,
`docs/PHASE3_NLI_BASELINE_B_METRICS.json`, `data/phase3/gold/
gold_frozen.json`, `data/phase3/policy/semantic_thresholds.json`). The
fine-tuned model closes the M26 gap (0 unsafe entailments on 31
heldout human contradictions; baseline B had 8/31). The heldout false-
block rate (4/26=0.154) is above the 0.05 calibration cap but
preserves the conservative-fusion invariant: every false block is a
refusal, not an unsafe allow. Calibration is on val; the heldout
behavior is recorded for transparency. License chain: base
cross-encoder/nli-deberta-v3-base is Apache-2.0; gold was never leaked
into training (P3-S09/S12); the training pool (frozen_v1/train.jsonl,
723 records) is template/seed-derived.

Alternatives considered:
- Keep baseline B as production: rejected on safety grounds (29 unsafe
  entailments on human contradictions = release-blocking per
  master prompt §12).
- Re-collect more training data first: unnecessary; val acc already
  0.982, test 0.984, the only known headroom is on adversarial
  lookalikes, addressed by the M41 lab scenarios.
- Train a larger base model: out of Phase-3 scope (D-038 no Qwen
  finetune; transformer budget is 0.2B).

Security/product consequences: P3-S01 (backend-only, no browser
exposure) preserved; P3-S03 (proposal not authority) preserved;
P3-S06/S16 (no payment network) preserved; P3-S08 (fail-closed on any
model error) preserved; P3-S09/S12 (gold never in training) preserved;
P3-S20 (no fabricated numbers) preserved — every cell in the table
above names the committed artifact. model_id in SEMANTIC_VERIFICATION_RUN
audit events now reports `phase3-finetuned-cross-encoder`.

Validation/evidence:
- `docs/PHASE3_NLI_FINETUNED_METRICS.json` (this milestone, generated
  2026-08-26T17:40 UTC)
- `docs/PHASE3_NLI_FINETUNE_EVAL.md` (one-page comparison)
- `data/phase3/policy/semantic_thresholds.json` (semantic-thresholds-v2,
  status GOLD_VALIDATED, recalibration evidence in manifest)
- `docs/PHASE3_END_TO_END_BENCHMARK.json` (re-run with fine-tuned
  verifier: block P=0.977 R=1.000 F1=0.989, 1 conservative unsafe-allow
  on a gold=neutral row)
- direct real-artifact smoke: BLOCK on a clear contradiction
  (p_c=1.000), PASS on a clear entailment (p_e=0.999), model_id
  resolves correctly from the policy manifest

Follow-up: M37 re-freeze + status flip (done in this same turn);
M38 verifier wiring (label_map read from artifact, done in this turn);
M45/M46/M47 e2e re-run (done in this turn); M48/M49 full battery
+ clean-room rerun; M50 completion report.


## D-047 — Prefer bounded OOD diversity and complete provenance over a raw candidate quota

Date: 2026-08-27
Milestone: P3-M20 standalone closure re-audit
Status: Accepted
Affected docs/code: `PHASE3_STATUS.md`, `MEMORY.md`,
`scripts/rzp_generate_candidates.py`, `agentpay_ir.py`,
`candidate_generation.py`, `data/phase3/dataset/candidates/`.

Context: the original resumable live run had produced 150 provisional rows, but
141 were easy budget examples and 9 were easy currency examples. File-order
iteration and index-derived request keys meant an interrupted run produced a
low-diversity prefix and reordering the seed pool changed request identities.
Compact result rows also omitted the source record id, actual reported model,
prompt version and batch id; failures were printed rather than retained.

Decision: keep Qwen labels strictly provisional and make every request identity
stable from prompt version plus source semantic identity. Schedule seed buckets
round-robin with OOD/adversarial families first, persist each successful response
atomically, retain only sanitized failure metadata, and store complete per-row
model/prompt/batch/source/request provenance. A finite high-quality batch is
acceptable; Phase 3 does not claim that reaching an arbitrary 10k count would
improve safety. The closure added 18 live v2 rows, including three each for
injection resistance, safe lookalikes, seller aliases and trial-renewal traps.

Compatibility: the 150 compact legacy rows were deterministically mapped back
to their original seed records and migrated to canonical AgentPay-IR. New
optional provenance fields serialize only when present, preserving byte-exact
regeneration of pre-existing template-truth seed data.

Consequences: M21 remains responsible for rejecting semantically or structurally
bad provisional rows; M22 remains responsible for fuzzy near-duplicate analysis;
M24 must add independent adversarial/OOD families rather than treating these 18
rows or any numerical quota as sufficient final-test evidence.


## D-048 — Make candidate validation a filtering data boundary

Date: 2026-08-27
Milestone: P3-M21 standalone closure re-audit
Status: Accepted
Affected docs/code: `ARCHITECTURE.md`, `SECURITY.md`, `TESTING.md`,
`PHASE3_STATUS.md`, `MEMORY.md`, `dataset_quality.py`,
`rzp_validate_candidates.py`, gold/freeze dataset builders, and
`data/phase3/dataset/candidates/validation/`.

Context: the prior M21 implementation validated one already-parsed record at a
time and checked only basic provenance, degenerate text and three warning-only
family signals. It had no raw JSON/schema batch boundary, malformed-money or
secret/generation-artifact checks, payment-authority misinformation rule,
duplicate-id detection, rejection artifact, quality report, or downstream
enforcement. Therefore it did not satisfy the original milestone gate.

Decision: preserve the raw Qwen candidate file as immutable provisional
evidence, but allow only the deterministic, hash-bound accepted output to enter
gold-pack selection or a frozen dataset. Structural, provenance, secret,
generation-artifact, malformed-money, false-authority, duplicate and clear
family-signal failures are excluded with stable reason codes. Adversarial false
authority text is allowed in the premise (untrusted evidence) but is rejected
if promoted into the hypothesis (claimed human authorization).

Observed result: 167/168 current candidates passed. One generated row claimed
the `safe_lookalike` family while containing only consent and issuer
pre-authorization evidence, so it was correctly excluded as
`lookalike-family-without-identity-signal`. No accepted row had a duplicate id/
content hash, secret-like value or residual generation artifact.

Consequences: filtering is reproducible and order-independent; rejected rows
remain traceable without their raw text being copied into rejection reports.
M22 still owns fuzzy near-duplicate analysis, and M24 must add independent OOD
families rather than relabeling this rejected row.


## D-049 — Curated OOD breadth supersedes adversarial template-volume inflation

Date: 2026-08-27
Milestone: P3-M24 standalone closure re-audit
Status: Accepted
Supersedes: the M24 2k–4k numerical suggestion where it would be satisfied by
deterministic surface siblings; applies the owner's explicit closure instruction
to prefer genuinely new adversarial/OOD families over a meaningless quota.
Affected docs/artifacts: `PHASE3_STATUS.md`, `MEMORY.md`, `ARCHITECTURE.md`,
`TESTING.md`, `docs/PHASE3_ADVERSARIAL_DATASET_REVIEW.md`,
`rzp_build_adversarial.py`, and `data/phase3/dataset/adversarial/`.

Context: the former artifact had 38 hard rows but 32 were minor surface variants
of injection and hidden-renewal templates. It had no neutral relation, covered
only seven AgentPay families and carried no sibling group identity. Inflating
those templates to thousands of rows would worsen evaluation dependence without
adding meaningful OOD evidence.

Decision: use a manually authored curated matrix of 43 independent adversarial/
OOD subfamilies. Each subfamily has exactly three truth-by-construction relations
(entailment, neutral, contradiction), a unique template id and one shared source
group. Cover all 18 semantic families; enforce a <=10% maximum family share,
zero exact/near/cross-class duplicate findings, M21 compatibility and M23 group
integrity. The resulting 129-row artifact is intentionally finite.

Consequences: the expansion is broad, balanced and leakage-aware, but it is
template truth—not human gold and not an untouched final OOD evaluation. It may
enter training/validation only through later freeze gates. The owner-requested
additional untouched human-reviewed OOD set must be constructed and frozen
separately, and no retraining/model selection/calibration may use its labels.
