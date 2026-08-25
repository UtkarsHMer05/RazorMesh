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

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from razormesh_api.reducer import ProviderStateReducer, VerifiedProviderEvent
from razormesh_api.settings import Settings, get_settings

router = APIRouter(tags=["webhooks"])

_MAX_WEBHOOK_BYTES = 256 * 1024

_KNOWN_EVENT_PREFIXES = ("payment.", "order.")

_logger = logging.getLogger("razormesh.webhooks")


def _log_safe_rejection(
    *,
    reason: str,
    signature_header_present: bool,
    event_id_present: bool,
    body_bytes: int,
    webhook_secret_len: int,
) -> None:
    """Server-side diagnostic for webhook rejections (P2-M38).

    Reports ONLY non-secret facts. Never logs the secret, the signature
    header value, the body, or any HMAC digest.
    """
    _logger.warning(
        "webhook rejected: reason=%s signature_header_present=%s "
        "event_id_present=%s body_bytes=%d webhook_secret_len=%d",
        reason,
        signature_header_present,
        event_id_present,
        body_bytes,
        webhook_secret_len,
    )


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

    if not signature_header:
        _log_safe_rejection(
            reason="SIGNATURE_MISSING",
            signature_header_present=False,
            event_id_present=True,
            body_bytes=len(raw),
            webhook_secret_len=len(settings.razorpay_webhook_secret.get_secret_value()),
        )
        raise HTTPException(status_code=403, detail={"code": "RAZORPAY_WEBHOOK_SIGNATURE_MISSING"})

    if not verify_webhook_signature(
        raw_body=raw,
        signature=signature_header,
        webhook_secret=settings.razorpay_webhook_secret.get_secret_value(),
    ):
        # No business mutation on unverified input (P2-S11).
        _log_safe_rejection(
            reason="SIGNATURE_INVALID",
            signature_header_present=True,
            event_id_present=True,
            body_bytes=len(raw),
            webhook_secret_len=len(settings.razorpay_webhook_secret.get_secret_value()),
        )
        raise HTTPException(status_code=403, detail={"code": "RAZORPAY_WEBHOOK_SIGNATURE_INVALID"})

    import json

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {"received": True, "processed": False, "reason": "UNPARSEABLE_BODY"}

    if not isinstance(payload, dict) or not isinstance(payload.get("event"), str):
        return {"received": True, "processed": False, "reason": "UNKNOWN_EVENT"}

    event_type = payload["event"]
    provider_payload = payload.get("payload", {})
    if not isinstance(provider_payload, dict):
        return {"received": True, "processed": False, "reason": "UNKNOWN_EVENT_PAYLOAD"}
    payment_wrapper = provider_payload.get("payment", {})
    order_wrapper = provider_payload.get("order", {})
    payment_entity = payment_wrapper.get("entity", {}) if isinstance(payment_wrapper, dict) else {}
    order_entity = order_wrapper.get("entity", {}) if isinstance(order_wrapper, dict) else {}
    if not isinstance(payment_entity, dict):
        payment_entity = {}
    if not isinstance(order_entity, dict):
        order_entity = {}
    order_id = payment_entity.get("order_id") or order_entity.get("id")
    payment_id = payment_entity.get("id")
    amount_minor = payment_entity.get("amount", order_entity.get("amount"))
    currency = payment_entity.get("currency", order_entity.get("currency"))

    from razormesh_api.webhook_inbox import ingest_verified_event

    reducer = _reducer(settings)
    repos = _repos_for(settings)
    import hashlib as _hl

    payload_sha256 = _hl.sha256(raw).hexdigest()
    rid = payment_entity.get("id") if isinstance(payment_entity, dict) else None

    def _apply() -> None:
        if event_type in (
            "payment.captured",
            "order.paid",
            "payment.failed",
            "payment.authorized",
        ) and isinstance(order_id, str):
            from razormesh_api.providers.razorpay import RazorpayProviderStateConflict

            if not isinstance(amount_minor, int) or amount_minor <= 0:
                raise RazorpayProviderStateConflict(
                    "RAZORPAY_AMOUNT_MISMATCH",
                    "verified provider event omitted a valid integer amount",
                )
            if not isinstance(currency, str) or len(currency) != 3:
                raise RazorpayProviderStateConflict(
                    "RAZORPAY_CURRENCY_MISMATCH",
                    "verified provider event omitted a valid currency",
                )
            reducer.apply_event(
                VerifiedProviderEvent(
                    kind=event_type,
                    razorpay_order_id=order_id,
                    razorpay_payment_id=payment_id if isinstance(payment_id, str) else None,
                    amount_minor=amount_minor,
                    currency=currency,
                )
            )

    if event_type in (
        "payment.captured",
        "order.paid",
        "payment.failed",
        "payment.authorized",
    ) and isinstance(order_id, str):
        result = ingest_verified_event(
            repos,
            event_id=event_id,
            event_type=event_type,
            payload_sha256=payload_sha256,
            razorpay_order_id=order_id,
            razorpay_payment_id=rid,
            process=_apply,
        )
        # P2-M44: tamper-evident ingestion record — the WINNER only, so
        # duplicate deliveries never grow the hash chain (single effect).
        # Best-effort correlation to the durable attempt (safe identifiers
        # only; an unmatched context still records its own evidence).
        if result.processed:
            from razormesh_api.ledger import EvidenceLedger
            from razormesh_api.persistence.models import ExecutionAttempt

            intent_ref = checkout_ref = attempt_ref = None
            with repos.transaction() as session:
                claimed = (
                    session.query(ExecutionAttempt)
                    .filter(ExecutionAttempt.razorpay_order_id == order_id)
                    .first()
                )
                if claimed is not None:
                    intent_ref = str(claimed.intent_id)
                    checkout_ref = str(claimed.checkout_id)
                    attempt_ref = claimed.execution_attempt_id

            EvidenceLedger(repos).append(
                event_type="RAZORPAY_WEBHOOK_INGESTED",
                actor="webhook-route",
                intent_id=intent_ref,
                checkout_id=checkout_ref,
                ticket_id=None,
                payload={
                    "event_id": event_id,
                    "event_type": event_type,
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": rid if isinstance(rid, str) else None,
                    "payload_sha256": payload_sha256,
                    "signature_verified": True,
                    "execution_attempt_id": attempt_ref,
                },
            )
        return {
            "received": True,
            "processed": result.processed,
            "duplicate": result.duplicate,
            "reason": result.reason or ("OK" if result.processed else "IGNORED"),
        }
    if not str(event_type).startswith(_KNOWN_EVENT_PREFIXES):
        return {"received": True, "processed": False, "reason": "IGNORED_EVENT_TYPE"}

    return {"received": True, "processed": False, "reason": "UNROUTED_EVENT"}


