# PHASE2_M38_EVIDENCE.md — Real Test Success Evidence Record (working)

Captured: 2026-08-24 18:33–18:45 UTC, BEFORE any further test runs, per human
instruction. This file is the durable record of what the local database still
proves about payment #2 after a pre-isolation pytest run destroyed the
business tables. It is completed into the final reconciliation doc at M39.

## Payment #2 identifiers (safe, non-secret)

| Field | Value |
|---|---|
| execution_attempt_id | `exa_01M0TFCS608MSJ59GHHVJ5NP8E` |
| razorpay_order_id | `order_TThUuhmUinebAX` |
| razorpay_payment_id | `pay_TThVaPlcLqu4XE` |
| amount_minor / currency | 239800 / INR |
| checkout completed (human, Test Mode, success@razorpay) | 2026-08-24 ~18:10 UTC |

## provider_events — REAL signed Razorpay deliveries (dev DB, survived)

Query: `SELECT ... FROM provider_events WHERE event_id NOT LIKE 'evt_ok_%' ORDER BY received_at;`
Database: `razormesh` (dev), alembic head `a93c7d5e21f0`.

| event_id | event_type | verified | processing_state | received_at (UTC) | order / payment | payload_sha256 |
|---|---|---|---|---|---|---|
| `TThVgbHU0l5E7y` | payment.authorized | true | PROCESSED | 2026-08-24 18:10:03.115688+00 | order_TThUuhmUinebAX / pay_TThVaPlcLqu4XE | b7e36b076cc3d21e9bf902f992c2e835175230eafb00f5ad88b20dcd4ab93012 |
| `TThVhMzdj2zNfo` | payment.captured | true | PROCESSED | 2026-08-24 18:10:03.274933+00 | order_TThUuhmUinebAX / pay_TThVaPlcLqu4XE | 90f29c5153e82d80f13163166c49861c766600a68dd7ec8b0939caaca8fecb49 |
| `TThVilsyhg1VWm` | order.paid | true | PROCESSED | 2026-08-24 18:10:04.994904+00 | order_TThUuhmUinebAX / pay_TThVaPlcLqu4XE | 7e1d3900ee0680c3f41e861dc2bfe726d7ac442628924f54332bc8db2a110ec7 |

These are the FIRST real Razorpay webhook deliveries ever accepted by the
system (D-032 obligation content). Event ids do not match the `evt_ok_*`
fixture pattern; they share the same ULID time-prefix (`TTh…`) as the
payment/order entities created by Razorpay at transaction time. All three:
raw-body HMAC verified against the root `.env` webhook secret (verified=true),
durable inbox claim PROCESSED (not DUPLICATE/ERROR), correlated to payment #2.

Human-observed delivery facts (same window): three webhook POSTs returned
HTTP 200 immediately after `/buyer/execute`; `/buyer/callback` returned 200.
Older payment-#1 retry deliveries still 403 SIGNATURE_INVALID — they are
signed with the OLD Dashboard secret that preceded the human's secret
correction; 403s are pre-verification with zero mutation (M31/M32 design).

## Business tables — DESTROYED by a pre-isolation pytest run (disclosed)

Exact counts captured 2026-08-24 18:33 UTC (dev DB `razormesh`):

```text
execution_attempts   | 0
authorization_spend  | 0
audit_events         | 0
provider_events      | 33   (30 synthetic evt_ok_* fixture rows + 3 real rows above)
```

Root cause of the loss: ~12 test files build engines from
`razormesh_api.settings.get_settings()`, which reads the real root `.env`
(dev DB URL), bypassing the conftest `settings` fixture. The P2-M38 conftest
change to `razormesh_test` (2026-08-24 18:24 UTC) did not cover them; the
gate run at 18:26–18:27 UTC (fixture rows `order_red_1`/`pay_route_w1`
timestamped there) wiped the dev business tables, destroying payment #2's
attempt/spend/audit rows — the same class of loss that destroyed payment #1.

Timeline (UTC, from DB timestamps + file mtimes):

