# ARCHITECTURE.md — RazorMesh Trust

## 1. Architectural objective

Provide a hard trust boundary between probabilistic/untrusted buyer behavior and payment-like side effects.

```text
Buyer proposal
    ↓
Intent + Checkout
    ↓
RazorGuard
    ↓
ALLOW / CHALLENGE / BLOCK
    ↓
Reservation
    ↓
Signed Execution Ticket
    ↓
Durable Execution Attempt
    ↓
Trusted Payment Executor
    ↓
PaymentProvider
```

Phase 1 uses `MockPaymentProvider`. A later phase swaps in `RazorpayPaymentProvider` without redesigning authorization.

---

# 2. Trust zones

## Trusted control plane

- confirmed `IntentContract`;
- RazorGuard deterministic rules;
- authorization state machine;
- spend reservation service;
- canonicalization/hashing;
- signing/verifying keys;
- execution-ticket validation;
- trusted Payment Executor;
- durable execution/payment state;
- audit ledger.

## Untrusted or lower-trust inputs

- buyer-agent proposals;
- product descriptions;
- merchant text;
- search/tool output;
- browser/client state;
- displayed totals;
- arbitrary checkout metadata.

Untrusted input may propose; it may not redefine authority.

---

# 3. Phase-1 runtime flow

```text
User Fixture
  ↓
FixtureIntentCompiler
  ↓
IntentContract
  ↓
User-authorized generation N
  ↓
Mock Buyer / Buyer UI
  ↓
Catalog API
  ↓
CheckoutService
  ↓
CheckoutEnvelope
  ↓
AuthorizationRelevantCheckout projection
  ↓
RazorGuard rule evaluation
  ↓
Decision
  ├─ BLOCK → audit, stop
  ├─ CHALLENGE → audit, await new authorization generation
  └─ ALLOW
       ↓
     issue signed ExecutionTicket
       ↓
     executor verifies signature, expiry and caller binding
       ↓
     executor re-reads PostgreSQL intent + checkout + ALLOW decision
       ↓
     derive idempotency identity from signed ticket ID
       ↓
     atomic Redis nonce claim
       ↓
     atomically reserve durable budget capacity
       ↓
     create durable ExecutionAttempt and mark ticket used
       ↓
     MockPaymentProvider
       ↓
     success / failure / unknown
       ↓
     commit / release / hold reservation
       ↓
     provider-like event(s)
       ↓
     idempotent state updates
       ↓
     Evidence Ledger
```

---

# 4. Core domain objects

## Money

```text
amount_minor: integer
currency: string
```

No float.

## IntentContract

Key fields:

- `intent_id`
- `principal_id`
- `agent_id`
- `authorization_generation`
- allowed merchants/products/categories
- brand/condition constraints
- max payable total
- aggregate budget
- currency
- max quantity
- recurring permission
- approval thresholds
- issued/authorized/expiry timestamps
- status

## CheckoutEnvelope

Key fields:

- checkout ID/revision
- merchant/seller
- line items
- authoritative product identity
- quantity
- unit price
- tax
- fees
- shipping
- total
- currency
- recurring terms
- product condition where relevant
- provenance
- observed timestamp

## AuthorizationRelevantCheckout

A canonical projection containing only fields that affect authority, including as applicable:

- merchant/seller
- line-item/product identity
- condition
- quantity
- unit price
- tax
- shipping
- fees
- total
- currency
- recurring terms

Presentation-only fields such as image URLs, view counters or formatting do not belong unless explicitly authorized.

## RazorGuardDecision

- decision ID
- intent ID/generation
- checkout hash
- policy version
- ALLOW/CHALLENGE/BLOCK
- rule results
- reason codes
- timestamp

## AuthorizationSpend

- authorized amount
- reserved amount
- committed amount
- available derived amount
- version/locking data

State semantics:

```text
AVAILABLE
  ↓ atomic reserve
RESERVED
  ├─ verified success → COMMITTED
  ├─ definitive failure → RELEASED back to available
  └─ unknown provider outcome → remains RESERVED
```

## ExecutionTicket

Claims include:

