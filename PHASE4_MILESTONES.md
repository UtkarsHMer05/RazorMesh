# Phase 4 Milestone Plan (M01..M50)

Carried verbatim from `RazorMesh_Trust_Phase4_Master_Prompt.md §27`. Each
milestone has its own gate; one PASS at a time, one local commit per
milestone where practical. Human gate is intentionally postponed until
after M50.

## M01 — Repository / Governance / UI Baseline Inspection
Read all governance and corrected Phase-3 completion evidence. Inspect UI
redesign status and route map. Inspect Git, secrets, untracked files,
current branch, DB migrations, model artifacts. No code changes until the
active truth is understood.

## M02 — Full Phase-1/2 Backend Revalidation
Format/lint, strict typing, full pytest, property/stateful/concurrency,
payment provider, ticket/replay, reservation, webhook/callback,
reconciliation, audit, dependency/security scans. Repair regressions
before proceeding.

## M03 — Full Phase-3 AI/ML Revalidation
Intent compiler, confirmation authorization, SemanticVerifier, AgentPay-IR,
thresholds, conservative fusion, context isolation, Phase-3 benchmark.
Do not retrain.

## M04 — Full Redesigned Frontend Revalidation
Lint, typecheck, build, unit/component, Playwright, secret scans,
accessibility, landing → demo → Security Lab → Audit journey, route
transitions.

## M05 — Freeze Phase-4 Baseline
HEAD, test counts, versions, current DB migration, Phase-3 model/hash,
UI state. No Phase-4 protocol code active.

## M06 — MCP Current-Spec Research + Pin
Live-verify MCP final revision and official Python SDK. Pin package/revision.

## M07 — UCP Release-Status Resolution + Pin
Resolve 2026-08-25 vs 2026-04-08. Pin actual target. Freeze schemas.

## M08 — AP2 / ACP / A2A Current-Spec Research + Pin
AP2 v0.2 release/tag/commit, ACP latest stable, A2A latest release.

## M09 — Phase-4 Threat Model + Architecture Decisions
D-0xx decisions for protocol envelope, IR, commitment, firewall, cross-protocol
consistency, pins, custom Razorpay handler, A2A slice, final human gate.
Update ARCHITECTURE/SECURITY/PRD.

## M10 — Official Protocol Fixture Registry
Versioned fixture registry with source URLs, commits, SHA-256, license.

## M11 — ProtocolEnvelope Domain Model
Versioned domain model. Property/negative tests.

## M12 — AgentCommerceIR Domain Model
Canonical semantic commerce model.

## M13 — commerce-commitment-v1
Deterministic authorization-relevant serialization + hash. Golden vectors.

## M14 — Protocol Identity + Provenance Model
Identities, keys, profile references, evidence provenance.

## M15 — Protocol Firewall Core
Deterministic firewall pipeline. Output PASS/CHALLENGE/BLOCK.

## M16 — Version / Downgrade / Capability Guard
Exact version resolution, capability negotiation.

## M17 — Protocol Idempotency / Replay Ledger
Durable protocol-level idempotency/replay records.

## M18 — Cross-Protocol Consistency Engine
Field-level comparison + commitment comparison.

## M19 — Protocol Evidence Persistence + Audit
Persist envelope/IR/evidence hashes. Add PROTOCOL_RECEIVED / VERIFIED /
NORMALIZED / CROSS_PROTOCOL_CHECKED events.

## M20 — MCP Modern Server Foundation
Integrate official current Python MCP SDK.

## M21 — MCP Discovery + Tool Catalog
server/discover, deterministic tools/list.

## M22 — MCP Read/Proposal Tools
search_catalog, get_product, cart, propose_checkout, get_checkout.

## M23 — MCP Trust/Status Tools
evaluate_checkout, request_authorization, get_authorization_status,
get_execution_status, get_order, get_audit_receipt.

## M24 — MCP Authorized Completion Tool
complete_authorized_checkout with strict preconditions.

## M25 — MCP Conformance + Security Gate
Modern protocol conformance/fixture tests.

## M26 — UCP Profile / Discovery
/.well-known/ucp for resolved target.

## M27 — UCP Catalog + Cart Adapter
Target-version Catalog and Cart semantics.

## M28 — UCP Checkout Adapter
create/get/update/complete.

## M29 — UCP Order + Signed Event Path
Order retrieval, signed order webhook/event fixture path.

## M30 — UCP RFC 9421 / Content-Digest Security
Verify current UCP message signing.

