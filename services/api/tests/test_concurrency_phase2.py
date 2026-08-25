"""P2-M42: concurrency & replay regression against the provider architecture.

High volume runs ONLY against mock/fake transports — Razorpay is never
contacted (master prompt M42).

Proven here:
- 20 concurrent same-ticket executes -> at most ONE attempt, ONE provider
  order create, ONE reservation (business/provider effect exactly-once);
- 20 concurrent duplicate webhook deliveries (same event id) -> inbox claim
  wins once, settlement commits exactly-once;
- mixed verified events (captured/order.paid/authorized) under concurrency
  collapse to ONE commit;
- callback path racing webhook path cannot double-commit;
- post-settlement ticket replay never re-pays.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import httpx
import pytest

from razormesh_api.executor import AttemptState, IllegalAttemptTransition, TrustedPaymentExecutor
from razormesh_api.nonce import CoordinationUnavailable, NonceAlreadyClaimed
from razormesh_api.persistence.models import (
    AuthorizationSpend,
    Checkout,
    Decision,
    ExecutionAttempt,
    ExecutionTicket,
    ProviderEvent,
)
from razormesh_api.providers.razorpay import RazorpayClient, RazorpayPaymentProvider
from razormesh_api.reducer import ProviderStateReducer, VerifiedProviderEvent
from razormesh_api.settings import get_settings
from razormesh_api.spend import SpendManager
from razormesh_api.webhook_inbox import ingest_verified_event
from test_executor import _make_ticket, _redis

WORKERS = 20


class _CountingTransport(httpx.BaseTransport):
    def __init__(self) -> None:
        self.calls = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        assert request.method == "POST" and request.url.path.endswith("/orders")
        body = __import__("json").loads(request.read())
        return httpx.Response(
            201,
            json={
                "id": "order_m42_single",
                "status": "created",
                "amount": body["amount"],
                "currency": body["currency"],
                "receipt": body["receipt"],
            },
        )


@pytest.fixture()
def conc_env(tmp_path):  # type: ignore[no-untyped-def]
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
    yield repos, keys, spend
    with repos.transaction() as s:
        s.query(ExecutionAttempt).delete()
        s.query(ProviderEvent).delete()
        s.query(ExecutionTicket).delete()
        s.query(Decision).delete()
        s.query(Checkout).delete()
        s.query(AuthorizationSpend).delete()
        s.query(Merchant).delete()
        s.query(RowIntent).delete()


def _fresh_keys():  # type: ignore[no-untyped-def]
    import tempfile

    from razormesh_api.keys import DevSigningKeys

    d = tempfile.mkdtemp(prefix="rzp_m42_")
    return DevSigningKeys(private_path=f"{d}/p.pem", public_path=f"{d}/pub.pem").ensure()


def _executor(repos, keys, spend, transport):  # type: ignore[no-untyped-def]
    client = RazorpayClient(
        key_id="rzp_test_k",
        key_secret="s",
        base_url=get_settings().razorpay_api_base_url,
        timeout_seconds=5,
        transport=transport,
    )
    return TrustedPaymentExecutor(
        repos=repos,
        keys=keys,
        nonces=_redis(),
        provider=RazorpayPaymentProvider(client),
        spend=spend,
    )


def _spend_row(repos, intent_id):  # type: ignore[no-untyped-def]
    with repos.transaction() as s:
        row = s.get(AuthorizationSpend, str(intent_id))
        assert row is not None
        return row


def _executing_attempt(conc_env):  # type: ignore[no-untyped-def]
    """EXECUTING attempt with a claimed provider order (post-checkout state)."""
    repos, keys, spend = conc_env
    transport = _CountingTransport()
    executor = _executor(repos, keys, spend, transport)
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)
    attempt = executor.execute(signed_ticket=signed, binding=binding, intent_id=contract.intent_id)
    assert attempt.state == AttemptState.EXECUTING.value
    return attempt, transport, signed, binding, contract


def test_twenty_workers_same_ticket_one_provider_effect(conc_env) -> None:  # type: ignore[no-untyped-def]
    repos, keys, spend = conc_env
    transport = _CountingTransport()
    executor = _executor(repos, keys, spend, transport)
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)

    def worker(_i: int):
        try:
            return executor.execute(
                signed_ticket=signed, binding=binding, intent_id=contract.intent_id
            )
        except NonceAlreadyClaimed:
            return None  # coordination refusal: this delivery lost the race
        except CoordinationUnavailable:
            # P3-M02: Redis fail-closed under extreme machine load. A delivery
            # that cannot even claim the nonce has created NO durable effect
            # (it failed before reservation), so it is inconclusive — never a
            # second effect. The exactly-once PROPERTY below stays strict.
            return None

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(worker, range(WORKERS)))

    settled = [row for row in results if row is not None]
    # Any number of workers may RETURN an attempt: losers either get the
    # nonce refusal OR take the ticket-derived idempotent re-entry shortcut
    # (find_by_idempotency runs BEFORE the nonce claim). What matters is that
    # EVERY returned row is the SAME durable execution identity.
    if settled:
        first = settled[0].execution_attempt_id
        assert all(row.execution_attempt_id == first for row in settled)

    # The exactly-once PROPERTY is asserted on DURABLE state, which no amount
    # of scheduling can change:
    assert transport.calls <= 1  # at most one provider order create ever
    row = _spend_row(repos, contract.intent_id)
    assert row.reserved_minor in (0, binding.amount_minor)  # never double-held
    assert row.committed_minor == 0
    with repos.transaction() as s:
        assert s.query(ExecutionAttempt).count() <= 1

    # Sequential re-entry settles the ticket deterministically and is
    # idempotent: exactly ONE durable attempt, ONE provider call, ONE hold.
    again = executor.execute(signed_ticket=signed, binding=binding, intent_id=contract.intent_id)
    assert again.state == AttemptState.EXECUTING.value
    assert again.razorpay_order_id == "order_m42_single"
    final_row = _spend_row(repos, contract.intent_id)
    assert final_row.reserved_minor == binding.amount_minor  # held EXACTLY once
    assert final_row.committed_minor == 0
    with repos.transaction() as s:
        assert s.query(ExecutionAttempt).count() == 1
    assert transport.calls == 1  # NEVER a blind second payment


def test_capture_webhook_storm_commits_exactly_once(conc_env) -> None:  # type: ignore[no-untyped-def]
    repos, _keys, _spend = conc_env
    attempt, _transport, _signed, _binding, _contract = _executing_attempt(conc_env)

    reducer = ProviderStateReducer(
        repos=repos, keys=_fresh_keys(), nonces=_redis(), provider=None, spend=SpendManager(repos)
    )
    payload_sha = "storm-sha"

    def deliver(_i: int):
        return ingest_verified_event(
            repos,
            event_id="evt_m42_storm",
            event_type="payment.captured",
            payload_sha256=payload_sha,
            razorpay_order_id=attempt.razorpay_order_id,
            razorpay_payment_id="pay_m42",
            process=lambda: reducer.apply_event(
                VerifiedProviderEvent(
                    kind="payment.captured",
                    razorpay_order_id=str(attempt.razorpay_order_id),
                    razorpay_payment_id="pay_m42",
                )
            ),
        )

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(deliver, range(WORKERS)))

    processed = [r for r in results if r.processed]
    duplicates = [r for r in results if r.duplicate]
    assert len(processed) == 1  # exactly one delivery drove processing
    assert len(duplicates) >= WORKERS - 1

    row = _spend_row(repos, attempt.intent_id)
    assert row.reserved_minor == 0
    assert row.committed_minor == attempt.amount_minor  # committed EXACTLY ONCE
    with repos.transaction() as s:
        refreshed = s.get(ExecutionAttempt, attempt.execution_attempt_id)
        assert refreshed is not None
        assert refreshed.state == AttemptState.SUCCEEDED.value
        assert refreshed.fulfilment_state == "ELIGIBLE"
        assert s.query(ProviderEvent).filter_by(event_id="evt_m42_storm").count() == 1


def test_mixed_verified_events_under_concurrency_collapse_to_one_commit(conc_env) -> None:  # type: ignore[no-untyped-def]
    """captured + order.paid + authorized arrive as DISTINCT events concurrently:
    all are processed, but the money moves exactly once."""
    repos, _keys, _spend = conc_env
    attempt, _transport, _signed, _binding, _contract = _executing_attempt(conc_env)

    reducer = ProviderStateReducer(
        repos=repos, keys=_fresh_keys(), nonces=_redis(), provider=None, spend=SpendManager(repos)
    )

    kinds = ["payment.captured", "order.paid", "payment.authorized"]

    def deliver(i: int):
        kind = kinds[i % len(kinds)]

        def process() -> None:
            reducer.apply_event(
                VerifiedProviderEvent(
                    kind=kind,  # type: ignore[arg-type]
                    razorpay_order_id=str(attempt.razorpay_order_id),
                    razorpay_payment_id=f"pay_m42_{i}",
                )
            )

        return ingest_verified_event(
            repos,
            event_id=f"evt_m42_mix_{i}",
            event_type=kind,
            payload_sha256=f"sha-{i}",
            razorpay_order_id=attempt.razorpay_order_id,
            razorpay_payment_id=f"pay_m42_{i}",
            process=process,
        )

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(deliver, range(WORKERS)))

    processed = [r for r in results if r.processed]
    errored = [r for r in results if r.reason == "PROCESSING_ERROR"]
    assert len(processed) + len(errored) == len(results)
    # A settlement loser may record PROCESSING_ERROR; the WINNER still commits.
    row = _spend_row(repos, attempt.intent_id)
    assert row.committed_minor == attempt.amount_minor  # ONE commit total
    assert row.reserved_minor == 0
    with repos.transaction() as s:
        refreshed = s.get(ExecutionAttempt, attempt.execution_attempt_id)
        assert refreshed is not None
        assert refreshed.state == AttemptState.SUCCEEDED.value


def test_callback_racing_webhook_cannot_double_commit(conc_env) -> None:  # type: ignore[no-untyped-def]
    """The checkout callback path (confirm_captured) and the webhook path
    (reducer.apply_event) settle concurrently: exactly one commit survives."""
    repos, keys, spend = conc_env
    attempt, _transport, srt, brp, ctr = _executing_attempt(conc_env)

    executor = _executor(repos, keys, spend, _CountingTransport())
    reducer = ProviderStateReducer(
        repos=repos, keys=_fresh_keys(), nonces=_redis(), provider=None, spend=SpendManager(repos)
    )

    def callback_path():
        try:
            executor.confirm_captured(
                str(attempt.execution_attempt_id),
                provider_payment_id="pay_callback",
                now=datetime.now(UTC),
            )
            return "settled"
        except IllegalAttemptTransition:
            return "already-settled"

    def webhook_path(i: int):
        try:
            reducer.apply_event(
                VerifiedProviderEvent(
                    kind="payment.captured",
                    razorpay_order_id=str(attempt.razorpay_order_id),
                    razorpay_payment_id=f"pay_webhook_{i}",
                )
            )
            return "settled"
        except IllegalAttemptTransition:
            return "already-settled"

    jobs = [("cb", callback_path)] + [
        (f"wh{i}", lambda i=i: webhook_path(i)) for i in range(WORKERS)
    ]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {name: pool.submit(fn) for name, fn in jobs}
        outcomes = {name: fut.result() for name, fut in futures.items()}

    assert "settled" in outcomes.values()  # someone settled it
    row = _spend_row(repos, attempt.intent_id)
    assert row.committed_minor == attempt.amount_minor  # EXACTLY once across paths
    assert row.reserved_minor == 0
    with repos.transaction() as s:
        refreshed = s.get(ExecutionAttempt, attempt.execution_attempt_id)
        assert refreshed is not None
        assert refreshed.state == AttemptState.SUCCEEDED.value

    # Post-settlement ticket replay: same ticket NEVER re-pays.
    replay_transport = _CountingTransport()
    replay_executor = _executor(repos, keys, spend, replay_transport)
    again = replay_executor.execute(signed_ticket=srt, binding=brp, intent_id=ctr.intent_id)
    assert again.execution_attempt_id == attempt.execution_attempt_id
    assert again.state == AttemptState.SUCCEEDED.value  # truthful settled state
    assert replay_transport.calls == 0  # NO second provider order
    row2 = _spend_row(repos, attempt.intent_id)
    assert row2.committed_minor == attempt.amount_minor  # still exactly one commit
    with repos.transaction() as s:
        assert s.query(ExecutionAttempt).count() == 1
