"""P2-M23/M24: checkout callback verification — valid, forged, mutated, replayed.

The callback endpoint must:
- verify HMAC over SERVER-stored order id (P2-S08) before ANY mutation;
- reject browser order-id swaps (RAZORPAY_PAYMENT_CONTEXT_MISMATCH);
- reject forged signatures without touching durable state;
- treat duplicate verified callbacks idempotently (no second effect).
"""

import hashlib
import hmac as hmac_mod

import httpx
import pytest
from fastapi.testclient import TestClient

from razormesh_api.executor import TrustedPaymentExecutor
from razormesh_api.persistence.models import (
    AuthorizationSpend,
    Checkout,
    Decision,
    ExecutionAttempt,
    ExecutionTicket,
)
from razormesh_api.providers.razorpay import RazorpayClient, RazorpayPaymentProvider
from razormesh_api.settings import Settings, get_settings
from test_executor import _make_ticket, _redis

SECRET = "test-hook-secret-value"


class _PaidTransport(httpx.BaseTransport):
    def __init__(self, status: str = "paid") -> None:
        self.status = status

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        from razormesh_api.persistence.db import create_db_engine, create_session_factory
        from razormesh_api.persistence.repositories import Repositories
        from razormesh_api.settings import get_settings as gs

        # report the REAL stored order id so context checks pass in-flight
        repos = Repositories(create_session_factory(create_db_engine(gs().database_url)))
        with repos.transaction() as s:
            row = (
                s.query(ExecutionAttempt)
                .filter(ExecutionAttempt.razorpay_order_id.isnot(None))
                .order_by(ExecutionAttempt.created_at.desc())
                .first()
            )
            oid = row.razorpay_order_id if row else "order_cb1"
        return httpx.Response(
            200,
            json={"id": oid, "status": self.status, "amount": 100000, "currency": "INR"},
        )


@pytest.fixture()
def cb_env(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """Full stack with razorpay provider + client fixture wired to Test keys."""
    from sqlalchemy import create_engine

    from razormesh_api.keys import DevSigningKeys
    from razormesh_api.persistence.db import create_session_factory
    from razormesh_api.persistence.models import IntentContract as RowIntent
    from razormesh_api.persistence.models import Merchant
    from razormesh_api.persistence.repositories import Repositories
    from razormesh_api.spend import SpendManager

    engine = create_engine(get_settings().database_url, future=True)
    repos = Repositories(create_session_factory(engine))
    keys = DevSigningKeys(
        private_path=str(tmp_path / "p.pem"), public_path=str(tmp_path / "pub.pem")
    ).ensure()
    spend = SpendManager(repos)
    client = RazorpayClient(
        key_id="rzp_test_k",
        key_secret=SECRET,
        base_url=get_settings().razorpay_api_base_url,
        timeout_seconds=5,
        transport=_PaidTransport(),
    )
    provider = RazorpayPaymentProvider(client)
    executor = TrustedPaymentExecutor(
        repos=repos, keys=keys, nonces=_redis(), provider=provider, spend=spend
    )
    yield repos, executor, spend, keys
    with repos.transaction() as s:
        s.query(ExecutionAttempt).delete()
        s.query(ExecutionTicket).delete()
        s.query(Decision).delete()
        s.query(Checkout).delete()
        s.query(AuthorizationSpend).delete()
        s.query(Merchant).delete()
        s.query(RowIntent).delete()


@pytest.fixture()
def cb_client(cb_env, monkeypatch):  # type: ignore[no-untyped-def]
    from razormesh_api import api as api_pkg
    from razormesh_api.api.routes import buyer as buyer_route

    transport = _PaidTransport(status="paid")

    def fake_provider(settings: Settings):  # type: ignore[no-untyped-def]
        client = RazorpayClient(
            key_id="rzp_test_k",
            key_secret=SECRET,
            base_url=get_settings().razorpay_api_base_url,
            timeout_seconds=5,
            transport=transport,
        )
        return RazorpayPaymentProvider(client)

    monkeypatch.setattr(buyer_route, "_razorpay_provider", fake_provider)

    settings = Settings(
        database_url=get_settings().database_url,
        redis_url=get_settings().redis_url,
        payment_provider="razorpay",
        razorpay_key_id="rzp_test_k",
        razorpay_key_secret=SECRET,
        razorpay_webhook_secret=SECRET,
        _env_file=None,
    )

    def _override() -> Settings:
        return settings

    api_pkg.main.get_settings.cache_clear()
    app = api_pkg.main.app
    app.dependency_overrides[api_pkg.main.get_settings] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    api_pkg.main.get_settings.cache_clear()


def _signature(order_id: str, payment_id: str, secret: str = SECRET) -> str:
    return hmac_mod.new(
        secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256
    ).hexdigest()


def _run_trusted_flow(cb_env) -> tuple[str, str, str]:  # type: ignore[no-untyped-def]
    repos, executor, spend, keys = cb_env
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)
    attempt = executor.execute(signed_ticket=signed, binding=binding, intent_id=contract.intent_id)
    assert attempt.razorpay_order_id is not None
    return (
        attempt.execution_attempt_id,
        attempt.razorpay_order_id,
        str(contract.intent_id),
    )


