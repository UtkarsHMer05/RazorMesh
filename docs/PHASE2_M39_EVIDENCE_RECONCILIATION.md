# Phase-2 Success Evidence Reconciliation (M39)

Scope: reconcile the durable local state, the tamper-evident audit chain,
read-only provider fetches, webhook deliveries and human-observed Dashboard
facts for the REAL Razorpay Test Mode success payments. Safe identifiers
only — no secrets, no raw payloads. Working capture log:
`docs/PHASE2_M38_EVIDENCE.md`.

Date: 2026-08-24/25. Account mode: Razorpay **Test Mode** (guard enforced:
`razorpay_mode` is `Literal["test"]`; live prefixes rejected, M09).

---

## 1. Payments under reconciliation

| | Payment #2 | Payment #3 |
|---|---|---|
| execution_attempt_id | `exa_01M0TFCS608MSJ59GHHVJ5NP8E` | `exa_01M0TJST9KD53EBCP4WMWNRZ5X` |
| razorpay_order_id | `order_TThUuhmUinebAX` | `order_TTiVopXKuCg5ol` |
| captured payment | `pay_TThVaPlcLqu4XE` | `pay_TTiY0Ny3rAEN9H` (after failed `pay_TTiWRlfGgjviWU`) |
| amount | 239800 INR minor | 479900 INR minor |
| checkout instrument | success@razorpay UPI (R-017) | success@razorpay UPI (R-017) |

## 2. DB ↔ Provider reconciliation (read-only fetches)

| Fact | Local durable state | Razorpay-side fetch | Match |
|---|---|---|---|
| #2 order status | attempt SUCCEEDED, order claimed | `order_TThUuhmUinebAX` status=`paid`, 239800 INR | ✓ |
| #2 order→attempt binding | receipt column (M14) | receipt=`r_exa_01M0TFCS608MSJ59GHHVJ5NP8E` | ✓ |
| #2 payment | razorpay_payment_id claimed | `pay_TThVaPlcLqu4XE` status=`captured`, 239800 INR, order matches | ✓ |
| #3 order status | attempt SUCCEEDED, order claimed | `order_TTiVopXKuCg5ol` status=`paid`, 479900 INR | ✓ |
| #3 order→attempt binding | receipt column (M14) | receipt=`r_exa_01M0TJST9KD53EBCP4WMWNRZ5X` | ✓ |
| #3 first payment | payment.failed event processed, release audited | `pay_TTiWRlfGgjviWU` status=`failed`, 479900 INR | ✓ |
| #3 captured payment | razorpay_payment_id claimed | `pay_TTiY0Ny3rAEN9H` status=`captured`, 479900 INR, order matches | ✓ |

Amounts on the provider side equal the server-authoritative amounts from the
verified checkout projection in both cases (browser never authoritative,
P2-S06). Events API (`GET /v1/events{,/{id}}`) returns 404 for this account
(R-018); event reality therefore rests on §3.

## 3. Webhook deliveries ↔ provider_events inbox

Seven REAL signed deliveries are durably recorded (all `verified=true`,
i.e. raw-body HMAC-SHA256 over the exact received bytes matched the Dashboard
secret before ANY parse or mutation — P2-S10/S11):

| event_id | type | inbox state | received (UTC) | correlates to |
|---|---|---|---|---|
| `TThVgbHU0l5E7y` | payment.authorized | PROCESSED | 08-24 18:10:03.115 | #2 order/payment |
| `TThVhMzdj2zNfo` | payment.captured | PROCESSED | 08-24 18:10:03.274 | #2 order/payment |
| `TThVilsyhg1VWm` | order.paid | PROCESSED | 08-24 18:10:04.994 | #2 order |
| `TTiWSPDZ6Drozh` | payment.failed | PROCESSED | 08-24 19:09:28.672 | #3 order, failed payment |
| `TTiY6VwFdJ22xL` | payment.authorized | ERROR* | 08-24 19:11:02.110 | #3 order, captured payment |
| `TTiY7EzWlfEjw9` | payment.captured | PROCESSED | 08-24 19:11:02.612 | #3 order/payment |
| `TTiY7guxwdrjKC` | order.paid | PROCESSED | 08-24 19:11:02.986 | #3 order |

