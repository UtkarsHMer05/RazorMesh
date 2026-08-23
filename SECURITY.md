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
