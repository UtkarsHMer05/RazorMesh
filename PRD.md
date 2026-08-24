# PRD.md — RazorMesh Trust Product Requirements

## Document status

- Product: RazorMesh Trust
- Current phase: Phase 1
- Status: Active source of truth
- Requirement changes require explicit human approval.
- Implementation details belong in `ARCHITECTURE.md`; decisions belong in `DECISIONS.md`.

---

# 1. Product statement

**RazorMesh Trust** is runtime trust infrastructure for agentic commerce.

Long-term goal:

> Make Razorpay merchants safely transactable by external AI buyers while verifying, immediately before payment, that the exact transaction still matches the human's confirmed authorization.

Core principle:

> **The AI proposes. RazorGuard authorizes. Razorpay executes.**

Phase 1 substitutes Razorpay with a local `MockPaymentProvider` so the trust core can be proved without credentials or real money.

---

# 2. Problem

Agentic commerce introduces an authorization gap:

1. a human expresses an intent;
2. an AI interprets it;
3. merchant/product state can change;
4. untrusted content can influence the agent;
5. the checkout can drift;
6. retries/concurrency can duplicate side effects;
7. the final transaction may no longer match the human's authority.

Traditional "the agent had permission" is insufficient if the current execution differs from what was authorized.

RazorMesh Trust targets **agentic authorization loss**: loss/dispute/refund risk caused when an AI-executed purchase departs from confirmed human authority.

---

# 3. Users

## U1 — Buyer / consumer

Wants an AI to shop but retain bounded control over money, merchants, products, recurring commitments and approval thresholds.

## U2 — Merchant / payment platform

Wants legitimate agentic purchases while reducing disputes caused by authorization drift, replay, stale checkout state or manipulated agent actions.

## U3 — Engineer / reviewer

Needs reproducible evidence explaining why a transaction was allowed, challenged or blocked.

---

# 4. Phase-1 goals

### G1
Build a credential-free local end-to-end trust pipeline.

### G2
Represent human authorization as a structured `IntentContract`.

### G3
Represent the current merchant checkout as a canonical `CheckoutEnvelope`.

### G4
Perform deterministic RazorGuard authorization.

### G5
Use ALLOW / CHALLENGE / BLOCK rather than binary "fraud/not-fraud".

### G6
Issue short-lived, context-bound, single-use signed execution tickets only for authorized execution.

### G7
Guarantee that only the trusted Payment Executor can invoke the payment-provider abstraction.

### G8
Prevent replay and context theft.

### G9
Protect aggregate authorization under concurrency with reservation semantics.

### G10
Revalidate authorization-relevant checkout state immediately before provider execution.

### G11
Track durable execution attempts and handle ambiguous provider outcomes without blind retries.

### G12
Produce append-oriented, tamper-evident audit evidence.

### G13
Provide a defensive Security Lab with synthetic attacks and safe lookalikes.

### G14
Produce reproducible benchmark metrics including precision, recall, F1, false-block rate, unsafe-execution rate, safe-completion rate and clearly labeled synthetic GMV measures.

### G15
Provide buyer, security-lab and audit UI sufficient for a hackathon demonstration.

---

# 5. Phase-1 non-goals

Phase 1 does not:

- move real money;
- call Razorpay;
- use real customer/payment data;
- require a real LLM;
- train/fine-tune DeBERTa;
- require Modal or Colab;
- perform generic card-fraud detection;
- solve returns/chargebacks generally;
- implement all agent-commerce protocols;
- claim production readiness.

---

# 6. Primary user flow

```text
Fixture Intent
  ↓
IntentContract
  ↓
Mock Buyer selects product
  ↓
CheckoutEnvelope
  ↓
RazorGuard
  ↓
ALLOW / CHALLENGE / BLOCK
  ↓
if ALLOW:
  reserve authorization capacity
  ↓
issue signed single-use ExecutionTicket
  ↓
durable ExecutionAttempt
  ↓
trusted PaymentExecutor
  ↓
MockPaymentProvider
  ↓
success / failure / unknown
  ↓
commit / release / hold reservation
  ↓
Audit Ledger
```