```text
18:10:03–04  real webhooks accepted (rows above); attempt settled SUCCEEDED
             by the captured event — but through the OLD webhook reducer,
             which lacked a SpendManager, so the reservation was stranded
             (reserved=239800, committed=0; observed by the prior session)
18:18–18:20  code fix: webhooks._reducer() gets SpendManager; provider name
             recorded on attempt creation (uncommitted working tree)
18:22–18:25  regression test + conftest isolation + guarded repair script
18:26–18:27  pytest run still hit DEV via get_settings() → business tables
             wiped → payment #2 attempt/spend/audit evidence destroyed;
             repair script rendered inapplicable (its guarded target row gone)
18:27:20     uvicorn --reload worker restarted → live API carries the fix
```

## Consequences for the M38 gate (non-fabrication statement)

- PROVEN locally, durable: real signed webhook delivery + raw-body HMAC
  verification + durable inbox dedup against REAL provider events
  (D-032 carried-forward obligation: SATISFIED).
- PROVEN by human observation + UI: checkout success, CAPTURED/PAID,
  three 200 webhook POSTs, 200 callback.
- NOT PROVEN for payment #2 (evidence destroyed before capture):
  attempt SUCCEEDED row, and the exactly-once reserved→committed spend
  transition. The commit in fact never ran for payment #2 (the old reducer
  skipped it — that is the defect found), and the stranded reservation row
  was wiped before the guarded repair could be applied and evidenced.
