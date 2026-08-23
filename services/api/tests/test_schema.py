from sqlalchemy import inspect, text

from razormesh_api.persistence.db import create_db_engine, create_session_factory
from razormesh_api.settings import get_settings


def _engine():
    s = get_settings()
    return create_db_engine(s.database_url)


def test_migration_creates_all_core_tables():
    engine = _engine()
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    expected = {
        "merchants",
        "products",
        "intent_contracts",
        "checkouts",
        "decisions",
        "authorization_spend",
        "execution_tickets",
        "execution_attempts",
        "audit_events",
        "alembic_version",
    }
    missing = expected - tables
    assert not missing, f"missing tables: {missing}"


def test_unique_constraints_present():
    engine = _engine()
    insp = inspect(engine)
    uq = {(r["name"]) for r in insp.get_unique_constraints("execution_tickets")}
    assert "uq_ticket_nonce" in uq
    uq2 = {(r["name"]) for r in insp.get_unique_constraints("execution_attempts")}
    assert "uq_attempt_idempotency" in uq2
    uq3 = {(r["name"]) for r in insp.get_unique_constraints("audit_events")}
    assert "uq_audit_current_hash" in uq3


def test_audit_events_append_only_trigger_blocks_mutation():
    engine = _engine()
    factory = create_session_factory(engine)
    with factory() as session:  # type: Session
        session.execute(
            text(
                """
                INSERT INTO audit_events
                (event_id, event_type, actor, timestamp,
                 current_event_hash, created_at)
                VALUES
                ('evt_01TEST00000000000000000001',
                 'TEST_EVENT', 'test', NOW(),
                 'hash_test_001', NOW())
                ON CONFLICT DO NOTHING
                """
            )
        )
        session.commit()
        try:
            session.execute(
                text(
                    "UPDATE audit_events SET actor='mutated' "
                    "WHERE event_id='evt_01TEST00000000000000000001'"
                )
            )
            session.commit()
            raise AssertionError("UPDATE should have been blocked")
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            assert "append-only" in str(exc).lower() or "forbidden" in str(exc).lower()
        try:
            session.execute(
                text("DELETE FROM audit_events WHERE event_id='evt_01TEST00000000000000000001'")
            )
            session.commit()
            raise AssertionError("DELETE should have been blocked")
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            assert "append-only" in str(exc).lower() or "forbidden" in str(exc).lower()
        session.execute(text("ALTER TABLE audit_events DISABLE TRIGGER trg_audit_no_update"))
        session.execute(
            text("DELETE FROM audit_events WHERE event_id='evt_01TEST00000000000000000001'")
        )
        session.execute(text("ALTER TABLE audit_events ENABLE TRIGGER trg_audit_no_update"))
        session.commit()


def test_check_constraints_exist():
    engine = _engine()
    insp = inspect(engine)
    ccs = insp.get_check_constraints("authorization_spend")
    names = {c["name"] for c in ccs}
    assert "ck_spend_reserved_nonneg" in names
