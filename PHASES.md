# PHASES.md — RazorMesh Trust Roadmap

## Phase governance

Only one phase is active at a time.

A later phase may be planned, but implementation must not leak backward into the active phase without explicit human approval.

Every phase transition requires:

1. current phase exit criteria pass;
2. completion report exists;
3. known limitations are documented;
4. human owner approves transition;
5. `MEMORY.md` and `PHASE1_STATUS.md`/future phase status are updated.

---

# Phase 1 — Local Trust Core

## Objective

Build the full credential-free trust boundary before adding Razorpay or probabilistic AI.

## Includes

- current version discovery and project governance;
- Next.js/React frontend;
- FastAPI/Python backend;
- PostgreSQL;
- Redis coordination;
- typed domain model;
- money value object;
- `IntentContract`;
- `CheckoutEnvelope`;
- provenance model;
- authorization state machine;
- RazorGuard deterministic rule engine;
- ALLOW/CHALLENGE/BLOCK;
- authorization spend reservation;
- canonical authorization hashing;
- Ed25519 execution tickets;
- strong ticket context binding;
- durable `ExecutionAttempt`;
- single-use nonce;
- trusted `PaymentExecutor`;
- `MockPaymentProvider`;
- provider success/failure/unknown simulation;
- live checkout revalidation;
- append-oriented tamper-evident evidence ledger;
- `SemanticVerifier` interface only;
- Security Lab;
- paired safe/unsafe benchmark;
- benchmark metrics;
- buyer/audit/security UI;
- deep security/concurrency/property-based tests;
- performance/reproducibility gate.

## Excludes

- Razorpay credentials/API;
- LLM APIs;
- DeBERTa production inference/fine-tuning;
- XGBoost production risk model;
- Modal/Colab runtime dependency;
- real agent protocols;
- cloud deployment.

## Exit

All 50 milestones in `MILESTONES.md` pass and Phase-1 completion report exists.

---

# Phase 2 — Real Razorpay Test-Mode Integration

> **Status: COMPLETE — local prototype (all 50 milestones PASS, finished
> 2026-08-25).** Completion report: `docs/PHASE2_COMPLETION_REPORT.md`.
> Progress: `PHASE2_STATUS.md`; plan: `PHASE2_MILESTONES.md`. Test Mode only;
> Live Mode forbidden (D-030 guard, P2-S01/S02). Phase 3 awaits explicit human
> approval.

## Objective

Replace `MockPaymentProvider` with a real Razorpay test-mode adapter without weakening the trust core.

## Planned work

- human obtains/configures Razorpay test credentials;
- secure environment-secret handling;
- Orders API integration;
- Standard Checkout integration;
- server-side payment signature verification;
- webhook endpoint;
- webhook signature validation;
- raw-body handling;
- payment/order state reconciliation;
- idempotent event processing;
- out-of-order/duplicate event handling;
- safe retry/reconcile flow;
- real test-mode success/failure demonstrations;
- evidence ledger records real test identifiers;
- no real-money production mode.

## Human gates

- Razorpay account/test keys;
- webhook dashboard configuration/public endpoint as needed;
- manual verification of dashboard/test payment behavior.

## Exit

Real test-mode payment flow works through RazorGuard + ExecutionTicket + trusted executor, including one graceful failure and replay-safe event handling.

---

# Phase 3 — AI/ML Intent and Semantic Verification

## Objective

Add meaningful AI/ML where semantics are probabilistic while preserving deterministic financial authority.

## Planned work

### Intent compiler
- structured-output LLM;
- strict JSON schema;
- human confirmation before authorization;
- prompt/tool-output trust boundaries.

### Semantic verifier
- pretrained DeBERTa-v3 NLI baseline;
- domain evaluation on AgentPay-IR scenarios;
- fine-tune only if baseline results justify it;
- Colab for experiments/fine-tuning when needed;
- model versioning;
- calibration/thresholds;
- deterministic hard rules always override.

### Optional behavioral model
- XGBoost only if it improves measured risk/friction tradeoff;
- explainable features;
- no fake "AI risk score".

### Inference
- local inference if practical;
- Modal endpoint only if latency/reliability justifies it.

## Exit

Measured comparison shows what AI/ML adds beyond deterministic baseline, including held-out and safe-lookalike behavior.

---

# Phase 4 — Agent-Commerce Interoperability + Advanced Evaluation

## Objective

Connect the trust core to real agent-commerce surfaces and strengthen research/demo evidence.

## Planned work

- MCP tool surface;
- UCP-compatible merchant/catalog/checkout path;
- AP2 concepts or real supported components where appropriate;
- second protocol adapter such as ACP if core remains stable;
- UAP-ready interface only until authoritative public specification is available;
- expanded AgentPay-IR benchmark;
- unseen templates/products/merchant wording;
- ablation study:
  - LLM only
  - prompt policy
  - structured contract
  - deterministic RazorGuard
  - runtime binding/replay protection
  - semantic verifier
  - adaptive challenge;
- latency and false-positive-cost analysis.

## Exit

At least one deep interoperability path works end-to-end and protocol claims are accurately documented.

---

# Phase 5 — Deployment, Polish and Hackathon Submission

## Objective

Turn the verified prototype into a robust, reproducible, persuasive Buildathon submission.

## Planned work

- deployment architecture;
- secret management;
- production-like observability;
- security review;
- dependency pin/audit;
- accessibility;
- responsive design;
- RazorSense/Blade design polish;
- demo datasets;
- benchmark report;
- architecture diagrams;
- README;
- setup script;
- 5-minute demo story;
- submission video;
- public repo cleanup;
- final claims/evidence audit.

## Exit

Public repository, reproducible demo, real Razorpay test integration, honest metrics, polished video and no unsupported claims.

---

# Anti-scope-creep rule

A feature belongs in the earliest phase that **needs it**, not the earliest phase where it is technically possible.

Phase 1 must remain focused on the trust core.
