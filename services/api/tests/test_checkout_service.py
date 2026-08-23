"""M38 acceptance: server-authoritative checkout proposal + RazorGuard path."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine

from razormesh_api.catalog import seed_catalog
from razormesh_api.checkout_service import (
    CheckoutError,
    CheckoutService,
    ClientTotalMismatch,
    ProposedItem,
    QuantityExceedsAuthorization,
    UnknownProduct,
)
from razormesh_api.decider import Decision, DecisionEngine
from razormesh_api.domain.ids import IntentId, new_ulid
from razormesh_api.domain.state_machine import NotExecutableError
from razormesh_api.keys import DevSigningKeys
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.persistence import models  # noqa: F401
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.models import (
    Checkout,
    ExecutionTicket,
)
from razormesh_api.persistence.models import (
    IntentContract as RowIntent,
)
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.rules.catalog_rules import CATALOG_RULES
from razormesh_api.rules.money_rules import MONEY_RULES
from razormesh_api.rules.policy_rules import POLICY_RULES


def _engine():
    from razormesh_api.settings import get_settings

    return create_engine(get_settings().database_url, future=True)


@pytest.fixture()
def service(tmp_path):  # type: ignore[no-untyped-def]
    from conftest import wipe_business_tables

    engine = _engine()
    repos = Repositories(create_session_factory(engine))
    wipe_business_tables(engine)
    seed_catalog(repos)
    keys = DevSigningKeys(
        private_path=str(tmp_path / "p.pem"), public_path=str(tmp_path / "pub.pem")
    ).ensure()
    ledger = EvidenceLedger(repos)
    engine_rules = DecisionEngine([*MONEY_RULES, *CATALOG_RULES, *POLICY_RULES])
    svc = CheckoutService(repos=repos, ledger=ledger, engine=engine_rules, keys=keys)
    yield svc, repos
    wipe_business_tables(engine)


def _intent_row(**overrides):  # type: ignore[no-untyped-def]
    from razormesh_api.settings import get_settings as _gs

    engine = create_engine(_gs().database_url, future=True)
    repos = Repositories(create_session_factory(engine))
    iid = IntentId.generate()
    now = datetime.now(UTC)
    defaults = dict(
        max_total_minor=10_000_000,
        aggregate_budget_minor=50_000_000,
        approval_threshold_minor=8_000_000,
        status="AUTHORIZED",
    )
    defaults.update(overrides)
    with repos.transaction() as s:
        s.merge(
            RowIntent(
                intent_id=str(iid),
                principal_id=f"usr_{new_ulid()}",
                agent_id=f"agt_{new_ulid()}",
                authorization_generation=1,
                currency="INR",
                recurring_allowed=False,
                max_quantity=2,
                issued_at=now,
                authorized_at=now,
                expires_at=now + timedelta(minutes=30),
                created_at=now,
                updated_at=now,
                **defaults,
            )
        )
    return iid


def _first_product(repos):  # type: ignore[no-untyped-def]
    return repos.products.list(limit=1)[0]


def test_propose_recomputes_total_server_side_and_persists(service) -> None:  # type: ignore[no-untyped-def]
    svc, repos = service
    iid = _intent_row()
    product = _first_product(repos)
    proposal = svc.propose(
        intent_id=iid,
        items=[ProposedItem(product_id=product.id, quantity=2)],
    )
    expected = product.price_minor * 2 + product.shipping_minor
    assert proposal.envelope.compute_total().amount_minor == expected
    assert proposal.envelope.line_items[0].unit_price.amount_minor == product.price_minor

    # durable projection exists
    with repos.transaction() as s:
        rows = list(s.query(Checkout).all())
    assert len(rows) == 1
    assert rows[0].computed_total_minor == expected

    # ledger captured the proposal
    report = EvidenceLedger(repos).verify()
    assert report.valid and report.events_checked >= 1


def test_client_total_manipulation_rejected_loudly(service) -> None:  # type: ignore[no-untyped-def]
    svc, repos = service
    iid = _intent_row()
    product = _first_product(repos)
    computed = product.price_minor + product.shipping_minor
    with pytest.raises(ClientTotalMismatch):
        svc.propose(
            intent_id=iid,
            items=[ProposedItem(product_id=product.id)],
            client_total_minor=computed - 1,
        )


def test_unknown_product_and_quantity_and_blocked_intent(service) -> None:  # type: ignore[no-untyped-def]
    svc, repos = service
    iid = _intent_row()
    with pytest.raises(UnknownProduct):
        svc.propose(intent_id=iid, items=[ProposedItem("prd_01ARZ3NDEKTSV4RRFFQ69G5FAV")])

    product = _first_product(repos)
    with pytest.raises(QuantityExceedsAuthorization):
        svc.propose(
            intent_id=iid,
            items=[ProposedItem(product.id, quantity=99)],  # max_quantity=2
        )

    blocked = _intent_row(status="BLOCKED")
    with pytest.raises(NotExecutableError):
        svc.propose(intent_id=blocked, items=[ProposedItem(product.id)])


def test_authorize_allow_issues_ticket_and_audits(service) -> None:  # type: ignore[no-untyped-def]
    svc, repos = service
    iid = _intent_row()
    product = min(repos.products.list(limit=100), key=lambda p: p.price_minor)
    proposal = svc.propose(intent_id=iid, items=[ProposedItem(product.id)])
    result = svc.authorize(intent_id=iid, proposal=proposal)

    assert result.outcome.decision is Decision.ALLOW
    assert result.ticket_json is not None
    with repos.transaction() as s:
        assert s.query(ExecutionTicket).count() == 1
    report = EvidenceLedger(repos).verify()
    assert report.valid
    kinds = [e.event_type for e in sorted(repos.audit.list_recent(10), key=lambda e: e.seq)]
    assert (
        "CHECKOUT_PROPOSED" in kinds and "DECISION_RECORDED" in kinds and "TICKET_ISSUED" in kinds
    )


def test_budget_block_produces_no_ticket(service) -> None:  # type: ignore[no-untyped-def]
    svc, repos = service
    iid = _intent_row(
        max_total_minor=50000,
        aggregate_budget_minor=50000,
        approval_threshold_minor=40000,
    )
    product = min(repos.products.list(limit=100), key=lambda p: p.price_minor)
    proposal = svc.propose(intent_id=iid, items=[ProposedItem(product.id)])
    result = svc.authorize(intent_id=iid, proposal=proposal)
    assert result.outcome.decision is Decision.BLOCK
    assert "BUDGET_EXCEEDED" in result.outcome.reason_codes
    assert result.ticket_json is None
    with repos.transaction() as s:
        assert s.query(ExecutionTicket).count() == 0


def test_approval_threshold_challenge_no_ticket(service) -> None:  # type: ignore[no-untyped-def]
    svc, repos = service
    product = min(repos.products.list(limit=100), key=lambda p: p.price_minor)
    # threshold below payable -> deterministic CHALLENGE signal
    iid = _intent_row(approval_threshold_minor=max(product.price_minor - 1, 1))
    proposal = svc.propose(intent_id=iid, items=[ProposedItem(product.id)])
    result = svc.authorize(intent_id=iid, proposal=proposal)
    assert result.outcome.decision is Decision.CHALLENGE
    assert "APPROVAL_REQUIRED" in result.outcome.reason_codes
    assert result.ticket_json is None


def test_proposal_requires_items(service) -> None:  # type: ignore[no-untyped-def]
    svc, _repos = service
    iid = _intent_row()
    with pytest.raises(CheckoutError, match="at least one item"):
        svc.propose(intent_id=iid, items=[])