## M31 — UCP-over-MCP Binding
Expose UCP capabilities through MCP binding.

## M32 — UCP Stable + Forward-Compatibility Suite
Conformance claim only for pinned stable; draft = compatibility fixtures.

## M33 — AP2 Test Crypto / SDK Foundation
Pin official AP2 release artifacts, generate dev/test keys, separate
AP2 ES256/P-256, user/agent PoP, ExecutionTicket Ed25519.

## M34 — AP2 Mandate Parser + Version Rules
Strict parse/model verification for current closed/open mandates and receipts.

## M35 — AP2 Closed Checkout Verification
Signature/credential chain, merchant checkout JWT, checkout hash, expiration.

## M36 — AP2 Closed Payment Verification
Payment Mandate, transaction/checkout binding, amount/currency, instrument.

## M37 — AP2 Human-Not-Present Open→Closed Verification
Open constraints, cnf/agent key binding, PoP, closed mandate relation.

## M38 — AP2 Receipts + Dispute Evidence
Deterministic evidence bundle.

## M39 — AP2 → AgentCommerceIR → Execution Binding
Normalize verified AP2 evidence into IR. Prove signature-valid + intent-mismatch
→ BLOCK.

## M40 — ACP Capability Negotiation + Session Domain
Resolved ACP version protocol wrapper. Capability intersection, session state
machine, strict lifecycle.

## M41 — ACP Checkout REST Compatibility
POST create, GET retrieve, POST/update, complete, cancel.

## M42 — ACP Razorpay Test Handoff Extension
io.razormesh.razorpay.test_checkout. Test mode only. No Delegate Payment.

## M43 — ACP Idempotency / Failure / Unknown-Outcome Semantics
Duplicate, conflict, illegal transition, payment failure, provider-unknown.

## M44 — A2A Compatibility Slice
Agent Card/profile, UCP extension metadata, DataPart mapping, messageId
idempotency, AP2 evidence refs.

## M45 — Untrusted Buyer-Agent Harness
Deterministic scripted agent for CI; optional Qwen/TokenRouter harness.
No provider/signing secrets.

## M46 — AgentPay-X Benchmark
150–300 defensive scenarios. Split safe/attack.

## M47 — Differential / Property / Fuzz / Concurrency Security Sweep
Equivalent normalization, one-field mutation, fuzz, signature mutation,
20+ concurrent duplicate completions, mandate replay, duplicate storms.

## M48 — Protocol Gateway + Security Lab UI
Protocol Gateway, Envelope inspector, IR, consistency matrix, signature/mandate
state, firewall/RazorGuard/NLI/final decision, AgentPay-X results, audit links.
Use existing design system. Bounded Impeccable adapt/audit/harden/polish for
new surfaces only.

## M49 — Full Phase-4 Quality / Security / Performance / Clean-Room Gate
Format, Ruff, mypy, full pytest, Hypothesis/property, fuzz, concurrency,
protocol conformance, Phase-1/2/3 regressions, audits/dependency/secret
checks. Frontend: lint, typecheck, build, unit, Playwright, accessibility,
secret scans, landing → protocols → demo → Security Lab → Audit journey.
Performance: MCP overhead, signature verify, AP2 verification, normalization/
hash, full local trust path. Clean room: disposable DB/Redis, migrations,
fixtures/keys, protocol servers, frontend, deterministic agent, complete
mock Test-mode-compatible flow. No human interaction.

## M50 — Autonomous Completion Report + Final Human Acceptance Preparation
Every M01..M49 must read PASS first. Create
`docs/PHASE4_PRE_HUMAN_COMPLETION_REPORT.md`. Set
`AUTONOMOUS_50_OF_50_PASS` / `AWAITING_FINAL_HUMAN_ACCEPTANCE`. Do NOT mark
final Phase-4 COMPLETE yet. Do NOT start Phase 5. STOP and ask the human for
the single final prepared Test-mode transaction.

## Final Human Acceptance (OUTSIDE M01..M50)
After M50, the agent provides the exact UI/terminal steps. The human performs
only the unavoidable browser interaction. After the human replies
`phase4 protocol payment done`, the agent captures evidence, creates
`docs/PHASE4_FINAL_HUMAN_ACCEPTANCE.md`, updates PHASE4_STATUS to COMPLETE,
and uses the approved completion phrase:

> **Phase-4 cross-protocol trust layer complete.**

No M51. STOP. Do not start Phase 5.
