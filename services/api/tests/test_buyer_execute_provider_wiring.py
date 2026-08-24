"""P2-M37 audit remediation: /buyer/execute must honor PAYMENT_PROVIDER.

Regression for the wiring defect found by the M01-M37 audit: the execute
route hardcoded MockPaymentProvider, so a razorpay-configured deployment
would have settled transactions as SUCCEEDED without any provider order and
the launch-payload branch was unreachable through the API. These tests pin
the route-level provider selection end to end (trust prelude included).
"""

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine

from razormesh_api.catalog import seed_catalog
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.models import AuthorizationSpend, ExecutionAttempt
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.settings import Settings


@pytest.fixture()
def wiring_client(settings: Settings) -> Iterator[TestClient]:
    from conftest import wipe_business_tables
    from razormesh_api import api

    api.main.get_settings.cache_clear()
    app = api.main.app
    app.dependency_overrides[api.main.get_settings] = lambda: settings
    engine = create_engine(settings.database_url, future=True)
    repos = Repositories(create_session_factory(engine))
    wipe_business_tables(engine)
    seed_catalog(repos)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    wipe_business_tables(engine)


def _propose_and_authorize(client: TestClient) -> dict[str, Any]:
    intent_id = client.post("/buyer/fixture-intent").json()["intent_id"]
    listing = client.get("/catalog/products", params={"limit": 100}).json()
    product_id = min(listing["items"], key=lambda p: p["price_minor"])["id"]
    res = client.post(
        "/buyer/propose",
        json={"intent_id": intent_id, "items": [{"product_id": product_id, "quantity": 1}]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["decision"] == "ALLOW"
    return {
        "intent_id": intent_id,
        "checkout_id": body["checkout_id"],
        "ticket_json": body["ticket_json"],
        "signature_hex": body["signature_hex"],
    }


def test_execute_razorpay_mode_returns_launch_and_stays_executing(
    wiring_client: TestClient,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from razormesh_api import api
    from razormesh_api.api.routes import buyer as buyer_route
    from razormesh_api.providers.razorpay import RazorpayClient, RazorpayPaymentProvider

    rz_settings = settings.model_copy(
        update={
            "payment_provider": "razorpay",
            "razorpay_key_id": "rzp_test_PUBLICKEY",
            "razorpay_key_secret": SecretStr("synthetic-secret"),
            "razorpay_webhook_secret": SecretStr("synthetic-hook"),
        }
    )
    wiring_client.app.dependency_overrides[api.main.get_settings] = lambda: rz_settings

    def _responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        return httpx.Response(
            200,
            json={
                "id": "order_WIRING0000000001",
                "status": "created",
                "amount": body["amount"],
                "currency": body["currency"],
                "receipt": body.get("receipt"),
            },
        )

    def _fake_provider(_settings: Settings) -> RazorpayPaymentProvider:
        client = RazorpayClient(
            key_id="rzp_test_PUBLICKEY",
            key_secret="synthetic-secret",
            base_url="https://api.razorpay.com/v1",
            timeout_seconds=5,
            transport=httpx.MockTransport(_responder),
        )
        return RazorpayPaymentProvider(client)

    monkeypatch.setattr(buyer_route, "_provider_for", _fake_provider)

    flow = _propose_and_authorize(wiring_client)
    run = wiring_client.post("/buyer/execute", json=flow)
    assert run.status_code == 200, run.text
    body = run.json()

    # Razorpay path: order created, attempt awaits capture evidence (M15/M19).
    assert body["state"] == "EXECUTING"
    launch = body["launch"]
    assert launch is not None
    assert launch["razorpay_order_id"] == "order_WIRING0000000001"
    assert launch["public_key_id"] == "rzp_test_PUBLICKEY"
    # P2-S03/S04: the launch payload never carries secrets.
    assert "synthetic-secret" not in json.dumps(launch)
    assert "synthetic-hook" not in json.dumps(launch)

    # Durable correlation + reservation HELD (not committed) pre-capture.
    engine = create_engine(settings.database_url, future=True)
    factory = create_session_factory(engine)
    with factory() as session:
        from sqlalchemy import select

        attempt = session.execute(select(ExecutionAttempt)).scalars().one()
        spend = session.execute(select(AuthorizationSpend)).scalars().one()
    assert attempt.razorpay_order_id == "order_WIRING0000000001"
    assert attempt.state == "EXECUTING"
    # P2-M38: the durable attempt must name the REAL provider, not the
    # column default 'mock' (audit truthfulness).
    assert attempt.provider_name == "razorpay"
    assert spend.reserved_minor == attempt.amount_minor
    assert spend.committed_minor == 0


def test_execute_mock_mode_succeeds_without_launch(
    wiring_client: TestClient,
) -> None:
    flow = _propose_and_authorize(wiring_client)
    run = wiring_client.post("/buyer/execute", json=flow)
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["state"] == "SUCCEEDED"
    assert body["launch"] is None


def test_execute_razorpay_mode_without_credentials_fails_closed(
    wiring_client: TestClient,
    settings: Settings,
) -> None:
    from razormesh_api import api

    broken = settings.model_copy(
        update={
            "payment_provider": "razorpay",
            "razorpay_key_id": "",
            "razorpay_key_secret": SecretStr(""),
            "razorpay_webhook_secret": SecretStr(""),
        }
    )
    wiring_client.app.dependency_overrides[api.main.get_settings] = lambda: broken

    flow = _propose_and_authorize(wiring_client)
    run = wiring_client.post("/buyer/execute", json=flow)
    assert run.status_code == 503
    detail = run.json()["detail"]
    assert detail["code"] == "RAZORPAY_CONFIG_UNAVAILABLE"
    # M09: errors name the missing variables, never values.
    assert "RAZORPAY_KEY_ID" in detail["detail"]


def test_status_endpoint_reflects_server_truth_and_is_read_only(
    wiring_client: TestClient,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P2-M40 regression: the buyer UI re-syncs via GET /buyer/status after the
    checkout modal is dismissed without a success callback (live evidence:
    attempt exa_01M0TKTPWPR593Y4HNW48BF0SE settled FAILED by webhook while the
    page still showed EXECUTING). The endpoint must mirror the authoritative
    attempt state, be strictly read-only, and leak no secrets.
    """
    from razormesh_api import api
    from razormesh_api.api.routes import buyer as buyer_route
    from razormesh_api.providers.razorpay import RazorpayClient, RazorpayPaymentProvider
    from razormesh_api.reducer import VerifiedProviderEvent

    rz_settings = settings.model_copy(
        update={
            "payment_provider": "razorpay",
            "razorpay_key_id": "rzp_test_PUBLICKEY",
            "razorpay_key_secret": SecretStr("synthetic-secret"),
            "razorpay_webhook_secret": SecretStr("synthetic-hook"),
        }
    )
    wiring_client.app.dependency_overrides[api.main.get_settings] = lambda: rz_settings

    def _responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        return httpx.Response(
            200,
            json={
                "id": "order_STATUS000000001",
                "status": "created",
                "amount": body["amount"],
                "currency": body["currency"],
                "receipt": body.get("receipt"),
            },
        )

    def _fake_provider(_settings: Settings) -> RazorpayPaymentProvider:
        client = RazorpayClient(
            key_id="rzp_test_PUBLICKEY",
            key_secret="synthetic-secret",
            base_url="https://api.razorpay.com/v1",
            timeout_seconds=5,
            transport=httpx.MockTransport(_responder),
        )
        return RazorpayPaymentProvider(client)

    monkeypatch.setattr(buyer_route, "_provider_for", _fake_provider)

    flow = _propose_and_authorize(wiring_client)
    run = wiring_client.post("/buyer/execute", json=flow)
    assert run.status_code == 200, run.text
    params = {"intent_id": flow["intent_id"], "checkout_id": flow["checkout_id"]}

    # EXECUTING snapshot while the checkout is still open
    res = wiring_client.get("/buyer/status", params=params)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["state"] == "EXECUTING"
    assert body["fulfilment_state"] == "NOT_ELIGIBLE"
    assert body["razorpay_order_id"] == "order_STATUS000000001"

    # A verified failure event settles the attempt (webhook path, M29)
    from razormesh_api.api.routes.webhooks import _reducer

    reducer = _reducer(rz_settings)
    reducer.apply_event(
        VerifiedProviderEvent(
            kind="payment.failed",
            razorpay_order_id="order_STATUS000000001",
            razorpay_payment_id="pay_STATUS_FAIL_1",
        )
    )

    res = wiring_client.get("/buyer/status", params=params)
    body = res.json()
    assert body["state"] == "FAILED"
    assert body["fulfilment_state"] == "NOT_ELIGIBLE"
    assert body["error_code"] == "RAZORPAY_PAYMENT_FAILED"
    assert body["razorpay_payment_status"] == "failed"
    assert "synthetic-secret" not in json.dumps(body)
    assert "synthetic-hook" not in json.dumps(body)

    # Strictly read-only: repeated reads are identical; the reservation was
    # released exactly once by the failure settlement and nothing re-reserves.
    engine = create_engine(settings.database_url, future=True)
    factory = create_session_factory(engine)
    with factory() as session:
        from sqlalchemy import select

        spend = session.execute(select(AuthorizationSpend)).scalars().one()
        version_after_settle = spend.version
    again = wiring_client.get("/buyer/status", params=params).json()
    assert again == body
    with factory() as session:
        from sqlalchemy import select

        spend = session.execute(select(AuthorizationSpend)).scalars().one()
    assert spend.reserved_minor == 0
    assert spend.committed_minor == 0
    assert spend.version == version_after_settle

    # Unknown context is a controlled NO_ATTEMPT, not an error
    unknown = wiring_client.get(
        "/buyer/status",
        params={"intent_id": "intent_unknown_000001", "checkout_id": "chk_unknown_000001"},
    )
    assert unknown.status_code == 200
    assert unknown.json()["state"] == "NO_ATTEMPT"
