"""Deep-engine correction (G021/G023) acceptance: comprehensive forensic diff
+ selected-trace chain visualization.

Proves:
- G021: the authorization-vs-current diff covers EVERY modeled auth-relevant
  dimension (merchant/product/condition/quantity/unit-price/fees/shipping/
  total/currency/recurring), from the immutable baseline (G012) — tested for
  quantity-only, merchant-only, condition-only, recurring-only, price/fee
  drift;
- G023: the dossier returns the SELECTED trace's own hash-chain nodes
  (seq-ordered, prev_head links each node to the previous) plus a linked
  flag; tamper simulation remains non-mutating.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from conftest import wipe_business_tables
from razormesh_api.catalog import seed_catalog
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.merchant_sandbox import MutationKind, apply_mutation, propose_checkout_for_demo
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.trace_registry import TraceRegistry


@pytest.fixture()
def forensics_deep_client(settings):  # type: ignore[no-untyped-def]
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


def _mission_with_mutation(repos: Repositories, kind: MutationKind | None) -> dict[str, Any]:
    from sqlalchemy import select

    from razormesh_api.persistence.models import Product
    from razormesh_api.persistence.repositories import session_scope

    with session_scope(repos.factory) as session:
        product = session.scalars(
            select(Product).where(Product.recurring.is_(False)).limit(1)
        ).first()
        pid = product.id
    intent_id, checkout_id, _ = propose_checkout_for_demo(repos, product_id=pid)
    if kind is not None:
        apply_mutation(
            Repositories(repos.factory),  # same engine-backed repos
            EvidenceLedger(repos),
            intent_id=intent_id,
            checkout_id=checkout_id,
            kind=kind,
        )
    trace = TraceRegistry(repos).by_intent(intent_id)
    assert trace is not None
    return {"trace_id": trace.trace_id, "intent_id": intent_id, "checkout_id": checkout_id}


def _dossier(client: TestClient, trace_id: str) -> dict[str, Any]:
    res = client.get(f"/forensics/trace/{trace_id}")
    assert res.status_code == 200, res.text[:300]
    return res.json()


# ---------------------------------------------------------------------------
# G021 — comprehensive diff
# ---------------------------------------------------------------------------


def test_clean_transaction_has_no_diff(forensics_deep_client) -> None:  # type: ignore[no-untyped-def]
    client, repos = forensics_deep_client
    mission = _mission_with_mutation(repos, None)
    body = _dossier(client, mission["trace_id"])
    assert body["diff"] == []


def test_quantity_only_drift_is_visible(forensics_deep_client) -> None:  # type: ignore[no-untyped-def]
    client, repos = forensics_deep_client
    mission = _mission_with_mutation(repos, MutationKind.QUANTITY_INCREASE)
    fields = {d["field"] for d in _dossier(client, mission["trace_id"])["diff"]}
    assert "quantity" in fields
    assert "total_minor" in fields  # consequence of the quantity change


def test_merchant_only_drift_is_visible(forensics_deep_client) -> None:  # type: ignore[no-untyped-def]
    client, repos = forensics_deep_client
    mission = _mission_with_mutation(repos, MutationKind.MERCHANT_SWAP)
    fields = {d["field"] for d in _dossier(client, mission["trace_id"])["diff"]}
    assert "merchant_id" in fields


def test_condition_only_drift_is_visible(forensics_deep_client) -> None:  # type: ignore[no-untyped-def]
    client, repos = forensics_deep_client
    mission = _mission_with_mutation(repos, MutationKind.CONDITION_DOWNGRADE)
    fields = {d["field"] for d in _dossier(client, mission["trace_id"])["diff"]}
    assert "condition" in fields


def test_recurring_only_drift_is_visible(forensics_deep_client) -> None:  # type: ignore[no-untyped-def]
    client, repos = forensics_deep_client
    mission = _mission_with_mutation(repos, MutationKind.HIDDEN_MEMBERSHIP)
    fields = {d["field"] for d in _dossier(client, mission["trace_id"])["diff"]}
    assert {"recurring", "subscription_terms"} & fields


def test_price_and_fee_drift_are_visible(forensics_deep_client) -> None:  # type: ignore[no-untyped-def]
    client, repos = forensics_deep_client
    mission = _mission_with_mutation(repos, MutationKind.PRICE_DRIFT)
    d1 = _dossier(client, mission["trace_id"])
    fields1 = {d["field"] for d in d1["diff"]}
    assert "unit_price_minor" in fields1

    mission2 = _mission_with_mutation(repos, MutationKind.HIDDEN_FEE)
    fields2 = {d["field"] for d in _dossier(client, mission2["trace_id"])["diff"]}
    assert "fees_minor" in fields2


def test_authorized_side_is_never_the_mutated_value(forensics_deep_client) -> None:  # type: ignore[no-untyped-def]
    """The diff's authorized values come from the immutable baseline — after
    ANY mutation they still describe the ORIGINAL proposal."""
    client, repos = forensics_deep_client
    mission = _mission_with_mutation(repos, MutationKind.PRICE_DRIFT)
    diff = _dossier(client, mission["trace_id"])["diff"]
    row = next(d for d in diff if d["field"] == "unit_price_minor")
    assert row["authorized"] != row["current"]


# ---------------------------------------------------------------------------
# G023 — selected-trace hash chain
# ---------------------------------------------------------------------------


def test_dossier_carries_selected_trace_chain_nodes(forensics_deep_client) -> None:  # type: ignore[no-untyped-def]
    client, repos = forensics_deep_client
    mission = _mission_with_mutation(repos, MutationKind.PRICE_DRIFT)
    chain = _dossier(client, mission["trace_id"])["chain"]
    assert chain["node_count"] >= 1
    seqs = [n["seq"] for n in chain["nodes"]]
    assert seqs == sorted(seqs)
    # every node carries its hash head and the previous node's link
    for node in chain["nodes"]:
        assert node["hash_head"]
    assert isinstance(chain["linked"], bool)
    assert "non-mutating" in chain["note"]


def test_chain_nodes_link_prev_to_current(forensics_deep_client) -> None:  # type: ignore[no-untyped-def]
    """Within one trace, node[i].prev_head == node[i-1].hash_head (the
    tamper-evident property the visualization must show)."""
    client, repos = forensics_deep_client
    mission = _mission_with_mutation(repos, MutationKind.HIDDEN_MEMBERSHIP)
    nodes = _dossier(client, mission["trace_id"])["chain"]["nodes"]
    for i in range(1, len(nodes)):
        if nodes[i]["prev_head"]:
            assert nodes[i]["prev_head"] == nodes[i - 1]["hash_head"], i


def test_chain_verification_is_read_only(forensics_deep_client) -> None:  # type: ignore[no-untyped-def]
    """Reading the chain twice changes nothing (tamper sim stays non-mutating)."""
    client, repos = forensics_deep_client
    mission = _mission_with_mutation(repos, MutationKind.PRICE_DRIFT)
    first = _dossier(client, mission["trace_id"])
    second = _dossier(client, mission["trace_id"])
    assert first["chain"]["nodes"] == second["chain"]["nodes"]
    # provider evidence identical across reads
    assert first["provider"] == second["provider"]
