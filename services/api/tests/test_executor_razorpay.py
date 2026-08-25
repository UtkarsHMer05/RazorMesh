"""P2-M15: server-side Razorpay order creation through the trusted executor."""

import httpx
import pytest

from razormesh_api.executor import AttemptState
from razormesh_api.executor import TrustedPaymentExecutor as Executor
from razormesh_api.persistence.models import (
    AuthorizationSpend,
    Checkout,
    Decision,
    ExecutionAttempt,
    ExecutionTicket,
)
from razormesh_api.providers.razorpay import RazorpayClient, RazorpayPaymentProvider
from razormesh_api.settings import get_settings
from test_executor import _make_ticket, _redis


class _CountingTransport(httpx.BaseTransport):
    def __init__(self, responder) -> None:  # type: ignore[no-untyped-def]
        self._responder = responder
        self.calls = 0
        self.bodies: list[bytes] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        self.bodies.append(request.read())
        return self._responder(request)


def _razorpay_executor(repos, keys, transport: _CountingTransport, spend=None):  # type: ignore[no-untyped-def]
    client = RazorpayClient(
        key_id="rzp_test_k",
        key_secret="s",
        base_url=get_settings().razorpay_api_base_url,
        timeout_seconds=5,
        transport=transport,
    )
    provider = RazorpayPaymentProvider(client)
    return Executor(
        repos=repos,
        keys=keys,
        nonces=_redis(),
        provider=provider,
        spend=spend,
    )


@pytest.fixture()
def rz_setup(tmp_path):  # type: ignore[no-untyped-def]
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
    yield repos, keys, spend
    with repos.transaction() as s:
        s.query(ExecutionAttempt).delete()
        s.query(ExecutionTicket).delete()
        s.query(Decision).delete()
        s.query(Checkout).delete()
        s.query(AuthorizationSpend).delete()
        s.query(Merchant).delete()
        s.query(RowIntent).delete()


def _ok_order(request: httpx.Request) -> httpx.Response:
    body = __import__("json").loads(request.read())
    return httpx.Response(
        201,
        json={
            "id": f"order_{request.method}",
            "status": "created",
            "amount": 100000,
            "currency": "INR",
            "receipt": body["receipt"],
        },
    )


def _reserved(repos, intent_id) -> int:  # type: ignore[no-untyped-def]
    with repos.transaction() as s:
        row = s.get(AuthorizationSpend, str(intent_id))
        assert row is not None
        return row.reserved_minor


def test_order_created_stays_executing_with_correlation(rz_setup) -> None:  # type: ignore[no-untyped-def]
    repos, keys, spend = rz_setup
    transport = _CountingTransport(_ok_order)
    executor = _razorpay_executor(repos, keys, transport, spend)
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)

    attempt = executor.execute(signed_ticket=signed, binding=binding, intent_id=contract.intent_id)

    assert attempt.state == AttemptState.EXECUTING.value  # not terminal: awaiting capture
    assert attempt.razorpay_order_id == "order_POST"
    assert attempt.provider_reference == "order_POST"
    assert _reserved(repos, contract.intent_id) == binding.amount_minor  # held, not committed
    assert transport.calls == 1
    body = __import__("json").loads(transport.bodies[0])
    assert body["amount"] == binding.amount_minor  # server-authoritative only
    assert body["currency"] == binding.currency
    assert body["notes"]["ticket_id"]
    assert len(body["receipt"]) <= 40

    # idempotent re-entry with the same ticket: SAME attempt, NO second order
    again = executor.execute(signed_ticket=signed, binding=binding, intent_id=contract.intent_id)
    assert again.execution_attempt_id == attempt.execution_attempt_id
    assert again.razorpay_order_id == "order_POST"
    assert transport.calls == 1