- ticket ID
- principal ID
- agent ID
- intent hash
- authorization generation
- checkout hash
- checkout revision / equivalent state version
- merchant ID
- amount minor
- currency
- decision ID
- policy version
- nonce
- issued at
- expires at

Signed with Phase-1 Ed25519 development keys.

## ExecutionAttempt

Durable financial side-effect attempt:

- execution attempt ID
- idempotency key
- ticket ID
- intent ID
- checkout ID
- amount/currency
- state
- provider reference when known
- error/outcome class
- timestamps

Minimum states:

```text
CREATED
EXECUTING
PROVIDER_UNKNOWN
SUCCEEDED
FAILED
```

A provider-unknown attempt cannot be replaced by a blind fresh payment attempt.

## AuditEvent

- event ID
- request/correlation ID
- timestamp
- actor/source
- event type
- entity references
- intent hash
- checkout hash
- decision/reason codes
- previous event hash
- current event hash
- safe metadata

---

# 5. Data authority

## PostgreSQL — durable authority

Stores:

- intents/authorization generations;
- merchants/products;
- checkouts;
- decisions;
- spend reservations/commit state;
- execution tickets metadata;
- execution attempts;
- payment state;
- audit events.

## Redis — ephemeral coordination

May store:

- nonce claims;
- short-lived execution locks;
- ephemeral cache;
- coordination state.

Redis is never the only durable record of authorization/spend/payment outcome.

---

# 6. Concurrency model

Critical operations require atomic behavior:

### Spend reservation
Use transaction + row lock/versioning/serializable strategy appropriate to the selected ORM/database design.

### Ticket/nonce execution
Concurrent execution of the same ticket must produce at most one provider effect.

### Provider callback/events
Event handling must be idempotent.

### Challenge/reauthorization
Old generation must not execute after new generation supersedes it.

---

# 7. Canonicalization

Authorization hashes must use deterministic cross-language canonical serialization.

Preferred Phase-1 target:

> RFC 8785 / JSON Canonicalization Scheme-compatible behavior where practical.

Constraints:

- no money floats;
- no NaN/Infinity;
- normalized timestamps;
- stable set/list semantics defined by schema;
- only authorization-relevant projection hashed for checkout authorization.

Do not rely on incidental Python dictionary behavior as the protocol definition.

---

# 8. Interfaces

## IntentCompiler

```text
compile(...)
```

Phase 1:
- `FixtureIntentCompiler`

Future:
- structured-output LLM implementation.

## SemanticVerifier

Phase 1:
- `NullSemanticVerifier`
- `DeterministicScenarioSemanticVerifier`

Future:
- DeBERTa-v3 NLI verifier.

## PaymentProvider

Conceptual methods:

- create/initiate order-like operation;
- execute/confirm simulated payment;
- query/reconcile provider state;
- verify provider-like event/callback.

Phase 1:
- `MockPaymentProvider`

Future:
- `RazorpayPaymentProvider`

The buyer/agent layer must never receive the provider object/credentials.

---

# 9. Error taxonomy

Differentiate:

- input validation error;
- policy BLOCK;
- policy CHALLENGE;
- stale authorization;
- context mismatch;
- replay;
- concurrency conflict;
- provider definitive failure;
- provider unknown outcome;
- infrastructure failure;
- invariant violation.

Normal business denials are not HTTP 500.

---

# 10. API ownership

Backend owns:

- money calculation;
- intent state;
- checkout authority;
- RazorGuard;
- reservations;
- tickets;
- nonce claims;
- execution attempts;
- provider calls;
- audit.

Frontend owns presentation only.

---

# 11. Implemented Phase-1 repository structure

The agent may refine this through an accepted decision, but must keep documentation synchronized.

```text
RazorMesh/
├── AGENTS.md
├── RULES.md
├── PRD.md
├── PHASES.md
├── ARCHITECTURE.md
├── SECURITY.md
├── DESIGN.md
├── DECISIONS.md
├── MILESTONES.md
├── TESTING.md
├── VERSION_MANIFEST.md
├── RESEARCH.md
├── PHASE1_STATUS.md
├── MEMORY.md
├── AI_WORKFLOW.md
│
├── apps/
│   └── web/
│       ├── src/app/{buyer,merchant,security-lab,audit}/
│       ├── e2e/
│       └── playwright.config.ts
│
├── services/
│   └── api/
│       ├── alembic/
│       ├── src/razormesh_api/
│       │   ├── api/
│       │   ├── domain/
│       │   ├── rules/
│       │   ├── providers/
│       │   └── persistence/
│       ├── tests/
│       ├── pyproject.toml
│       └── uv.lock
│
├── docs/
├── scripts/
├── infra/keys/                 # generated local keys; ignored
└── docker-compose.yml
```

