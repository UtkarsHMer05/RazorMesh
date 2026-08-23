"""M39 acceptance: live revalidation — relevant drift blocks, cosmetics don't."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text

from razormesh_api.catalog import seed_catalog
from razormesh_api.checkout_service import (
    CheckoutService,
    ProposedItem,
)
from razormesh_api.decider import Decision, DecisionEngine
from razormesh_api.domain.ids import IntentId, new_ulid
from razormesh_api.keys import DevSigningKeys
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.persistence import models  # noqa: F401
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.models import (
    IntentContract as RowIntent,
)
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.revalidation import Revalidator
from razormesh_api.rules.catalog_rules import CATALOG_RULES
from razormesh_api.rules.money_rules import MONEY_RULES
from razormesh_api.rules.policy_rules import POLICY_RULES


def _engine():
    from razormesh_api.settings import get_settings

    return create_engine(get_settings().database_url, future=True)


@pytest.fixture()
def env(tmp_path):  # type: ignore[no-untyped-def]
    from conftest import wipe_business_tables

    engine = _engine()
    repos = Repositories(create_session_factory(engine))
    wipe_business_tables(engine)
    seed_catalog(repos)
    keys = DevSigningKeys(
        private_path=str(tmp_path / "p.pem"), public_path=str(tmp_path / "pub.pem")
    ).ensure()
    ledger = EvidenceLedger(repos)
    rules = DecisionEngine([*MONEY_RULES, *CATALOG_RULES, *POLICY_RULES])
    svc = CheckoutService(repos=repos, ledger=ledger, engine=rules, keys=keys)

    # one permissive intent row
    iid = IntentId.generate()
    now = datetime.now(UTC)
    with repos.transaction() as s:
        s.merge(
            RowIntent(
                intent_id=str(iid),
                principal_id=f"usr_{new_ulid()}",
                agent_id=f"agt_{new_ulid()}",
                authorization_generation=1,
                status="AUTHORIZED",
                currency="INR",
                recurring_allowed=False,
                max_total_minor=10_000_000,
                aggregate_budget_minor=50_000_000,
                max_quantity=2,
                approval_threshold_minor=8_000_000,
                issued_at=now,
                authorized_at=now,
                expires_at=now + timedelta(minutes=30),
                created_at=now,
                updated_at=now,
            )
        )
    yield svc, repos, engine, iid
    wipe_business_tables(engine)


def _propose_and_authorize(svc, repos, iid):  # type: ignore[no-untyped-def]
    product = min(repos.products.list(limit=100), key=lambda p: p.price_minor)
    proposal = svc.propose(intent_id=iid, items=[ProposedItem(product.id)])
    result = svc.authorize(intent_id=iid, proposal=proposal)
    assert result.outcome.decision is Decision.ALLOW
    return proposal


def test_fresh_decision_passes_revalidation(env) -> None:  # type: ignore[no-untyped-def]
    svc, repos, _engine, iid = env
    proposal = _propose_and_authorize(svc, repos, iid)
    verdict = Revalidator(repos).revalidate(
        intent_id=str(iid),
        checkout_id=str(proposal.envelope.checkout_id),
        expected_checkout_hash=proposal.checkout_hash,
        expected_revision=1,
        expected_intent_hash=proposal.intent_hash,
        expected_generation=1,
    )
    assert verdict.ok, verdict.detail


def test_relevant_drift_invalidates_stale_ticket(env) -> None:  # type: ignore[no-untyped-def]
    """Server-side quantity change between decision and execution."""
    svc, repos, engine, iid = env
    proposal = _propose_and_authorize(svc, repos, iid)
    cid = str(proposal.envelope.checkout_id)

    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE checkouts SET line_items = CAST(:li AS jsonb) "
                "WHERE checkout_id = :cid"
            ).bindparams(
                li='[{"product_id": "prd_01ARZ3NDEKTSV4RRFFQ69G5FAV", "quantity": 9, '
                '"unit_price_minor": 100000, "currency": "INR", "condition": "new"}]',
                cid=cid,
            )
        )

    verdict = Revalidator(repos).revalidate(
        intent_id=str(iid),
        checkout_id=cid,
        expected_checkout_hash=proposal.checkout_hash,
        expected_revision=1,
        expected_intent_hash=proposal.intent_hash,
        expected_generation=1,
    )
    assert not verdict.ok
    assert verdict.code == "STALE_CHECKOUT"


def test_presentation_change_does_not_invalidate(env) -> None:  # type: ignore[no-untyped-def]
    """Untrusted catalog title/image changes must NOT break valid tickets."""
    svc, repos, engine, iid = env
    proposal = _propose_and_authorize(svc, repos, iid)

    with engine.begin() as conn:
        conn.execute(text("UPDATE products SET title = 'HACKED SUPER DEAL', image_url = NULL"))

    verdict = Revalidator(repos).revalidate(
        intent_id=str(iid),
        checkout_id=str(proposal.envelope.checkout_id),
        expected_checkout_hash=proposal.checkout_hash,
        expected_revision=1,
        expected_intent_hash=proposal.intent_hash,
        expected_generation=1,
    )
    assert verdict.ok, "cosmetic drift must not invalidate"


def test_superseded_authorization_detected_at_revalidation(env) -> None:  # type: ignore[no-untyped-def]
    svc, repos, engine, iid = env
    proposal = _propose_and_authorize(svc, repos, iid)

    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE intent_contracts SET authorization_generation = 2, "
                "max_total_minor = max_total_minor WHERE intent_id = :i"
            ).bindparams(i=str(iid))
        )

    verdict = Revalidator(repos).revalidate(
        intent_id=str(iid),
        checkout_id=str(proposal.envelope.checkout_id),
        expected_checkout_hash=proposal.checkout_hash,
        expected_revision=1,
        expected_intent_hash=proposal.intent_hash,
        expected_generation=1,
    )
    assert not verdict.ok
    assert verdict.code == "AUTHORIZATION_SUPERSEDED"


def test_blocked_intent_detected_at_revalidation(env) -> None:  # type: ignore[no-untyped-def]
    svc, repos, engine, iid = env
    proposal = _propose_and_authorize(svc, repos, iid)

    with engine.begin() as conn:
        conn.execute(
            text("UPDATE intent_contracts SET status = 'BLOCKED' WHERE intent_id = :i").bindparams(
                i=str(iid)
            )
        )

    verdict = Revalidator(repos).revalidate(
        intent_id=str(iid),
        checkout_id=str(proposal.envelope.checkout_id),
        expected_checkout_hash=proposal.checkout_hash,
        expected_revision=1,
        expected_intent_hash=proposal.intent_hash,
        expected_generation=1,
    )
    assert not verdict.ok
    assert verdict.code == "AUTHORIZATION_STALE"
