"""M36 acceptance: trusted executor, durable attempts, provider-unknown safety."""

from datetime import UTC, datetime, timedelta

import pytest

from razormesh_api.domain.authz_hash import (
    checkout_authorization_hash,
    intent_authorization_hash,
)
from razormesh_api.domain.checkout import BoundedText, CheckoutEnvelope, LineItem
from razormesh_api.domain.ids import (
    DecisionId,
    ExecutionTicketId,
    IntentId,
    new_ulid,
)
from razormesh_api.domain.intent import IntentContract
from razormesh_api.domain.money import Money
from razormesh_api.domain.provenance import Provenanced
from razormesh_api.executor import (
    AttemptState,
    ChargeResult,
    IllegalAttemptTransition,
    ProviderOutcome,
)
from razormesh_api.executor import TrustedPaymentExecutor as Executor
from razormesh_api.keys import DevSigningKeys
from razormesh_api.nonce import NonceAlreadyClaimed, NonceRegistry
from razormesh_api.persistence import models  # noqa: F401
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.models import (
    AuthorizationSpend,
    Checkout,
    Decision,
    ExecutionAttempt,
    ExecutionTicket,
    Merchant,
)
from razormesh_api.persistence.models import (
    IntentContract as RowIntent,
)
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.spend import SpendManager
from razormesh_api.tickets import (
    CurrentBinding,
    ExecutionTicketClaims,
    TicketIssuer,
    TicketRejected,
)

NOW = datetime.now(UTC)


def _redis() -> NonceRegistry:
    import os

    from redis import Redis

    url = os.environ.get("RAZORMESH_TEST_REDIS_URL", "redis://127.0.0.1:16379/0")
    return NonceRegistry(Redis.from_url(url, decode_responses=True), ttl_seconds=120)


class FakeProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.script: list[ChargeResult | Exception] = []

    def charge(self, command):  # type: ignore[no-untyped-def]
        self.calls += 1
        action = (
            self.script.pop(0)
            if self.script
            else ChargeResult(
                outcome=ProviderOutcome.SUCCEEDED,
                provider_reference=f"ref_{command.execution_attempt_id[:10]}",
            )
        )
        if isinstance(action, Exception):
            raise action
        return action


def _envelope() -> CheckoutEnvelope:
    it = LineItem(
        product_id=f"prd_{new_ulid()}",
        display_name=Provenanced[BoundedText].model_construct(
            value=BoundedText(text="Headphones"),
            trust_class="UNTRUSTED_CONTENT",
            source_type="MERCHANT_FREE_TEXT",
            source_id="c",
            observed_at=NOW,
        ),
        quantity=1,
        unit_price=Money(100000),
    )
    return CheckoutEnvelope(
        checkout_id=f"chk_{new_ulid()}",
        revision=1,
        merchant_id=f"mrc_{new_ulid()}",
        line_items=(it,),
        tax=Money(0),
        shipping=Money(0),
        fees=Money(0),
        provided_total=Money(100000),
        observed_at=NOW,
    )


def _intent() -> IntentContract:
    return IntentContract(
        intent_id=IntentId.generate(),
        principal_id=f"usr_{new_ulid()}",
        agent_id=f"agt_{new_ulid()}",
        authorization_generation=1,
        currency="INR",
        max_total=Money(500000),
        aggregate_budget=Money(5000000),
        approval_threshold=Money(400000),
        issued_at=NOW,
        authorized_at=NOW,
        expires_at=NOW + timedelta(minutes=30),
    )


