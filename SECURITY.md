# SECURITY.md — Phase-1 Security Model

## 1. Security objective

Prevent a proposed transaction from producing a payment-like side effect unless:

- human authority is valid;
- the current checkout remains inside that authority;
- the execution context matches;
- authorization capacity is available/reserved;
- the execution authority is valid and unused;
- state has not become stale;
- the trusted executor validates everything at the side-effect boundary.

---

# 2. Primary protected assets

- human authorization;
- authorization budget;
- execution authority;
- merchant/product/checkout integrity;
- payment-like side-effect uniqueness;
- payment/execution state;
- audit evidence;
- signing keys;
- future provider credentials.

---

# 3. Trust model

## Trusted

- confirmed `IntentContract`;
- server-side RazorGuard policy;
- server-side current checkout read;
- PostgreSQL durable state;
- execution ticket signer/verifier;
- trusted Payment Executor;
- audit service.

## Untrusted / lower trust

- browser;
- buyer agent;
- merchant free text;
- product description;
- search/tool results;
- client-computed totals;
- client decisions;
- external model output.

---

# 4. Mandatory invariants

**SEC-001** Buyer/agent cannot call `PaymentProvider` directly.

**SEC-002** Payment Executor rejects missing/invalid ticket.

**SEC-003** Ticket binds principal ID.

**SEC-004** Ticket binds agent ID.

**SEC-005** Ticket binds merchant ID.

**SEC-006** Ticket binds intent hash + authorization generation.

**SEC-007** Ticket binds authorization-relevant checkout hash.

**SEC-008** Ticket binds amount + currency.

**SEC-009** Ticket binds decision/policy version.

**SEC-010** Ticket has nonce + expiry.

**SEC-011** Ticket is single-use.

**SEC-012** Superseded authorization invalidates old ticket.

**SEC-013** Money is integer minor units.

**SEC-014** Checkout total is recomputed server-side.

**SEC-015** Checkout is re-read/revalidated before execution.

**SEC-016** BLOCKED can never execute.

**SEC-017** CHALLENGED cannot execute before valid reauthorization.

**SEC-018** Unknown security-critical data never defaults ALLOW.

**SEC-019** PostgreSQL is durable source of truth.

**SEC-020** Redis loss cannot erase durable authorization/payment truth.

**SEC-021** Aggregate authorization cannot be overspent under concurrency.

**SEC-022** Reservation is committed only on verified success.

**SEC-023** Reservation is released only on definitive failure/cancellation.

**SEC-024** Unknown provider outcome retains reservation.

**SEC-025** Unknown provider outcome is not blindly retried as a fresh operation.

**SEC-026** One execution authority causes at most one provider effect.

**SEC-027** Audit history is append-oriented at application boundary.

**SEC-028** Audit tampering is detectable by verification.

**SEC-029** Untrusted content cannot mutate trusted authorization.

**SEC-030** Secrets/private keys are not committed or logged.

## Provider-boundary enforcement details

- Signature verification precedes every durable reservation or execution-attempt write.
- Immediately before any provider call, the executor re-reads PostgreSQL and requires the current intent to be `AUTHORIZED` and unexpired, the intent and rebuilt checkout hashes to match the ticket, and the durable decision to be the ticket's matching `ALLOW` under the same policy version.
- The durable idempotency identity is derived from the signed ticket ID; callers cannot select it.
- Durable capacity is synchronized to the current intent's aggregate authorization without erasing held/committed spend; lowering authority below already consumed capacity fails closed. PostgreSQL enforces one execution attempt per ticket and `reserved + committed <= authorized` in addition to application row locks.
- A failure before the provider boundary closes any created attempt, releases its reservation and releases the coordination nonce. A provider-unknown result keeps its reservation until an explicit terminal reconciliation updates spend and attempt state atomically.
- The public tamper demonstration never mutates the evidence ledger. It verifies a hypothetical changed record in memory, while database protections continue to prohibit real historical updates/deletes.

---

# 5. Defensive attack scenarios

## T1 Price drift
Initial safe checkout changes above max authority.

Expected: BLOCK/CHALLENGE according to policy; no provider effect.

## T2 Merchant substitution
Seller/merchant changes.

Expected: context/policy failure.

## T3 Quantity manipulation
Quantity exceeds authority.

Expected: BLOCK.

## T4 Subscription insertion
Recurring term appears despite recurring forbidden.

Expected: BLOCK in structured case; future semantic verifier helps with disguised language.

## T5 Authorization expiry
Execution after expiry.

Expected: BLOCK.

## T6 Replay
Same ticket/nonce reused.

Expected: first may succeed; all later uses rejected.

## T7 Concurrent replay
20 workers use same ticket.

Expected: provider effect count exactly 1.

## T8 Cross-principal confused deputy
User B attempts User A ticket.

Expected: context mismatch before provider.

## T9 Cross-agent theft
Agent B attempts Agent A ticket.

Expected: context mismatch.

## T10 Cross-merchant reuse
Ticket issued for merchant A used for B.

Expected: context mismatch.

## T11 Stale checkout
Authorization-relevant checkout projection changes after ALLOW.