def test_timeout_maps_to_unknown_and_holds_reservation(rz_setup) -> None:  # type: ignore[no-untyped-def]
    repos, keys, spend = rz_setup

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("simulated", request=request)

    transport = _CountingTransport(timeout)
    executor = _razorpay_executor(repos, keys, transport, spend)
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)

    attempt = executor.execute(signed_ticket=signed, binding=binding, intent_id=contract.intent_id)
    assert attempt.state == AttemptState.PROVIDER_UNKNOWN.value
    assert (attempt.error_code or "").startswith("RAZORPAY_ORDER_CREATE_UNKNOWN")
    assert attempt.reconcile_state == "REQUIRED"
    assert _reserved(repos, contract.intent_id) == binding.amount_minor  # P2-S18

    # re-entry returns the SAME attempt; no fresh financial operation (P2-S19)
    again = executor.execute(signed_ticket=signed, binding=binding, intent_id=contract.intent_id)
    assert again.execution_attempt_id == attempt.execution_attempt_id
    assert transport.calls == 1


def test_definitive_rejection_fails_and_releases(rz_setup) -> None:  # type: ignore[no-untyped-def]
    repos, keys, spend = rz_setup
    transport = _CountingTransport(lambda request: httpx.Response(400))
    executor = _razorpay_executor(repos, keys, transport, spend)
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)

    attempt = executor.execute(signed_ticket=signed, binding=binding, intent_id=contract.intent_id)
    assert attempt.state == AttemptState.FAILED.value
    assert attempt.error_code == "RAZORPAY_ORDER_CREATE_REJECTED"
    assert _reserved(repos, contract.intent_id) == 0


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("amount", 99999, "RAZORPAY_AMOUNT_MISMATCH"),
        ("currency", "USD", "RAZORPAY_CURRENCY_MISMATCH"),
        ("status", "paid", "RAZORPAY_PROVIDER_STATE_CONFLICT"),
    ],
)
def test_created_order_authority_mismatch_is_never_launched(
    rz_setup, field: str, value: object, code: str
) -> None:  # type: ignore[no-untyped-def]
    """A provider-created order with different authority is UNKNOWN, not launchable."""
    repos, keys, spend = rz_setup

    def mismatch(request: httpx.Request) -> httpx.Response:
        body = __import__("json").loads(request.read())
        payload = {
            "id": "order_mismatch",
            "status": "created",
            "amount": 100000,
            "currency": "INR",
            "receipt": body["receipt"],
        }
        payload[field] = value
        return httpx.Response(201, json=payload)

    executor = _razorpay_executor(repos, keys, _CountingTransport(mismatch), spend)
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)

    attempt = executor.execute(signed_ticket=signed, binding=binding, intent_id=contract.intent_id)

    assert attempt.state == AttemptState.PROVIDER_UNKNOWN.value
    assert attempt.error_code == code
    assert attempt.reconcile_state == "REQUIRED"
    assert attempt.razorpay_order_id == "order_mismatch"  # known identity retained
    assert _reserved(repos, contract.intent_id) == binding.amount_minor


def test_contradictory_create_cannot_rebind_an_order_claimed_by_another_attempt(
    rz_setup,
) -> None:  # type: ignore[no-untyped-def]
    """A duplicate contradictory provider id fails closed instead of raising 500."""
    repos, keys, spend = rz_setup

    def duplicate_paid(request: httpx.Request) -> httpx.Response:
        body = __import__("json").loads(request.read())
        return httpx.Response(
            201,
            json={
                "id": "order_duplicate_contradiction",
                "status": "paid",
                "amount": body["amount"],
                "currency": body["currency"],
                "receipt": body["receipt"],
            },
        )

    executor = _razorpay_executor(repos, keys, _CountingTransport(duplicate_paid), spend)
    results = []
    for _ in range(2):
        signed, binding, contract = _make_ticket(keys, repos)
        spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)
        results.append(
            executor.execute(
                signed_ticket=signed,
                binding=binding,
                intent_id=contract.intent_id,
            )
        )

    assert [result.state for result in results] == [
        AttemptState.PROVIDER_UNKNOWN.value,
        AttemptState.PROVIDER_UNKNOWN.value,
    ]
    assert results[0].razorpay_order_id == "order_duplicate_contradiction"
    assert results[1].razorpay_order_id is None
    assert results[1].provider_reference == "order_duplicate_contradiction"
