"""M37 acceptance: mock provider modes drive real executor/reservation/audit."""

from datetime import UTC, datetime

import pytest

from razormesh_api.domain.ids import new_ulid
from razormesh_api.executor import AttemptState, ProviderOutcome
from razormesh_api.executor import TrustedPaymentExecutor as Executor
from razormesh_api.keys import DevSigningKeys
from razormesh_api.nonce import NonceRegistry
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.providers.mock import MockMode, MockPaymentProvider
from razormesh_api.spend import SpendManager
from test_executor import _make_ticket  # reuse the FK-consistent builder

NOW = datetime.now(UTC)


def _redis() -> NonceRegistry:
    import os

    from redis import Redis

    url = os.environ.get("RAZORMESH_TEST_REDIS_URL", "redis://127.0.0.1:16379/0")
    return NonceRegistry(Redis.from_url(url, decode_responses=True), ttl_seconds=120)


@pytest.fixture()
def harness(tmp_path):  # type: ignore[no-untyped-def]
    from sqlalchemy import create_engine

    from razormesh_api.settings import get_settings

    engine = create_engine(get_settings().database_url, future=True)
    repos = Repositories(create_session_factory(engine))
    keys = DevSigningKeys(
        private_path=str(tmp_path / "p.pem"), public_path=str(tmp_path / "pub.pem")
    ).ensure()
    nonces = _redis()
    spend = SpendManager(repos)
    provider = MockPaymentProvider(mode=MockMode.SUCCESS)
    executor = Executor(repos=repos, keys=keys, nonces=nonces, provider=provider, spend=spend)

    def run(mode: MockMode):  # type: ignore[no-untyped-def]
        provider.mode = mode
        signed, binding, contract = _make_ticket(keys, repos)
        iid = contract.intent_id
        spend.ensure_authorization(iid, authorized_minor=5_000_000)
        spend.reserve(iid, 100000)
        attempt = executor.execute(
            signed_ticket=signed,
            binding=binding,
            intent_id=iid,
            idempotency_key=f"idx-{new_ulid()}",
            now_utc=NOW,
        )
        return attempt, iid

    yield run, provider, repos, spend
    from conftest import wipe_business_tables

    wipe_business_tables(engine)


def test_success_mode_effect_and_commit(harness) -> None:  # type: ignore[no-untyped-def]
    run, provider, _repos, spend = harness
    attempt, iid = run(MockMode.SUCCESS)
    assert attempt.state == AttemptState.SUCCEEDED.value
    snap = spend.snapshot(iid)
    assert snap is not None and snap.committed_minor == 100000 and snap.reserved_minor == 0
    # provider-side effect exists exactly once
    assert len(provider.effects) == 1


def test_definitive_failure_releases_without_effect(harness) -> None:  # type: ignore[no-untyped-def]
    run, provider, _repos, spend = harness
    attempt, iid = run(MockMode.DEFINITIVE_FAILURE)
    assert attempt.state == AttemptState.FAILED.value
    snap = spend.snapshot(iid)
    assert snap is not None and snap.reserved_minor == 0
    assert provider.effects == {}, "failed payments must not leave provider effects"


def test_timeout_before_effect_unknown_but_no_provider_effect(harness) -> None:  # type: ignore[no-untyped-def]
    run, provider, _repos, spend = harness
    attempt, iid = run(MockMode.TIMEOUT_BEFORE_EFFECT)
    assert attempt.state == AttemptState.PROVIDER_UNKNOWN.value
    assert provider.effects == {}, "timeout-before-effect must NOT have moved money"
    snap = spend.snapshot(iid)
    assert snap is not None and snap.reserved_minor == 100000  # held


def test_timeout_after_success_money_moved_despite_unknown(harness) -> None:  # type: ignore[no-untyped-def]
    run, provider, _repos, _spend = harness
    attempt, _iid = run(MockMode.TIMEOUT_AFTER_SUCCESS)
    assert attempt.state == AttemptState.PROVIDER_UNKNOWN.value
    # provider-side truth: the payment DID happen
    refs = list(provider.effects.values())
    assert len(refs) == 1
    # reconciliation resolves the unknown using the delivered event
    events = provider.pending_events()
    succeeded = [e for e in events if e.kind == "SUCCEEDED"]
    assert len(succeeded) == 1 and succeeded[0].reference == refs[0]
    resolved = executor_resolve(harness, attempt, succeeded[0].reference)
    assert resolved.state == AttemptState.SUCCEEDED.value


def executor_resolve(harness, attempt, reference):  # type: ignore[no-untyped-def]
    _run, provider, repos, spend = harness
    from razormesh_api.executor import TrustedPaymentExecutor

    # resolve through a fresh executor sharing repos (ops reconciliation path)
    ex = TrustedPaymentExecutor(
        repos=repos,
        keys=DevSigningKeys(
            private_path=".dev-reconcile/p.pem", public_path=".dev-reconcile/pub.pem"
        ),
        nonces=_redis(),
        provider=provider,
        spend=spend,
    )
    return ex.resolve_unknown(attempt.execution_attempt_id, ProviderOutcome.SUCCEEDED, reference)


def test_duplicate_event_same_reference_single_effect(harness) -> None:  # type: ignore[no-untyped-def]
    from razormesh_api.executor import ChargeCommand

    _run, provider, _repos, _spend = harness
    cmd = ChargeCommand(
        execution_attempt_id="exa_DUPTEST000000000000000000",
        intent_id="intent_x",
        amount_minor=100000,
        currency="INR",
        nonce="nonce-dup-0001",
    )
    r1 = provider.charge(cmd)
    r2 = provider.charge(cmd)  # webhook-style duplicate
    assert r1.provider_reference == r2.provider_reference
    assert len(provider.effects) == 1, "duplicate delivery must not double-effect"


def test_delayed_event_unknown_then_later_delivery(harness) -> None:  # type: ignore[no-untyped-def]
    run, provider, _repos, _spend = harness
    attempt, _iid = run(MockMode.DELAYED_EVENT)
    assert attempt.state == AttemptState.PROVIDER_UNKNOWN.value
    events = provider.pending_events()
    assert [e.kind for e in events] == ["SUCCEEDED"]


def test_out_of_order_events_delivered_terminal_first(harness) -> None:  # type: ignore[no-untyped-def]
    run, provider, _repos, _spend = harness
    attempt, _iid = run(MockMode.OUT_OF_ORDER_EVENT)
    assert attempt.state == AttemptState.SUCCEEDED.value
    events = provider.pending_events()
    kinds = [e.kind for e in events]
    assert kinds == ["SUCCEEDED", "CREATED"], "terminal arrives before creation"
    seqs = [e.seq for e in events]
    assert seqs != sorted(seqs), "sequence numbers prove out-of-order arrival"
