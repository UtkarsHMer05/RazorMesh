#!/usr/bin/env python3
"""P2-M38 live webhook probe: signed delivery through the public tunnel.

Sends ONE synthetic webhook payload signed with the REAL root .env webhook
secret to the PUBLIC tunnel URL, against an order id that matches nothing.
Expected outcome: HTTP 200, processed=false, UNMATCHED_CONTEXT — proving:

1. the tunnel share is alive and reaches the local API;
2. the live API process verifies raw-body HMAC with the CURRENT .env secret
   (the same check real Razorpay deliveries must pass);
3. unmatched contexts cause ZERO business mutation (inbox claim only).

The probe event id is obviously synthetic (evt_probe_*) so the single inbox
row it creates can never be confused with a real delivery. Prints no secrets.
Run from the repo root:
  uv run --project services/api python scripts/webhook_live_probe.py
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time


def main() -> int:
    import httpx
    from razormesh_api.settings import Settings

    settings = Settings()
    public_url = settings.razorpay_webhook_public_url.rstrip("/")
    secret = settings.razorpay_webhook_secret.get_secret_value()
    if not public_url:
        print("RAZORPAY_WEBHOOK_PUBLIC_URL is empty — set it in .env first")
        return 2
    if not secret:
        print("RAZORPAY_WEBHOOK_SECRET is ABSENT — cannot sign the probe")
        return 2

    probe_id = f"evt_probe_m38_{int(time.time())}"
    raw = json.dumps(
        {
            "entity": "event",
            "event": "payment.captured",
            "id": probe_id,
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_PROBE_NONE",
                        "order_id": "order_PROBE_NONE",
                        "status": "captured",
                    }
                }
            },
        },
        separators=(",", ":"),
    ).encode()
    signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()

    url = f"{public_url}{settings.razorpay_webhook_path}"
    response = httpx.post(
        url,
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
            "x-razorpay-event-id": probe_id,
        },
        timeout=15,
    )
    print(f"POST {url}")
    print(f"probe_event_id: {probe_id}")
    print(f"status_code:    {response.status_code}")
    print(f"body:           {response.text[:400]}")

    ok = response.status_code == 200
    if ok:
        try:
            data = response.json()
            ok = (
                data.get("processed") is False
                and data.get("reason") == "UNMATCHED_CONTEXT"
            )
        except ValueError:
            ok = False
    print(
        "RESULT: PASS — signature verified by live API, unmatched context, "
        "zero business mutation"
        if ok
        else "RESULT: UNEXPECTED — investigate before relying on the webhook path"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