\* The single ERROR row is a disclosed semantics defect, not a security
failure: authorized-in-FAILED-state hit the reducer's unsupported-kind
fallback (D-031 said informative-only). Zero business mutation occurred; the
fix (authorized informative in every state) and regression test landed in the
same milestone (M38/D-034). The row is preserved as the append-only record.

Event-id reality: none match the synthetic `evt_ok_*`/`evt_probe_*`
patterns; all share the ULID time-prefix of the Razorpay entities created at
transaction time; payload_sha256 of each raw body is stored in the inbox.
Durable dedup (P2-S12/S13): event_id is the PRIMARY KEY; duplicates classify
DUPLICATE with zero processing. Human-observed Dashboard fact: every listed
delivery received HTTP 200 from our endpoint. Older payment-#1 retry
deliveries (signed with the pre-correction Dashboard secret) were rejected
403 SIGNATURE_INVALID pre-verification with zero mutation — as designed.

## 4. Audit chain ↔ event sequence (payment #3, chain `valid=true`, 7 events)

```text
CHECKOUT_PROPOSED → DECISION_RECORDED(ALLOW) → TICKET_ISSUED
→ EXECUTION_ATTEMPT_CREATED → RAZORPAY_ORDER_CREATED
→ PAYMENT_FAILED (release) → RAZORPAY_RECONCILED_LATE_CAPTURE (commit)
```

Hash chain verified live (`GET /audit/verify` → `valid=true,
events_checked=7`): tamper-evident, append-oriented, no gaps.

## 5. Reservation semantics (RULES financial-correctness 6–9)

Payment #3 spend row: `authorized=200000000, reserved=0, committed=479900,
version=4` — the version history is exactly: ensure → reserve → release
(definitive failure) → commit (guarded late-capture reconciliation,
capacity-checked, loudly audited as RAZORPAY_RECONCILED_LATE_CAPTURE).
Exactly ONE commit; committed equals the attempt amount; reserved returned to
0. Subsequent order.paid and the verified browser callback were idempotent
no-ops (P2-S15). Payment #2's commit was skipped by a since-fixed wiring
defect and its rows were destroyed by a since-fixed test-isolation defect
before repair (D-033 non-fabrication statement); payment #3 therefore
carries the end-to-end exactly-once proof, performed by the live fixed
webhook path with no repair script.

## 6. Callback ↔ webhook race (payment #3)

Browser callback signature verified server-side against the SERVER-stored
order id (P2-S07/S08) at 19:11:13.789 (`callback_verified_at`) — AFTER the
webhook captured event had already reconciled the attempt at 19:11:02. The
callback path correctly degraded to an idempotent no-op returning the
settled state; no second settlement, no double commit.

## 7. Trust-core invariants observed in production

- Ticket single-use: `used_at` (19:08:50.837) == attempt creation; one
  attempt per ticket (unique constraints).
- RazorGuard ALLOW preceded order creation; decision row `ALLOW`, no
  reason codes.
- Server-recomputed checkout total: computed_total_minor ==
  provided_total_minor == ticket amount == provider order amount.
- provider_name truthfulness: attempt records `razorpay`.
- Test Mode guard live throughout (`/ready` reports razorpay/mock=false;
  mode=test).

## 8. Honest limitations

- Events API unavailable for this account (R-018) — provider-side event
  entities could not be fetched; delivery reality established by HMAC +
  correlation + Dashboard observations.
- Payment #2's local business rows remain destroyed (disclosed, D-033); its
  provider-side order/payment still reconcile (this doc §2) and its three
  real webhook rows remain in the inbox.
- One authorized delivery carries inbox state ERROR for the disclosed
  semantics defect (this doc §3 note); no security impact, fixed + tested.
