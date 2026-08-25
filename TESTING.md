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

1. Config guards: live-key rejection; only `rzp_test_` key ids and the official
   HTTPS API base URL accepted for Razorpay execution; missing-credential refusal
   names variables only; mock mode remains credential-free.
2. Order creation: server-authoritative amount/currency; returned id, amount,
   currency, receipt and create status validated before launch; correlation
   persisted; mismatched response and timeouts map to provider-unknown with the
   reservation held.
3. Callback verification: exact server-issued execution-attempt binding; valid,
   forged, mutated payment id, wrong intent/checkout/order context, replayed,
   superseded authorization, stale checkout, duplicate → only a current,
   legitimately correlated callback may commit.
4. Webhook: raw-body HMAC tests (valid, one-byte mutation, reserialization
   mismatch, wrong secret, missing header); durable event-id dedup under
   concurrency; unknown event types and signed malformed envelopes handled as
   controlled no-ops.
5. Reducer permutations: event amount/currency must match durable authority;
   authorized→captured, captured→authorized,
   failed→captured, order.paid→captured, captured→order.paid, duplicates,
   delayed events → converge with exactly one commit/fulfilment effect. A
   failed payment retains its hold, blocks authorization-capacity reuse, and a
   later capture converts that hold to committed exactly once.
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
11. UI truth re-sync (P2-M40, D-035): `GET /buyer/status` is strictly
    read-only and mirrors the authoritative attempt state (EXECUTING→FAILED
    transition visible; no secrets; unknown context → controlled
    `NO_ATTEMPT`); a verified failure settlement leaves a later browser
    callback inert (FAILED preserved, reservation hold intact, no commit,
    NOT_ELIGIBLE); the callback's not-captured response reports the CURRENT
    state even when a webhook settles mid-request; the frontend re-syncs on
    modal dismiss, hides Re-open on FAILED, and renders SUCCEEDED as
    CAPTURED/PAID.
12. Provider-unknown reconciliation (P2-M41, D-036): timeout faults leave
    PROVIDER_UNKNOWN/REQUIRED with reservation held and no blind second order
    create; receipt discovery claims correlation only after amount/currency
    authority validation; duplicate receipts conflict loudly; fetch-proven
    capture settles exactly-once via the reducer and marks RESOLVED; webhooks
    correlate after a claim; mismatches mutate nothing; /ops surface is
    read-only listing + single safe pass.

Real Razorpay interaction is limited to milestones that explicitly require it
(M12 auth diagnostic, M17 first order, M18 fetch, M36 webhook, M38/M40 human-gated
checkouts). All high-volume/fault tests use mock/fakes so Razorpay is not spammed.

---

# 15. Test isolation and secret-scan policy (P2-M37 audit remediation)

## Test isolation from the real environment

The backend test suite must NEVER read the real root `.env`, and must NEVER
touch the dev database (`razormesh`):

- `conftest.py` pins the environment BEFORE any `razormesh_api` import:
  `DATABASE_URL` → the DEDICATED `razormesh_test` database (overridable via
  `RAZORMESH_TEST_DATABASE_URL`), `PAYMENT_PROVIDER=mock`, and the three
  Razorpay credential variables pinned to EMPTY strings. Env vars take
  precedence over dotenv in pydantic-settings, so this also neutralizes the
  root `.env` for every `get_settings()` call anywhere in the suite; an
  absent variable would NOT — it would let the `.env` value through.
- a session-scoped autouse guard fails the ENTIRE suite instantly if
  `get_settings()` resolves the dev DB, a non-mock provider, or any Razorpay
  credential (P2-S20);
- the session `settings` fixture additionally constructs
  `Settings(_env_file=None, ...)`;
- integration fixtures wipe business tables ONLY in `razormesh_test`. Two
  pre-isolation gate runs (payments #1 and #2, 2026-08-24) reached the dev DB
  through `get_settings()` and destroyed real Test Mode payment evidence; the
  pinning + guard make that class of loss impossible;
- real-provider behavior is exercised exclusively through `httpx.MockTransport`
  seams and monkeypatched provider factories;
- standalone real-interaction scripts (`scripts/rzp_auth_check.py`,
  `scripts/rzp_first_order.py`, `scripts/rzp_m38_evidence.py`,
  `scripts/webhook_live_probe.py`) are NOT pytest tests and read `.env` on
  purpose;
- evidence capture after a REAL payment happens via direct DB queries /
  read-only scripts BEFORE any pytest run, even though the suite is now
  isolated (belt and braces).

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

Current entries: callback-verification HMAC fixture, webhook-verification HMAC
fixture, the P2-M38 route-wiring regression HMAC fixture
(`wh-route-wiring-secret` in `tests/test_reducer.py`), the `rzp_live_`
rejection literal, and the allowlist's own repeated `rzp_live_` literal.
