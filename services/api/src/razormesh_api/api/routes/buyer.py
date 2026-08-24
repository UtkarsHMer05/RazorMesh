"""M45: buyer-flow API — propose/authorize/execute through the trusted core.

Direct API bypass remains protected: every execution request carries the
signed ticket and is FULLY re-verified server-side (signature, expiry, all
context bindings against freshly read durable rows). No endpoint executes
without a valid ticket; no client field influences totals.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from razormesh_api.checkout_service import (
    CheckoutError,
    CheckoutService,
    ProposedItem,
)
from razormesh_api.decider import DecisionEngine
from razormesh_api.domain.authz_hash import intent_authorization_hash
from razormesh_api.domain.ids import IntentId, new_ulid
from razormesh_api.domain.state_machine import NotExecutableError
from razormesh_api.keys import DevSigningKeys
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.nonce import NonceAlreadyClaimed
from razormesh_api.persistence.models import IntentContract as RowIntent
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.revalidation import Revalidator
from razormesh_api.rules.catalog_rules import CATALOG_RULES
from razormesh_api.rules.money_rules import MONEY_RULES
from razormesh_api.rules.policy_rules import POLICY_RULES
from razormesh_api.settings import Settings, get_settings
from razormesh_api.spend import SpendManager
from razormesh_api.tickets import CurrentBinding, SignedTicket, TicketRejected

router = APIRouter(tags=["buyer"])


def _repos(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Repositories:
    from razormesh_api.persistence.db import create_db_engine, create_session_factory

    return Repositories(create_session_factory(create_db_engine(settings.database_url)))


def _keys(settings: Annotated[Settings, Depends(get_settings)]) -> DevSigningKeys:
    return DevSigningKeys(
        private_path=settings.dev_ticket_private_key_path,
        public_path=settings.dev_ticket_public_key_path,
    )


def _service(repos: Repositories, keys: DevSigningKeys) -> CheckoutService:
    rules = DecisionEngine([*MONEY_RULES, *CATALOG_RULES, *POLICY_RULES])
    return CheckoutService(
        repos=repos, ledger=EvidenceLedger(repos), engine=rules, keys=keys.ensure()
    )


class ProposedItemIn(BaseModel):
    product_id: str = Field(min_length=6, max_length=64)
    quantity: int = Field(default=1, ge=1, le=10)


class ProposeIn(BaseModel):
    intent_id: str = Field(min_length=6, max_length=64)
    items: list[ProposedItemIn] = Field(min_length=1, max_length=50)


class DecisionBody(BaseModel):
    decision: str
    reason_codes: list[str]
    checkout_id: str
    total_minor: int
    ticket_json: str | None = None
    signature_hex: str | None = None


class ExecuteIn(BaseModel):
    intent_id: str = Field(min_length=6, max_length=64)
    checkout_id: str = Field(min_length=6, max_length=64)
    ticket_json: str = Field(min_length=20, max_length=20000)
    signature_hex: str = Field(min_length=32, max_length=256)


class ExecutionBody(BaseModel):
    state: str
    attempt_id: str
    detail: str | None = None


@router.post("/buyer/fixture-intent")
def create_fixture_intent(repos: Annotated[Repositories, Depends(_repos)]) -> dict:
    """Phase-1 fixture authorization: a permissive demo intent (no real money)."""
    iid = IntentId.generate()
    now = datetime.now(UTC)
    with repos.transaction() as session:
        session.merge(
            RowIntent(
                intent_id=str(iid),
                principal_id=f"usr_{new_ulid()}",
                agent_id=f"agt_{new_ulid()}",
                authorization_generation=1,
                status="AUTHORIZED",
                currency="INR",
                recurring_allowed=False,
                max_total_minor=50_000_000,
                aggregate_budget_minor=200_000_000,
                max_quantity=2,
                approval_threshold_minor=40_000_000,
                issued_at=now,
                authorized_at=now,
                expires_at=now + timedelta(minutes=30),
                created_at=now,
                updated_at=now,
            )
        )
    return {"intent_id": str(iid), "expires_at": (now + timedelta(minutes=30)).isoformat()}


@router.post("/buyer/propose")
def propose(
    body: ProposeIn,
    repos: Annotated[Repositories, Depends(_repos)],
    keys: Annotated[DevSigningKeys, Depends(_keys)],
) -> DecisionBody:
    svc = _service(repos, keys)
    try:
        proposal = svc.propose(
            intent_id=IntentId(body.intent_id),
            items=[ProposedItem(product_id=i.product_id, quantity=i.quantity) for i in body.items],
        )
        result = svc.authorize(intent_id=IntentId(body.intent_id), proposal=proposal)
    except CheckoutError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except NotExecutableError as exc:
        raise HTTPException(status_code=422, detail=f"authorization not executable: {exc}") from exc

    return DecisionBody(
        decision=result.outcome.decision.value,
        reason_codes=list(result.outcome.reason_codes),
        checkout_id=str(proposal.envelope.checkout_id),
        total_minor=proposal.envelope.compute_total().amount_minor,
        ticket_json=result.ticket_json,
        signature_hex=result.signed_ticket.signature_hex if result.signed_ticket else None,
    )


@router.post("/buyer/execute")
def execute(
    body: ExecuteIn,
    repos: Annotated[Repositories, Depends(_repos)],
    keys: Annotated[DevSigningKeys, Depends(_keys)],
) -> ExecutionBody:
    # Rebuild the CURRENT binding exclusively from durable rows.
    try:
        intent_row = repos.intents.get(IntentId(body.intent_id))
    except Exception:  # noqa: BLE001 - malformed ids fail closed
        intent_row = None
    if intent_row is None:
        raise HTTPException(status_code=404, detail="unknown intent")

    from razormesh_api.revalidation import domain_intent_from_row

    contract = domain_intent_from_row(intent_row)

    with repos.factory() as session:
        row = (
            session.execute(
                select(RowCheckoutForSelect).where(
                    RowCheckoutForSelect.checkout_id == body.checkout_id
                )
            )
            .scalars()
            .first()
        )
    if row is None:
        raise HTTPException(status_code=404, detail="unknown checkout")

    rebuilt = Revalidator(repos).rebuild_envelope(row)
    binding = CurrentBinding(
        principal_id=str(contract.principal_id),
        agent_id=str(contract.agent_id),
        intent_id=str(contract.intent_id),
        intent_hash=intent_authorization_hash(contract),
        authorization_generation=contract.authorization_generation,
        checkout_id=str(rebuilt.checkout_id),
        checkout_hash=_checkout_hash(rebuilt),
        checkout_revision=rebuilt.revision,
        merchant_id=str(rebuilt.merchant_id),
        amount_minor=rebuilt.compute_total().amount_minor,
        currency=str(rebuilt.compute_total().currency),
    )

    spend = SpendManager(repos)
    spend.ensure_authorization(
        contract.intent_id, authorized_minor=contract.aggregate_budget.amount_minor
    )
    spend.reserve(contract.intent_id, binding.amount_minor)

    executor = _executor(repos, keys.ensure(), spend)
    try:
        attempt = executor.execute(
            signed_ticket=SignedTicket(body.ticket_json, body.signature_hex),
            binding=binding,
            intent_id=contract.intent_id,
            idempotency_key=f"api-{body.checkout_id}",
            now_utc=datetime.now(UTC),
        )
    except TicketRejected as exc:
        raise HTTPException(
            status_code=403, detail={"code": exc.code, "detail": exc.detail}
        ) from exc
    except NonceAlreadyClaimed:
        # A concurrent/replayed use of the same single-use authority is a
        # business denial (error taxonomy: replay), never a server fault.
        raise HTTPException(status_code=409, detail={"code": "NONCE_REPLAY_REJECTED"}) from None

    return ExecutionBody(state=attempt.state, attempt_id=attempt.execution_attempt_id)


def _checkout_hash(env):  # type: ignore[no-untyped-def]
    from razormesh_api.domain.authz_hash import checkout_authorization_hash

    return checkout_authorization_hash(env)


def _executor(repos: Repositories, pair, spend: SpendManager):  # type: ignore[no-untyped-def]
    from razormesh_api.executor import TrustedPaymentExecutor
    from razormesh_api.providers.mock import MockMode, MockPaymentProvider

    return TrustedPaymentExecutor(
        repos=repos,
        keys=pair,
        nonces=_nonce_registry(),
        provider=MockPaymentProvider(mode=MockMode.SUCCESS),
        spend=spend,
    )


def _nonce_registry():  # type: ignore[no-untyped-def]
    import os

    from redis import Redis

    from razormesh_api.nonce import NonceRegistry

    url = os.environ.get("RAZORMESH_REDIS_URL") or get_settings().redis_url
    return NonceRegistry(Redis.from_url(url, decode_responses=True), ttl_seconds=120)


# imported late to avoid circulars in route typing
from razormesh_api.persistence.models import Checkout as RowCheckoutForSelect  # noqa: E402
