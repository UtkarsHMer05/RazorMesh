# MILESTONES.md — Phase-1 Gated Plan

## Rule

Exactly one milestone is active at a time. Every milestone uses the loop in `AI_WORKFLOW.md` and must update `PHASE1_STATUS.md` + `MEMORY.md` before the next milestone.

The original 50-milestone plan remains intact, with payment/security refinements integrated rather than creating scope creep.

## M01 — Environment Discovery
Inspect OS/architecture, Git, runtimes, Docker/Compose, disk, repo state. Modify nothing until environment/user work is understood.

## M02 — Live Version Intelligence
Live-resolve stable/LTS runtime/package families from authoritative sources, check security notices, fill `VERSION_MANIFEST.md`.

## M03 — Project Charter
Ensure product charter/PRD framing is coherent: intent-to-execution integrity, Phase-1 local trust core, explicit non-goals.

## M04 — Threat Model
Document assets, actors, trust boundaries, threats and mitigations. Include price drift, replay, context theft, approval splitting, stale authorization, provider-unknown outcome, duplicate/out-of-order events.

## M05 — Architecture Decisions
Record/verify architecture decisions in `DECISIONS.md`; no hidden significant decisions.

## M06 — Repository Scaffold
Create clean repo structure and core governance/scaffold files without overwriting unrelated work.

## M07 — Secret Hygiene
Create safe `.env.example`, ignores and local-key hygiene; run secret checks.

## M08 — Root Development Commands
Create stable setup/dev/test/lint/typecheck/security-check/benchmark/reset-local commands with safe semantics.

## M09 — Local PostgreSQL
Docker Compose PostgreSQL with healthcheck, persistence, internal network/localhost binding only when host access is needed.

## M10 — Local Redis
Docker Compose Redis with healthcheck and safe local/internal exposure. Verify connectivity; Redis is not durable financial truth.

## M11 — FastAPI Scaffold
Create FastAPI `/health` and `/ready`; readiness should reflect DB/Redis dependencies where appropriate.

## M12 — Python Engineering Baseline
Configure uv/lock, Ruff, typing, pytest, pytest-asyncio, Hypothesis, coverage. Avoid broad suppressions.

## M13 — Next.js Scaffold
Create current stable Next.js/React/TypeScript app and routes `/`, `/buyer`, `/merchant`, `/security-lab`, `/audit`.

## M14 — Frontend Test Baseline
Configure Vitest/RTL/Playwright baseline and smoke tests.

## M15 — Shared Identifier Types
Implement validated IDs for intents, checkouts, decisions, tickets, merchants, products, executions, payments and audit events.

## M16 — Money Value Object
Implement integer-minor-unit `Money`, currency safety and Hypothesis properties.

## M17 — Intent Contract Model
Implement fixture-driven `IntentContract` including principal/agent and authorization generation.

## M18 — Canonical Checkout Envelope
Implement `CheckoutEnvelope`, server-side total recomputation and revision/provenance fields.

## M19 — Provenance Model
Implement trust/provenance classes so untrusted data cannot masquerade as user authority.

## M20 — Database Schema
Create migrations/tables including merchants, products, intents, checkouts, decisions, spend reservations, tickets, execution attempts, payment state and audit events with indexes/uniques.

## M21 — Repository/Data Access Layer
Implement repository/data-access layer and transaction rollback/concurrency behavior; avoid SQL scattered through route handlers.

## M22 — Merchant Catalog
Seed 20–50 synthetic products including pricing, seller, condition and recurring-term variations.

## M23 — Catalog API
Implement bounded read-only catalog APIs with validation and pagination.

## M24 — Authorization State Machine
Implement explicit authorization/payment state machine; illegal transitions fail; BLOCKED and unresolved CHALLENGE cannot execute.

## M25 — Evidence Ledger
Implement append-oriented hash-chained evidence ledger; protect ordinary update/delete where practical and test tamper detection.

## M26 — Canonical Authorization Hashing
Implement deterministic cross-language-friendly canonicalization, preferably JCS/RFC 8785-compatible; hash only documented authorization projection.

## M27 — RazorGuard Rule Engine Foundation
Implement composable deterministic rules returning PASS/FAIL/UNKNOWN, reason codes and explanations.

## M28 — Money Rules
Implement amount/currency/final-fee/shipping/budget rules with boundary tests.

