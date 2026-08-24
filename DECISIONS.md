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
