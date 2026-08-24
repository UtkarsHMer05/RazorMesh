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

---

# 14. Phase-2 test gates (Razorpay Test Mode — active)

Release-blocking additions on top of all Phase-1 gates:

1. Config guards: live-key rejection; missing-credential refusal naming variables
   only; mock mode credential-free.
2. Order creation: server-authoritative amount/currency; correlation persisted;
   provider-unknown mapping on timeout-before-response and timeout-after-send.
3. Callback verification: valid, forged, mutated payment id, wrong order context,
   replayed, superseded authorization, stale checkout, duplicate → only the first
   legitimate verified callback may commit.
4. Webhook: raw-body HMAC tests (valid, one-byte mutation, reserialization
   mismatch, wrong secret, missing header); durable event-id dedup under
   concurrency; unknown event types handled safely.
5. Reducer permutations: authorized→captured, captured→authorized,
   failed→captured, order.paid→captured, captured→order.paid, duplicates,
   delayed events → converge with exactly one commit/fulfilment effect.
6. Provider-unknown: fault injection proves identity + reservation retention and
   reconciliation (never blind retry).
7. Concurrency regression WITH the real-provider adapter present (mock transport
   for volume): 20 same-ticket attempts → ≤1 provider/business effect.
8. Frontend: launch payload contains public data only; VERIFYING/CAPTURED/FAILED/
   PROVIDER_UNKNOWN states render; no secrets in rendered output/bundle checks.
9. Provider-selector wiring at the API boundary (P2-M37 audit remediation):
   `/buyer/execute` must honor `PAYMENT_PROVIDER` — razorpay mode returns the
   launch payload and stays EXECUTING awaiting capture evidence; mock mode keeps
   Phase-1 SUCCEEDED semantics; razorpay mode without credentials fails closed
   with 503 `RAZORPAY_CONFIG_UNAVAILABLE`. Route-level tests must cover this —
   unit-testing the payload builder alone is not sufficient.
10. Readiness honesty: `/ready` reports the provider selector actually loaded
    from settings; no hardcoded provider flag.

Real Razorpay interaction is limited to milestones that explicitly require it
(M12 auth diagnostic, M17 first order, M18 fetch, M36 webhook, M38/M40 human-gated
checkouts). All high-volume/fault tests use mock/fakes so Razorpay is not spammed.

---

# 15. Test isolation and secret-scan policy (P2-M37 audit remediation)

## Test isolation from the real environment

The backend test suite must NEVER read the real root `.env`:

- the session `settings` fixture constructs `Settings(_env_file=None, ...)`;
- tests therefore run with `PAYMENT_PROVIDER=mock` and NO Razorpay credentials
  regardless of the developer's local selection (P2-S20 determinism);
- real-provider behavior is exercised exclusively through `httpx.MockTransport`
  seams and monkeypatched provider factories;
- standalone real-interaction scripts (`scripts/rzp_auth_check.py`,
  `scripts/rzp_first_order.py`) are NOT pytest tests and read `.env` on purpose.

## Format gate

`ruff format --check .` must be clean in addition to `ruff check .`
(`make lint` runs both). A milestone gate is not green if either fails.

## Secret-scan allowlist

`scripts/security_check.py` may carry an explicit allowlist for synthetic test
fixtures that must look secret-shaped to prove the controls around them
(HMAC fixture secrets; the `rzp_live_` literal required to prove live-key
rejection, P2-S02). Rules:

- each entry pins (exact file path, rule) to the exact literal(s) accepted;
  any other value, or the same value elsewhere, still fails the scan;
- every entry carries a justification comment in the script;
- adding an entry requires updating this section in the same change.
