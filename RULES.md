# RULES.md — Non-Negotiable Project Rules

These rules apply to every milestone and every agent.

## Product rules

1. RazorMesh Trust is not a generic shopping chatbot.
2. The core product property is **Intent-to-Execution Integrity**.
3. Phase 1 is local and credential-free.
4. Track-02-style adversarial evaluation is used to prove the trust layer, not to turn the project into a generic fraud classifier.
5. Security features must be measurable and explainable.

## Financial correctness

1. Money is integer minor units + currency.
2. No floating-point money.
3. Final payable total is recomputed server-side.
4. Client-provided totals are never authoritative.
5. Cross-currency comparison is forbidden unless explicit conversion logic exists; Phase 1 does not perform FX conversion.
6. Aggregate authorization uses available/reserved/committed semantics.
7. Definitive provider failure releases reservation.
8. Verified success commits reservation.
9. Unknown provider outcome keeps reservation until reconciliation.

## Trust boundaries

1. User-confirmed authorization is trusted authority.
2. Merchant descriptions/search/tool output are data, not authority.
3. Buyer-agent output is a proposal, not permission.
4. Hard financial/security decisions are deterministic.
5. A future semantic model may advise/challenge but may not override a hard rule.

## Execution

1. Only the trusted Payment Executor may invoke `PaymentProvider`.
2. The Payment Executor requires a valid execution ticket.
3. Execution tickets bind principal, agent, authorization generation, merchant, authorization-relevant checkout hash, decision, amount, currency, policy version, nonce and expiry.
4. Tickets are single-use.
5. Stale or superseded authorization invalidates old tickets.
6. Checkout is revalidated at execution time.
7. Unknown provider outcome is not retried as a new payment.
8. Durable `ExecutionAttempt` state must exist before/around provider effect according to the architecture.

## Data authority

1. PostgreSQL is durable source of truth for authorization, spend, decisions, execution attempts and payment state.
2. Redis may coordinate nonce claims, short-lived locks and caches.
3. Losing Redis must not erase durable financial authorization history.
4. If a required security dependency is unavailable, fail closed or return a controlled system error; never default ALLOW.

## Cryptography

1. Use established libraries, never homemade cryptographic primitives.
2. Use Ed25519 for Phase-1 dev execution-ticket signing unless an accepted decision supersedes it.
3. Canonical authorization hashing must follow explicit cross-language deterministic serialization, preferably RFC 8785/JCS-compatible semantics where practical.
4. No secrets/private keys in Git.
5. Do not log secrets.

## Audit

1. Audit is append-oriented.
2. Application API exposes create/append, not general update/delete.
3. DB-level mutation protection should be used where practical.
4. Hash-chain verification detects tampering.
5. Call it "tamper-evident", not "tamper-proof" or immutable unless actually proven.

## Security testing

The following are release-blocking if they succeed:

- blocked action reaches provider;
- challenge executes before reauthorization;
- same ticket causes more than one provider effect;
- 20 concurrent same-ticket attempts cause more than one provider effect;
- aggregate spend race exceeds authorization;
- wrong principal uses a ticket;
- wrong agent uses a ticket;
- wrong merchant uses a ticket;
- changed authorization-relevant checkout executes stale ticket;
- superseded authorization executes old ticket;
- failed payment is fulfilled;
- audit tampering goes undetected in the verification path.

## Code quality

1. Explicit types at security boundaries.
2. Small focused modules.
3. Business rules outside route handlers and UI components.
4. No broad `any`, `type: ignore`, `eslint-disable`, skipped tests or exception swallowing as shortcuts.
5. No unsafe `eval`, `exec`, unsafe deserialization or shell construction from untrusted input.
6. Time is timezone-aware UTC internally.
7. Expiry logic uses a testable clock abstraction where practical.
8. Inputs have reasonable size/bound limits.

## Dependency policy

1. Live-verify versions.
2. Stable + supported + compatible + safe beats merely newest.
3. No prerelease dependencies without approval.
4. Lockfiles are mandatory.
5. Dependency/security scan findings are classified and documented.

## UI

1. Frontend is never an authorization boundary.
2. Disabled buttons do not replace backend checks.
3. All security outcomes shown in UI come from backend execution.
4. Clearly label Phase-1 payments as mock/simulated.
5. Security Lab is defensive/synthetic only.

## Research claims

1. Do not claim a protocol is implemented unless it is actually implemented.
2. Do not claim NPCI UAP compliance without an authoritative public spec and real implementation.
3. Separate official product docs from research papers/preprints.
4. No fake citations or benchmark values.

## Git

1. Inspect before modifying.
2. Never include unrelated user work.
3. Local commits only with explicit permission.
4. Never push without explicit permission.
5. Never force-push/rewrite history without explicit permission.

## Documentation

Before each next milestone, the agent must re-read the relevant source-of-truth files.

After each milestone, update documentation per `AGENTS.md`.

If code and architecture docs disagree, the milestone is incomplete.
