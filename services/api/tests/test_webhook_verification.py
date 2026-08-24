"""P2-M31/M32: webhook endpoint — raw-body necessity and signature matrix."""

import hashlib
import hmac as hmac_mod
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from razormesh_api import api as api_pkg
from razormesh_api.settings import Settings, get_settings

SECRET = "webhook-secret-test-value"


def _sign(raw: bytes, secret: str = SECRET) -> str:
    return hmac_mod.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def _payload(event: str = "payment.captured", order_id: str = "order_w1") -> bytes:
    return json.dumps(
        {
            "entity": "event",
            "event": event,
            "payload": {
                "payment": {"entity": {"id": "pay_w1", "order_id": order_id, "status": "captured"}}
            },
        }
    ).encode()


@pytest.fixture()
def hook_client(monkeypatch):  # type: ignore[no-untyped-def]
    from razormesh_api.api.routes import webhooks as wh

    settings = Settings(
        database_url=get_settings().database_url,
        redis_url=get_settings().redis_url,
        payment_provider="razorpay",
        razorpay_key_id="rzp_test_k",
        razorpay_key_secret=SECRET,
        razorpay_webhook_secret=SECRET,
        _env_file=None,
    )

    class _NoReducer:
        def apply_event(self, event):  # type: ignore[no-untyped-def]
            return {"state": "SUCCEEDED"}

    monkeypatch.setattr(wh, "_reducer", lambda s: _NoReducer())

    def _override() -> Settings:
        return settings

    api_pkg.main.get_settings.cache_clear()
    app = api_pkg.main.app
    app.dependency_overrides[api_pkg.main.get_settings] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    api_pkg.main.get_settings.cache_clear()


def test_valid_signature_accepted(hook_client: TestClient) -> None:
    raw = _payload()
    res = hook_client.post(
        "/api/v1/webhooks/razorpay",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": _sign(raw),
            "x-razorpay-event-id": f"evt_ok_{uuid.uuid4()}",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["received"] is True and body["processed"] is True


def test_missing_signature_rejected_no_mutation(hook_client: TestClient) -> None:
    raw = _payload()
    res = hook_client.post(
        "/api/v1/webhooks/razorpay",
        content=raw,
        headers={"x-razorpay-event-id": "evt_x"},
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "RAZORPAY_WEBHOOK_SIGNATURE_MISSING"


def test_signature_header_lookup_is_case_insensitive(hook_client: TestClient) -> None:
    """P2-M38: Razorpay sends X-Razorpay-Signature; HTTP header names are
    case-insensitive, so a lowercase variant of a VALID signature must also
    verify (Starlette Headers lookup is case-insensitive)."""
    raw = _payload()
    res = hook_client.post(
        "/api/v1/webhooks/razorpay",
        content=raw,
        headers={
            "x-razorpay-signature": _sign(raw),
            "x-razorpay-event-id": f"evt_ok_{uuid.uuid4()}",
        },
    )
    assert res.status_code == 200, res.text


def test_rejection_bodies_disclose_only_controlled_code(hook_client: TestClient) -> None:
    """P2-M38: 403/400 rejection payloads carry exactly one controlled code.
    No secret material, signature, digest, or body echo may leak."""
    raw = _payload()
    missing = hook_client.post(
        "/api/v1/webhooks/razorpay", content=raw, headers={"x-razorpay-event-id": "evt_l1"}
    )
    invalid = hook_client.post(
        "/api/v1/webhooks/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": "0" * 64, "x-razorpay-event-id": "evt_l2"},
    )
    for res in (missing, invalid):
        detail = res.json()["detail"]
        assert set(detail) == {"code"}
        assert isinstance(detail["code"], str) and detail["code"].startswith("RAZORPAY_WEBHOOK_")


def test_one_byte_body_mutation_rejected(hook_client: TestClient) -> None:
    raw = _payload()
    mutated = bytearray(raw)
    mutated[mutated.index(b"1")] = ord("2")
    res = hook_client.post(
        "/api/v1/webhooks/razorpay",
        content=bytes(mutated),
        headers={
            "X-Razorpay-Signature": _sign(raw),  # signature over ORIGINAL bytes
            "x-razorpay-event-id": f"evt_mut_{uuid.uuid4()}",
        },
    )
    assert res.status_code == 403


def test_wrong_secret_rejected(hook_client: TestClient) -> None:
    raw = _payload()
    res = hook_client.post(
        "/api/v1/webhooks/razorpay",
        content=raw,
        headers={
            "X-Razorpay-Signature": _sign(raw, secret="attacker"),
            "x-razorpay-event-id": f"evt_ws_{uuid.uuid4()}",
        },
    )
    assert res.status_code == 403


def test_reserialization_can_break_signature_proving_raw_body_necessity(hook_client) -> None:  # type: ignore[no-untyped-def]
    """§25: parse→re-dump may change bytes; only ORIGINAL bytes verify."""
    raw = _payload()
    parsed = json.loads(raw)
    redumped = json.dumps(parsed, separators=(",", ":")).encode()  # different spacing
    if redumped == raw:
        redumped = json.dumps(parsed, indent=1).encode()
    assert redumped != raw

    sig_over_redumped = _sign(redumped)
    # sending REDUMPED bytes but verifying expectation built over original fails;
    # conversely the endpoint must verify against the bytes it RECEIVED.
    res = hook_client.post(
        "/api/v1/webhooks/razorpay",
        content=raw,
        headers={
            "X-Razorpay-Signature": sig_over_redumped,
            "x-razorpay-event-id": f"evt_r_{uuid.uuid4()}",
        },
    )
    assert res.status_code == 403


def test_missing_event_id_rejected(hook_client: TestClient) -> None:
    raw = _payload()
    res = hook_client.post(
        "/api/v1/webhooks/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": _sign(raw)},
    )
    assert res.status_code == 400