@pytest.fixture()
def env_setup(tmp_path):  # type: ignore[no-untyped-def]
    from sqlalchemy import create_engine

    from razormesh_api.settings import get_settings

    engine = create_engine(get_settings().database_url, future=True)
    repos = Repositories(create_session_factory(engine))
    keys = DevSigningKeys(
        private_path=str(tmp_path / "p.pem"), public_path=str(tmp_path / "pub.pem")
    ).ensure()
    nonces = _redis()
    provider = FakeProvider()
    spend = SpendManager(repos)
    executor = Executor(repos=repos, keys=keys, nonces=nonces, provider=provider, spend=spend)
    yield executor, provider, repos, spend, keys
    with repos.transaction() as s:
        s.query(ExecutionAttempt).delete()
        s.query(ExecutionTicket).delete()
        s.query(Decision).delete()
        s.query(Checkout).delete()
        s.query(AuthorizationSpend).delete()
        s.query(Merchant).delete()
        s.query(RowIntent).delete()


def _persist_chain(
    repos, contract: IntentContract, env: CheckoutEnvelope, decision_id: DecisionId
) -> None:
    """Persist the durable authorization chain the FK graph requires."""
    now = datetime.now(UTC)
    total = env.compute_total().amount_minor
    with repos.transaction() as s:
        # NOTE: explicit flush after each parent insert. SQLAlchemy's unit of
        # work did not derive merchants->checkouts dependency order here
        # (no relationship()), emitting the child INSERT first.
        s.merge(
            Merchant(
                id=str(env.merchant_id),
                name="Chain Merchant",
                display_name="Chain Merchant",
                created_at=now,
                updated_at=now,
            )
        )
        s.flush()
        s.merge(
            RowIntent(
                intent_id=str(contract.intent_id),
                principal_id=str(contract.principal_id),
                agent_id=str(contract.agent_id),
                authorization_generation=1,
                status="AUTHORIZED",
                currency="INR",
                max_total_minor=500000,
                aggregate_budget_minor=5000000,
                max_quantity=contract.max_quantity,
                recurring_allowed=False,
                approval_threshold_minor=400000,
                issued_at=NOW,
                authorized_at=NOW,
                expires_at=NOW + timedelta(minutes=30),
                created_at=now,
                updated_at=now,
            )
        )
        s.flush()
        s.merge(
            Checkout(
                checkout_id=str(env.checkout_id),
                revision=env.revision,
                merchant_id=str(env.merchant_id),
                line_items=[
                    {
                        "product_id": str(i.product_id),
                        "quantity": i.quantity,
                        "unit_price_minor": i.unit_price.amount_minor,
                        "currency": i.unit_price.currency,
                        "condition": i.condition,
                    }
                    for i in env.line_items
                ],
                tax_minor=env.tax.amount_minor,
                shipping_minor=env.shipping.amount_minor,
                fees_minor=env.fees.amount_minor,
                provided_total_minor=total,
                computed_total_minor=total,
                currency="INR",
                observed_at=now,
                created_at=now,
            )
        )
        s.flush()
        s.merge(
            Decision(
                decision_id=str(decision_id),
                intent_id=str(contract.intent_id),
                checkout_id=str(env.checkout_id),
                intent_generation=1,
                checkout_hash=checkout_authorization_hash(env),
                policy_version="razormesh-phase1-policy-v1",
                decision="ALLOW",
                created_at=now,
            )
        )


def _make_ticket(keys, repos):  # type: ignore[no-untyped-def]
    """Build env/contract/decision consistently and persist the chain."""
    env, contract, decision_id = _envelope(), _intent(), DecisionId.generate()
    _persist_chain(repos, contract, env, decision_id)
    claims = ExecutionTicketClaims(
        ticket_id=ExecutionTicketId.generate(),
        decision_id=decision_id,
        checkout_id=env.checkout_id,
        intent_id=contract.intent_id,
        principal_id=str(contract.principal_id),
        agent_id=str(contract.agent_id),
        authorization_generation=1,
        intent_hash=intent_authorization_hash(contract),
        checkout_hash=checkout_authorization_hash(env),
        checkout_revision=env.revision,
        merchant_id=str(env.merchant_id),
        amount_minor=env.compute_total().amount_minor,
        currency="INR",
        policy_version="razormesh-phase1-policy-v1",
        nonce=f"nonce-{new_ulid()}{new_ulid()}",
        issued_at=NOW,
        expires_at=NOW + timedelta(seconds=60),
    )
    signed = TicketIssuer(keys).issue(claims)
    binding = CurrentBinding(
        principal_id=str(contract.principal_id),
        agent_id=str(contract.agent_id),
        intent_id=str(contract.intent_id),
        intent_hash=claims.intent_hash,
        authorization_generation=1,
        checkout_id=str(env.checkout_id),
        checkout_hash=claims.checkout_hash,
        checkout_revision=env.revision,
        merchant_id=str(env.merchant_id),
        amount_minor=claims.amount_minor,
        currency="INR",
    )
    return signed, binding, contract


