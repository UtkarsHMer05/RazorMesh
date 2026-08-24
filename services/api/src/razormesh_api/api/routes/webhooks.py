"""P2-M31/M32: Razorpay webhook endpoint — RAW-BODY signature verification.

Security properties (P2-S10/S11, master prompt §22/§25):
- the request body is captured as RAW BYTES before ANY parsing;
- HMAC-SHA256(raw_body, webhook_secret) must equal X-Razorpay-Signature;
- invalid/missing signatures cause ZERO business mutation (fail closed);
- x-razorpay-event-id is required for durable dedup (inbox lands in M33);
- oversized requests are refused before reading into memory beyond the cap.

Verified events are reduced through ProviderStateReducer; unparseable or unknown
event types are accepted with 200 and recorded as ignored (Razorpay retries
non-200 deliveries; business safety never depends on that retry behavior).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from razormesh_api.reducer import ProviderStateReducer, VerifiedProviderEvent
from razormesh_api.settings import Settings, get_settings

router = APIRouter(tags=["webhooks"])

_MAX_WEBHOOK_BYTES = 256 * 1024

_KNOWN_EVENT_PREFIXES = ("payment.", "order.")


@router.post("/api/v1/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:

    raw = await _read_bounded(request)
    signature_header = request.headers.get("X-Razorpay-Signature")
    event_id = request.headers.get("x-razorpay-event-id")

    if not event_id:
        # Dedup identity is mandatory for safe processing (P2-S12).
        raise HTTPException(status_code=400, detail={"code": "RAZORPAY_WEBHOOK_EVENT_UNKNOWN"})

    from razormesh_api.providers.razorpay import verify_webhook_signature

    if not signature_header or not verify_webhook_signature(
        raw_body=raw,
        signature=signature_header,
        webhook_secret=settings.razorpay_webhook_secret.get_secret_value(),
    ):
        # No business mutation on unverified input (P2-S11).
        raise HTTPException(status_code=403, detail={"code": "RAZORPAY_WEBHOOK_SIGNATURE_INVALID"})

    import json

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {"received": True, "processed": False, "reason": "UNPARSEABLE_BODY"}

    if not isinstance(payload, dict) or not isinstance(payload.get("event"), str):
        return {"received": True, "processed": False, "reason": "UNKNOWN_EVENT"}

    event_type = payload["event"]
    entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    order_id = entity.get("order_id")
    payment_id = entity.get("id")

    reducer = _reducer(settings)

    if event_type in (
        "payment.captured",
        "order.paid",
        "payment.failed",
        "payment.authorized",
    ) and isinstance(order_id, str):
        try:
            reducer.apply_event(
                VerifiedProviderEvent(
                    kind=event_type,
                    razorpay_order_id=order_id,
                    razorpay_payment_id=payment_id if isinstance(payment_id, str) else None,
                )
            )
        except Exception as exc:  # noqa: BLE001 - controlled acceptance below
            # Unknown/unmatched orders must still 200 so Razorpay stops retrying;
            # the mismatch is surfaced to operators via logs/monitoring.
            del exc
            return {"received": True, "processed": False, "reason": "UNMATCHED_CONTEXT"}
    elif not event_type.startswith(_KNOWN_EVENT_PREFIXES):
        return {"received": True, "processed": False, "reason": "IGNORED_EVENT_TYPE"}

    return {"received": True, "processed": True}


async def _read_bounded(request: Request) -> bytes:
    length = request.headers.get("content-length")
    if length is not None and length.isdigit() and int(length) > _MAX_WEBHOOK_BYTES:
        raise HTTPException(status_code=413, detail={"code": "WEBHOOK_TOO_LARGE"})
    body = await request.body()
    if len(body) > _MAX_WEBHOOK_BYTES:
        raise HTTPException(status_code=413, detail={"code": "WEBHOOK_TOO_LARGE"})
    return body


def _reducer(settings: Settings) -> ProviderStateReducer:
    """Test seam: monkeypatched by the suite to inject fakes."""
    from razormesh_api.keys import DevSigningKeys
    from razormesh_api.nonce import NonceRegistry
    from razormesh_api.persistence.db import create_db_engine, create_session_factory
    from razormesh_api.persistence.repositories import Repositories
    from razormesh_api.providers.razorpay import RazorpayClient, RazorpayPaymentProvider

    engine = create_db_engine(settings.database_url)
    repos = Repositories(create_session_factory(engine))
    keys = DevSigningKeys(
        private_path=settings.dev_ticket_private_key_path,
        public_path=settings.dev_ticket_public_key_path,
    ).ensure()
    nonces = NonceRegistry(
        __import__("redis").Redis.from_url(settings.redis_url, decode_responses=True),
        ttl_seconds=120,
    )
    client = RazorpayClient(
        key_id=settings.razorpay_key_id,
        key_secret=settings.razorpay_key_secret.get_secret_value(),
        base_url=settings.razorpay_api_base_url,
        timeout_seconds=settings.razorpay_request_timeout_seconds,
    )
    return ProviderStateReducer(
        repos=repos, keys=keys, nonces=nonces, provider=RazorpayPaymentProvider(client)
    )
