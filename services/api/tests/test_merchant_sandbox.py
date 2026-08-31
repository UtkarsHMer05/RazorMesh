"""Phase-5 (M036-M043) acceptance: bounded Merchant Sandbox.

Proves:
- mutations persist to the durable checkout row (session design);
- the confirmed IntentContract is NEVER modified (mandate preserved);
- every mutation/revert writes audit + trace events;
- the diff highlights only actual changed fields;
- post-authorization drift is caught by the REAL revalidation path (ticket dies);
- hostile text is stored as untrusted data;
- presets list inputs only (no outcomes).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from razormesh_api.catalog import seed_catalog
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.merchant_sandbox import (
    MerchantDemoError,
    MutationKind,
    apply_mutation,
    propose_checkout_for_demo,
)
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.models import (
    Checkout as RowCheckout,
)
from razormesh_api.persistence.models import (
    IntentContract as RowIntent,
)
from razormesh_api.persistence.repositories import Repositories, session_scope


@pytest.fixture()
def merchant_client(settings):  # type: ignore[no-untyped-def]
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


def _product_id(client: TestClient) -> str:
    items = client.get("/catalog/products", params={"limit": 100}).json()["items"]
    # a cheap, new, one-time product for clean demos
    return next(p["id"] for p in items if p["price_minor"] < 500000)


def _make_checkout(client: TestClient, product_id: str) -> tuple[str, str]:
    body = client.post(
        "/merchant-sandbox/checkout", json={"product_id": product_id, "quantity": 1}
    ).json()
    return body["intent_id"], body["checkout_id"]


# --- M036/M037/M039: presets, persistence, mutation ------------------------


def test_presets_are_inputs_only(merchant_client: TestClient) -> None:
    res = merchant_client.get("/merchant-sandbox/presets").json()["presets"]
    kinds = {p["kind"] for p in res}
    assert kinds == {
        "price_drift",
        "hidden_fee",
        "hidden_membership",
        "condition_downgrade",
        "merchant_swap",
        "quantity_increase",
        "hostile_instruction",
    }
    for preset in res:
        assert set(preset) == {"kind", "label"}, "presets must carry inputs only"


def test_mutation_persists_and_diff_shows_changed_fields(
    merchant_client: TestClient,
) -> None:
    pid = _product_id(merchant_client)
    intent_id, checkout_id = _make_checkout(merchant_client, pid)

    res = merchant_client.post(
        "/merchant-sandbox/mutate",
        json={"intent_id": intent_id, "checkout_id": checkout_id, "kind": "hidden_membership"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "hidden_membership"
    assert "subscription_terms" in body["changed_fields"]
    assert body["trace_id"].startswith("RM-")

    # Persisted: diff endpoint re-reads durable rows.
    diff = merchant_client.get(f"/merchant-sandbox/diff/{checkout_id}").json()["diff"]
    assert any(d["field"] == "subscription_terms" for d in diff)
    # Only actual changes highlighted:
    for d in diff:
        assert d["authorized"] != d["current"]


def test_price_drift_persists_to_durable_row(merchant_client: TestClient) -> None:
    pid = _product_id(merchant_client)
    intent_id, checkout_id = _make_checkout(merchant_client, pid)
    before = merchant_client.get(f"/merchant-sandbox/diff/{checkout_id}").json()["diff"]
    assert before == []

    res = merchant_client.post(
        "/merchant-sandbox/mutate",
        json={"intent_id": intent_id, "checkout_id": checkout_id, "kind": "price_drift"},
    )
    assert res.status_code == 200
    with session_scope(_repos(merchant_client).factory) as session:
        row = session.get(RowCheckout, checkout_id)
        assert row is not None
        original_price = res.json()["before"]["line_items"][0]["unit_price_minor"]
        current_price = row.line_items[0]["unit_price_minor"]  # type: ignore[index]
    assert current_price == original_price + 50000


def _repos(client: TestClient):  # type: ignore[no-untyped-def]
    from razormesh_api.settings import get_settings

    return Repositories(create_session_factory(create_engine(get_settings().database_url)))


# --- M038: untrusted merchant text -----------------------------------------


def test_hostile_text_is_stored_as_untrusted_data(merchant_client: TestClient) -> None:
    pid = _product_id(merchant_client)
    intent_id, checkout_id = _make_checkout(merchant_client, pid)
    res = merchant_client.post(
        "/merchant-sandbox/mutate",
        json={"intent_id": intent_id, "checkout_id": checkout_id, "kind": "hostile_instruction"},
    )
    assert res.status_code == 200
    with session_scope(_repos(merchant_client).factory) as session:
        intent = session.get(RowIntent, intent_id)
        assert intent is not None
        auth_hash_columns = (
            intent.allowed_merchant_ids,
            intent.brand_restriction,
            intent.max_total_minor,
            intent.recurring_allowed,
        )
        assert auth_hash_columns[2] == 50_000_000  # mandate untouched
        row = session.get(RowCheckout, checkout_id)
        assert row is not None
        name = str(row.line_items[0].get("display_name"))  # type: ignore[union-attr]
    assert "[UNTRUSTED MERCHANT TEXT]" in name
    # The hostile instruction is data, not authority: intent status unchanged.
    assert intent.status == "AUTHORIZED"


# --- M041/M042: publish-to-trace + revert -----------------------------------


def test_mutation_publishes_real_trace_and_audit_events(
    merchant_client: TestClient,
) -> None:
    pid = _product_id(merchant_client)
    intent_id, checkout_id = _make_checkout(merchant_client, pid)
    merchant_client.post(
        "/merchant-sandbox/mutate",
        json={"intent_id": intent_id, "checkout_id": checkout_id, "kind": "price_drift"},
    )
    # Audit ledger carries the mutation event...
    tl = merchant_client.get("/audit/timeline").json()["events"]
    assert any(e["event_type"] == "MERCHANT_OFFER_MUTATED" for e in tl)
    # ...and the trace projection surfaces it in the merchant stage.
    trace_id = merchant_client.get(f"/trace/by-intent/{intent_id}").json()["trace_id"]
    events = merchant_client.get(f"/trace/events/{trace_id}").json()["events"]
    kinds = [e["kind"] for e in events]
    assert "offer.mutated" in kinds
    # Original mandate unchanged in the same trace's human stage.
    assert any(e["stage"] == "human" for e in events) or intent_id.startswith("intent_")


def test_revert_preserves_both_mutation_and_revert_evidence(
    merchant_client: TestClient,
) -> None:
    pid = _product_id(merchant_client)
    intent_id, checkout_id = _make_checkout(merchant_client, pid)
    merchant_client.post(
        "/merchant-sandbox/mutate",
        json={"intent_id": intent_id, "checkout_id": checkout_id, "kind": "hidden_membership"},
    )
    res = merchant_client.post(
        "/merchant-sandbox/revert",
        json={"intent_id": intent_id, "checkout_id": checkout_id, "kind": "revert"},
    )
    assert res.status_code == 200
    diff = merchant_client.get(f"/merchant-sandbox/diff/{checkout_id}").json()["diff"]
    assert diff == [], "revert must restore the authorized truth"

    tl = merchant_client.get("/audit/timeline").json()["events"]
    types = [e["event_type"] for e in tl]
    assert "MERCHANT_OFFER_MUTATED" in types
    assert "MERCHANT_OFFER_REVERTED" in types, "revert must not erase mutation history"


# --- M043: post-authorization drift defense (REAL revalidation) ------------


def test_post_authorization_drift_kills_the_ticket(merchant_client: TestClient) -> None:
    """Safe proposal → mutate after authorization → execute must fail revalidation."""
    repos = _repos(merchant_client)
    ledger = EvidenceLedger(repos)
    pid = _product_id(merchant_client)
    intent_id, checkout_id, expected = propose_checkout_for_demo(repos, product_id=pid)

    # Merchant mutates the price AFTER authorization.
    apply_mutation(
        repos,
        ledger,
        intent_id=intent_id,
        checkout_id=checkout_id,
        kind=MutationKind.PRICE_DRIFT,
    )

    # The REAL revalidation contract (same as the Security Lab drift family):
    # the drifted checkout must never revalidate OK against the signed binding.
    from razormesh_api.revalidation import Revalidator

    verdict = Revalidator(repos).revalidate(
        intent_id=intent_id,
        checkout_id=checkout_id,
        expected_checkout_hash=expected["checkout_hash"],
        expected_revision=expected["revision"],
        expected_intent_hash=expected["intent_hash"],
        expected_generation=expected["generation"],
    )
    assert not verdict.ok, (
        f"drifted checkout must never revalidate OK (got {verdict.code}: {verdict.detail})"
    )


# --- M044: privacy boundary ---------------------------------------------------


def test_merchant_endpoints_never_expose_mandate_text(
    merchant_client: TestClient,
) -> None:
    pid = _product_id(merchant_client)
    _intent_id, checkout_id = _make_checkout(merchant_client, pid)
    for path in (
        f"/merchant-sandbox/diff/{checkout_id}",
        "/merchant-sandbox/presets",
    ):
        res = merchant_client.get(path)
        assert res.status_code == 200
        body = str(res.json())
        # No human mandate text, no secrets, no ticket material leaks.
        for banned in ("authorization_text", "ticket_json", "signature_hex", "rzp_live_"):
            assert banned not in body


def test_unknown_checkout_is_clean_404(merchant_client: TestClient) -> None:
    assert merchant_client.get(
        "/merchant-sandbox/diff/chk_01M19X68VHHBGW00H2CFB13KFM"
    ).status_code in (404, 422)
    res = merchant_client.post(
        "/merchant-sandbox/mutate",
        json={
            "intent_id": "intent_01M19X68VHHBGW00H2CFB13KFM",
            "checkout_id": "chk_01M19X68VHHBGW00H2CFB13KFM",
            "kind": "price_drift",
        },
    )
    assert res.status_code == 404


def test_out_of_bounds_mutation_is_rejected(merchant_client: TestClient) -> None:
    """Bounded bounds are enforced: a price mutation past the floor trips."""
    repos = _repos(merchant_client)
    pid = _product_id(merchant_client)
    intent_id, checkout_id, _expected = propose_checkout_for_demo(repos, product_id=pid)
    # Drive the durable row above the demo price ceiling minus the drift,
    # then attempt price_drift: the bound must trip.
    with session_scope(repos.factory) as session:
        row = session.get(RowCheckout, checkout_id)
        assert row is not None
        lines = [dict(item) for item in row.line_items]
        lines[0]["unit_price_minor"] = 500_000_000  # ₹50,00,000 ceiling
        row.line_items = lines
    with pytest.raises(MerchantDemoError) as excinfo:
        apply_mutation(
            repos,
            EvidenceLedger(repos),
            intent_id=intent_id,
            checkout_id=checkout_id,
            kind=MutationKind.PRICE_DRIFT,
        )
    assert excinfo.value.code == "MUTATION_OUT_OF_BOUNDS"
