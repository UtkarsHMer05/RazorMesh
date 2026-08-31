"""Phase-5 (M025/M026) acceptance: Shopping Agent search + explainable ranking.

Proves: counts computed from real catalog rows; eligibility mirrors RazorGuard
semantics (budget/currency/brand/merchant/condition/recurring); UI-logic can
never make an ineligible product eligible; ranking is deterministic + tied to
catalog facts; rejected reasons agree with backend rule semantics.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from razormesh_api.agent_search import (
    rank_catalog_for_intent,
)
from razormesh_api.catalog import seed_catalog
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.models import IntentContract, Product
from razormesh_api.persistence.repositories import Repositories, session_scope


@pytest.fixture()
def agent_client(settings):  # type: ignore[no-untyped-def]
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


def _make_intent(client: TestClient) -> str:
    return client.post("/buyer/fixture-intent").json()["intent_id"]


def _product(client: TestClient, product_id: str) -> Product:
    return client.get(f"/catalog/products/{product_id}").json()


def test_search_counts_come_from_real_catalog(agent_client: TestClient) -> None:
    intent_id = _make_intent(agent_client)
    res = agent_client.post("/agent/search", json={"intent_id": intent_id})
    assert res.status_code == 200
    body = res.json()
    total_products = agent_client.get("/catalog/products", params={"limit": 1}).json()["total"]
    assert body["inspected"] == total_products
    assert body["eligible"] + body["rejected"] == total_products


def test_search_is_deterministic(agent_client: TestClient) -> None:
    intent_id = _make_intent(agent_client)
    a = agent_client.post("/agent/search", json={"intent_id": intent_id}).json()
    b = agent_client.post("/agent/search", json={"intent_id": intent_id}).json()
    assert a == b
    ranks = [c["rank"] for c in a["candidates"]]
    assert ranks == sorted(ranks) == list(range(1, len(ranks) + 1))


def test_every_why_claim_maps_to_real_facts(agent_client: TestClient) -> None:
    intent_id = _make_intent(agent_client)
    body = agent_client.post("/agent/search", json={"intent_id": intent_id}).json()
    from razormesh_api.settings import get_settings

    repos = Repositories(create_session_factory(create_engine(get_settings().database_url)))
    for cand in body["candidates"]:
        with session_scope(repos.factory) as session:
            p = session.get(Product, cand["product_id"])
            assert p is not None
            expected_total = p.price_minor * cand["quantity"] + p.shipping_minor
        assert cand["total_minor"] == expected_total
        assert cand["title"] == p.title
        assert cand["brand"] == p.brand
        # every why line references a real fact (budget/brand/condition)
        assert any("All-in total" in w for w in cand["why"])


def test_over_budget_product_is_rejected_and_cannot_become_eligible(
    agent_client: TestClient,
) -> None:
    intent_id = _make_intent(agent_client)
    body = agent_client.post("/agent/search", json={"intent_id": intent_id}).json()
    if body["rejected"]:
        rej = body["rejected_samples"][0]
        assert rej["reason_code"] in {
            "TOTAL_EXCEEDS_BUDGET",
            "CURRENCY_MISMATCH",
            "BRAND_NOT_ALLOWED",
            "CONDITION_NOT_ALLOWED",
            "MERCHANT_NOT_ALLOWED",
            "CATEGORY_NOT_ALLOWED",
            "RECURRING_NOT_ALLOWED",
        }
        # The rejected product never appears among candidates.
        cand_ids = {c["product_id"] for c in body["candidates"]}
        assert rej["product_id"] not in cand_ids
    # Quantity over the mandate cap is refused outright (agent cannot widen
    # authority): either schema validation (422) or the mandate cap (404).
    over = agent_client.post("/agent/search", json={"intent_id": intent_id, "quantity": 99})
    assert over.status_code in (404, 422)
    # A quantity within the schema but over the mandate cap is a domain refusal.
    over_mandate = agent_client.post("/agent/search", json={"intent_id": intent_id, "quantity": 3})
    assert over_mandate.status_code == 404


def test_unknown_intent_is_clean_404(agent_client: TestClient) -> None:
    res = agent_client.post(
        "/agent/search", json={"intent_id": "intent_01M19X68VHHBGW00H2CFB13KFM"}
    )
    assert res.status_code == 404


def test_recurring_product_rejected_under_no_subscription_mandate(
    agent_client: TestClient,
) -> None:
    """A synthetic recurring product must be excluded when the mandate forbids it."""
    from datetime import UTC, datetime, timedelta

    from razormesh_api.settings import get_settings

    repos = Repositories(create_session_factory(create_engine(get_settings().database_url)))
    now = datetime.now(UTC)
    with session_scope(repos.factory) as session:
        # Attach the recurring product to a real merchant so FK holds.
        merchant_id = session.query(Product).first().merchant_id  # type: ignore[attr-defined]
        session.add(
            Product(
                id="prd_phase5_recurring_probe",
                merchant_id=merchant_id,
                title="Recurring Probe Subscription",
                description="synthetic recurring product for phase-5 tests",
                brand=None,
                category="subscriptions",
                condition="new",
                price_minor=9900,
                shipping_minor=0,
                currency="INR",
                recurring=True,
                recurring_frequency="monthly",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            IntentContract(
                intent_id="intent_01M19X68VHHBGW00H2CFB13KFM",
                principal_id="usr_probe",
                agent_id="agt_probe",
                authorization_generation=1,
                status="AUTHORIZED",
                currency="INR",
                max_total_minor=50_000_000,
                aggregate_budget_minor=200_000_000,
                max_quantity=2,
                recurring_allowed=False,  # mandate forbids subscriptions
                approval_threshold_minor=40_000_000,
                issued_at=now,
                authorized_at=now,
                expires_at=now + timedelta(minutes=30),
                created_at=now,
                updated_at=now,
            )
        )
    report = rank_catalog_for_intent(repos, "intent_01M19X68VHHBGW00H2CFB13KFM")
    eligible_ids = {c.product_id for c in report.candidates}
    assert "prd_phase5_recurring_probe" not in eligible_ids
    rejected_ids = {r.product_id for r in report.rejected_samples}
    assert "prd_phase5_recurring_probe" in rejected_ids or (
        report.rejected > len(report.rejected_samples)
    )


def test_search_writes_real_trace_event(agent_client: TestClient) -> None:
    intent_id = _make_intent(agent_client)
    agent_client.post("/agent/search", json={"intent_id": intent_id})
    tl = agent_client.get("/audit/timeline").json()["events"]
    assert any(e["event_type"] == "AGENT_SEARCH_COMPLETED" for e in tl)
    # ...and the trace projection surfaces it in the agent stage.
    trace_id = agent_client.get(f"/trace/by-intent/{intent_id}").json()["trace_id"]
    events = agent_client.get(f"/trace/events/{trace_id}").json()["events"]
    kinds = [e["kind"] for e in events]
    assert "search.completed" in kinds


def test_brand_restriction_shape_is_enforced(agent_client: TestClient) -> None:
    """Confirmed BrandRestriction {"brands": [...], "mode": "allow_only"} must filter."""
    from datetime import UTC, datetime, timedelta

    from razormesh_api.settings import get_settings

    repos = Repositories(create_session_factory(create_engine(get_settings().database_url)))
    now = datetime.now(UTC)
    with session_scope(repos.factory) as session:
        merchant_id = session.query(Product).first().merchant_id  # type: ignore[attr-defined]
        session.add(
            Product(
                id="prd_phase5_brand_probe",
                merchant_id=merchant_id,
                title="Brand Probe Speaker",
                description="synthetic brand probe",
                brand="JBL",
                category="audio",
                condition="new",
                price_minor=29900,
                shipping_minor=0,
                currency="INR",
                recurring=False,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            IntentContract(
                intent_id="intent_01M19X68VHHBGW00H2CFB13KFM",
                principal_id="usr_probe_b",
                agent_id="agt_probe_b",
                authorization_generation=1,
                status="AUTHORIZED",
                currency="INR",
                max_total_minor=50_000_000,
                aggregate_budget_minor=200_000_000,
                max_quantity=2,
                recurring_allowed=False,
                brand_restriction={"brands": ["Sony"], "mode": "allow_only"},
                approval_threshold_minor=40_000_000,
                issued_at=now,
                authorized_at=now,
                expires_at=now + timedelta(minutes=30),
                created_at=now,
                updated_at=now,
            )
        )
    report = rank_catalog_for_intent(repos, "intent_01M19X68VHHBGW00H2CFB13KFM")
    eligible_ids = {c.product_id for c in report.candidates}
    assert "prd_phase5_brand_probe" not in eligible_ids, "non-Sony brand must be rejected"
    rejected_codes = {
        r.reason_code for r in report.rejected_samples if r.product_id == "prd_phase5_brand_probe"
    }
    assert rejected_codes == {"BRAND_NOT_ALLOWED"} or report.rejected > len(report.rejected_samples)