---

# 7. Functional requirements

## Authorization

**PRD-AUTH-001**  
The system shall validate all `IntentContract` inputs.

**PRD-AUTH-002**  
The system shall support merchant, product/category, brand/condition, amount, quantity, currency, recurring-payment, expiry, aggregate-budget and approval constraints appropriate to Phase 1.

**PRD-AUTH-003**  
Human authorization state shall have an `authorization_generation` or equivalent version.

**PRD-AUTH-004**  
Superseding authorization shall invalidate tickets bound to the prior generation.

## Checkout

**PRD-CHK-001**  
The server shall recompute checkout total from authoritative line items, taxes, fees and shipping.

**PRD-CHK-002**  
Authorization-relevant checkout state shall have a canonical projection/hash.

**PRD-CHK-003**  
Presentation-only metadata shall not invalidate authorization unless explicitly part of authority.

**PRD-CHK-004**  
The system shall detect post-ALLOW drift before execution.

## RazorGuard

**PRD-RG-001**  
Hard policy checks shall be deterministic.

**PRD-RG-002**  
RazorGuard shall emit machine-readable reason codes plus human explanations.

**PRD-RG-003**  
RazorGuard shall support ALLOW, CHALLENGE and BLOCK.

**PRD-RG-004**  
Unknown security-critical facts shall not silently become ALLOW.

## Spend reservation

**PRD-SPEND-001**  
Authorization capacity shall model authorized, reserved, committed and available amounts.

**PRD-SPEND-002**  
Reservation shall be atomic under concurrency.

**PRD-SPEND-003**  
Definitive success commits reservation.

**PRD-SPEND-004**  
Definitive failure releases reservation.

**PRD-SPEND-005**  
Unknown provider outcome retains reservation until reconciliation.

## Execution ticket

**PRD-TKT-001**  
A valid ticket shall bind principal, agent, intent, authorization generation, merchant, authorization-relevant checkout, decision, amount, currency, policy version, nonce and expiry.

**PRD-TKT-002**  
Tampering shall invalidate a ticket.

**PRD-TKT-003**  
A ticket shall be single-use.

**PRD-TKT-004**  
Context mismatch shall reject execution before provider invocation.

## Payment execution

**PRD-EXEC-001**  
Only the trusted `PaymentExecutor` may invoke `PaymentProvider`.

**PRD-EXEC-002**  
A durable `ExecutionAttempt` shall represent financial side-effect attempts.

**PRD-EXEC-003**  
A timeout/ambiguous provider outcome shall not lead to a blind fresh payment retry.

**PRD-EXEC-004**  
At most one provider effect is allowed for one single-use execution authority.

## Audit

**PRD-AUD-001**  
Security-relevant state transitions shall emit audit events.

**PRD-AUD-002**  
Audit events shall be append-oriented at the application layer.

**PRD-AUD-003**  
Audit chain verification shall detect modified historical event content.

## Security Lab

**PRD-LAB-001**  
All attack scenarios shall be synthetic and defensive.

**PRD-LAB-002**  
The lab shall include at least:
- price drift;
- merchant substitution;
- quantity manipulation;
- subscription insertion;
- expired authorization;
- replay;
- cross-principal misuse;
- cross-agent misuse;
- cross-merchant misuse;
- approval splitting;
- authorization supersession;
- changed checkout;
- untrusted instruction influence;
- safe lookalikes.

**PRD-LAB-003**  
Displayed outcomes must come from backend execution, never hard-coded UI labels.

## Benchmark

**PRD-BENCH-001**  
Expected labels shall not leak into RazorGuard input.

**PRD-BENCH-002**  
The benchmark shall contain safe and unsafe paired/lookalike scenarios.

**PRD-BENCH-003**  
Metrics shall be computed from actual results.

