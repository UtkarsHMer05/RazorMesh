# RazorMesh Trust — Project Charter

Status: Active source of truth (Phase 1)
Created: 2026-08-23 (M03)
Owner: human project owner; maintained by engineering agent per `AGENTS.md`

---

## 1. Problem statement

Agentic commerce introduces an **authorization gap** between what a human permits and
what an AI actually executes:

1. a human expresses an intent ("buy Sony headphones under ₹5,000, Croma only, no subscription");
2. an AI interprets and acts on it;
3. merchant/product state can change between authorization and execution;
4. untrusted content can influence the agent;
5. the checkout can drift;
6. retries and concurrency can duplicate financial side effects;
7. the final transaction may no longer match the human's authority.

Traditional permission models answer only *"was the agent allowed?"*.
RazorMesh Trust answers the harder question:

> **Does this exact transaction, right now, still match the human's confirmed authorization?**

We call this property **Intent-to-Execution Integrity**. The product targets
*agentic authorization loss*: disputes, refunds and trust erosion caused when an
AI-executed purchase departs from confirmed human authority.

> RazorMesh is **not** a generic chatbot checkout.
>
> The core contribution is intent-to-execution integrity.

---

## 2. Track-01 objective (product)

Build runtime trust infrastructure that makes Razorpay merchants safely transactable
by external AI buyers:

```text
Human confirms structured Intent Contract
    ↓
AI buyer proposes checkout against real catalog state
    ↓
RazorGuard deterministically authorizes (ALLOW / CHALLENGE / BLOCK)
    ↓
Signed single-use execution ticket
    ↓
Trusted Payment Executor performs the provider call
```

The AI proposes. RazorGuard authorizes. The trusted executor executes.

## 3. Track-02-inspired verification methodology

Trust claims are proven, not narrated. Following adversarial-evaluation methodology
(the spirit of security-track evaluations such as AgentDojo-style red-teaming):

1. **Synthetic attack scenarios** (price drift, replay, context theft, approval splitting,
   injection-influenced proposals…) run against the real authorization path;
2. **Safe lookalikes** for every attack family prevent "block everything" from scoring well;
3. **Measured metrics**: precision, recall, F1, false-block rate, unsafe-execution rate,
   safe-completion rate, and clearly-labeled *synthetic* GMV prevented/blocked;
4. **Concurrency and property-based tests** prove invariants hold under parallel load,
   not just sequential demos;
5. Expected labels never leak into the decision input.

## 4. Phase-1 objective

Prove the complete credential-free local trust core:

- structured `IntentContract` (fixture-driven; no LLM);
- canonical `CheckoutEnvelope` with server-side recomputation;
- provenance/trust classes so untrusted content cannot redefine authority;
- deterministic RazorGuard rule engine → ALLOW / CHALLENGE / BLOCK;
- atomic aggregate-spend reservation (authorized/reserved/committed/available);
- Ed25519-signed, context-bound, single-use execution tickets;
- durable `ExecutionAttempt` handling ambiguous provider outcomes safely;
- Redis-coordinated nonce claiming (PostgreSQL remains durable authority);
- append-oriented tamper-evident evidence ledger;
- mock payment provider with success/failure/timeout/duplicate/delayed modes;
- Security Lab + paired benchmark with honest metrics;
- buyer/security-lab/audit UI sufficient for demonstration.

Phase 1 substitutes Razorpay with `MockPaymentProvider` behind the same interface a
future `RazorpayPaymentProvider` will implement.

## 5. Non-goals (Phase 1)

No real money · no Razorpay API calls or credentials · no LLM APIs · no DeBERTa/XGBoost
training or production inference · no Modal/Colab dependency · no cloud deployment ·
no real customer/payment/card data · no generic card-fraud classification · no protocol
implementations (ACP/AP2/UAP/x402) beyond future-facing interfaces · no production-readiness claims.

Interfaces for future components MAY exist (`IntentCompiler`, `SemanticVerifier`,
`PaymentProvider`); external services MUST NOT be required.

## 6. Trust boundaries

| Class | Examples | May influence | May never do |
|---|---|---|---|
| Trusted authority | confirmed IntentContract, RazorGuard policy, PostgreSQL durable state, ticket signer, trusted executor, audit service | authorize/deny execution | be redefined by lower-trust input |
| Untrusted input | buyer-agent proposals, merchant text, product descriptions, search/tool output, browser state, client totals | propose/rank/recommend | mutate limits, permissions, thresholds, nonce/ticket state, executor rights |

Hard financial rules are deterministic. A future semantic model may advise or challenge;
it may never override a hard rule.

## 7. Future phases (summary — see PHASES.md)

- **Phase 2:** real Razorpay test-mode adapter behind the existing `PaymentProvider`
  interface (orders, checkout, signature verification, webhooks).
- **Phase 3:** structured-output LLM intent compiler + DeBERTa-v3 NLI semantic verifier;
  deterministic rules always retain final authority.
- **Phase 4:** agent-commerce interoperability (MCP/UCP-style surfaces) + expanded held-out benchmark.
- **Phase 5:** deployment, polish, submission evidence.

## 8. Definition of done (Phase 1)

From a fresh clone on documented commands: infrastructure starts → migrations succeed →
seeds load → API starts → frontend builds → normal transaction succeeds end-to-end →
blocked/challenged scenarios cannot execute → replay fails → checkout mutation fails closed →
audit chain verifies and detects tampering → 20-worker same-ticket race yields exactly one
provider effect → aggregate budget cannot be overspent concurrently → superseded/stale/
wrong-context tickets fail before the provider → benchmark produces real metrics from
executed scenarios → full test suite, lint, typecheck, build pass → dependency findings
classified → documentation matches code.

Exit wording, exactly:

> **Phase-1 local prototype complete.**

Nothing stronger may be claimed until later phases add real integrations.
