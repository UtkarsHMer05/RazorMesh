# AGENTS.md — RazorMesh Trust Agent Operating Contract

## 1. Mission

You are working on **RazorMesh Trust — Runtime Trust Infrastructure for Agentic Commerce**.

The central engineering principle is:

> **The AI proposes. RazorGuard authorizes. The trusted executor executes.**

The central security property is:

> **Intent-to-Execution Integrity:** a financial action may execute only when the exact current transaction remains within the human-confirmed authorization and the trusted execution context.

Phase 1 is a local, credential-free, deterministic prototype of the trust core.

---

## 2. Mandatory preflight before every work session

Before editing implementation code:

1. Inspect the repository and `git status`.
2. Detect existing governance/project documents.
3. Read the files below in the required order.
4. Read the current milestone and current memory.
5. Reconcile your intended work with the PRD, security invariants, architecture and accepted decisions.
6. Only then modify code.

Required reading order:

1. `AGENTS.md`
2. `RULES.md`
3. `PRD.md`
4. `PHASES.md`
5. `SECURITY.md`
6. `ARCHITECTURE.md`
7. `DESIGN.md` when UI/UX is affected
8. `DECISIONS.md`
9. `MILESTONES.md`
10. `VERSION_MANIFEST.md`
11. `TESTING.md`
12. `RESEARCH.md` when external facts/versions/design guidance matter
13. `PHASE1_STATUS.md`
14. `MEMORY.md`

Never treat `MEMORY.md` or `PHASE1_STATUS.md` as permission to violate higher-authority documents.

---

## 3. Governance precedence

If documents conflict, use this precedence:

1. Latest explicit instruction from the human owner
2. `AGENTS.md`
3. `RULES.md`
4. `PRD.md`
5. `PHASES.md`
6. `SECURITY.md`
7. `ARCHITECTURE.md`
8. `DESIGN.md`
9. Accepted entries in `DECISIONS.md`
10. `MILESTONES.md`
11. `VERSION_MANIFEST.md`
12. `TESTING.md`
13. `RESEARCH.md`
14. `PHASE1_STATUS.md`
15. `MEMORY.md`

If an accepted new decision changes a higher-level document, update that higher-level document in the **same milestone** so persistent contradictions do not remain.

Do not resolve a meaningful conflict silently. If resolving it would change product scope, a security invariant, or user intent, stop and ask the human.

---

## 4. Existing-file protection

Before creating/replacing a governance file:

- inspect whether it already exists;
- preserve user-authored content;
- merge rather than replace where safe;
- never erase historical decisions;
- never erase evidence of prior failures;
- never overwrite unrelated work.

If a local file disagrees with this governance pack and the local file contains later explicit user decisions, preserve the later user decision and document the reconciliation.

---

## 5. Phase-1 boundary

Phase 1 MUST NOT require:

- Razorpay credentials or real Razorpay calls;
- LLM API keys;
- DeBERTa training/inference as a production dependency;
- XGBoost risk scoring as a production requirement;
- Modal;
- Colab;
- real ACP/AP2/UAP/x402 integrations;
- cloud deployment;
- real payment/customer data.

Interfaces for future integrations are allowed.

If Phase 1 appears to require an external key, stop and re-check the architecture. It is probably a scope violation.

---

## 6. Milestone rule

Work one milestone at a time.

For every milestone:

1. Understand.
2. Inspect existing state.
3. Confirm requirement IDs and security invariants affected.
4. Plan the smallest correct implementation.
5. Implement.
6. Format.
7. Lint/static-check.
8. Type-check.
9. Unit test.
10. Integration test when relevant.
11. Security regression.
12. Concurrency/property-based tests when relevant.
13. Full relevant regression suite.
14. Inspect actual output.
15. Update documentation.
16. Update `PHASE1_STATUS.md`.
17. Compact/update `MEMORY.md`.
18. Only then proceed.

Never start milestone N+1 with unexplained failures from milestone N.

---

## 7. Documentation synchronization matrix

At the end of every milestone update:

