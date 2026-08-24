#!/usr/bin/env python3
"""P2-M40 read-only evidence fetch (Razorpay side).

Fetches, READ-ONLY, from the Razorpay Test Mode API:
- the M40 failure order  (status/amount/currency/receipt — receipt embeds the attempt id)
- the M40 failed payment (status/amount/currency/order correlation)

and prints a safe reconciliation summary (identifiers and statuses only;
never secrets, never full payloads). Run from the repo root:
  uv run --project services/api python scripts/rzp_m40_evidence.py
"""

from __future__ import annotations

# (order_id, payment_ids) — M40 guided-failure checkout evidence set.
CASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("order_TTionNHkv0TPGs", ("pay_TTipbCGaqWBrVD",)),
)


def main() -> int:
    from razormesh_api.providers.razorpay import RazorpayError, RazorpayPaymentProvider
    from razormesh_api.settings import Settings

    settings = Settings()
    provider = RazorpayPaymentProvider.from_settings(settings)

    print(f"mode: {settings.razorpay_mode} (test-mode guard passed)")
    failures = 0
    try:
        for order_id, payment_ids in CASES:
            try:
                order = provider.fetch_order(order_id)
                print(
                    f"order:   id={order.order_id} status={order.status} "
                    f"amount_minor={order.amount_minor} currency={order.currency} "
                    f"receipt={order.receipt}"
                )
                for payment_id in payment_ids:
                    payment = provider.fetch_payment(payment_id)
                    print(
                        f"payment: id={payment.payment_id} status={payment.status} "
                        f"amount_minor={payment.amount_minor} currency={payment.currency} "
                        f"order_id={payment.order_id}"
                    )
            except RazorpayError as exc:
                failures += 1
                print(f"FETCH FAILED ({order_id}): {type(exc).__name__}: {exc}")
    finally:
        provider.client.close()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