Expected: stale decision/ticket rejected.

## T12 Superseded authorization
Generation N+1 created after ticket for N.

Expected: ticket N invalid.

## T13 Approval splitting
Concurrent smaller attempts individually below limit exceed aggregate authorization.

Expected: atomic reservation prevents overspend.

## T14 Provider failure
Provider returns definitive failure.

Expected: reservation released, no fulfilment.

## T15 Timeout after provider success
Provider side effect succeeds but response is lost.

Expected: execution attempt becomes PROVIDER_UNKNOWN or equivalent; reservation held; no blind second payment.

## T16 Duplicate provider event
Same event delivered multiple times.

Expected: idempotent state, no duplicate fulfilment/commit.

## T17 Out-of-order event
Later/final state and delayed earlier event arrive in non-simple order.

Expected: valid state reconciliation, no regression to invalid state.

## T18 Untrusted prompt-like merchant content
Merchant text says "ignore user's budget".

Expected: content remains data; trusted authority unchanged.

---

# 6. AuthorizationRelevantCheckout

Security-sensitive fields must be explicit.

Changing a relevant field invalidates prior authorization context.

Irrelevant UI metadata must not cause false invalidation.

Document exact projection in code and `ARCHITECTURE.md`.

---

# 7. Spend lifecycle

```text
AUTHORIZED CAPACITY
       ↓
atomic reserve
       ↓
RESERVED
  ├─ success → COMMITTED
  ├─ definitive fail → RELEASED
  └─ unknown → RESERVED until reconciliation
```

Concurrency tests are mandatory.

---

# 8. Execution-attempt lifecycle

At minimum:

```text
CREATED
  ↓
EXECUTING
  ├─ SUCCEEDED
  ├─ FAILED
  └─ PROVIDER_UNKNOWN
```

Transitions must be explicit.

A `PROVIDER_UNKNOWN` state is a safety state, not permission to retry.

---

# 9. Canonicalization

Use an explicit deterministic canonical serialization.

Preferred: RFC 8785/JCS-compatible approach where practical.

Test:

- identical semantic object → same hash;
- relevant mutation → different hash;
- irrelevant excluded metadata → same authorization hash;
- invalid numeric/canonical values rejected.

---

# 10. Audit

Audit events include enough information to explain:

- what was authorized;
- what checkout was checked;
- what changed;
- why decision occurred;
- what execution authority was issued/rejected;
- provider attempt/outcome;
- replay/context failures.

Do not log private keys/secrets.

---

# 11. Release-blocking security tests

Phase-1 exit is blocked if any of these occur:

- unauthorized provider invocation;
- second provider effect from same ticket;
- overspend under concurrency;
- cross-context ticket succeeds;
- stale checkout executes;
- old authorization generation executes;
- unknown provider outcome causes blind second payment;
- audit verification fails to detect intentional test tampering;
- BLOCK/CHALLENGE bypass through direct API;
- test failure is hidden/skipped.

---

# 12. Defensive-only rule

Security Lab and benchmark must operate only on the local synthetic system.

Do not scan, exploit or attack real Razorpay, merchants, payment systems or third-party services.

---

# 13. Phase-2 security invariants (Razorpay Test Mode — active)

All Phase-1 invariants (SEC-001..030) remain release-blocking.

**P2-S01** Only Razorpay Test Mode is allowed.
**P2-S02** Live-key prefix (`rzp_live_`) is rejected in any provider mode.
**P2-S03** Key Secret never reaches the browser.
**P2-S04** Webhook secret never reaches the browser.
**P2-S05** Every real Test payment flow uses a server-created Razorpay Order.
**P2-S06** Browser/provider amount, currency and order context is never
authoritative without exact correlation to the durable execution attempt.
**P2-S07** Checkout success signature is verified server-side (HMAC-SHA256).
**P2-S08** Verification uses the SERVER-stored Razorpay order id for the internal execution context.
**P2-S09** Invalid callback signature cannot commit/fulfil.
**P2-S10** Webhook verification uses the raw request body before any parse.
**P2-S11** Invalid webhook signature causes no business mutation.
**P2-S12** Provider event ID dedup is durable (unique constraint).
**P2-S13** Duplicate events produce one business effect.
**P2-S14** Event delivery order is never assumed.
**P2-S15** `payment.captured` + `order.paid` produce exactly one commit/fulfilment effect.
**P2-S16** A verified later capture can reconcile an earlier failure per
Razorpay semantics; failure retains the original reservation until capture or
an explicit terminal resolution, so authorization capacity cannot be reused in
the interim.
**P2-S17** Network timeout is not definitive failure.
**P2-S18** Provider-unknown retains reservation.
**P2-S19** Provider-unknown is not blindly retried as a fresh payment.
**P2-S20** Mock provider remains available for deterministic tests/fault injection.
**P2-S21** No provider failure silently switches a user transaction to mock mode.
**P2-S22** Provider identifiers may be stored; secrets may not.
**P2-S23** Real-provider integration cannot bypass ticket/nonce checks.
**P2-S24** Real-provider integration cannot weaken aggregate authorization concurrency guarantees.