def test_success_persists_succeeded_and_commits_spend(env_setup):  # type: ignore[no-untyped-def]
    executor, provider, repos, spend, keys = env_setup
    signed, binding, contract = _make_ticket(keys, repos)
    iid = contract.intent_id
    spend.ensure_authorization(iid, authorized_minor=5_000_000)
    attempt = executor.execute(
        signed_ticket=signed,
        binding=binding,
        intent_id=iid,
        now_utc=NOW,
    )
    assert attempt.state == AttemptState.SUCCEEDED.value
    assert provider.calls == 1
    snap = spend.snapshot(iid)
    assert snap is not None and snap.committed_minor == 100000


def test_definitive_failure_fails_and_releases(env_setup):  # type: ignore[no-untyped-def]
    executor, provider, repos, spend, keys = env_setup
    signed, binding, contract = _make_ticket(keys, repos)
    iid = contract.intent_id
    spend.ensure_authorization(iid, authorized_minor=5_000_000)
    provider.script = [ChargeResult(outcome=ProviderOutcome.FAILED, error_code="CARD_DECLINED")]
    attempt = executor.execute(
        signed_ticket=signed,
        binding=binding,
        intent_id=iid,
        now_utc=NOW,
    )
    assert attempt.state == AttemptState.FAILED.value
    assert attempt.error_code == "CARD_DECLINED"
    snap = spend.snapshot(iid)
    assert snap is not None and snap.reserved_minor == 0


def test_provider_exception_yields_unknown_and_keeps_reservation(env_setup):  # type: ignore[no-untyped-def]
    executor, provider, repos, spend, keys = env_setup
    signed, binding, contract = _make_ticket(keys, repos)
    iid = contract.intent_id
    spend.ensure_authorization(iid, authorized_minor=5_000_000)
    provider.script = [TimeoutError("socket died after send")]
    attempt = executor.execute(
        signed_ticket=signed,
        binding=binding,
        intent_id=iid,
        now_utc=NOW,
    )
    assert attempt.state == AttemptState.PROVIDER_UNKNOWN.value
    snap = spend.snapshot(iid)
    assert snap is not None and snap.reserved_minor == 100000  # KEPT


def test_retry_same_idempotency_never_recharges(env_setup):  # type: ignore[no-untyped-def]
    executor, provider, repos, spend, keys = env_setup
    signed, binding, contract = _make_ticket(keys, repos)
    iid = contract.intent_id
    spend.ensure_authorization(iid, authorized_minor=5_000_000)
    provider.script = [TimeoutError("unknown")]
    first = executor.execute(
        signed_ticket=signed,
        binding=binding,
        intent_id=iid,
        now_utc=NOW,
    )
    second = executor.execute(
        signed_ticket=signed,
        binding=binding,
        intent_id=iid,
        now_utc=NOW + timedelta(seconds=5),
    )
    assert second.execution_attempt_id == first.execution_attempt_id
    assert provider.calls == 1, "retry must not create a fresh financial operation"


def test_invalid_ticket_blocks_before_side_effects(env_setup):  # type: ignore[no-untyped-def]
    executor, provider, repos, spend, keys = env_setup
    signed, binding, contract = _make_ticket(keys, repos)
    iid = contract.intent_id
    spend.ensure_authorization(iid, authorized_minor=5_000_000)
    tampered = CurrentBinding(**{**binding.__dict__, "principal_id": "usr_attacker"})
    with pytest.raises(TicketRejected):
        executor.execute(
            signed_ticket=signed,
            binding=tampered,
            intent_id=iid,
            now_utc=NOW,
        )
    assert provider.calls == 0
    with repos.transaction() as s:
        assert s.query(ExecutionAttempt).count() == 0


