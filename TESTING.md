# TESTING.md — Verification and Release Gates

## 1. Philosophy

Tests prove security properties, not just code coverage.

A green UI is not sufficient.

A milestone is complete only when relevant correctness, security and regression gates pass.

---

# 2. Per-milestone loop

For each milestone run as applicable:

1. formatter;
2. linter/static analysis;
3. type check;
4. narrow unit tests;
5. subsystem integration tests;
6. security regression tests;
7. concurrency/property-based tests if the milestone affects state/authorization;
8. frontend tests if UI affected;
9. full relevant regression suite;
10. inspect actual output.

Record commands/results in `PHASE1_STATUS.md`.

---

# 3. Backend testing

Use:

- pytest;
- pytest-asyncio;
- Hypothesis;
- database integration tests;
- Redis integration tests;
- concurrency tests.

Targets include:

- parsing/validation;
- money arithmetic;
- canonicalization;
- state machine;
- policy rules;
- spend reservation;
- ticket signing/verification;
- nonce claim;
- execution attempts;
- provider simulation;
- audit chain.

---

# 4. Property-based testing

At minimum cover:

## Money
- arithmetic;
- non-negative constraints;
- currency mismatch;
- boundaries;
- no float acceptance.

## Canonicalization
- stable result;
- relevant mutation changes hash;
- excluded irrelevant metadata does not change authorization hash.

## Stateful authorization/payment lifecycle
Generate legal/illegal sequences including:

- authorize;
- challenge;
- reauthorize;
- mutate checkout;
- issue ticket;
- expire;
- reserve;
- execute;
- retry;
- fail;
- unknown;
- provider event duplication.

Properties must include:

- BLOCKED never produces provider effect;
- CHALLENGED never executes before reauthorization;
- consumed ticket never causes second provider effect;
- FAILED never becomes fulfilled without a valid later execution;
- stale checkout never uses stale authority;
- aggregate budget never exceeds authorization.

---

# 5. Concurrency tests

Mandatory:

### C1 — same ticket, many workers
Run at least 20 simultaneous execution attempts.

Expected:
- successful execution claimant = 1;
- provider effect count = 1;
- all others rejected/idempotently resolved.

### C2 — aggregate budget
Concurrent reservations that would overspend must result in total reserved+committed <= authorized.

### C3 — duplicate provider events
Concurrent/repeated processing remains idempotent.

---

# 6. Payment-provider simulation tests

Mock provider modes:

- success;
- definitive failure;
- timeout before side effect;
- timeout after side effect;
- duplicate event;
- delayed event;
- out-of-order event.

Verify spend and `ExecutionAttempt` semantics for each.

---

# 7. Frontend testing

- Vitest/component tests;
- React Testing Library;
- Playwright smoke/E2E;
- accessibility checks where practical.

UI tests must not replace backend authorization tests.

---

# 8. Security benchmark

Unsafe = positive class.

Document how CHALLENGE is scored for each scenario type.

Compute from actual outcomes:

- TP;
- FP;
- TN;
- FN;
- precision;
- recall;
- F1;
- false-block rate;
- unsafe-execution rate;
- safe-completion rate;
- synthetic unauthorized GMV prevented;
- synthetic legitimate GMV blocked.

Never hard-code result numbers.

Expected labels are evaluation-only and must not influence RazorGuard input.

---

# 9. Safe/unsafe pairs

Every major unsafe family should have safe lookalikes where practical.

This prevents "block everything" from scoring well.

Examples:

- amount just over vs just under limit;
- allowed merchant vs similar unapproved merchant;
- single-use vs legitimate new authorization;
- benign product text vs subscription language;
- irrelevant checkout metadata change vs authorization-relevant change.

---

# 10. Dependency/security scanning

At final gate and after major dependency change:

- dependency audit;
- secret scan;
- lint/type checks;
- classify findings:
  - fixed;
  - not applicable;
  - temporarily accepted with reason;
  - blocking.

An exploitable critical issue is blocking.

---

# 11. Performance baseline

Measure locally:

- deterministic RazorGuard latency;
- ticket sign/verify latency;
- execution-path latency against mock provider;
- benchmark throughput;
- relevant API latency.

Record hardware/runtime versions.

Do not present as production capacity.

---

# 12. Clean-room acceptance

From documented setup:

- infrastructure starts;
- migrations run;
- seeds load;
- API starts;
- frontend builds/starts;
- tests pass;
- benchmark runs;
- normal transaction works;
- attack scenarios behave correctly;
- audit verifies.

Approved final phrase only after this:

> Phase-1 local prototype complete.

---

# 13. Permanent execution-integrity regressions

The final Phase-1 gate must also prove:

- forged or malformed tickets create no reservation and no execution attempt;
- a current durable non-`ALLOW` decision cannot execute even when ticket bytes are otherwise valid;
- persisted merchant/product/category/brand/condition constraints survive row-to-domain reconstruction;
- trusted tax, fee, currency and recurring terms enter the checkout authorization projection, while missing recurring frequency fails closed;
- provider-unknown reconciliation persists its reference/outcome and atomically commits or releases the retained reservation;
- a changed authorization amount synchronizes durable capacity while preserving committed/reserved spend and rejects a cap below already consumed capacity;
- a pre-provider setup failure closes partial attempt state and releases both durable reservation and coordination nonce;
- the public audit tamper simulation does not change the ledger's event count or validity;
- the adversarial registry covers all required Phase-1 families and benchmark pipeline errors cannot be scored as prevented attacks.
