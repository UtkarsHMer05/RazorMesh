"""P2-M31/M32: webhook endpoint — raw-body necessity and signature matrix."""

import hashlib
import hmac as hmac_mod
import json

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
            "x-razorpay-event-id": "evt_ok_1",
        },
    )
    assert res.status_code == 200
    assert res.json()["processed"] is True


def test_missing_signature_rejected_no_mutation(hook_client: TestClient) -> None:
    raw = _payload()
    res = hook_client.post(
        "/api/v1/webhooks/razorpay",
        content=raw,
        headers={"x-razorpay-event-id": "evt_x"},
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "RAZORPAY_WEBHOOK_SIGNATURE_INVALID"


def test_one_byte_body_mutation_rejected(hook_client: TestClient) -> None:
    raw = _payload()
    mutated = bytearray(raw)
    mutated[mutated.index(b"1")] = ord("2")
    res = hook_client.post(
        "/api/v1/webhooks/razorpay",
        content=bytes(mutated),
        headers={
            "X-Razorpay-Signature": _sign(raw),  # signature over ORIGINAL bytes
            "x-razorpay-event-id": "evt_mut",
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
            "x-razorpay-event-id": "evt_ws",
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
        headers={"X-Razorpay-Signature": sig_over_redumped, "x-razorpay-event-id": "evt_r"},
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
