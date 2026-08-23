# PASTE THIS INTO THE CODING AGENT

You already received the original RazorMesh Trust Phase-1 master prompt and produced a 50-milestone build plan.

Before continuing implementation, apply this governance pack and the mandatory architecture/security refinements below.

## 1. First: inspect, do not overwrite blindly

Immediately inspect the current repository, existing Markdown governance files and `git status`.

If any of these files already exist:

`AGENTS.md`, `RULES.md`, `PRD.md`, `PHASES.md`, `ARCHITECTURE.md`, `SECURITY.md`, `DESIGN.md`, `DECISIONS.md`, `MILESTONES.md`, `TESTING.md`, `VERSION_MANIFEST.md`, `RESEARCH.md`, `PHASE1_STATUS.md`, `MEMORY.md`, `AI_WORKFLOW.md`

do NOT blindly replace later user-authored content.

Compare and merge.

Preserve:
- explicit human requirements;
- already accepted later decisions;
- truthful milestone/test evidence;
- existing user work.

If there is a meaningful conflict that changes product scope or a security invariant, stop and show me the conflict before choosing.

## 2. These files are now persistent project governance

Read them before implementation in the order defined by `AGENTS.md`.

They are not passive documentation.

They are the persistent source of truth that prevents you from drifting as the repository grows.

At the start of EVERY milestone:
- reread `AGENTS.md`;
- reread `RULES.md`;
- inspect relevant `PRD.md`, `PHASES.md`, `SECURITY.md`, `ARCHITECTURE.md`, `DESIGN.md`, `DECISIONS.md`, `MILESTONES.md`, `TESTING.md`;
- inspect `PHASE1_STATUS.md` and `MEMORY.md`;
- verify the previous milestone gate.

At the end of EVERY milestone:
- update `PHASE1_STATUS.md`;
- compact/update `MEMORY.md`;
- update `DECISIONS.md` if a significant decision was made;
- update `ARCHITECTURE.md` if flow/modules/schema/data authority/folder structure changed;
- update `SECURITY.md` if threats/invariants/controls changed;
- update `DESIGN.md` if UI/design rules changed;
- update `VERSION_MANIFEST.md` for dependency/runtime changes;
- update `RESEARCH.md` for material external research;
- update `TESTING.md` for permanent new gates;
- reread changed documentation and confirm it matches the code.

Do not move to the next milestone while documentation and code disagree.

## 3. Mandatory refinements to the original 50-milestone plan

Integrate these into the existing milestones. Do NOT create random extra scope.

### A. Durable payment execution attempts

Nonce consumption alone is insufficient.

Introduce a durable `ExecutionAttempt` with an idempotency identity and states covering at least:

- CREATED
- EXECUTING
- PROVIDER_UNKNOWN
- SUCCEEDED
- FAILED

A timeout-after-provider-success must never cause a blind second provider execution.

Ambiguous outcomes retain the original execution identity and must be reconciled rather than retried as a fresh financial operation.

### B. Authorization spend reservation

Do not model aggregate budget as only `spent_so_far`.

Implement durable:

- AUTHORIZED
- RESERVED
- COMMITTED
- AVAILABLE (derived or explicit)

Reserve atomically before financial execution.

On verified success:
- reserved decreases;
- committed increases.

On definitive failure:
- reserved decreases;
- available capacity is restored.

On unknown provider outcome:
- reservation remains held.

Concurrency tests must prove parallel attempts cannot exceed authorized aggregate spend.

### C. Strong execution-ticket context binding

Ticket claims must bind at least:

- ticket_id
- principal_id
- agent_id
- intent_hash
- authorization_generation
- AuthorizationRelevantCheckout hash
- checkout revision/equivalent state version
- merchant_id
- amount_minor
- currency
- decision_id
- policy_version
- nonce
- issued_at
- expires_at

Old tickets become invalid when relevant human authorization is superseded.

### D. AuthorizationRelevantCheckout projection

Do not invalidate authorization because irrelevant presentation metadata changes.

Define one explicit canonical authorization projection containing authority-sensitive fields such as:

- merchant/seller
- line-item/product identity
- product condition where applicable
- quantity
- unit price
- tax
- shipping
- fees
- total
- currency
- recurring/subscription terms

Hash this projection.

Image URLs, analytics metadata, view counters and presentation formatting should not change the authorization hash unless explicitly made relevant.

### E. Canonical serialization

Use explicit deterministic canonical serialization suitable for later cross-language verification.

Prefer RFC 8785 / JCS-compatible semantics where practical.

Do not define the protocol as "whatever Python json.dumps currently does".

Keep:
- no floating-point money;
- no NaN/Infinity;
- normalized timestamps;
- deterministic collection semantics.

### F. Audit protection

Audit is:
- append-oriented;
- tamper-evident.

At the application layer, historical audit update/delete operations should not exist.