- `PHASE1_STATUS.md` — always.
- `MEMORY.md` — always, compactly.
- `DECISIONS.md` — if a non-trivial decision was made.
- `ARCHITECTURE.md` — if flow, modules, boundaries, schemas, data authority or folder structure changed.
- `PRD.md` — only if the human approved a requirement change/clarification.
- `SECURITY.md` — if a threat, invariant, control or security behavior changed.
- `DESIGN.md` — if UI design tokens, component rules or page behavior changed.
- `VERSION_MANIFEST.md` — if dependencies/runtimes are added or changed.
- `RESEARCH.md` — if external research materially informed a decision.
- `MILESTONES.md` — only if the milestone plan itself was explicitly changed.
- `TESTING.md` — if a new permanent test/release gate is introduced.

Documentation changes are part of the milestone. They are not optional cleanup.

---

## 8. Decision discipline

Do not make hidden architectural decisions.

A decision is significant if it affects:

- security;
- money representation;
- transaction semantics;
- data authority;
- concurrency;
- cryptography;
- provider interfaces;
- external dependencies;
- storage schema;
- public API;
- major UI behavior;
- phase scope;
- test methodology.

Record significant decisions in `DECISIONS.md`.

Historical decision entries are append-only. Supersede an old decision with a new entry; do not rewrite history.

---

## 9. Security non-negotiables

At all times preserve:

- no execution without a valid trusted execution ticket;
- buyer/agent code never directly invokes a payment provider;
- tickets are context-bound, short-lived and single-use;
- PostgreSQL is durable authority for authorization/decision/spend/payment state;
- Redis is coordination, not sole durable financial truth;
- money uses integer minor units;
- checkout authorization hashes cover only authorization-relevant projection;
- authorization-relevant state is revalidated immediately before execution;
- hard financial rules are deterministic;
- untrusted content cannot redefine trusted authority;
- ambiguous provider outcomes are never blindly retried as a new financial operation;
- budget uses reservation semantics: available/reserved/committed/released;
- BLOCKED never executes;
- CHALLENGED never executes before reauthorization;
- append-oriented audit events are tamper-evident;
- no fabricated security/performance/benchmark claims.

Read `SECURITY.md` for the complete invariant list.

---

## 10. Dependency/version rule

Before adding/upgrading a meaningful dependency:

1. Check the authoritative vendor/package source.
2. Resolve the latest **stable, supported, compatible and security-acceptable** release.
3. Avoid prerelease/canary/nightly versions unless the human explicitly approves.
4. Check security notices.
5. Update lockfiles.
6. Update `VERSION_MANIFEST.md`.
7. Run compatibility and security gates.

"Newest number" is not automatically "best version".

---

## 11. Research rule

For time-sensitive product, library, Razorpay or protocol facts:

- verify from current authoritative sources;
- record the URL/date/finding in `RESEARCH.md`;
- distinguish official specification from paper/preprint/blog interpretation;
- never invent protocol compliance.

In Phase 1, research may guide architecture but must not create an external runtime dependency.

---

## 12. Git rule

Do not assume permission to commit or push.

Always:
- inspect `git status`;
- avoid unrelated files;
- never force-push;
- never rewrite history;
- never push unless explicitly authorized.

Local milestone commits are allowed only if the human has explicitly authorized autonomous local commits.

---

## 13. Human gates

Stop and ask the human only when necessary, including:

- destructive action may affect user work;
- repository state is ambiguous and choosing automatically risks data loss;
- required system installation/permission cannot be completed safely;
- a security invariant conflicts with an explicit requirement;
- bounded repair attempts are exhausted;
- an external account/credential is genuinely required in a later phase;
- a phase transition requires human approval.

Do not ask trivial implementation questions that can be safely resolved by engineering judgment.

---

## 14. Bounded repair

For one root cause:

- diagnose;
- attempt targeted repairs;
- verify after each repair;
- after 5 serious failed repair attempts, stop and produce a blocker report.

Never random-walk through edits.

---

## 15. Completion integrity

Never mark work PASS unless the recorded validation actually passed.

Never weaken a security test to make it pass.

Never fabricate benchmark numbers.

Never describe Phase 1 as production-ready.

Approved completion phrase:

> **Phase-1 local prototype complete.**

---

## 16. Start/continue behavior

Whenever asked to "continue":

1. read this file and the governance set;
2. inspect `MEMORY.md` and `PHASE1_STATUS.md`;
3. identify the next incomplete milestone;
4. verify the previous milestone gate remains valid;
5. continue autonomously until a genuine human gate or phase gate occurs.