def test_nonce_replay_rejected_by_registry(env_setup):  # type: ignore[no-untyped-def]
    _executor, provider, _repos, _spend, _keys = env_setup
    nonces = _redis()
    nonce = f"nonce-{new_ulid()}{new_ulid()}"
    nonces.claim(nonce, "first-attempt")
    with pytest.raises(NonceAlreadyClaimed):
        nonces.claim(nonce, "second-attempt")
    assert provider.calls == 0


def test_blocked_authorization_rejected_at_executor_boundary(env_setup) -> None:  # type: ignore[no-untyped-def]
    executor, provider, repos, spend, keys = env_setup
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)
    with repos.transaction() as session:
        row = session.get(RowIntent, str(contract.intent_id))
        assert row is not None
        row.status = "BLOCKED"

    with pytest.raises(TicketRejected) as error:
        executor.execute(
            signed_ticket=signed,
            binding=binding,
            intent_id=contract.intent_id,
            now_utc=NOW,
        )
    assert error.value.code == "STATUS_NOT_EXECUTABLE"
    assert provider.calls == 0
    snapshot = spend.snapshot(contract.intent_id)
    assert snapshot is not None and snapshot.reserved_minor == 0


def test_non_allow_durable_decision_rejected_at_executor_boundary(env_setup) -> None:  # type: ignore[no-untyped-def]
    executor, provider, repos, spend, keys = env_setup
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)
    with repos.transaction() as session:
        decision = session.query(Decision).one()
        decision.decision = "BLOCK"

    with pytest.raises(TicketRejected) as error:
        executor.execute(
            signed_ticket=signed,
            binding=binding,
            intent_id=contract.intent_id,
            now_utc=NOW,
        )
    assert error.value.code == "DECISION_NOT_EXECUTABLE"
    assert provider.calls == 0


def test_unknown_reconciliation_persists_reference_and_settles_reservation(env_setup) -> None:  # type: ignore[no-untyped-def]
    executor, provider, repos, spend, keys = env_setup
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)
    provider.script = [TimeoutError("unknown after send")]
    unknown = executor.execute(
        signed_ticket=signed,
        binding=binding,
        intent_id=contract.intent_id,
        now_utc=NOW,
    )

    resolved = executor.resolve_unknown(
        unknown.execution_attempt_id,
        ProviderOutcome.SUCCEEDED,
        provider_reference="mock_reconciled_001",
    )
    assert resolved.state == AttemptState.SUCCEEDED.value
    assert resolved.provider_reference == "mock_reconciled_001"
    snapshot = spend.snapshot(contract.intent_id)
    assert snapshot is not None
    assert snapshot.reserved_minor == 0 and snapshot.committed_minor == 100000

    with pytest.raises(IllegalAttemptTransition):
        executor.resolve_unknown(resolved.execution_attempt_id, ProviderOutcome.UNKNOWN)


def test_pre_provider_failure_closes_attempt_and_releases_capacity(
    env_setup, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    executor, provider, repos, spend, keys = env_setup
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)

    def fail_audit(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr("razormesh_api.executor.EvidenceLedger.append", fail_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        executor.execute(
            signed_ticket=signed,
            binding=binding,
            intent_id=contract.intent_id,
            now_utc=NOW,
        )

    with repos.transaction() as session:
        attempt = session.query(ExecutionAttempt).one()
        ticket = session.query(ExecutionTicket).one()
    assert attempt.state == AttemptState.FAILED.value
    assert attempt.error_code == "PRE_PROVIDER_ABORTED"
    assert provider.calls == 0
    snapshot = spend.snapshot(contract.intent_id)
    assert snapshot is not None and snapshot.reserved_minor == 0
    assert _redis().holder_of(ticket.nonce) is None