- Therefore M38 "end-to-end exactly-once verification" is INCOMPLETE for
  payment #2. Per AGENTS.md §15 (no PASS without recorded validation) the
  gate requires one further real success checkout (payment #3) against the
  FIXED + test-isolated stack.

## Remediation status (code, this milestone)

1. `webhooks._reducer()` now constructs the reducer WITH `SpendManager`
   (webhook-side settlement converts reserved→committed exactly like the
   callback/execute paths).
2. `PaymentProvider.name` added to the protocol; attempts record the real
   provider name at creation (no more 'mock' column-default for real runs).
3. Test suite isolation: dedicated `razormesh_test` DB + env pinning in
   conftest so `get_settings()` inside tests can never reach the dev DB.
4. Regression `test_webhook_route_wiring_commits_reservation` drives the
   REAL route + REAL `_reducer` wiring and pins reserved→committed once.
5. Guarded one-time repair script kept as evidence of the defect handling
   (`scripts/repair_m38_spend_commit.py`); it now refuses to run because its
   exact guarded target row no longer exists (recorded at M38 close).

## Provider-side reconciliation (READ-ONLY fetch, 2026-08-24 ~18:55 UTC)

`scripts/rzp_m38_evidence.py` (new typed read-only client fetches
`fetch_payment` / `fetch_event`, MockTransport-tested):

```text
mode:    test (test-mode guard passed)
order:   id=order_TThUuhmUinebAX status=paid amount_minor=239800 currency=INR
         receipt=r_exa_01M0TFCS608MSJ59GHHVJ5NP8E
payment: id=pay_TThVaPlcLqu4XE status=captured amount_minor=239800 currency=INR
         order_id=order_TThUuhmUinebAX
```

- The provider-side order row is DURABLE evidence that execution attempt
  `exa_01M0TFCS608MSJ59GHHVJ5NP8E` created this order (receipt embeds the
  attempt id, M14 correlation contract) and that it is now `paid`.
- The payment is `captured` for exactly the server-authoritative amount
  (239800 INR minor) and correlates to the same order.
- Event-entity fetch (`GET /v1/events/{id}`) and event listing
  (`GET /v1/events`) both return 404 for this Test Mode account — the
  Events API is not available here (recorded as R-018). The reality of the
  three deliveries is instead established by: raw-body HMAC against the
  `.env` secret (only Razorpay holds the Dashboard secret), ULID
  time-prefix identity with the order/payment entities, exact order/payment
  correlation, and the human-observed Dashboard delivery 200s.

## Live signed probe through the public tunnel (zero mutation)

`scripts/webhook_live_probe.py` — signs a synthetic payload with the real
`.env` webhook secret and posts it to the registered public share:

```text
POST https://1pvdxdizehva.shares.zrok.io/api/v1/webhooks/razorpay
probe_event_id: evt_probe_m38_1787597607
status_code:    200
body:           {"received":true,"processed":false,"duplicate":false,
                 "reason":"UNMATCHED_CONTEXT"}
```

Proves, against the LIVE process: tunnel alive at the Dashboard-registered
URL; raw-body HMAC verification with the CURRENT secret; unmatched contexts
cause zero business mutation. (First probe returned PROCESSING_ERROR: the
inbox folded unmatched contexts into the generic error path; fixed to the
M31-documented UNMATCHED_CONTEXT classification + `UNMATCHED` inbox state,
regression-tested, and the second probe confirms it live.) The two probe
inbox rows (`evt_probe_*`) are the only new dev rows from verification.

The live probe also proves the running API reloaded the milestone's code
fixes (uvicorn --reload): the UNMATCHED_CONTEXT reason exists only in code
written minutes before the probe, so the SpendManager wiring fix is live too.

## Gate run on the fixed + isolated stack (2026-08-24)

```text
ruff format --check / ruff check      → clean / clean
mypy strict (root + services/api)     → no issues in 52 source files (both)
pytest (full)                         → 329 passed
dev DB after the suite                → BYTE-IDENTICAL (33 provider_events
                                        rows incl. 3 real; business tables
                                        unchanged); fixture residue landed in
                                        razormesh_test ONLY
pnpm lint / typecheck / test          → clean / clean / 6 passed
playwright                            → 2 passed
make security-check                   → PASS (one new documented allowlist
                                        entry for the route-wiring test's
                                        synthetic HMAC secret)
```

Final dev DB state at M38 evidence close: 35 provider_events rows = 30
synthetic `evt_ok_*` fixtures + 3 REAL deliveries + 2 labeled `evt_probe_*`
probe rows; catalog reseeded (50 products / 5 merchants) so the buyer UI is
ready for the next checkout.

## What remains for M38 PASS

One further human success checkout (payment #3) at http://localhost:3000/buyer
(success@razorpay, R-017), after which the agent captures, BEFORE any test
run: attempt row (SUCCEEDED, provider_name=razorpay), spend row
(reserved→committed exactly once), ledger events, and the new real
provider_events rows. The fixed webhook path must perform the commit itself
— no repair script may be needed.

---

# PAYMENT #3 — captured 2026-08-24 19:15 UTC, BEFORE any test run

## Identifiers (safe, non-secret)

| Field | Value |
|---|---|
| intent_id | `intent_01M0TJSMR51H1GVBDWFYKTDRDQ` |
| checkout_id | `chk_01M0TJSRP2ZACBGT2FPDW3KXV7` (rev 1, computed_total=provided_total=479900) |
| decision_id | `dec_01M0TJSRQYC1DDR9Z0Y2XAG890` — **ALLOW**, reason_codes=[] |
| ticket_id | `tk_01M0TJSRRF59BEPPK1HQTSCM47` (issued 19:08:49.271, expiry 19:10:49.271, **used_at 19:08:50.837** — single-use) |
| execution_attempt_id | `exa_01M0TJST9KD53EBCP4WMWNRZ5X` |
| razorpay_order_id | `order_TTiVopXKuCg5ol` |
| payments | `pay_TTiWRlfGgjviWU` (FAILED) → `pay_TTiY0Ny3rAEN9H` (CAPTURED) |
| amount_minor / currency | 479900 / INR |

## Durable state (exact DB rows)

```text
execution_attempts: state=SUCCEEDED  provider_name=razorpay
  razorpay_order_id=order_TTiVopXKuCg5ol  razorpay_payment_id=pay_TTiY0Ny3rAEN9H
  razorpay_payment_status=captured  callback_verified_at=19:11:13.789473+00
  fulfilment_state=ELIGIBLE  reconcile_state=RESOLVED
  created_at=19:08:50.837489  updated_at=19:11:13.789473
authorization_spend: authorized=200000000 reserved=0 committed=479900 version=4
audit chain verify (live /audit/verify): valid=true, events_checked=7
```

## provider_events — payment #3 real deliveries (all verified=true)

| event_id | type | state | received (UTC) | payment |
|---|---|---|---|---|
| `TTiWSPDZ6Drozh` | payment.failed | PROCESSED | 19:09:28.672850 | pay_TTiWRlfGgjviWU |
| `TTiY6VwFdJ22xL` | payment.authorized | **ERROR** | 19:11:02.110227 | pay_TTiY0Ny3rAEN9H |
| `TTiY7EzWlfEjw9` | payment.captured | PROCESSED | 19:11:02.612136 | pay_TTiY0Ny3rAEN9H |
| `TTiY7guxwdrjKC` | order.paid | PROCESSED | 19:11:02.986515 | pay_TTiY0Ny3rAEN9H |

(payload_sha256 for each recorded in the DB rows.)

## Audit timeline (chain verified valid)

```text
1 CHECKOUT_PROPOSED               19:08:49.242  total_minor=479900
2 DECISION_RECORDED               19:08:49.286  decision=ALLOW
3 TICKET_ISSUED                   19:08:49.306  amount_minor=479900
4 EXECUTION_ATTEMPT_CREATED       19:08:50.874  exa_01M0TJST9KD53EBCP4WMWNRZ5X
5 RAZORPAY_ORDER_CREATED          19:08:51.403  order_TTiVopXKuCg5ol
6 PAYMENT_FAILED                  19:09:28.790  RAZORPAY_PAYMENT_FAILED (release)
7 RAZORPAY_RECONCILED_LATE_CAPTURE 19:11:02.821 pay_TTiY0Ny3rAEN9H
                                  reason=RAZORPAY_RECONCILIATION_REQUIRED_RESOLVED
```

## Exactly-once reservation proof (spend version history)

version 1 ensure_authorization → 2 reserve (attempt creation) → 3 release
(payment.failed, definitive) → 4 commit (guarded late-capture reconciliation,
19:11:02.772645). Final: reserved=0, committed=479900 == attempt amount,
exactly one commit. The later order.paid event (19:11:02.986) and the
verified browser callback (19:11:13.789) were idempotent no-ops after
settlement (committed unchanged). The commit was performed by the FIXED
webhook reducer path — no repair script involved.

## Defect found live and fixed (same milestone)

The `payment.authorized` event arrived while the attempt was FAILED and hit
the reducer's fallback `ValueError` ("unsupported provider event kind") —
the M27/D-031 informative-only branch only covered EXECUTING. Zero business
mutation (inbox claimed it, ERROR recorded, controlled 200 returned) and no
settlement impact, but it violated D-031 semantics. Fixed: authorized is now
informative-only in EVERY state; regression
`test_authorized_is_informative_in_every_state` (FAILED and
SUCCEEDED-after-reconcile cases). The ERROR inbox row remains as the
append-only record of the live occurrence.

## Provider-side reconciliation (READ-ONLY fetch, 2026-08-24 ~19:20 UTC)

```text
order:   id=order_TTiVopXKuCg5ol status=paid amount_minor=479900 currency=INR
         receipt=r_exa_01M0TJST9KD53EBCP4WMWNRZ5X
payment: id=pay_TTiWRlfGgjviWU status=failed  amount_minor=479900 order=order_TTiVopXKuCg5ol
payment: id=pay_TTiY0Ny3rAEN9H status=captured amount_minor=479900 order=order_TTiVopXKuCg5ol
```

Provider truth matches local durable state exactly, including the
documented failed→captured same-transaction semantics (R-014/P2-S16).

## Gate run after payment #3 (fixed stack)

```text
ruff format --check / ruff check → clean / clean
mypy strict (both dirs)          → no issues in 52 source files
pytest (full)                    → 330 passed; dev DB business rows unchanged
                                   (only the 4 new real provider events added)
/audit/verify (live)             → valid=true, events_checked=7
```
