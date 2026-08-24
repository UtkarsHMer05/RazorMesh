"""P2-M41: operator surface for provider-unknown reconciliation.

- GET  /ops/reconciliation/required   read-only listing of attempts whose
  reconcile_state is REQUIRED (safe identifiers only, zero mutation);
- POST /ops/reconciliation/{attempt_id} runs ONE reconciliation pass: a
  READ-ONLY provider fetch validated against durable authority, with any
  fetch-proven capture evidence reduced through the single reducer.

This surface never creates financial operations and never retries the
original order creation (P2-S18/S19).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from razormesh_api.api.routes.webhooks import _repos_for
from razormesh_api.persistence.models import ExecutionAttempt
from razormesh_api.providers.razorpay import RazorpayProviderStateConflict
from razormesh_api.reconciliation import ReconciliationOutcome, ReconciliationService
from razormesh_api.settings import Settings, get_settings

router = APIRouter(prefix="/ops", tags=["ops"])


def _repos(settings: Annotated[Settings, Depends(get_settings)]):  # type: ignore[no-untyped-def]
    return _repos_for(settings)


class ReconciliationRequiredRow(BaseModel):
    execution_attempt_id: str
    intent_id: str
    checkout_id: str
    state: str
    amount_minor: int
    currency: str
    error_code: str | None
    razorpay_order_id: str | None
    razorpay_order_status: str | None
    created_at_utc: str


class ReconciliationRequiredBody(BaseModel):
    count: int
    attempts: list[ReconciliationRequiredRow]


@router.get("/reconciliation/required", response_model=ReconciliationRequiredBody)
def reconciliation_required(
    repos: Annotated[Any, Depends(_repos)],
) -> ReconciliationRequiredBody:
    """Expose the reconciliation-required state (P2-M41). READ-ONLY."""
    with repos.transaction() as session:
        rows = (
            session.query(ExecutionAttempt)
            .filter(ExecutionAttempt.reconcile_state == "REQUIRED")
            .order_by(ExecutionAttempt.created_at.asc())
            .all()
        )
        attempts = [
            ReconciliationRequiredRow(
                execution_attempt_id=row.execution_attempt_id,
                intent_id=row.intent_id,
                checkout_id=row.checkout_id,
                state=row.state,
                amount_minor=row.amount_minor,
                currency=row.currency,
                error_code=row.error_code,
                razorpay_order_id=row.razorpay_order_id,
                razorpay_order_status=row.razorpay_order_status,
                created_at_utc=row.created_at.isoformat() if row.created_at else "",
            )
            for row in rows
        ]
    return ReconciliationRequiredBody(count=len(attempts), attempts=attempts)


def _service(settings: Settings) -> ReconciliationService:
    """Test seam: monkeypatched by the suite to inject a fake provider."""
    from razormesh_api.keys import DevSigningKeys
    from razormesh_api.nonce import NonceRegistry
    from razormesh_api.providers.razorpay import RazorpayPaymentProvider
    from razormesh_api.reducer import ProviderStateReducer
    from razormesh_api.spend import SpendManager

    repos = _repos_for(settings)
    keys = DevSigningKeys(
        private_path=settings.dev_ticket_private_key_path,
        public_path=settings.dev_ticket_public_key_path,
    ).ensure()
    nonces = NonceRegistry(
        __import__("redis").Redis.from_url(settings.redis_url, decode_responses=True),
        ttl_seconds=120,
    )
    provider = RazorpayPaymentProvider.from_settings(settings)
    reducer = ProviderStateReducer(
        repos=repos,
        keys=keys,
        nonces=nonces,
        provider=provider,
        spend=SpendManager(repos),
    )
    return ReconciliationService(repos=repos, provider=provider, reducer=reducer)


@router.post("/reconciliation/{attempt_id}", response_model=ReconciliationOutcome)
def run_reconciliation(
    attempt_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReconciliationOutcome:
    service = _service(settings)
    try:
        outcome = service.reconcile(attempt_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "ATTEMPT_NOT_RECONCILABLE"}) from exc
    except RazorpayProviderStateConflict as exc:
        # Authority conflict: fail loudly, mutate nothing (P2-S06).
        raise HTTPException(status_code=409, detail={"code": exc.code}) from exc

    # P2-M44: tamper-evident record of the operator-driven reconciliation pass.
    from razormesh_api.ledger import EvidenceLedger

    EvidenceLedger(_repos_for(settings)).append(
        event_type="RAZORPAY_RECONCILIATION_RUN",
        actor="ops-reconciliation-route",
        intent_id=outcome.intent_id,
        payload={
            "execution_attempt_id": outcome.attempt_id,
            "razorpay_order_id": outcome.order_id,
            "state_before": outcome.attempt_state_before,
            "state_after": outcome.attempt_state_after,
            "reconcile_state_after": outcome.reconcile_state_after,
            "provider_order_status": outcome.provider_order_status,
            "order_discovered_and_claimed": outcome.order_discovered_and_claimed,
            "settled_by_reconciliation": outcome.settled_by_reconciliation,
            "reservation_note": (
                "committed exactly-once via reducer"
                if outcome.settled_by_reconciliation
                else "held/unchanged"
            ),
            "detail": outcome.detail,
        },
    )
    return outcome
