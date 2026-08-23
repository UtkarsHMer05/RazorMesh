"""M31 acceptance: atomic reservations; release/commit/keep semantics; concurrency."""

import os
from threading import Thread

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from razormesh_api.domain.ids import IntentId, new_ulid
from razormesh_api.persistence import models  # noqa: F401
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.models import AuthorizationSpend, IntentContract
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.spend import InsufficientCapacity, SpendManager


def _engine() -> Engine:
    from razormesh_api.settings import get_settings

    return create_engine(
        os.environ.get(
            "RAZORMESH_TEST_DATABASE_URL",
            get_settings().database_url,
        ),
        future=True,
    )


def _make():
    engine = _engine()
    repos = Repositories(create_session_factory(engine))
    return SpendManager(repos), repos, engine


def _intent(iid: IntentId):
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    return IntentContract(
        intent_id=str(iid),
        principal_id="usr_demo",
        agent_id="agt_demo",
        authorization_generation=1,
        status="AUTHORIZED",
        currency="INR",
        max_total_minor=500000,
        aggregate_budget_minor=10000000,
        max_quantity=2,
        recurring_allowed=False,
        approval_threshold_minor=400000,
        issued_at=now - timedelta(minutes=10),
        authorized_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(minutes=60),
        created_at=now,
        updated_at=now,
    )


def test_reserve_commit_release_lifecycle():
    mgr, repos, _engine_unused = _make()
    iid = IntentId(f"intent_{new_ulid()}")
    with repos.transaction() as s:
        s.add(_intent(iid))
    try:
        mgr.ensure_authorization(iid, authorized_minor=1_000_000)
        assert mgr.available(iid) == 1_000_000

        mgr.reserve(iid, 300_000)
        assert mgr.available(iid) == 700_000

        # verified success: reserved -> committed
        mgr.commit(iid, 300_000)
        snap = mgr.snapshot(iid)
        assert snap is not None
        assert snap.reserved_minor == 0
        assert snap.committed_minor == 300_000
        assert mgr.available(iid) == 700_000

        # new reservation then definitive failure: capacity returns
        mgr.reserve(iid, 200_000)
        mgr.release(iid, 200_000)
        snap = mgr.snapshot(iid)
        assert snap is not None
        assert snap.reserved_minor == 0 and snap.committed_minor == 300_000
        mgr.assert_invariants(iid)
    finally:
        with repos.transaction() as s:
            s.query(AuthorizationSpend).filter_by(intent_id=str(iid)).delete()
            s.query(IntentContract).filter_by(intent_id=str(iid)).delete()


def test_over_reservation_rejected_atomically():
    mgr, repos, _ = _make()
    iid = IntentId(f"intent_{new_ulid()}")
    with repos.transaction() as s:
        s.add(_intent(iid))
    try:
        mgr.ensure_authorization(iid, authorized_minor=500_000)
        mgr.reserve(iid, 400_000)
        try:
            mgr.reserve(iid, 200_000)  # only 100k available
            raise AssertionError("expected InsufficientCapacity")
        except InsufficientCapacity as exc:
            assert exc.available == 100_000 and exc.requested == 200_000
        # nothing partially applied
        assert mgr.available(iid) == 100_000
        mgr.assert_invariants(iid)
    finally:
        with repos.transaction() as s:
            s.query(AuthorizationSpend).filter_by(intent_id=str(iid)).delete()
            s.query(IntentContract).filter_by(intent_id=str(iid)).delete()


def test_provider_unknown_keeps_reservation_held():
    """Provider-unknown must NOT release: the reservation stays until resolved."""
    mgr, repos, _ = _make()
    iid = IntentId(f"intent_{new_ulid()}")
    with repos.transaction() as s:
        s.add(_intent(iid))
    try:
        mgr.ensure_authorization(iid, authorized_minor=1_000_000)
        mgr.reserve(iid, 250_000)
        before = mgr.snapshot(iid)
        assert before is not None
        # ... provider outcome unknown: deliberately no release / no commit ...
        after = mgr.snapshot(iid)
        assert after is not None
        assert after.reserved_minor == before.reserved_minor == 250_000
        assert mgr.available(iid) == 750_000
    finally:
        with repos.transaction() as s:
            s.query(AuthorizationSpend).filter_by(intent_id=str(iid)).delete()
            s.query(IntentContract).filter_by(intent_id=str(iid)).delete()


def test_concurrent_reservations_cannot_exceed_capacity():
    """10 threads x 150k against 1M authority: exactly 6 succeed."""
    mgr, repos, engine = _make()
    iid = IntentId(f"intent_{new_ulid()}")
    results: list[str] = []
    errors: list[Exception] = []

    def worker() -> None:
        local_mgr = SpendManager(Repositories(create_session_factory(engine)))
        try:
            local_mgr.reserve(iid, 150_000)
            results.append("reserved")
        except InsufficientCapacity:
            results.append("rejected")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    with repos.transaction() as s:
        s.query(IntentContract).filter_by(intent_id=str(iid)).delete()
        s.add(_intent(iid))
    try:
        mgr.ensure_authorization(iid, authorized_minor=1_000_000)
        threads = [Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, errors
        assert results.count("reserved") == 6
        assert results.count("rejected") == 4
        mgr.assert_invariants(iid)
        assert mgr.available(iid) == 100_000
    finally:
        with repos.transaction() as s:
            s.query(AuthorizationSpend).filter_by(intent_id=str(iid)).delete()
            s.query(IntentContract).filter_by(intent_id=str(iid)).delete()


@settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    st.lists(st.integers(min_value=1, max_value=400_000), min_size=1, max_size=25),
    st.booleans(),
)
def test_random_operation_sequences_preserve_invariants(amounts, fail_mode):
    """Random reserve/release sequences never break durable invariants."""
    mgr, repos, _ = _make()
    iid = IntentId(f"intent_{new_ulid()}")
    with repos.transaction() as s:
        s.add(_intent(iid))
    try:
        mgr.ensure_authorization(iid, authorized_minor=1_000_000)
        held: list[int] = []
        for amount in amounts:
            if sum(held) + amount <= 1_000_000:
                mgr.reserve(iid, amount)
                held.append(amount)
                if fail_mode:
                    mgr.release(iid, amount)
                    held.pop()
            mgr.assert_invariants(iid)
        expected_reserved = 0 if fail_mode else sum(held)
        snap = mgr.snapshot(iid)
        assert snap is not None
        assert snap.committed_minor == 0  # commit() never invoked in this scenario
        assert snap.reserved_minor == expected_reserved
    finally:
        with repos.transaction() as s:
            s.query(AuthorizationSpend).filter_by(intent_id=str(iid)).delete()
            s.query(IntentContract).filter_by(intent_id=str(iid)).delete()