**PRD-BENCH-004**  
All monetary benchmark values shall be labeled synthetic.

---

# 8. Non-functional requirements

## NFR-SEC
Security invariants in `SECURITY.md` are release-blocking.

## NFR-TEST
Required test gates in `TESTING.md` must pass.

## NFR-REPRO
A fresh local setup must be reproducible from documented commands.

## NFR-RESOURCE
Phase 1 must not require a GPU or heavyweight local AI model.

## NFR-EXPLAIN
Every BLOCK/CHALLENGE must identify reason codes and explain relevant differences.

## NFR-PERF
Phase 1 shall measure local RazorGuard/ticket/benchmark latency but shall not claim production capacity.

## NFR-UX
Critical trust states must be understandable in the UI and accessible.

---

# 9. Phase-1 demonstration acceptance

The final local prototype must demonstrate:

1. Normal authorized purchase → ALLOW → ticket → mock provider success.
2. Price drift beyond authority → no provider execution.
3. Replay of a consumed ticket → no second provider effect.
4. 20 concurrent same-ticket attempts → exactly one winning provider effect.
5. Aggregate-spend concurrency cannot exceed budget.
6. Wrong principal/agent/merchant ticket use → blocked.
7. Superseded authorization invalidates old ticket.
8. Untrusted merchant instruction does not mutate authority.
9. Provider failure leaves correct state and does not fulfil.
10. Provider-unknown outcome does not trigger blind duplicate payment.
11. Audit chain validates, and test tampering is detectable.
12. Benchmark computes real metrics from scenario execution.

---

# 10. Success wording

Allowed:

> **Phase-1 local prototype complete.**

Not allowed:

- production ready;
- fraud proof;
- perfectly secure;
- real GMV prevented;
- Razorpay integrated;
- AI model trained.

Those belong to later phases or require actual evidence.

---

# 11. Phase-2 requirements (Razorpay Test Mode — added P2-M10)

Phase-2 status: ACTIVE. Source of truth for scope: `PHASE2_MILESTONES.md` +
human-approved Phase-2 master prompt. Test Mode ONLY; Live Mode forbidden.

**PRD-RZP-001** Every real payment flow shall use a server-created Razorpay Order; amount/currency are server-authoritative.
**PRD-RZP-002** The browser receives only public launch data (Key ID, order ID, amount, currency, display metadata); Key Secret/webhook secret never reach the browser.
**PRD-RZP-003** Checkout success callbacks shall be signature-verified server-side using the SERVER-stored Razorpay order id (P2-S08).
**PRD-RZP-004** Webhooks shall be verified over the RAW body before any parse/mutation; invalid signatures cause zero business change.
**PRD-RZP-005** Provider events shall dedup durably by `x-razorpay-event-id`; duplicates and out-of-order delivery produce exactly one business effect.
**PRD-RZP-006** `payment.captured`/`order.paid` commit reservation exactly once; a documented later capture may reconcile an earlier failure.
**PRD-RZP-007** Timeouts are provider-unknown: execution identity + reservation retained; no blind retry as fresh payment.
**PRD-RZP-008** Provider fetch is the active reconciliation path for missing/delayed/contradictory signals.
**PRD-RZP-009** Live-mode keys/configuration are rejected at startup; missing credentials fail startup naming only variable names.
**PRD-RZP-010** Mock provider remains available (`PAYMENT_PROVIDER=mock`) for CI/fault injection; provider failures never silently fall back to mock.
**PRD-RZP-011** All Razorpay evidence (order/payment/event IDs, verification states) lands in the tamper-evident ledger without secrets.
**PRD-RZP-012** UI must label Test Mode ("no real money") and distinguish VERIFYING / CAPTURED / FAILED / PROVIDER_UNKNOWN states; unknown must not offer dangerous fresh-pay actions.

Phase-2 non-goals inherit §5 plus: no refunds/payouts/subscriptions/payment links,
no real fulfilment, no protocol implementations (UCP/AP2/ACP/UAP/x402).
