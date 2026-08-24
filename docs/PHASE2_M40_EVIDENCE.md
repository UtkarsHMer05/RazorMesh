# P2-M40 Evidence — Real Test Mode Failure Checkout

Date: 2026-08-25 (evidence captured session-local; DB timestamps UTC)
Milestone: Phase-2 M40 — HUMAN GATE, Real Test Failure
Real Razorpay interaction: TEST_CHECKOUT (human, one failure) + WEBHOOK
(one real signed payment.failed delivery) + READ_ONLY (order/payment fetches)

All identifiers below are safe (ULIDs / provider test-mode ids / SHA prefixes).
No secrets, no raw payloads, no secret-derived values appear in this document.

---

## 1. Human-observed facts (gate input)

- Human performed ONE failure checkout at `http://localhost:3000/buyer`
  (Razorpay Test Mode; R-017 failure instrument).
- Razorpay displayed "Payment could not be completed / Payment failed".
  Human closed the modal and did NOT retry.
- The buyer page kept showing `Payment state: EXECUTING` and a
  "Re-open Razorpay Test Checkout" button.
- Instruction: capture evidence BEFORE any test run or state reset; decide
  whether this is UI/state-propagation lag or a real reconciliation defect.

## 2. Evidence captured BEFORE any pytest run (read-only)

Captured via `docker exec razormesh-postgres psql` (read-only queries),
`curl` against the live API (read-only endpoints), and one READ_ONLY
provider fetch script. No test suite had run yet in this session.

### 2.1 Execution attempt (dev DB, `execution_attempts`)

```text
execution_attempt_id    exa_01M0TKTPWPR593Y4HNW48BF0SE
state                   FAILED
error_code              RAZORPAY_PAYMENT_FAILED
provider_name           razorpay
razorpay_order_id       order_TTionNHkv0TPGs
razorpay_payment_id     pay_TTipbCGaqWBrVD
razorpay_order_status   created
razorpay_payment_status failed
callback_verified_at    NULL            (no browser success callback — correct:
                                         checkout.js invokes the handler only on
                                         success; a failed payment produces none)
fulfilment_state        NOT_ELIGIBLE
reconcile_state         NONE
created_at              2026-08-24 19:26:48.691039+00
updated_at              2026-08-24 19:27:41.671257+00   (webhook settlement)
intent_id               intent_01M0TKTHR5D43WHWY4ZCDANCPC
checkout_id             chk_01M0TKTN2YPSNDFE53XE3FX3DB
ticket_id               tk_01M0TKTN4D7C5CDRWWD1NQD7M7 (used_at == attempt
                        created_at → single-use honored)
```

### 2.2 Reservation / spend (`authorization_spend`)

```text
intent_id        intent_01M0TKTHR5D43WHWY4ZCDANCPC
authorized_minor 200000000
reserved_minor   0          ← reservation RELEASED
committed_minor  0          ← unchanged; nothing was ever committed
version          3          ← ensure(v1) → reserve(v2) → release(v3):
                              exactly ONE release, no re-reservation
```

M38 payment #3's spend row verified unchanged in the same capture
(committed_minor=479900, version=4) — no cross-transaction interference.

### 2.3 Webhook inbox (`provider_events`, real rows only)

```text
event_id          event_type        received_at                      verified  state
TTiphMTgXsdq0K    payment.failed    2026-08-24 19:27:41.541738+00    true      PROCESSED
                  payload_sha256 prefix acc1b020b0ab9f6d…  error: (none)
```

- The M40 payment.failed delivery is signature-verified (`verified=true`)
  and processed exactly once. Settlement (19:27:41.671) follows inbox claim
  (19:27:41.541) by ~130 ms.
- The event id shares the ULID time-prefix of `pay_TTipbCGaqWBrVD`
  (created at transaction time) — same identity pattern established in M38/M39.
- Real-row census at capture time: 10 rows excluding `evt_ok_*` fixtures —
  3 payment-#2 deliveries, 2 signed probes (one ERROR pre-D-033 fix, one
  UNMATCHED), 4 payment-#3 deliveries, 1 M40 delivery. All verified=true.

### 2.4 Audit trail (`audit_events`)

```text
seq  event_type                     actor                       timestamp
 8   CHECKOUT_PROPOSED              checkout-service            19:26:46.893154+00
 9   DECISION_RECORDED (ALLOW)      razorguard                  19:26:46.920191+00
10   TICKET_ISSUED                  checkout-service            19:26:46.932176+00
11   EXECUTION_ATTEMPT_CREATED      trusted-payment-executor    19:26:48.734085+00
12   RAZORPAY_ORDER_CREATED         trusted-payment-executor    19:26:49.240539+00
13   PAYMENT_FAILED                 trusted-payment-executor    19:27:41.651753+00
     metadata: error_code=RAZORPAY_PAYMENT_FAILED,
               execution_attempt_id=exa_01M0TKTPWPR593Y4HNW48BF0SE
```