## M29 — Merchant/Product/Quantity Rules
Implement allowed merchant/product/category/brand/quantity structured rules and unknown-data behavior.

## M30 — Subscription/Expiry/Approval Rules
Implement recurring permission, expiry and approval/challenge rules.

## M31 — Stateful Spend Reservation and Aggregate Budget
Replace simple `spent_so_far` logic with durable authorization capacity and atomic reservation semantics. Model authorized/reserved/committed/available. Concurrency must prove multiple requests cannot exceed authority. Definitive failure releases reservation; verified success commits; provider-unknown keeps reservation.

## M32 — Decision Engine
Combine rule outputs into deterministic ALLOW/CHALLENGE/BLOCK decision matrix. No fake ML scores.

## M33 — Dev Signing Key Management
Generate/manage local Ed25519 dev keys through established libraries; gitignore private keys and handle missing keys clearly.

## M34 — Context-Bound Single-Use Execution Ticket
Ticket must bind principal_id, agent_id, authorization_generation, intent_hash, AuthorizationRelevantCheckout hash/revision, merchant, amount_minor, currency, decision_id, policy_version, nonce, issued_at and expires_at. Test tampering, expiry, wrong principal/agent/merchant, superseded authorization and changed checkout.

## M35 — Redis Nonce Claim and Concurrency
Use Redis only for atomic coordination such as nonce claim. Test first use, replay and a real many-worker same-ticket race (target at least 20 workers). PostgreSQL remains durable authority.

## M36 — Trusted Payment Executor + Durable ExecutionAttempt
Only this trusted executor may invoke PaymentProvider. Introduce durable ExecutionAttempt with idempotency identity and states including CREATED, EXECUTING, PROVIDER_UNKNOWN, SUCCEEDED, FAILED. Unknown provider outcome may not trigger a fresh financial operation.

## M37 — Mock Payment Provider
Mock modes: success, definitive failure, timeout-before-effect, timeout-after-provider-success, duplicate event, delayed event and out-of-order event. Ensure these drive real execution/reservation/audit behavior rather than UI-only simulation.

## M38 — Checkout Service
Implement checkout proposal service; recompute totals server-side and reject client-authoritative amount manipulation.

## M39 — Live Checkout Revalidation
Define AuthorizationRelevantCheckout projection. Re-read authoritative checkout immediately before execution. Relevant drift invalidates stale decision/ticket; irrelevant presentation metadata must not cause false invalidation.

## M40 — Untrusted Content Boundary
Store malicious-looking merchant text as untrusted data; prove it cannot mutate authorization/policy/execution privileges.

## M41 — Future SemanticVerifier Interface
Create `SemanticVerifier` abstraction with Null + deterministic test implementation only; no Transformer dependency in Phase 1.

## M42 — Attack Scenario Specification
Create schema-validated synthetic scenarios including safe and unsafe context/replay/drift/split/unknown cases.

## M43 — Adversarial Evaluation Runner
Runner initializes clean state, executes real RazorGuard path, records actual results and never leaks expected labels into decision input.

## M44 — Safe/Unsafe Paired Benchmark
Create paired safe/unsafe cases and compute TP/FP/TN/FN, precision, recall, F1, false-block, safe-completion, unsafe-execution and clearly labeled synthetic GMV metrics.

## M45 — Buyer Experience UI
Buyer UI: fixture authorization → catalog → checkout → backend decision → ticket/mock execution states. Direct API bypass remains protected.

## M46 — Security Lab UI
Security Lab: backend-executed synthetic scenarios, step-by-step evidence and no offensive real-system behavior.

## M47 — Audit Dashboard
Audit UI: timelines, hashes, reason codes, reservation/execution states, ticket/nonce and chain verification, including visible tamper-test failure.

## M48 — Deep Test and Security Gate
Run complete quality/security suite including Hypothesis stateful lifecycle tests, concurrency, wrong-context ticket use, stale authorization, reservation invariants, provider-unknown semantics, audit mutation/tamper tests, dependency audit, secret scan, lint/typecheck/build/E2E.

## M49 — Performance/Resource Baseline
Measure local deterministic RazorGuard, ticket verification, execution path, API and benchmark performance with hardware/version context; no production claims.

## M50 — Clean-Room Phase-1 Acceptance
Reproduce from documented setup; run scenarios A–F plus context/concurrency/provider-unknown acceptance; create Phase-1 completion report and stop for human Phase-2 approval.
