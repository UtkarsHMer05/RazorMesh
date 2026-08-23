"""M25 acceptance: hash-chained evidence ledger + tamper detection."""

from threading import Thread

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine

from razormesh_api.domain.evidence import GENESIS_HASH
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.persistence import models  # noqa: F401
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.models import AuditEvent
from razormesh_api.persistence.repositories import Repositories


def _make() -> tuple[EvidenceLedger, Engine]:
    from razormesh_api.settings import get_settings

    engine = create_engine(get_settings().database_url, future=True)
    repos = Repositories(create_session_factory(engine))
    return EvidenceLedger(repos), engine


def _wipe_audit(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE audit_events DISABLE TRIGGER trg_audit_no_update"))
        conn.execute(text("DELETE FROM audit_events"))
        conn.execute(text("ALTER SEQUENCE audit_events_seq_seq RESTART WITH 1"))
        conn.execute(text("ALTER TABLE audit_events ENABLE TRIGGER trg_audit_no_update"))


@pytest.fixture()
def env():
    led, engine = _make()
    _wipe_audit(engine)
    yield led, engine
    _wipe_audit(engine)


def test_genesis_append_and_chain_verification(env) -> None:
    led, _ = env
    e1 = led.append(event_type="INTENT_AUTHORIZED", actor="principal", payload={"gen": 1})
    assert e1.previous_event_hash == GENESIS_HASH
    assert e1.seq == 1
    led.append(
        event_type="DECISION_RECORDED",
        actor="razorguard",
        payload={"decision": "ALLOW"},
        reason_codes=["BUDGET_OK"],
    )
    report = led.verify()
    assert report.valid, report.reason
    assert report.events_checked == 2


def test_tampered_record_is_detected(env) -> None:
    led, engine = env
    led.append(event_type="A", actor="x", payload={"n": 1})
    middle = led.append(event_type="B", actor="x", payload={"n": 2})
    led.append(event_type="C", actor="x", payload={"n": 3})
    intact = led.verify()
    assert intact.valid and intact.events_checked == 3

    # Simulate an attacker who somehow bypassed the append-only trigger.
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE audit_events DISABLE TRIGGER trg_audit_no_update"))
        conn.execute(
            text(
                "UPDATE audit_events SET metadata = '{\"n\": 999}' WHERE event_id = :eid"
            ).bindparams(eid=middle.event_id)
        )
        conn.execute(text("ALTER TABLE audit_events ENABLE TRIGGER trg_audit_no_update"))

    report = led.verify()
    assert not report.valid
    assert report.events_checked == 3
    assert report.broken_at_event_id == middle.event_id
    assert "altered" in (report.reason or "")


def test_tampered_link_is_detected(env) -> None:
    led, engine = env
    led.append(event_type="A", actor="x")
    last = led.append(event_type="B", actor="x")

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE audit_events DISABLE TRIGGER trg_audit_no_update"))
        conn.execute(
            text(
                "UPDATE audit_events SET previous_event_hash = :fake WHERE event_id = :eid"
            ).bindparams(fake="f" * 64, eid=last.event_id)
        )
        conn.execute(text("ALTER TABLE audit_events ENABLE TRIGGER trg_audit_no_update"))

    report = led.verify()
    assert not report.valid
    assert report.events_checked == 2
    assert report.broken_at_event_id == last.event_id
    assert "broken link" in (report.reason or "")


def test_concurrent_appends_keep_single_linear_chain() -> None:
    _led, engine = _make()
    _wipe_audit(engine)

    def worker(n: int) -> None:
        led, _ = _make()
        for i in range(10):
            led.append(event_type=f"W{n}", actor="load", payload={"i": i})

    threads = [Thread(target=worker, args=(n,)) for n in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with create_session_factory(engine)() as s:
        seqs = list(s.execute(select(AuditEvent.seq).order_by(AuditEvent.seq)).scalars())
        assert len(seqs) == 50
        assert seqs == sorted(seqs)
        assert len(set(seqs)) == len(seqs)
    led, _ = _make()
    report = led.verify()
    assert report.valid, report.reason
    assert report.events_checked == 50
    _wipe_audit(engine)