# 14. Phase-2 defensive scenarios

T19 Forged client callback → rejected pre-commit, precise reason code.
T20 Wrong order context in callback → RAZORPAY_PAYMENT_CONTEXT_MISMATCH.
T21 Duplicate callback/webhook → one effect (durable dedup).
T22 Out-of-order webhooks (captured before authorized; order.paid before captured)
    → reducer converges safely.
T23 failed→captured same transaction → reconciled to captured exactly once.
T24 Timeout after send → PROVIDER_UNKNOWN + reservation held + reconciliation path;
    never a blind second order/payment.

## 14.1 Phase-2 exit-audit enforcement notes (D-037)

- Order-create and order-fetch responses are checked against durable order id
  (when known), amount, currency and receipt; an unexpected create status or
  mismatch cannot produce a browser launch.
- Callback input must name the exact server-issued execution attempt. Intent,
  checkout and server-stored order must all match that row before signature
  verification can become evidence.
- Captured/paid settlement revalidates the current ticket-bound authorization
  and checkout immediately before commit. Stale or superseded authority keeps
  captured provider truth for reconciliation but grants no fulfilment.
- Financial webhook payload amount/currency must match the durable attempt.
- Correctly signed but structurally malformed webhook envelopes are handled as
  controlled no-ops and never reach the inbox/reducer business transition.
- Test execution requires an `rzp_test_` key id and the official HTTPS Razorpay
  API base URL; alternative endpoints fail configuration validation.

# 15. Webhook error precedence note (P2-M36)

`POST /api/v1/webhooks/razorpay` validates in this order: size cap (413) ->
x-razorpay-event-id presence (400 RAZORPAY_WEBHOOK_EVENT_UNKNOWN) -> HMAC
signature over the raw body (403 RAZORPAY_WEBHOOK_SIGNATURE_INVALID).

The event-id check firing BEFORE the signature check is intentional and
cryptographically safe: both rejections occur before any body parsing, reducer
invocation, inbox claim, or ledger write. An unauthenticated caller learning
which structural check failed gains no advantage — every path to business state
requires a valid signature computed with the secret. Pinned by tests
(test_unauthenticated_variants_cause_zero_state_mutation) asserting zero rows in
provider_events and audit_events across all unauthenticated header variants.


# 16. Phase-3 security invariants (AI/ML trust layer — added P3-M08)

**P3-S01** The TokenRouter API key is backend-only (SecretStr, env-injected);
it never reaches the browser, bundle, logs, or dataset artifacts.
**P3-S02** The Qwen Intent Compiler receives only trusted human authorization
text plus system/schema instructions — never merchant pages or untrusted
product content.
**P3-S03** An AI-produced IntentDraft is not authority until explicit human
confirmation; only CONFIRMED drafts create/supersede authorization generations.
**P3-S04** Merchant/untrusted text cannot mutate a confirmed IntentContract.
**P3-S05** Semantic hypotheses derive exclusively from confirmed human
authorization; premises come from current sanitized commerce evidence with
provenance.
**P3-S06** The semantic verifier holds no payment provider client, no payment
tool, and no direct DB mutation capability.
**P3-S07** The semantic model can make decisions strictly stricter, never
looser: hard BLOCK stays BLOCK; hard CHALLENGE + semantic PASS stays CHALLENGE;
hard ALLOW + semantic BLOCK → BLOCK; hard ALLOW + semantic CHALLENGE → CHALLENGE.
No probability combination may weaken a hard decision.
**P3-S08** Inference failure/model unavailability fails closed to CHALLENGE
(or another documented fail-closed state) — never silent ALLOW.
**P3-S09** Gold labels never leak into training data or threshold tuning.
**P3-S10** A fine-tuned model is selected ONLY on held-out evidence vs the
zero-shot baseline; otherwise the baseline remains.
**P3-S11** Dataset splits are group-based; pair siblings and template/entity/
lookalike families cannot cross splits; automated leakage tests are
release-blocking.
**P3-S12** Qwen-generated dataset labels are provisional, never automatic gold.
**P3-S13** Model id/hash, prompt version/hash, schema version, and threshold
manifest are audit-visible.
**P3-S14** TokenRouter outage cannot bypass human confirmation; no silent
provider switching.
**P3-S15** Phase-1/2 runtime payment guarantees are unchanged by Phase 3.
**P3-S16** AI components cannot call Razorpay or any PaymentProvider.
**P3-S17** Untrusted content cannot enter privileged compiler context.
**P3-S18** NLI-only output never constitutes production payment authority.
**P3-S19** Semantic false positives (safe transactions blocked/challenged) are
measured and disclosed.
**P3-S20** No fabricated model/benchmark metrics; every number traces to a
recorded artifact with hash.

Defensive scenario families T25+ (Security Lab, M41): disguised subscription,
refurbished-vs-new condition, seller alias/ambiguity, hidden renewal,
bundle obligation, double negation, prompt injection, safe lookalikes — each
surfacing hard rule, NLI probabilities, semantic action, fused final decision.