async def _read_bounded(request: Request) -> bytes:
    length = request.headers.get("content-length")
    if length is not None and length.isdigit() and int(length) > _MAX_WEBHOOK_BYTES:
        raise HTTPException(status_code=413, detail={"code": "WEBHOOK_TOO_LARGE"})
    body = await request.body()
    if len(body) > _MAX_WEBHOOK_BYTES:
        raise HTTPException(status_code=413, detail={"code": "WEBHOOK_TOO_LARGE"})
    return body


def _repos_for(settings: Settings):  # type: ignore[no-untyped-def]
    from razormesh_api.persistence.db import create_db_engine, create_session_factory
    from razormesh_api.persistence.repositories import Repositories

    engine = create_db_engine(settings.database_url)
    return Repositories(create_session_factory(engine))


def _reducer(settings: Settings) -> ProviderStateReducer:
    """Test seam: monkeypatched by the suite to inject fakes."""
    from razormesh_api.keys import DevSigningKeys
    from razormesh_api.nonce import NonceRegistry
    from razormesh_api.providers.razorpay import RazorpayClient, RazorpayPaymentProvider
    from razormesh_api.spend import SpendManager

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
    repos = _repos_for(settings)
    return ProviderStateReducer(
        repos=repos,
        keys=keys,
        nonces=nonces,
        provider=RazorpayPaymentProvider(client),
        # P2-M38 fix: webhook-side settlement MUST convert reserved->committed
        # exactly like the callback/execute paths. Without a SpendManager the
        # executor silently skipped the spend block in _settle().
        spend=SpendManager(repos),
    )