Where practical in Phase 1, protect ordinary UPDATE/DELETE at the DB boundary too.

Tests must cover:
- normal append;
- rejected mutation path;
- deliberate test tampering causes chain verification failure.

Do NOT claim absolute immutability.

### G. Context-theft scenarios

Add and test:

- User B attempts User A ticket.
- Agent B attempts Agent A ticket.
- Ticket for Merchant A used against Merchant B.
- Ticket used after authorization generation changes.
- Ticket used after authorization-relevant checkout changes.

All must fail before provider execution.

### H. Stateful/property-based security tests

Use Hypothesis stateful testing for lifecycle sequences, not only Money.

Generate legal/illegal combinations around:

- authorization;
- challenge;
- reauthorization;
- checkout mutation;
- reservation;
- ticket issuance;
- expiry;
- execution;
- retry;
- provider failure;
- provider unknown;
- duplicate event.

Invariants must hold for generated sequences.

### I. Real concurrency

Do not call sequential retry a concurrency test.

At minimum:
- 20 simultaneous attempts using the same ticket → provider effect count must equal 1.
- concurrent spend reservations that would exceed authorization → total reserved + committed never exceeds authorized amount.

### J. Data authority

PostgreSQL is durable source of truth for:
- authorization;
- generation/version;
- decisions;
- spend reservation;
- execution attempts;
- payment state;
- audit.

Redis is for short-lived atomic coordination such as nonce claims/locks/cache.

Redis must not become the only durable financial/security truth.

### K. Local network exposure

PostgreSQL and Redis must use Docker-internal networking or localhost `127.0.0.1` binding where host access is needed.

Do not unintentionally expose them on all interfaces.

### L. Git behavior

Do not assume permission to create 50 commits.

Always maintain status/evidence.

Only create local milestone commits if I explicitly authorize it.

Never push, force-push or rewrite history without explicit human authorization.

## 4. Design requirements

Before UI implementation, read `DESIGN.md` and research the current official public Razorpay design sources.

Use:
- RazorSense principles for expressive but restrained state communication;
- public Razorpay Blade components/tokens when currently compatible and appropriate.

Do not invent proprietary brand tokens/fonts.

If Blade is used:
- live-check latest stable package;
- verify React/Next compatibility;
- update `VERSION_MANIFEST.md`;
- run accessibility/build/tests.

If Blade is not technically suitable, use the documented RazorMesh fallback design tokens and record the decision.

The UI must feel like a serious fintech/agentic product, not a generic neon AI dashboard.

## 5. Version requirement

Never trust old version numbers from previous chat or memory.

For every important runtime/package:
- inspect the authoritative current source;
- choose latest stable/LTS that is compatible and security-acceptable;
- check advisories;
- lock it;
- update `VERSION_MANIFEST.md`.

If the numerically latest release is known unsafe/incompatible, choose the newest safe supported release and document why.

## 6. Phase boundary

Phase 1 is still local and credential-free.

Do NOT request:
- Razorpay API keys;
- LLM API keys;
- Hugging Face token;
- Modal credentials;
- Colab credentials.

Do NOT implement real Razorpay, real LLM runtime, DeBERTa production inference, fine-tuning, or cloud deployment.

If you believe one is required, stop and explain why. Re-check `PHASES.md`.

## 7. Autonomous loop

Continue milestone-by-milestone without waiting for approval after every ordinary step.

Only stop for a genuine human gate.

For each milestone:

UNDERSTAND
→ INSPECT
→ PLAN
→ IMPLEMENT
→ FORMAT
→ LINT
→ TYPECHECK
→ UNIT TEST
→ INTEGRATION TEST
→ SECURITY TEST
→ PROPERTY/CONCURRENCY TEST IF RELEVANT
→ REGRESSION
→ INSPECT OUTPUT
→ UPDATE GOVERNANCE DOCS
→ UPDATE STATUS
→ COMPACT MEMORY
→ VERIFY DOCS MATCH CODE
→ NEXT MILESTONE

Maximum 5 serious attempts for one unresolved root cause. Then stop with a blocker report.

## 8. Before continuing now

Do the following first:

1. Print a concise list of governance files found.
2. Report any conflicts with existing files.
3. Merge/install this governance safely.
4. Verify `AGENTS.md` precedence and current Phase-1 scope.
5. Update `MEMORY.md` with the real current milestone.
6. Update `PHASE1_STATUS.md` to reflect work already actually completed — do not mark anything PASS without evidence.
7. Reconcile your existing 50-milestone build plan with `MILESTONES.md`.
8. Show me only genuine conflicts/blockers if any.
9. If there are no blockers, continue autonomously from the first milestone that is not proven PASS.

Do not restart completed work blindly.

Do not skip validation.

Do not fabricate evidence.

Do not start Phase 2.

The persistent rule is:

> **The AI proposes. RazorGuard authorizes. The trusted executor executes.**