Live chain verification (read-only): `GET /audit/verify` →
`{"valid": true, "events_checked": 13, "broken_at_event_id": null}`.

The PAYMENT_FAILED event exists (checklist item ✓) and the chain is intact.

### 2.5 Live authoritative status (new read-only endpoint)

```text
GET /buyer/status?intent_id=intent_01M0TKTHR5D43WHWY4ZCDANCPC
                 &checkout_id=chk_01M0TKTN2YPSNDFE53XE3FX3DB
→ {"state":"FAILED","attempt_id":"exa_01M0TKTPWPR593Y4HNW48BF0SE",
   "fulfilment_state":"NOT_ELIGIBLE","razorpay_order_id":"order_TTionNHkv0TPGs",
   "razorpay_payment_status":"failed","error_code":"RAZORPAY_PAYMENT_FAILED"}
```

### 2.6 Provider-side READ_ONLY fetch (`scripts/rzp_m40_evidence.py`)

```text
mode: test (test-mode guard passed)
order:   id=order_TTionNHkv0TPGs status=attempted amount_minor=479900
         currency=INR receipt=r_exa_01M0TKTPWPR593Y4HNW48BF0SE
payment: id=pay_TTipbCGaqWBrVD status=failed amount_minor=479900
         currency=INR order_id=order_TTionNHkv0TPGs
```

Provider truth matches local durable state: the payment failed; the order
is `attempted` (payment attempted, never paid); the receipt binds the
provider order to exactly one attempt.

## 3. Diagnosis: UI state-propagation gap, NOT a reconciliation defect

Backend reconciliation worked exactly as designed: the verified
payment.failed webhook settled the attempt EXECUTING→FAILED with an atomic,
single release of the reservation, audited, with no fulfilment.

The stale UI happened because, on the failure path, the browser receives
NO signal: checkout.js invokes `handler` only on success, so no
`/buyer/callback` ever occurs, and the pre-M40 page had no way to re-read
server truth after the modal was dismissed — it kept its last local phase
(`awaiting_checkout` → "EXECUTING" + Re-open button) while the webhook had
already settled the attempt 53 seconds after order creation.

Conclusion: **UI/state propagation lag only.** Durable state was FAILED the
whole time; no attempt was ever stuck in EXECUTING server-side.

## 4. Fix (completed this milestone)

An in-progress remediation was found uncommitted in the working tree at
session start (read-only `GET /buyer/status`, UI `ondismiss` re-sync, one
backend regression test referencing the live attempt above). It was
reviewed, completed, and fully gated this milestone:

1. `GET /buyer/status` (buyer.py): read-only authoritative snapshot
   (state, attempt_id, fulfilment_state, razorpay_order_id,
   razorpay_payment_status, error_code); controlled `NO_ATTEMPT` for
   unknown contexts; zero mutation.
2. Buyer page: modal `ondismiss` → re-sync from `/buyer/status`;
   manual "Refresh status from server" button while EXECUTING/UNKNOWN;
   FAILED renders a truthful note (nothing fulfilled, reservation released)
   and HIDES the Re-open button; SUCCEEDED renders CAPTURED/PAID.
3. Callback not-captured branch now re-reads the CURRENT attempt state
   instead of returning its initial pre-lock snapshot — a webhook settling
   mid-request can no longer produce a stale "EXECUTING" response.
4. Reducer `_mark_payment_fields`: removed a dead `if False` code artifact
   (behavior unchanged).

## 5. Race analysis — no callback/webhook race can stick an attempt in EXECUTING

Paths that can move an EXECUTING attempt, and their serialization:

- **Webhook reducer** (`_settle`): `SELECT … FOR UPDATE` on the attempt row
  + `require_transition` state gate + reservation release/commit in the
  SAME transaction. Terminal states (`SUCCEEDED`, `FAILED`) have an empty
  transition set — once settled, no reducer/callback path can move the row.
- **Duplicate deliveries** (same event id): inbox primary-key claim —
  exactly one PROCESSED, losers DUPLICATE with zero business logic.
