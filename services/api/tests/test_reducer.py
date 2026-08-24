"""P2-M26: provider state reducer — event permutations converge safely.

Every verified event flows through ONE reducer; duplicates and out-of-order
delivery never duplicate commit/fulfilment, and failed->captured reconciles
with a capacity guard (P2-S13..S16).
"""

import httpx
import pytest

from razormesh_api.executor import AttemptState, TrustedPaymentExecutor
from razormesh_api.persistence.models import (
    AuthorizationSpend,
    Checkout,
    Decision,
    ExecutionAttempt,
    ExecutionTicket,
)
from razormesh_api.providers.razorpay import RazorpayPaymentProvider
from razormesh_api.reducer import ProviderStateReducer, VerifiedProviderEvent
from razormesh_api.settings import get_settings
from razormesh_api.spend import SpendManager
from test_executor import _make_ticket, _redis


class _ScriptedTransport(httpx.BaseTransport):
    """Answers order creation only; asserts no other network use."""

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        assert request.method == "POST" and request.url.path.endswith("/orders")
        return httpx.Response(
            201,
            json={"id": "order_red_1", "status": "created", "amount": 100000, "currency": "INR"},
        )


def _rz_provider() -> RazorpayPaymentProvider:
    from razormesh_api.providers.razorpay import RazorpayClient

    client = RazorpayClient(
        key_id="rzp_test_k",
        key_secret="s",
        base_url=get_settings().razorpay_api_base_url,
        timeout_seconds=5,
        transport=_ScriptedTransport(),
    )
    return RazorpayPaymentProvider(client)


@pytest.fixture()
def reducer_env(tmp_path):  # type: ignore[no-untyped-def]
    from sqlalchemy import create_engine

    from razormesh_api.keys import DevSigningKeys
    from razormesh_api.persistence.db import create_session_factory
    from razormesh_api.persistence.models import IntentContract as RowIntent
    from razormesh_api.persistence.models import Merchant
    from razormesh_api.persistence.repositories import Repositories

    engine = create_engine(get_settings().database_url, future=True)
    repos = Repositories(create_session_factory(engine))
    keys = DevSigningKeys(
        private_path=str(tmp_path / "p.pem"), public_path=str(tmp_path / "pub.pem")
    ).ensure()
    spend = SpendManager(repos)
    executor = TrustedPaymentExecutor(
        repos=repos,
        keys=keys,
        nonces=_redis(),
        provider=_rz_provider(),
        spend=spend,
    )
    reducer = ProviderStateReducer(
        repos=repos, keys=keys, nonces=_redis(), provider=None, spend=spend
    )
    yield repos, keys, spend, executor, reducer
    with repos.transaction() as s:
        s.query(ExecutionAttempt).delete()
        s.query(ExecutionTicket).delete()
        s.query(Decision).delete()
        s.query(Checkout).delete()
        s.query(AuthorizationSpend).delete()
        s.query(Merchant).delete()
        s.query(RowIntent).delete()


def _captured(order_id: str) -> VerifiedProviderEvent:
    return VerifiedProviderEvent(
        kind="payment.captured",
        razorpay_order_id=order_id,
        razorpay_payment_id="pay_red_1",
    )


def _paid_order_event(order_id: str) -> VerifiedProviderEvent:
    return VerifiedProviderEvent(kind="order.paid", razorpay_order_id=order_id)


def _failed(order_id: str) -> VerifiedProviderEvent:
    return VerifiedProviderEvent(
        kind="payment.failed", razorpay_order_id=order_id, razorpay_payment_id="pay_fail_1"
    )


def _authorized(order_id: str) -> VerifiedProviderEvent:
    return VerifiedProviderEvent(
        kind="payment.authorized",
        razorpay_order_id=order_id,
        razorpay_payment_id="pay_auth_1",
    )


def _spend_row(repos, intent_id) -> AuthorizationSpend:  # type: ignore[no-untyped-def]
    with repos.transaction() as s:
        row = s.get(AuthorizationSpend, str(intent_id))
        assert row is not None
        repos.session_expunge(row) if hasattr(repos, "session_expunge") else None
        return row


def _attempt_state(repos, order_id: str) -> tuple[str, str]:  # type: ignore[no-untyped-def]
    with repos.transaction() as s:
        a = s.query(ExecutionAttempt).filter(ExecutionAttempt.razorpay_order_id == order_id).first()
        assert a is not None
        return a.state, a.fulfilment_state


# ---------------------------------------------------------------------------
def test_captured_then_paid_dedups_to_one_effect(reducer_env) -> None:  # type: ignore[no-untyped-def]
    """EXECUTING + captured -> SUCCEEDED once; order.paid duplicate is a no-op."""
    repos, keys, spend, executor, reducer = reducer_env
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)
    attempt = executor.execute(signed_ticket=signed, binding=binding, intent_id=contract.intent_id)
    oid = attempt.razorpay_order_id
    assert oid == "order_red_1"

    first = reducer.apply_event(_captured(oid))
    assert first.state == AttemptState.SUCCEEDED.value

    dup1 = reducer.apply_event(_captured(oid))
    dup2 = reducer.apply_event(_paid_order_event(oid))

    assert dup1.execution_attempt_id == first.execution_attempt_id
    assert dup2.state == AttemptState.SUCCEEDED.value
    state, fulfilment = _attempt_state(repos, oid)
    assert (state, fulfilment) == ("SUCCEEDED", "ELIGIBLE")
    row = _spend_row(repos, contract.intent_id)
    assert row.committed_minor == binding.amount_minor  # committed EXACTLY once
    assert row.reserved_minor == 0


