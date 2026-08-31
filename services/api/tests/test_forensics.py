"""Phase-5 (M079-M089) acceptance: Audit as Transaction Forensics.

Proves: smart search across id shapes; recent trace cards; forensic dossier
with timeline ordering; authorization-vs-current diff on a drifted checkout;
provider-contact card from audit evidence; strict validation (404s); no
secrets/private review data anywhere.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from razormesh_api.catalog import seed_catalog
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.merchant_sandbox import (
    MutationKind,
    apply_mutation,
)
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.repositories import Repositories


@pytest.fixture()
def forensics_client(settings):  # type: ignore[no-untyped-def]
    from conftest import wipe_business_tables
    from razormesh_api import api

    api.main.get_settings.cache_clear()
    app = api.main.app
    app.dependency_overrides[api.main.get_settings] = lambda: settings
    engine = create_engine(settings.database_url, future=True)
    repos = Repositories(create_session_factory(engine))
    wipe_business_tables(engine)
    seed_catalog(repos)
    from fastapi.testclient import TestClient as TC

    with TC(app) as c:
        yield c
    app.dependency_overrides.clear()
    wipe_business_tables(engine)


def test_smart_search_resolves_three_id_shapes(forensics_client: TestClient) -> None:
    items = forensics_client.get("/catalog/products", params={"limit": 100}).json()["items"]
    pid = next(p["id"] for p in items if p["price_minor"] < 500000)
    body = forensics_client.post(
        "/merchant-sandbox/checkout", json={"product_id": pid, "quantity": 1}
    ).json()
    intent_id, checkout_id = body["intent_id"], body["checkout_id"]

    # by display trace
    trace = forensics_client.get(f"/trace/by-intent/{intent_id}").json()["trace_id"]
    r1 = forensics_client.get("/forensics/search", params={"q": trace})
    assert r1.status_code == 200
    assert r1.json()["match"]["trace_id"] == trace

    # by intent id
    r2 = forensics_client.get("/forensics/search", params={"q": intent_id})
    assert r2.status_code == 200
    assert r2.json()["match"]["trace_id"] == trace

    # by checkout id
    r3 = forensics_client.get("/forensics/search", params={"q": checkout_id})
    assert r3.status_code == 200
    assert r3.json()["match"]["trace_id"] == trace


def test_search_rejects_unknown_and_malformed(forensics_client: TestClient) -> None:
    for bad in ("RM-ZZZZZZ", "intent_NOT_A_ULID", "'; DROP TABLE x; --"):
        assert forensics_client.get("/forensics/search", params={"q": bad}).status_code == 404, bad
    # too-short input is refused by validation (still a clean rejection).
    assert forensics_client.get("/forensics/search", params={"q": "x"}).status_code == 422


def test_recent_traces_are_discoverable_without_copying_ids(
    forensics_client: TestClient,
) -> None:
    items = forensics_client.get("/catalog/products", params={"limit": 100}).json()["items"]
    pid = next(p["id"] for p in items if p["price_minor"] < 500000)
    for _ in range(2):
        forensics_client.post("/merchant-sandbox/checkout", json={"product_id": pid, "quantity": 1})
    recent = forensics_client.get("/forensics/recent").json()
    assert recent["count"] >= 2
    for t in recent["traces"]:
        assert t["trace_id"].startswith("RM-")
        assert "state" in t and "provider_call_count" in t


def test_forensic_dossier_shows_drift_diff_and_provider_card(
    forensics_client: TestClient,
) -> None:
    from razormesh_api.settings import get_settings

    repos = Repositories(create_session_factory(create_engine(get_settings().database_url)))
    items = forensics_client.get("/catalog/products", params={"limit": 100}).json()["items"]
    pid = next(p["id"] for p in items if p["price_minor"] < 500000)
    body = forensics_client.post(
        "/merchant-sandbox/checkout", json={"product_id": pid, "quantity": 1}
    ).json()
    intent_id, checkout_id = body["intent_id"], body["checkout_id"]
    apply_mutation(
        repos,
        EvidenceLedger(repos),
        intent_id=intent_id,
        checkout_id=checkout_id,
        kind=MutationKind.PRICE_DRIFT,
    )

    trace = forensics_client.get(f"/trace/by-intent/{intent_id}").json()["trace_id"]
    res = forensics_client.get(f"/forensics/trace/{trace}")
    assert res.status_code == 200
    dossier = res.json()

    # Timeline: projected events, seq-ordered.
    seqs = [e["seq"] for e in dossier["events"]]
    assert seqs == sorted(seqs)

    # Diff highlights the drifted total (authorized vs current).
    fields = {d["field"] for d in dossier["diff"]}
    assert "total_minor" in fields
    row = next(d for d in dossier["diff"] if d["field"] == "total_minor")
    assert row["current"] == row["authorized"] + 50000

    # Provider card: audit-backed, no order for an unexecuted trace.
    assert dossier["provider"]["contacted"] is False
    assert dossier["provider"]["call_count"] == 0
    assert dossier["provider"]["order_id"] is None


def test_dossier_unknown_trace_is_404(forensics_client: TestClient) -> None:
    assert forensics_client.get("/forensics/trace/RM-ZZZZZZ").status_code == 404
    assert forensics_client.get("/forensics/trace/zzz-bad-id").status_code == 404


def test_no_secret_material_in_dossier(forensics_client: TestClient) -> None:
    recent = forensics_client.get("/forensics/recent").json()
    if recent["traces"]:
        trace = recent["traces"][0]["trace_id"]
        blob = str(forensics_client.get(f"/forensics/trace/{trace}").json())
        for banned in (
            "BEGIN PRIVATE KEY",
            "rzp_live_",
            "key_secret",
            "signature_hex",
            "premise",
        ):
            assert banned not in blob