- **Concurrent distinct events** (e.g. failed vs captured for one order):
  both serialize on the row lock; the loser either no-ops (SUCCEEDED
  short-circuit), reconciles through the guarded capacity-checked
  FAILED→SUCCEEDED path, or raises `IllegalAttemptTransition` under the
  lock → inbox ERROR row, attempt ALREADY terminal. Every interleaving
  leaves the attempt FAILED or SUCCEEDED — never EXECUTING.
- **Callback**: never settles FAILED; settles SUCCEEDED only on provider
  `paid` evidence via the same locked, exactly-once path (duplicate after
  settlement = idempotent no-op); otherwise writes only `callback_verified_at`
  metadata. A callback racing a failure webhook cannot block or revert it.
- **UI reads** (`/buyer/status`): strictly read-only.

Residual narrow window (documented, money-safe): capture evidence processed
against a stale EXECUTING snapshot of an already-FAILED row raises
`IllegalAttemptTransition` → inbox ERROR; the attempt stays FAILED (no
fulfilment, reservation already released). Recovery is a later distinct
capture event (order.paid follows captured) or operator reconciliation —
M41's scope. No interleaving leaves EXECUTING.

## 6. Regression tests added (permanent)

Backend (`services/api/tests`):
- `test_buyer_execute_provider_wiring.py::
  test_status_endpoint_reflects_server_truth_and_is_read_only` — status
  mirrors EXECUTING→FAILED, leaks no secrets, repeated reads identical,
  reservation released exactly once (spend version frozen after settle),
  unknown context → controlled NO_ATTEMPT.
- `test_callback_verification.py::
  test_callback_after_webhook_failure_settlement_stays_failed_and_released`
  — the live M40 sequence: reducer-settled FAILED, then verified callback
  is inert (FAILED response, release intact, no re-reserve/commit,
  NOT_ELIGIBLE).
- `test_callback_verification.py::
  test_callback_reports_fresh_state_when_failure_settles_mid_request` —
  failure settles WHILE the callback is in flight; response reports FAILED,
  never the stale EXECUTING snapshot.

Frontend (`apps/web/src/app/buyer/buyer-state-sync.test.tsx`):
- modal dismiss shows FAILED when the webhook already settled (re-open and
  refresh removed; exactly one correctly-parameterized status call);
- modal dismiss keeps re-open available while the server says EXECUTING;
- manual refresh renders SUCCEEDED (CAPTURED/PAID) and removes actions.

## 7. Gate run at PASS

```text
ruff format --check / ruff check        → clean / clean
mypy strict (root + services/api)       → no issues in 52 source files (both)
pytest (full)                           → 333 passed (330 + status endpoint
                                          + 2 callback race regressions);
                                          dev DB business rows byte-identical
                                          after the run (isolation guard)
pnpm lint / typecheck / test            → clean / clean / 9 passed (6 + 3 new)
pnpm build                              → OK (6 routes, static prerender)
playwright                              → 2 passed
make security-check                     → PASS (secret scan 0; pip-audit clean;
                                          pnpm audit clean)
live /ready                             → payment_provider=razorpay, mock=false
live GET /buyer/status (M40 attempt)    → FAILED / NOT_ELIGIBLE / failed
dev server bundle                       → served chunk contains the new
                                          "Refresh status from server" UI
```

## 8. Checklist disposition (human-requested verification)

| Check | Result |
|---|---|
| real payment.failed webhook verified=true | ✓ `TTiphMTgXsdq0K`, verified=true, PROCESSED (§2.3) |
| ExecutionAttempt transitions to FAILED | ✓ §2.1 (settled 19:27:41.671 UTC) |
| fulfilment remains not eligible | ✓ NOT_ELIGIBLE (§2.1, §2.5) |
| reservation released exactly once | ✓ version 3 = ensure→reserve→release; reserved=0 (§2.2) |
| committed amount unchanged | ✓ committed=0 before and after; M38 row untouched (§2.2) |
| PAYMENT_FAILED audit event exists | ✓ seq 13; chain valid, 13 events (§2.4) |
| no callback/webhook race leaves attempt EXECUTING | ✓ analysis §5 + 2 new race regressions §6 |

## 9. Known limitations / carry-forward

- The buyer page holds attempt context in component state: a full page
  RELOAD resets to an idle flow and cannot redisplay a past attempt's
  server state (the backend remains the durable record). Candidate for
  M45 (Buyer UI Trust-State Polish).
- The human's stale tab predates the new bundle; the served bundle now
  includes the re-sync UI (§7). With the new bundle, dismissing the modal
  or clicking "Refresh status from server" renders the truthful FAILED
  state and removes the Re-open action.
- No financial state was repaired or reconstructed — none needed to be:
  the live pipeline was correct end to end.
