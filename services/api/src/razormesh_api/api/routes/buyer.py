"""M45: buyer-flow API — propose/authorize/execute through the trusted core.

Direct API bypass remains protected: every execution request carries the
signed ticket and is FULLY re-verified server-side (signature, expiry, all
context bindings against freshly read durable rows). No endpoint executes
without a valid ticket; no client field influences totals.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from razormesh_api.checkout_service import (
    CheckoutError,
    CheckoutService,
    ProposedItem,
)
from razormesh_api.decider import DecisionEngine
from razormesh_api.domain.authz_hash import intent_authorization_hash
from razormesh_api.domain.checkout import CheckoutEnvelope
from razormesh_api.domain.ids import ExecutionAttemptId, IntentId, new_ulid
from razormesh_api.domain.state_machine import NotExecutableError
from razormesh_api.executor import AttemptState, IllegalAttemptTransition, TrustedPaymentExecutor
from razormesh_api.keys import DevKeyPair, DevSigningKeys
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.nonce import (
    CoordinationUnavailable,
    NonceAlreadyClaimed,
    NonceRegistry,
)
from razormesh_api.persistence.models import ExecutionAttempt as ExecutionAttemptForCallback
from razormesh_api.persistence.models import IntentContract as RowIntent
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.providers.mock import MockPaymentProvider
from razormesh_api.providers.razorpay import RazorpayPaymentProvider, build_payment_provider
from razormesh_api.revalidation import Revalidator
from razormesh_api.rules.catalog_rules import CATALOG_RULES
from razormesh_api.rules.money_rules import MONEY_RULES
from razormesh_api.rules.policy_rules import POLICY_RULES
from razormesh_api.settings import ProviderConfigError, Settings, get_settings
from razormesh_api.spend import SpendError, SpendManager
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


class LaunchPayload(BaseModel):
    """Public Standard Checkout data — never contains secrets (P2-S03/S04)."""

    public_key_id: str
    razorpay_order_id: str
    amount_minor: int
    currency: str
    execution_attempt_id: str
    intent_id: str
    checkout_id: str


class CallbackIn(BaseModel):
    execution_attempt_id: str = Field(min_length=6, max_length=64)
    intent_id: str = Field(min_length=6, max_length=64)
    checkout_id: str = Field(min_length=6, max_length=64)
    razorpay_payment_id: str = Field(min_length=6, max_length=64)
    razorpay_order_id: str = Field(min_length=6, max_length=64)
    razorpay_signature: str = Field(min_length=32, max_length=256)


class ExecutionBody(BaseModel):
    state: str
    attempt_id: str
    detail: str | None = None
    launch: LaunchPayload | None = None


class StatusBody(BaseModel):
    """Read-only authoritative attempt snapshot for UI re-sync (P2-M40)."""

    state: str
    attempt_id: str | None = None
    fulfilment_state: str | None = None
    razorpay_order_id: str | None = None
    razorpay_payment_status: str | None = None
    error_code: str | None = None


@router.post("/buyer/fixture-intent")
def create_fixture_intent(repos: Annotated[Repositories, Depends(_repos)]) -> dict[str, Any]:
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
        intent_id = IntentId(body.intent_id)
        proposal = svc.propose(
            intent_id=intent_id,
            items=[ProposedItem(product_id=i.product_id, quantity=i.quantity) for i in body.items],
        )
        result = svc.authorize(intent_id=intent_id, proposal=proposal)
    except (CheckoutError, ValueError) as exc:
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
    settings: Annotated[Settings, Depends(get_settings)],
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

    try:
        rebuilt = Revalidator(repos).rebuild_envelope(row)
    except Exception as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "CHECKOUT_INVALID", "detail": type(exc).__name__},
        ) from exc
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
    try:
        provider = _provider_for(settings)
    except ProviderConfigError as exc:
        # Fail-closed server misconfiguration (names only, never values, M09).
        raise HTTPException(
            status_code=503,
            detail={"code": "RAZORPAY_CONFIG_UNAVAILABLE", "detail": "; ".join(exc.problems)},
        ) from exc
    executor = _executor(repos, keys.ensure(), spend, provider)
    try:
        attempt = executor.execute(
            signed_ticket=SignedTicket(body.ticket_json, body.signature_hex),
            binding=binding,
            intent_id=contract.intent_id,
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
    except SpendError as exc:
        raise HTTPException(
            status_code=409, detail={"code": "AUTHORIZATION_CAPACITY_UNAVAILABLE"}
        ) from exc
    except CoordinationUnavailable as exc:
        raise HTTPException(
            status_code=503, detail={"code": "NONCE_COORDINATION_UNAVAILABLE"}
        ) from exc

    result_body = ExecutionBody(state=attempt.state, attempt_id=attempt.execution_attempt_id)
    if attempt.state == "EXECUTING" and attempt.razorpay_order_id:
        from razormesh_api.providers.razorpay import build_launch_payload

        launch = build_launch_payload(
            attempt_state=attempt.state,
            attempt_amount_minor=attempt.amount_minor,
            attempt_currency=attempt.currency,
            attempt_execution_attempt_id=attempt.execution_attempt_id,
            attempt_intent_id=attempt.intent_id,
            attempt_checkout_id=attempt.checkout_id,
            attempt_razorpay_order_id=attempt.razorpay_order_id,
            settings=settings,
        )
        result_body.launch = LaunchPayload(**launch.__dict__)
    return result_body


def _checkout_hash(env: CheckoutEnvelope) -> str:
    from razormesh_api.domain.authz_hash import checkout_authorization_hash

    return checkout_authorization_hash(env)


def _provider_for(settings: Settings) -> MockPaymentProvider | RazorpayPaymentProvider:
    """Test seam: provider selection for trusted execution (D-030).

    Honors the typed PAYMENT_PROVIDER selector: razorpay construction runs the
    fail-safe config guard via build_payment_provider and never falls back to
    mock (P2-S21); mock stays credential-free (P2-S20).
    """
    provider, _kind = build_payment_provider(settings)
    return provider


def _executor(
    repos: Repositories,
    pair: DevKeyPair,
    spend: SpendManager,
    provider: MockPaymentProvider | RazorpayPaymentProvider,
) -> TrustedPaymentExecutor:
    return TrustedPaymentExecutor(
        repos=repos,
        keys=pair,
        nonces=_nonce_registry(),
        provider=provider,
        spend=spend,
    )


def _nonce_registry() -> NonceRegistry:
    import os

    from redis import Redis

    url = os.environ.get("RAZORMESH_REDIS_URL") or get_settings().redis_url
    return NonceRegistry(Redis.from_url(url, decode_responses=True), ttl_seconds=120)


# imported late to avoid circulars in route typing
from razormesh_api.persistence.models import Checkout as RowCheckoutForSelect  # noqa: E402


@router.post("/buyer/callback")
def checkout_callback(
    payload_in: CallbackIn,
    repos: Annotated[Repositories, Depends(_repos)],
    keys: Annotated[DevSigningKeys, Depends(_keys)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExecutionBody:
    """Verify the browser callback against the SERVER-stored order (P2-S07/S08).

    Zero business mutation occurs before signature verification succeeds. Even a
    valid signature alone is not fulfilment authority: captured/paid evidence is
    confirmed via provider fetch (M25) before any settlement.
    """
    from razormesh_api.providers.razorpay import verify_checkout_signature

    with repos.transaction() as session:
        attempt = session.get(
            ExecutionAttemptForCallback,
            payload_in.execution_attempt_id,
        )
        context_matches = bool(
            attempt is not None
            and attempt.intent_id == payload_in.intent_id
            and attempt.checkout_id == payload_in.checkout_id
        )
        stored_order = attempt.razorpay_order_id if context_matches and attempt else None

    if attempt is None:
        raise HTTPException(status_code=404, detail={"code": "RAZORPAY_ORDER_CONTEXT_MISMATCH"})
    if not context_matches:
        raise HTTPException(
            status_code=403,
            detail={"code": "RAZORPAY_PAYMENT_CONTEXT_MISMATCH"},
        )
    if stored_order is None:
        raise HTTPException(status_code=404, detail={"code": "RAZORPAY_ORDER_CONTEXT_MISMATCH"})

    # Browser-provided order id is advisory only; verification uses the stored id.
    if payload_in.razorpay_order_id != stored_order:
        raise HTTPException(
            status_code=403,
            detail={"code": "RAZORPAY_PAYMENT_CONTEXT_MISMATCH"},
        )

    if not verify_checkout_signature(
        order_id=stored_order,
        payment_id=payload_in.razorpay_payment_id,
        signature_hex=payload_in.razorpay_signature,
        key_secret=settings.razorpay_key_secret.get_secret_value(),
    ):
        raise HTTPException(
            status_code=403,
            detail={"code": "RAZORPAY_PAYMENT_SIGNATURE_INVALID"},
        )

    now = datetime.now(UTC)
    provider = _razorpay_provider(settings)
    executor = TrustedPaymentExecutor(
        repos=repos,
        keys=keys.ensure(),
        nonces=_nonce_registry(),
        provider=provider,
        spend=SpendManager(repos),
    )

    # A valid callback signature proves the payment/order pair, not that the
    # provider order still matches durable amount/currency/context. Reuse the
    # same authority validation as operator reconciliation before any callback
    # verification marker or fulfilment transition (P2-S06, M18/M24/M25).
    from razormesh_api.providers.razorpay import (
        RazorpayError,
        RazorpayProviderStateConflict,
        reconcile_attempt,
    )

    try:
        provider_snapshot = reconcile_attempt(
            repos=repos,
            provider=provider,
            attempt_id=attempt.execution_attempt_id,
            now=now,
        )
    except RazorpayProviderStateConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "detail": exc.detail},
        ) from exc
    except RazorpayError as exc:
        current = repos.attempts.get(ExecutionAttemptId(attempt.execution_attempt_id))
        if current is not None and current.state in {
            AttemptState.SUCCEEDED.value,
            AttemptState.FAILED.value,
        }:
            # A replay cannot demote an already-settled attempt merely because
            # the provider read is temporarily unavailable.
            return ExecutionBody(
                state=current.state,
                attempt_id=current.execution_attempt_id,
            )
        unknown = executor.record_provider_unknown(
            attempt.execution_attempt_id,
            error_code=exc.code,
            now=now,
        )
        return ExecutionBody(
            state=unknown.state,
            attempt_id=unknown.execution_attempt_id,
            detail="RAZORPAY_RECONCILIATION_REQUIRED",
        )

    first_verification = False
    with repos.transaction() as session:
        row = session.get(
            ExecutionAttemptForCallback, attempt.execution_attempt_id, with_for_update=True
        )
        if row is not None:
            first_verification = row.callback_verified_at is None
            row.callback_verified_at = now
            row.updated_at = now

    # P2-M44: tamper-evident record of callback verification (exactly-once:
    # duplicate deliveries must not grow the ledger).
    if first_verification:
        EvidenceLedger(repos).append(
            event_type="RAZORPAY_CALLBACK_VERIFIED",
            actor="buyer-callback-route",
            intent_id=str(attempt.intent_id),
            checkout_id=str(attempt.checkout_id),
            ticket_id=str(attempt.ticket_id),
            payload={
                "execution_attempt_id": attempt.execution_attempt_id,
                "razorpay_order_id": stored_order,
                "razorpay_payment_id": payload_in.razorpay_payment_id,
                "verification": "HMAC-SHA256(server-stored order|payment)",
            },
        )

    # ---- P2-M25: a valid signature alone is NOT fulfilment authority.
    # Require captured/paid evidence from the provider before any settlement.
    if provider_snapshot.provider_status == "paid":
        try:
            settled = executor.confirm_captured(
                attempt.execution_attempt_id,
                provider_payment_id=payload_in.razorpay_payment_id,
                now=now,
            )
        except RazorpayProviderStateConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": exc.code, "detail": exc.detail},
            ) from exc
        except IllegalAttemptTransition:
            # Duplicate delivery after settlement: idempotent no-op (P2-S13).
            existing = repos.attempts.get(ExecutionAttemptId(attempt.execution_attempt_id))
            if existing is None:  # pragma: no cover - row vanished mid-request
                raise HTTPException(status_code=404, detail={"code": "ATTEMPT_GONE"}) from None
            settled = existing
        return ExecutionBody(state=settled.state, attempt_id=settled.execution_attempt_id)

    # Re-read the CURRENT durable state: a webhook may have settled the attempt
    # (e.g. payment.failed) while this callback was in flight. The response must
    # never report a pre-lock snapshot as the truth (P2-M40 race analysis).
    with repos.factory() as session:
        fresh = session.get(ExecutionAttemptForCallback, attempt.execution_attempt_id)
    current_state = fresh.state if fresh is not None else attempt.state
    return ExecutionBody(
        state=current_state,
        attempt_id=attempt.execution_attempt_id,
        detail="RAZORPAY_PAYMENT_NOT_CAPTURED",
    )


@router.get("/buyer/status")
def attempt_status(
    repos: Annotated[Repositories, Depends(_repos)],
    intent_id: Annotated[str, Query(min_length=6, max_length=64)],
    checkout_id: Annotated[str, Query(min_length=6, max_length=64)],
) -> StatusBody:
    """P2-M40: READ-ONLY authoritative attempt state for UI re-sync.

    The browser is never a source of payment truth: after the checkout modal
    is dismissed without a success callback, a webhook may already have
    settled the attempt (FAILED or SUCCEEDED). The UI must render the server
    state, not its last local phase. Zero mutation.
    """
    with repos.transaction() as session:
        attempt = (
            session.query(ExecutionAttemptForCallback)
            .filter(
                ExecutionAttemptForCallback.intent_id == intent_id,
                ExecutionAttemptForCallback.checkout_id == checkout_id,
            )
            .order_by(ExecutionAttemptForCallback.created_at.desc())
            .first()
        )
        if attempt is None:
            return StatusBody(state="NO_ATTEMPT")
        return StatusBody(
            state=attempt.state,
            attempt_id=attempt.execution_attempt_id,
            fulfilment_state=attempt.fulfilment_state,
            razorpay_order_id=attempt.razorpay_order_id,
            razorpay_payment_status=attempt.razorpay_payment_status,
            error_code=attempt.error_code,
        )


def _razorpay_provider(settings: Settings) -> RazorpayPaymentProvider:
    """Test seam: unit tests monkeypatch this to inject a MockTransport client.

    Construction goes through from_settings so the fail-safe config guard
    (P2-S01..S03) applies to the callback path as well.
    """
    return RazorpayPaymentProvider.from_settings(settings)
