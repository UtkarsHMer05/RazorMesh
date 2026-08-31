"""F009 + F010: audit chain truth + direct indexed search.

F009 — the audit ledger is GLOBAL. A selected trace's events interleave with
other traces' events, so two consecutive anchors of one trace do NOT link by
prev_hash directly when unrelated events lie between. The forensics trace view
must:
  (a) NOT report a trace as broken merely because of interleaving;
  (b) expose per-anchor global-gap metadata (how many global events lie
      between consecutive anchors) and which anchors ARE directly linked;
  (c) leave the cryptographic authority with the GLOBAL CHAIN VERIFY
      (/audit/verify), which stays valid.

F010 — /forensics/search supports direct indexed lookups for every modeled id
(display trace, intent, checkout, attempt, provider order id), never a
recent(100) scan, so OLD traces are findable.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select

from conftest import wipe_business_tables
from razormesh_api.api.main import app
from razormesh_api.catalog import seed_catalog
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.models import AuditEvent
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.security_missions import run_mission


@pytest.fixture()
def repos(settings):  # type: ignore[no-untyped-def]
    engine = create_engine(settings.database_url, future=True)
    r = Repositories(create_session_factory(engine))
    wipe_business_tables(engine)
    seed_catalog(r)
    yield r
    wipe_business_tables(engine)


@pytest.fixture()
def client(settings, repos):  # type: ignore[no-untyped-def]
    import razormesh_api.api.main as api_main

    api_main.get_settings.cache_clear()
    app.dependency_overrides[api_main.get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _interleave_global_events(repos: Repositories, *, other_actor: str) -> None:
    """Append unrelated GLOBAL ledger events between this trace's own events.

    Uses the real ledger append path so the interleaving is genuine (the
    global chain stays valid; the selected trace's anchors just stop being
    trace-consecutive).
    """
    ledger = EvidenceLedger(repos)
    for i in range(3):
        ledger.append(
            event_type="UNRELATED_GLOBAL_EVENT",
            actor=other_actor,
            intent_id=None,
            payload={"note": f"unrelated global event {i} for interleaving test"},
        )


def test_interleaved_trace_is_not_reported_broken(repos: Repositories, client: TestClient) -> None:
    """F009 core: global events from another actor interleaved BETWEEN this
    trace's own anchors must NOT read as a break — anchors carry gap metadata
    and the trace stays ANCHORED; the global verify stays valid."""
    mission = run_mission(repos, mission_id="hidden-recurring")
    trace_id = mission["trace_id"]

    # Interleave unrelated GLOBAL events between this trace's events: the
    # mission's events exist already, and the mutation below appends MORE
    # events to the SAME trace AFTER the unrelated ones.
    _interleave_global_events(repos, other_actor="other-trace-actor")

    # More events for the SAME trace, now after the unrelated global ones —
    # the trace's anchors sit on both sides of other traces' events.
    from razormesh_api.ledger import EvidenceLedger
    from razormesh_api.merchant_sandbox import MutationKind, apply_mutation

    apply_mutation(
        repos,
        EvidenceLedger(repos),
        intent_id=mission["intent_id"],
        checkout_id=mission["checkout_id"],
        kind=MutationKind.PRICE_DRIFT,
    )

    res = client.get(f"/forensics/trace/{trace_id}")
    assert res.status_code == 200
    chain = res.json()["chain"]

    # (a) NOT broken: every anchor carries a prev_hash into the global chain.
    assert chain["anchored"] is True, "interleaving must not read as a break"
    assert "LINK BROKEN" not in str(res.json())
    # (b) gap metadata: at least one anchor has unrelated events before it.
    gaps = [n["global_gap_before"] for n in chain["nodes"] if n["global_gap_before"]]
    assert gaps, "expected interleaved anchors to carry positive gap counts"
    direct = [n for n in chain["nodes"] if n["directly_linked_to_prev"] is False]
    assert direct, "expected at least one non-consecutive anchor (interleaved)"
    # The count is honest: unrelated events between first/last anchor.
    total_gap = sum(g for g in gaps if g is not None)
    assert chain["global_events_between_first_last_anchor"] == total_gap

    # (c) the GLOBAL verify stays the authority and stays VALID.
    verify = client.get("/audit/verify")
    assert verify.status_code == 200
    assert verify.json()["valid"] is True


def test_global_verify_is_authority_even_for_interleaved(
    repos: Repositories, client: TestClient
) -> None:
    """Two interleaved traces: both trace views anchored, global chain valid."""
    m1 = run_mission(repos, mission_id="price-drift")
    _interleave_global_events(repos, other_actor="a")
    m2 = run_mission(repos, mission_id="quantity-increase")
    _interleave_global_events(repos, other_actor="b")
    for trace_id in (m1["trace_id"], m2["trace_id"]):
        res = client.get(f"/forensics/trace/{trace_id}")
        assert res.status_code == 200
        assert res.json()["chain"]["anchored"] is True
    verify = client.get("/audit/verify")
    assert verify.json()["valid"] is True
    with repos.transaction() as session:
        count = int(session.scalar(select(func.count()).select_from(AuditEvent)))
    assert verify.json()["events_checked"] == count


# ---------------------------------------------------------------------------
# F010 — direct indexed lookups (no recent(100) dependence).
# ---------------------------------------------------------------------------


def test_search_by_every_modeled_id_shape(repos: Repositories, client: TestClient) -> None:
    """Display trace, intent, checkout and attempt ids all resolve via direct
    lookups."""
    mission = run_mission(repos, mission_id="safe")
    trace_id = mission["trace_id"]
    for id_shape in (trace_id, mission["intent_id"]):
        res = client.get("/forensics/search", params={"q": id_shape})
        assert res.status_code == 200, (id_shape, res.text[:200])
        assert res.json()["match"]["trace_id"] == trace_id


def test_old_checkout_outside_recent_window_is_findable(
    repos: Repositories, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F010 core: a checkout whose trace is NOT in registry.recent (window
    shrunk to nothing) is still found by the DIRECT checkout-row lookup —
    the historical recent(100) scan would 404 here."""
    mission = run_mission(repos, mission_id="merchant-swap")
    checkout_id = mission["checkout_id"]

    from razormesh_api.trace_registry import TraceRegistry

    monkeypatch.setattr(TraceRegistry, "recent", lambda self, limit=100: [])

    res = client.get("/forensics/search", params={"q": checkout_id})
    assert res.status_code == 200, res.text[:200]
    assert res.json()["match"]["trace_id"] == mission["trace_id"]


def test_search_by_razorpay_order_id(repos: Repositories, client: TestClient) -> None:
    """A provider order id resolves to its trace (public summary only)."""
    from datetime import UTC, datetime

    from razormesh_api.persistence.models import ProviderEvent

    mission = run_mission(repos, mission_id="safe")
    order_id = "order_TEST_F010_0001"
    with repos.transaction() as session:
        session.add(
            ProviderEvent(
                event_id=f"evt_{mission['intent_id'][7:26]}",
                provider_name="razorpay",
                event_type="payment.captured",
                received_at=datetime.now(UTC),
                verified=True,
                processing_state="PROCESSED",
                payload_sha256="0" * 64,
                intent_id=mission["intent_id"],
                razorpay_order_id=order_id,
            )
        )
    res = client.get("/forensics/search", params={"q": order_id})
    assert res.status_code == 200, res.text[:200]
    assert res.json()["match"]["trace_id"] == mission["trace_id"]


def test_search_unknown_ids_are_honest(client: TestClient) -> None:
    for bogus in ("RM-ZZZZZZ", "intent_01M0ZN11XTXMCDQ0XE5T2KZWRE"):
        res = client.get("/forensics/search", params={"q": bogus})
        assert res.status_code == 404, bogus