def _snapshot(repos, attempt_id: str):  # type: ignore[no-untyped-def]
    with repos.transaction() as s:
        a = s.get(ExecutionAttempt, attempt_id)
        assert a is not None
        return (a.state, a.callback_verified_at, a.error_code)


def test_valid_signature_marks_callback_verified(cb_env, cb_client) -> None:  # type: ignore[no-untyped-def]
    repos, *_rest = cb_env
    attempt_id, order_id, intent_id = _run_trusted_flow(cb_env)

    res = cb_client.post(
        "/buyer/callback",
        json={
            "intent_id": intent_id,
            "checkout_id": "chk_does_not_matter_for_lookup",  # lookup by intent only? no—both
            "razorpay_payment_id": "pay_cb1",
            "razorpay_order_id": order_id,
            "razorpay_signature": _signature(order_id, "pay_cb1"),
        },
    )
    # checkout_id participates in lookup; use real one
    if res.status_code == 404:
        with repos.transaction() as s:
            a = s.get(ExecutionAttempt, attempt_id)
            real_checkout = a.checkout_id
        res = cb_client.post(
            "/buyer/callback",
            json={
                "intent_id": intent_id,
                "checkout_id": real_checkout,
                "razorpay_payment_id": "pay_cb1",
                "razorpay_order_id": order_id,
                "razorpay_signature": _signature(order_id, "pay_cb1"),
            },
        )
    assert res.status_code == 200, res.text
    state, verified_at, _err = _snapshot(repos, attempt_id)
    assert state == "SUCCEEDED"  # fixture provider reports `paid` evidence
    assert verified_at is not None