Prefer a modular monolith for Phase 1 over unnecessary microservices.

---

# 12. Tech stack policy

Phase-1 target families:

- Web: Next.js + React + TypeScript
- API: Python + FastAPI + Pydantic
- ORM/migrations: SQLAlchemy + Alembic
- Durable data: PostgreSQL
- Coordination: Redis
- Python packaging: `uv` if current stable/compatible
- Backend testing: pytest + pytest-asyncio + Hypothesis
- Frontend testing: Vitest + React Testing Library
- E2E: Playwright
- Python lint/format: Ruff
- Local infrastructure: Docker Compose
- UI: prefer current official Razorpay Blade Design System if compatible and appropriate; otherwise use a small internal token/component layer documented in `DESIGN.md`.

Actual versions MUST be live-resolved and written to `VERSION_MANIFEST.md`.

---

# 13. Future architecture boundaries

## Phase 2
Replace mock provider with Razorpay test-mode adapter while keeping RazorGuard unchanged.

## Phase 3
Add structured-output LLM intent compiler and DeBERTa semantic verifier; fine-tune only if benchmark demonstrates value.

## Phase 4
Add real agent-commerce adapters/protocol work and expanded held-out benchmark.

## Phase 5
Deployment, hardening, demo/submission and final evidence.

See `PHASES.md`.

---

# 14. Phase-2 provider architecture (Razorpay Test Mode)

Status: ACTIVE from P2-M10. Decision D-030: one thin Razorpay HTTP wrapper over
httpx 0.28.1 (no SDK, no transport-level retries). The `PaymentProvider` boundary
and the trusted executor are unchanged; `MockPaymentProvider` remains for CI and
fault injection.

```text
RazorGuard ALLOW -> reservation -> ExecutionTicket -> durable ExecutionAttempt
    -> trusted executor
        -> RazorpayPaymentProvider.create_order (server-authoritative amount/currency)
        -> launch payload (PUBLIC key id + order id + amount/currency) to browser
    -> Standard Checkout in browser (handler flow)
        -> client callback {payment_id, order_id, signature}
            -> server verification: HMAC-SHA256(SERVER-stored order_id|payment_id)
        -> verified webhook (raw body) + x-razorpay-event-id dedup
        -> provider fetch reconciliation
    -> provider-state reducer (callback | webhook | fetch feed ONE reducer)
        -> captured/paid evidence -> exactly-once reservation commit
        -> synthetic fulfilment state -> Evidence Ledger
```

## State dimensions kept separate (master prompt §23)

- internal execution attempt: CREATED/EXECUTING/PROVIDER_UNKNOWN/SUCCEEDED/FAILED
- provider order: created/attempted/paid (+ documented states)
- provider payment: authorized/captured/failed
- reservation: RESERVED/COMMITTED/RELEASED (existing semantics unchanged)
- fulfilment: NOT_ELIGIBLE / ELIGIBLE / FULFILLED_SYNTHETIC

`payment.failed → payment.captured` for the same transaction is documented Razorpay
behavior (UPI TPAP retries/late auth); failure is therefore never modeled as an
unrecoverable terminal for reconciliation purposes. Durable correlation lives in
PostgreSQL (provider order/payment/event ids with uniqueness constraints); Redis
stays coordination-only.

## Configuration model

Typed `Settings` (SecretStr secrets): PAYMENT_PROVIDER mock|razorpay,
RAZORPAY_MODE=test only, RAZORPAY_KEY_ID (public), RAZORPAY_KEY_SECRET /
RAZORPAY_WEBHOOK_SECRET (backend-only), bounded request timeout, webhook path +
public tunnel URL. Startup guard `validate_payment_provider_config` enforces
P2-S01..S03 with name-only errors.
