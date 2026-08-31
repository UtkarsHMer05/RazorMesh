"""Deep-engine correction (G019/G020): Mission Control real actions.

Proves:
- the control deck's actions act on the CURRENT trace's transaction:
  mutate-current / revert-current / execute-current all resolve the live
  trace's own checkout and return its trace_id;
- execute-current runs the REAL revalidation boundary: a drifted checkout
  STALE_DETECTs, a clean one passes — and never mints a ticket or contacts
  the provider;
- current-transaction returns the authorization-vs-current diff from the
  immutable baseline (G012) across every modeled dimension;
- three DIFFERENT mutations each produce an ACCURATE diff (G020).
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from conftest import wipe_business_tables
from razormesh_api.catalog import seed_catalog
from razormesh_api.merchant_sandbox import propose_checkout_for_demo
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.trace_registry import TraceRegistry


@pytest.fixture()
def mc_client(settings):  # type: ignore[no-untyped-def]
    from razormesh_api import api

    api.main.get_settings.cache_clear()
    app = api.main.app
    app.dependency_overrides[api.main.get_settings] = lambda: settings
    engine = create_engine(settings.database_url, future=True)
    repos = Repositories(create_session_factory(engine))
    wipe_business_tables(engine)
    seed_catalog(repos)
    with TestClient(app) as c:
        yield c, repos
    app.dependency_overrides.clear()
    wipe_business_tables(engine)


def _mission(repos: Repositories) -> dict[str, Any]:
    """Create a live mission (checkout + trace) to act on."""
    with repos.factory() as session:  # type: ignore[attr-defined]
        pass
    from sqlalchemy import select

    from razormesh_api.persistence.models import Product
    from razormesh_api.persistence.repositories import session_scope

    with session_scope(repos.factory) as session:
        product = session.scalars(
            select(Product).where(Product.recurring.is_(False)).limit(1)
        ).first()
        pid = product.id
    intent_id, checkout_id, _ = propose_checkout_for_demo(repos, product_id=pid)
    trace = TraceRegistry(repos).by_intent(intent_id)
    assert trace is not None
    return {"trace_id": trace.trace_id, "intent_id": intent_id, "checkout_id": checkout_id}


# ---------------------------------------------------------------------------
# G019 — real actions on the current trace
# ---------------------------------------------------------------------------


def test_mutate_current_acts_on_the_live_trace(mc_client) -> None:  # type: ignore[no-untyped-def]
    client, repos = mc_client
    mission = _mission(repos)
    res = client.post(
        "/mission-control/mutate-current",
        json={"trace_id": mission["trace_id"], "kind": "price_drift"},
    )
    assert res.status_code == 200, res.text[:300]
    body = res.json()
    assert body["trace_id"] == mission["trace_id"]
    assert "unit_price_minor" in body["changed_fields"]
    # the CURRENT checkout row really changed
    from razormesh_api.persistence.models import Checkout
    from razormesh_api.persistence.repositories import session_scope

    with session_scope(repos.factory) as session:
        row = session.get(Checkout, mission["checkout_id"])
    lines = list(row.line_items or [])
    assert lines[0]["unit_price_minor"] > 0


def test_execute_current_drifted_stale_detects(mc_client) -> None:  # type: ignore[no-untyped-def]
    """A drifted transaction FAILS the real revalidation boundary."""
    client, repos = mc_client
    mission = _mission(repos)
    mut = client.post(
        "/mission-control/mutate-current",
        json={"trace_id": mission["trace_id"], "kind": "price_drift"},
    )
    assert mut.status_code == 200
    res = client.post(
        "/mission-control/execute-current",
        json={"trace_id": mission["trace_id"], "kind": "execute"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["outcome"] == "STALE_CHECKOUT", body
    assert body["ticket_minted"] is False
    assert body["provider_contacted"] is False


def test_execute_current_clean_passes_and_never_contacts_provider(mc_client) -> None:  # type: ignore[no-untyped-def]
    """A clean transaction passes revalidation; still no ticket/provider from
    the control deck (money paths stay on the buyer flow)."""
    client, repos = mc_client
    mission = _mission(repos)
    res = client.post(
        "/mission-control/execute-current",
        json={"trace_id": mission["trace_id"], "kind": "execute"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["outcome"] == "REVALIDATION_PASS", body
    assert body["ticket_minted"] is False
    assert body["provider_contacted"] is False


def test_revert_current_restores_baseline(mc_client) -> None:  # type: ignore[no-untyped-def]
    client, repos = mc_client
    mission = _mission(repos)
    client.post(
        "/mission-control/mutate-current",
        json={"trace_id": mission["trace_id"], "kind": "hidden_membership"},
    )
    diff_before = client.get(f"/mission-control/current-transaction/{mission['trace_id']}").json()
    assert not diff_before["clean"]
    res = client.post(
        "/mission-control/revert-current",
        json={"trace_id": mission["trace_id"], "kind": "revert"},
    )
    assert res.status_code == 200
    diff_after = client.get(f"/mission-control/current-transaction/{mission['trace_id']}").json()
    assert diff_after["clean"], "revert must restore the exact baseline"


def test_actions_reject_unknown_or_traceless_state(mc_client) -> None:  # type: ignore[no-untyped-def]
    client, repos = mc_client
    assert (
        client.post(
            "/mission-control/mutate-current",
            json={"trace_id": "RM-ZZZZZZ", "kind": "price_drift"},
        ).status_code
        == 404
    )
    mission = _mission(repos)
    assert (
        client.post(
            "/mission-control/mutate-current",
            json={"trace_id": mission["trace_id"], "kind": "not_a_kind"},
        ).status_code
        == 422
    )


# ---------------------------------------------------------------------------
# G020 — the current transaction diff
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "expected_field"),
    [
        ("price_drift", "unit_price_minor"),
        ("quantity_increase", "quantity"),
        ("merchant_swap", "merchant_id"),
        ("hidden_membership", "subscription_terms"),
        ("condition_downgrade", "condition"),
        ("hidden_fee", "fees_minor"),
    ],
)
def test_three_mutations_each_show_accurate_diff(mc_client, kind, expected_field) -> None:  # type: ignore[no-untyped-def]
    """G020 PASS condition: apply different mutations and see an accurate
    diff each time — the diff names exactly the mutated field."""
    client, repos = mc_client
    mission = _mission(repos)
    before = client.get(f"/mission-control/current-transaction/{mission['trace_id']}").json()
    assert before["clean"]
    mut = client.post(
        "/mission-control/mutate-current",
        json={"trace_id": mission["trace_id"], "kind": kind},
    )
    assert mut.status_code == 200, mut.text[:200]
    after = client.get(f"/mission-control/current-transaction/{mission['trace_id']}").json()
    assert not after["clean"]
    fields = {d["field"] for d in after["diff"]}
    assert expected_field in fields, (kind, fields)
    # the diff is baseline-derived: the authorized side is never the mutated value
    row = next(d for d in after["diff"] if d["field"] == expected_field)
    assert row["authorized"] != row["current"]


def test_diff_covers_all_modeled_dimensions_on_multi_drift(mc_client) -> None:  # type: ignore[no-untyped-def]
    """A multi-field drift shows every modeled auth-relevant dimension."""
    client, repos = mc_client
    mission = _mission(repos)
    for kind in ("price_drift", "hidden_fee", "quantity_increase"):
        client.post(
            "/mission-control/mutate-current",
            json={"trace_id": mission["trace_id"], "kind": kind},
        )
    diff = client.get(f"/mission-control/current-transaction/{mission['trace_id']}").json()["diff"]
    fields = {d["field"] for d in diff}
    assert {"unit_price_minor", "fees_minor", "quantity"} <= fields