def test_unknown_event_type_accepted_ignored(hook_client: TestClient) -> None:
    raw = _payload(event="refund.processed")
    res = hook_client.post(
        "/api/v1/webhooks/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": _sign(raw), "x-razorpay-event-id": "evt_u"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["processed"] is False and body["reason"] == "IGNORED_EVENT_TYPE"


# ---------------------------------------------------------------------------
# P2-M36: error PRECEDENCE safety — event-id check fires before signature
# check, but BOTH paths reject before ANY parsing/reduction/inbox write.
# Cryptographic safety does not depend on which 4xx an unauthenticated caller
# sees: no code path reaches business logic without a VALID signature over the
# exact received bytes. These tests pin zero-mutation behavior for both orders.
# ---------------------------------------------------------------------------


def _inbox_count() -> int:
    from sqlalchemy import text as _t

    from razormesh_api.persistence.db import create_db_engine

    engine = create_db_engine(get_settings().database_url)
    with engine.connect() as c:
        return int(c.execute(_t("SELECT count(*) FROM provider_events")).scalar_one())


def _audit_count() -> int:
    from sqlalchemy import text as _t

    from razormesh_api.persistence.db import create_db_engine

    engine = create_db_engine(get_settings().database_url)
    with engine.connect() as c:
        return int(c.execute(_t("SELECT count(*) FROM audit_events")).scalar_one())


@pytest.mark.parametrize(
    "headers",
    [
        {},  # no signature, no event id (the human's manual curl case)
        {"x-razorpay-event-id": "evt_prec_1"},  # event id but no signature
        {"X-Razorpay-Signature": "0" * 64},  # signature but no event id
    ],
)
def test_unauthenticated_variants_cause_zero_state_mutation(
    hook_client: TestClient, headers: dict[str, str]
) -> None:
    raw = _payload()
    inbox_before = _inbox_count()
    audit_before = _audit_count()

    res = hook_client.post("/api/v1/webhooks/razorpay", content=raw, headers=headers)

    assert res.status_code in (400, 403)  # controlled rejection, never 500
    assert res.status_code != 200
    assert res.json()["detail"]["code"] in (
        "RAZORPAY_WEBHOOK_SIGNATURE_INVALID",
        "RAZORPAY_WEBHOOK_SIGNATURE_MISSING",
        "RAZORPAY_WEBHOOK_EVENT_UNKNOWN",
    )
    assert _inbox_count() == inbox_before  # no durable claim
    assert _audit_count() == audit_before  # no ledger event


def test_precedence_event_id_before_signature_is_documented_behavior(
    hook_client: TestClient,
) -> None:
    """400 EVENT_UNKNOWN precedes 403 SIGNATURE_INVALID by design.

    Rationale: the event-id presence check is a cheap structural validation of
    the REQUEST CONTRACT; leaking 'you omitted a required header' to an
    unauthenticated caller discloses no secret material and cannot bypass the
    subsequent HMAC gate. Any request failing EITHER check is dropped before
    parse/reduce/inbox. A caller holding neither the secret nor an event id
    learns nothing that shortens a brute-force path.
    """
    raw = _payload()
    res = hook_client.post("/api/v1/webhooks/razorpay", content=raw)
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "RAZORPAY_WEBHOOK_EVENT_UNKNOWN"
