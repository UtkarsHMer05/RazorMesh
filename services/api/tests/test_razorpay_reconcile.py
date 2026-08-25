"""P2-M18: fetch-based reconciliation vs internal authority."""

from datetime import UTC, datetime

import httpx
import pytest

from razormesh_api.executor import TrustedPaymentExecutor
from razormesh_api.persistence.models import (
    AuthorizationSpend,
    Checkout,
    Decision,
    ExecutionAttempt,
    ExecutionTicket,
)
from razormesh_api.providers.razorpay import (
    RazorpayClient,
    RazorpayPaymentProvider,
    RazorpayProviderStateConflict,
    reconcile_attempt,
)
from razormesh_api.settings import get_settings
from test_executor import _make_ticket, _redis


class _Transport(httpx.BaseTransport):
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            import json

            self._payload["receipt"] = json.loads(request.content)["receipt"]
        return httpx.Response(200, json=self._payload)


def _setup(tmp_path, payload: dict):  # type: ignore[no-untyped-def]
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
        key_secret="s",
        base_url=get_settings().razorpay_api_base_url,
        timeout_seconds=5,
        transport=_Transport(payload),
    )
    provider = RazorpayPaymentProvider(client)
    executor = TrustedPaymentExecutor(
        repos=repos, keys=keys, nonces=_redis(), provider=provider, spend=spend
    )
    yield repos, provider, executor, spend, keys
    with repos.transaction() as s:
        s.query(ExecutionAttempt).delete()
        s.query(ExecutionTicket).delete()
        s.query(Decision).delete()
        s.query(Checkout).delete()
        s.query(AuthorizationSpend).delete()
        s.query(Merchant).delete()
        s.query(RowIntent).delete()


@pytest.fixture()
def _order_payload() -> dict:
    return {
        "id": "order_recon1",
        "status": "created",
        "amount": 100000,
        "currency": "INR",
    }


@pytest.fixture()
def env(tmp_path, _order_payload: dict):  # type: ignore[no-untyped-def]
    yield from _setup(tmp_path, _order_payload)


def _make_attempt(env) -> str:  # type: ignore[no-untyped-def]
    repos, _provider, executor, spend, keys = env
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)
    attempt = executor.execute(signed_ticket=signed, binding=binding, intent_id=contract.intent_id)
    assert attempt.razorpay_order_id is not None
    return attempt.execution_attempt_id


def test_reconcile_created_is_consistent_and_nonterminal(env) -> None:  # type: ignore[no-untyped-def]
    repos, provider, _executor, _spend, _keys = env
    attempt_id = _make_attempt(env)
    result = reconcile_attempt(
        repos=repos, provider=provider, attempt_id=attempt_id, now=datetime.now(UTC)
    )
    assert result.consistent is True
    assert result.provider_status == "created"
    assert result.payment_status is None  # created is NOT capture evidence


def test_amount_mismatch_conflicts(env, _order_payload: dict) -> None:  # type: ignore[no-untyped-def]
    repos, provider, _executor, _spend, _keys = env
    attempt_id = _make_attempt(env)
    _order_payload["amount"] = 999  # provider disagrees with durable authority
    with pytest.raises(RazorpayProviderStateConflict) as exc:
        reconcile_attempt(
            repos=repos, provider=provider, attempt_id=attempt_id, now=datetime.now(UTC)
        )
    assert exc.value.code == "RAZORPAY_AMOUNT_MISMATCH"


def test_currency_mismatch_conflicts(env, _order_payload: dict) -> None:  # type: ignore[no-untyped-def]
    repos, provider, _executor, _spend, _keys = env
    attempt_id = _make_attempt(env)
    _order_payload["currency"] = "USD"
    with pytest.raises(RazorpayProviderStateConflict) as exc:
        reconcile_attempt(
            repos=repos, provider=provider, attempt_id=attempt_id, now=datetime.now(UTC)
        )
    assert exc.value.code == "RAZORPAY_CURRENCY_MISMATCH"


def test_receipt_context_mismatch_conflicts(env) -> None:  # type: ignore[no-untyped-def]
    """A fetched order whose receipt references another attempt is a hijack signal."""
    repos, _provider, _executor, _spend, _keys = env

    def hijacked(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "order_other",
                "status": "created",
                "amount": 100000,
                "currency": "INR",
                "receipt": "r_exa_SOMEONE_ELSE",
            },
        )

    client = RazorpayClient(
        key_id="rzp_test_k",
        key_secret="s",
        base_url=get_settings().razorpay_api_base_url,
        timeout_seconds=5,
        transport=httpx.MockTransport(hijacked),
    )
    attempt_id = _make_attempt(env)
    with pytest.raises(RazorpayProviderStateConflict) as exc:
        reconcile_attempt(
            repos=repos,
            provider=RazorpayPaymentProvider(client),
            attempt_id=attempt_id,
            now=datetime.now(UTC),
        )
    assert exc.value.code == "RAZORPAY_ORDER_CONTEXT_MISMATCH"


def test_missing_receipt_context_conflicts(env, _order_payload: dict) -> None:  # type: ignore[no-untyped-def]
    """A response that omits the requested receipt has not proven correlation."""
    repos, provider, _executor, _spend, _keys = env
    attempt_id = _make_attempt(env)
    _order_payload.pop("receipt")

    with pytest.raises(RazorpayProviderStateConflict) as exc:
        reconcile_attempt(
            repos=repos,
            provider=provider,
            attempt_id=attempt_id,
            now=datetime.now(UTC),
        )

    assert exc.value.code == "RAZORPAY_ORDER_CONTEXT_MISMATCH"


def test_fetch_returning_a_different_order_identity_conflicts(env) -> None:  # type: ignore[no-untyped-def]
    repos, _provider, _executor, _spend, _keys = env
    attempt_id = _make_attempt(env)

    def wrong_identity(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "order_not_the_requested_order",
                "status": "paid",
                "amount": 100000,
                "currency": "INR",
            },
        )

    provider = RazorpayPaymentProvider(
        RazorpayClient(
            key_id="rzp_test_k",
            key_secret="s",
            base_url=get_settings().razorpay_api_base_url,
            timeout_seconds=5,
            transport=httpx.MockTransport(wrong_identity),
        )
    )
    with pytest.raises(RazorpayProviderStateConflict) as exc:
        reconcile_attempt(
            repos=repos,
            provider=provider,
            attempt_id=attempt_id,
            now=datetime.now(UTC),
        )
    assert exc.value.code == "RAZORPAY_ORDER_CONTEXT_MISMATCH"


def test_unknown_attempt_rejected(env) -> None:  # type: ignore[no-untyped-def]
    repos, provider, *_rest = env
    with pytest.raises(ValueError):
        reconcile_attempt(
            repos=repos, provider=provider, attempt_id="exa_missing", now=datetime.now(UTC)
        )


def test_paid_status_reports_capture_evidence_without_settling(env, _order_payload: dict) -> None:  # type: ignore[no-untyped-def]
    """Reducer (M26+) owns settlement; reconciliation only classifies evidence."""
    repos, provider, _executor, _spend, _keys = env
    attempt_id = _make_attempt(env)
    _order_payload["status"] = "paid"
    result = reconcile_attempt(
        repos=repos, provider=provider, attempt_id=attempt_id, now=datetime.now(UTC)
    )
    assert result.provider_status == "paid"
    assert result.payment_status == "captured"

    # read-only: called twice, no business mutation either time
    again = reconcile_attempt(
        repos=repos, provider=provider, attempt_id=attempt_id, now=datetime.now(UTC)
    )
    assert again.consistent is True