def test_authorized_only_never_fulfils(reducer_env) -> None:  # type: ignore[no-untyped-def]
    repos, keys, spend, executor, reducer = reducer_env
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)
    attempt = executor.execute(signed_ticket=signed, binding=binding, intent_id=contract.intent_id)
    assert attempt.razorpay_order_id
    out = reducer.apply_event(_authorized(str(attempt.razorpay_order_id)))
    assert out.state == AttemptState.EXECUTING.value
    state, fulfilment = _attempt_state(repos, str(attempt.razorpay_order_id))
    assert (state, fulfilment) == ("EXECUTING", "NOT_ELIGIBLE")


def test_failed_then_captured_reconciles_with_capacity_guard(reducer_env) -> None:  # type: ignore[no-untyped-def]
    """P2-S16: verified late capture reconciles a FAILED attempt exactly once."""
    repos, keys, spend, executor, reducer = reducer_env
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)
    attempt = executor.execute(signed_ticket=signed, binding=binding, intent_id=contract.intent_id)
    oid = str(attempt.razorpay_order_id)

    reducer.apply_event(_failed(oid))
    state, _f = _attempt_state(repos, oid)
    assert state == "FAILED"

    reconciled = reducer.apply_event(_captured(oid))
    assert reconciled.state == AttemptState.SUCCEEDED.value
    state, fulfilment = _attempt_state(repos, oid)
    assert (state, fulfilment) == ("SUCCEEDED", "ELIGIBLE")
    row = _spend_row(repos, contract.intent_id)
    assert row.committed_minor == binding.amount_minor

    # duplicate captured after reconciliation: no second commit
    again = reducer.apply_event(_captured(oid))
    assert again.state == AttemptState.SUCCEEDED.value
    row2 = _spend_row(repos, contract.intent_id)
    assert row2.committed_minor == binding.amount_minor


def test_captured_resolves_provider_unknown(reducer_env) -> None:  # type: ignore[no-untyped-def]
    """PROVIDER_UNKNOWN + verified capture evidence -> SUCCEEDED, reservation kept."""
    repos, keys, spend, executor, reducer = reducer_env
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)

    from razormesh_api.providers.mock import MockMode, MockPaymentProvider

    executor._provider = MockPaymentProvider(mode=MockMode.TIMEOUT_AFTER_SUCCESS)
    attempt = executor.execute(signed_ticket=signed, binding=binding, intent_id=contract.intent_id)
    assert attempt.state == AttemptState.PROVIDER_UNKNOWN.value

    oid = f"order_unknown_{attempt.execution_attempt_id[:10]}"
    with repos.transaction() as s:
        row = s.get(ExecutionAttempt, attempt.execution_attempt_id, with_for_update=True)
        assert row is not None
        row.razorpay_order_id = oid
    out = reducer.apply_event(
        VerifiedProviderEvent(
            kind="order.paid", razorpay_order_id=oid, razorpay_payment_id="pay_unk_1"
        )
    )
    assert out.state == AttemptState.SUCCEEDED.value
    row3 = _spend_row(repos, contract.intent_id)
    assert row3.committed_minor == binding.amount_minor


def test_lagged_authorized_snapshot_cannot_regress_state(reducer_env) -> None:  # type: ignore[no-untyped-def]
    """M27: authorized payload may LAG reality (docs R-014) — never regresses."""
    repos, keys, spend, executor, reducer = reducer_env
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)
    attempt = executor.execute(
        signed_ticket=signed, binding=binding, intent_id=contract.intent_id
    )
    oid = str(attempt.razorpay_order_id)
    reducer.apply_event(_captured(oid))
    before = _attempt_state(repos, oid)

    out = reducer.apply_event(_authorized(oid))  # late/duplicated snapshot
    assert out.state == AttemptState.SUCCEEDED.value
    assert _attempt_state(repos, oid) == before


def test_failure_releases_reservation_definitively(reducer_env) -> None:  # type: ignore[no-untyped-def]
    """M29: verified failure releases capacity; duplicate failure is a no-op."""
    repos, keys, spend, executor, reducer = reducer_env
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)
    attempt = executor.execute(
        signed_ticket=signed, binding=binding, intent_id=contract.intent_id
    )
    oid = str(attempt.razorpay_order_id)

    first = reducer.apply_event(_failed(oid))
    second = reducer.apply_event(_failed(oid))

    assert first.state == AttemptState.FAILED.value
    assert second.state == AttemptState.FAILED.value
    row = _spend_row(repos, contract.intent_id)
    assert row.reserved_minor == 0 and row.committed_minor == 0
    state, fulfilment = _attempt_state(repos, oid)
    assert (state, fulfilment) == ("FAILED", "NOT_ELIGIBLE")


def test_order_paid_alone_settles_exactly_once(reducer_env) -> None:  # type: ignore[no-untyped-def]
    """M30: order.paid WITHOUT prior captured still yields ONE settlement."""
    repos, keys, spend, executor, reducer = reducer_env
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)
    attempt = executor.execute(
        signed_ticket=signed, binding=binding, intent_id=contract.intent_id
    )
    oid = str(attempt.razorpay_order_id)

    out1 = reducer.apply_event(_paid_order_event(oid))
    out2 = reducer.apply_event(_paid_order_event(oid))

    assert out1.state == AttemptState.SUCCEEDED.value
    assert out2.state == AttemptState.SUCCEEDED.value
    row = _spend_row(repos, contract.intent_id)
    assert row.committed_minor == binding.amount_minor
    assert row.reserved_minor == 0