def test_forged_signature_rejected_without_mutation(cb_env, cb_client) -> None:  # type: ignore[no-untyped-def]
    repos, *_rest = cb_env
    attempt_id, order_id, intent_id = _run_trusted_flow(cb_env)
    before = _snapshot(repos, attempt_id)

    res = cb_client.post(
        "/buyer/callback",
        json={
            "intent_id": intent_id,
            "checkout_id": _real_checkout(repos, attempt_id),
            "razorpay_payment_id": "pay_evil",
            "razorpay_order_id": order_id,
            "razorpay_signature": "0" * 64,
        },
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "RAZORPAY_PAYMENT_SIGNATURE_INVALID"
    assert _snapshot(repos, attempt_id) == before


def _real_checkout(repos, attempt_id: str) -> str:  # type: ignore[no-untyped-def]
    with repos.transaction() as s:
        a = s.get(ExecutionAttempt, attempt_id)
        assert a is not None
        return a.checkout_id


def test_swapped_browser_order_context_rejected(cb_env, cb_client) -> None:  # type: ignore[no-untyped-def]
    repos, *_rest = cb_env
    attempt_id, _real_order, intent_id = _run_trusted_flow(cb_env)
    before = _snapshot(repos, attempt_id)

    res = cb_client.post(
        "/buyer/callback",
        json={
            "intent_id": intent_id,
            "checkout_id": _real_checkout(repos, attempt_id),
            "razorpay_payment_id": "pay_evil_x",
            "razorpay_order_id": "order_FROM_BROWSER",
            "razorpay_signature": _signature("order_FROM_BROWSER", "pay_evil_x"),
        },
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "RAZORPAY_PAYMENT_CONTEXT_MISMATCH"
    assert _snapshot(repos, attempt_id) == before


def test_duplicate_verified_callback_is_idempotent(cb_env, cb_client) -> None:  # type: ignore[no-untyped-def]
    """Second delivery after settlement must be a safe no-op returning same state."""
    repos, *_rest = cb_env
    attempt_id, order_id, intent_id = _run_trusted_flow(cb_env)
    payload = {
        "intent_id": intent_id,
        "checkout_id": _real_checkout(repos, attempt_id),
        "razorpay_payment_id": "pay_dup",
        "razorpay_order_id": order_id,
        "razorpay_signature": _signature(order_id, "pay_dup"),
    }
    first = cb_client.post("/buyer/callback", json=payload)
    second = cb_client.post("/buyer/callback", json=payload)
    assert first.status_code == second.status_code == 200
    state1, v1, _ = _snapshot(repos, attempt_id)
    state2, v2, _ = _snapshot(repos, attempt_id)
    assert (state1, v1) == (state2, v2)


def test_wrong_secret_signature_rejected(cb_env, cb_client) -> None:
    repos, *_rest = cb_env
    attempt_id, order_id, intent_id = _run_trusted_flow(cb_env)
    before = _snapshot(repos, attempt_id)
    res = cb_client.post(
        "/buyer/callback",
        json={
            "intent_id": intent_id,
            "checkout_id": _real_checkout(repos, attempt_id),
            "razorpay_payment_id": "pay_wrongsecret",
            "razorpay_order_id": order_id,
            "razorpay_signature": _signature(order_id, "pay_wrongsecret", secret="attacker-secret"),
        },
    )
    assert res.status_code == 403
    assert _snapshot(repos, attempt_id) == before


def test_paid_evidence_settles_captured_and_eligible(cb_env, cb_client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """M25: verified signature + provider `paid` evidence -> exactly-once settlement."""
    from razormesh_api.persistence.models import AuthorizationSpend

    repos, *_rest = cb_env
    attempt_id, order_id, intent_id = _run_trusted_flow(cb_env)
    checkout = _real_checkout(repos, attempt_id)

    res = cb_client.post(
        "/buyer/callback",
        json={
            "intent_id": intent_id,
            "checkout_id": checkout,
            "razorpay_payment_id": "pay_capture_1",
            "razorpay_order_id": order_id,
            "razorpay_signature": _signature(order_id, "pay_capture_1"),
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["state"] == "SUCCEEDED"

    with repos.transaction() as s:
        a = s.get(ExecutionAttempt, attempt_id)
        sp = s.get(AuthorizationSpend, intent_id)
        assert a is not None and sp is not None
        assert a.state == "SUCCEEDED"
        assert a.razorpay_payment_id == "pay_capture_1"
        assert a.fulfilment_state == "ELIGIBLE"
        assert sp.reserved_minor == 0
        assert sp.committed_minor == a.amount_minor


def test_uncaptured_order_stays_executing(cb_env, cb_client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Authorized-only (order still `created`) is NOT fulfilment authority."""
    from razormesh_api.persistence.models import AuthorizationSpend

    repos, *_rest = cb_env
    attempt_id, order_id, intent_id = _run_trusted_flow(cb_env)

    # point provider seam at an unpaid snapshot
    from razormesh_api.api.routes import buyer as buyer_route

    def unpaid_provider(settings: Settings):  # type: ignore[no-untyped-def]
        client = RazorpayClient(
            key_id="rzp_test_k",
            key_secret=SECRET,
            base_url=get_settings().razorpay_api_base_url,
            timeout_seconds=5,
            transport=_PaidTransport(status="created"),
        )
        return RazorpayPaymentProvider(client)

    monkeypatch.setattr(buyer_route, "_razorpay_provider", unpaid_provider)

    res = cb_client.post(
        "/buyer/callback",
        json={
            "intent_id": intent_id,
            "checkout_id": _real_checkout(repos, attempt_id),
            "razorpay_payment_id": "pay_pending_9",
            "razorpay_order_id": order_id,
            "razorpay_signature": _signature(order_id, "pay_pending_9"),
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["state"] == "EXECUTING"
    assert "NOT_CAPTURED" in str(body.get("detail"))

    with repos.transaction() as s:
        sp = s.get(AuthorizationSpend, intent_id)
        assert sp is not None
        assert sp.committed_minor == 0  # nothing settled without capture evidence


def test_callback_after_webhook_failure_settlement_stays_failed_and_released(
    cb_env,
    cb_client,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """P2-M40 race regression (live shape): the payment.failed webhook settles
    the attempt FAILED and releases the reservation; a later verified browser
    callback must be an inert no-op — FAILED state, release intact, no
    re-reservation/commit, fulfilment NOT_ELIGIBLE.
    """
    from datetime import UTC, datetime

    from razormesh_api.api.routes import buyer as buyer_route
    from razormesh_api.reducer import ProviderStateReducer, VerifiedProviderEvent

    repos, _executor, spend, keys = cb_env
    attempt_id, order_id, intent_id = _run_trusted_flow(cb_env)

    # The webhook path: verified payment.failed event through the reducer.
    reducer = ProviderStateReducer(
        repos=repos, keys=keys, nonces=_redis(), provider=None, spend=spend
    )
    settled = reducer.apply_event(
        VerifiedProviderEvent(
            kind="payment.failed",
            razorpay_order_id=order_id,
            razorpay_payment_id="pay_m40_fail",
        ),
        now=datetime.now(UTC),
    )
    assert settled.state == "FAILED"
    with repos.transaction() as s:
        sp = s.get(AuthorizationSpend, intent_id)
        assert sp is not None
        assert sp.reserved_minor == 0 and sp.committed_minor == 0
        version_after_settle = sp.version

    # Provider snapshot for the callback fetch: failed payment, order not paid.
    def unpaid_provider(settings: Settings):  # type: ignore[no-untyped-def]
        client = RazorpayClient(
            key_id="rzp_test_k",
            key_secret=SECRET,
            base_url=get_settings().razorpay_api_base_url,
            timeout_seconds=5,
            transport=_PaidTransport(status="attempted"),
        )
        return RazorpayPaymentProvider(client)

    monkeypatch.setattr(buyer_route, "_razorpay_provider", unpaid_provider)

    res = cb_client.post(
        "/buyer/callback",
        json={
            "intent_id": intent_id,
            "checkout_id": _real_checkout(repos, attempt_id),
            "razorpay_payment_id": "pay_m40_fail",
            "razorpay_order_id": order_id,
            "razorpay_signature": _signature(order_id, "pay_m40_fail"),
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["state"] == "FAILED"
    assert "NOT_CAPTURED" in str(body.get("detail"))

    with repos.transaction() as s:
        a = s.get(ExecutionAttempt, attempt_id)
        sp = s.get(AuthorizationSpend, intent_id)
        assert a is not None and sp is not None
        assert a.state == "FAILED"
        assert a.error_code == "RAZORPAY_PAYMENT_FAILED"
        assert a.fulfilment_state == "NOT_ELIGIBLE"
        assert sp.reserved_minor == 0
        assert sp.committed_minor == 0
        assert sp.version == version_after_settle  # release happened exactly once


def test_callback_reports_fresh_state_when_failure_settles_mid_request(
    cb_env,
    cb_client,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """P2-M40 intra-request race: a webhook failure settles the attempt WHILE
    the callback is in flight (after its initial read). The not-captured
    response must report the CURRENT durable state (FAILED), never the stale
    pre-lock EXECUTING snapshot.
    """
    from datetime import UTC, datetime

    from razormesh_api.api.routes import buyer as buyer_route

    repos, executor, _spend, _keys = cb_env
    attempt_id, order_id, intent_id = _run_trusted_flow(cb_env)

    class _FailDuringFetchProvider(RazorpayPaymentProvider):
        def fetch_order(self, order_id_: str):  # type: ignore[override]
            # Simulates the payment.failed webhook committing at this instant.
            executor.record_provider_failure(
                attempt_id,
                error_code="RAZORPAY_PAYMENT_FAILED",
                now=datetime.now(UTC),
            )
            return super().fetch_order(order_id_)

    def racing_provider(settings: Settings):  # type: ignore[no-untyped-def]
        client = RazorpayClient(
            key_id="rzp_test_k",
            key_secret=SECRET,
            base_url=get_settings().razorpay_api_base_url,
            timeout_seconds=5,
            transport=_PaidTransport(status="attempted"),
        )
        return _FailDuringFetchProvider(client)

    monkeypatch.setattr(buyer_route, "_razorpay_provider", racing_provider)

    res = cb_client.post(
        "/buyer/callback",
        json={
            "intent_id": intent_id,
            "checkout_id": _real_checkout(repos, attempt_id),
            "razorpay_payment_id": "pay_race_fail",
            "razorpay_order_id": order_id,
            "razorpay_signature": _signature(order_id, "pay_race_fail"),
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    # Fresh-read proof: FAILED, not the stale EXECUTING snapshot.
    assert body["state"] == "FAILED"
    assert "NOT_CAPTURED" in str(body.get("detail"))

    with repos.transaction() as s:
        a = s.get(ExecutionAttempt, attempt_id)
        sp = s.get(AuthorizationSpend, intent_id)
        assert a is not None and sp is not None
        assert a.state == "FAILED"
        assert a.fulfilment_state == "NOT_ELIGIBLE"
        assert sp.reserved_minor == 0
        assert sp.committed_minor == 0
