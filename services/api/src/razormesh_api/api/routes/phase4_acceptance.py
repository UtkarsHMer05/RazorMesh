"""Phase-4 acceptance orchestration HTTP surface.

This module exposes the live Phase-4 cross-protocol ingress as HTTP
endpoints so the acceptance client (or the browser-driven UI) can
trigger the full chain:

  POST /phase4/acceptance/prepare   -> run MCP->UCP->AP2->Firewall->IR
                                       ->Consistency->RazorGuard->ALLOW
  GET  /phase4/acceptance/run/{id}  -> inspect a recorded run
  POST /phase4/acceptance/finalize  -> reauthorize + execute the same run
  GET  /phase4/acceptance/handoff/{id} -> Razorpay launch payload
  GET  /phase4/acceptance/runs      -> snapshot of the in-memory registry

The route is intentionally thin: it delegates to the
`Phase4AcceptanceOrchestrator` and never re-implements trust logic.
The orchestrator never holds the Razorpay secret, webhook secret,
DB credentials, AP2 private keys, the ExecutionTicket private key,
the payment provider, shell access, or arbitrary networking.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from razormesh_api.api.routes.buyer import (
    _keys,
    _nonce_registry,
    _provider_for,
    _repos,
    _service,
)
from razormesh_api.executor import TrustedPaymentExecutor
from razormesh_api.protocol.acceptance import (
    REGISTRY,
    Phase4AcceptanceOrchestrator,
)
from razormesh_api.settings import Settings, get_settings
from razormesh_api.spend import SpendError, SpendManager
from razormesh_api.tickets import TicketRejected

router = APIRouter(prefix="/phase4/acceptance", tags=["phase4-acceptance"])

RunIdPath = Annotated[str, Path(min_length=10, max_length=64)]


def build_orchestrator() -> Phase4AcceptanceOrchestrator:
    """Construct an orchestrator with the real buyer-flow services.

    Nothing here can force an ALLOW: the orchestrator reaches RazorGuard
    through ``CheckoutService``, and the semantic seam defaults to the
    credential-free deterministic verifier, which can only make the
    outcome stricter.
    """
    settings: Settings = get_settings()
    repos_obj = _repos(settings=settings)
    keys_obj = _keys(settings=settings)
    return Phase4AcceptanceOrchestrator(
        checkout_service=_service(repos=repos_obj, keys=keys_obj),
    )


def build_executor() -> TrustedPaymentExecutor:
    """Build the production trusted executor for one acceptance handoff."""
    settings: Settings = get_settings()
    repos_obj = _repos(settings=settings)
    keys_obj = _keys(settings=settings)
    provider = _provider_for(settings)
    return TrustedPaymentExecutor(
        repos=repos_obj,
        keys=keys_obj.ensure(),
        nonces=_nonce_registry(),
        provider=provider,
        spend=SpendManager(repos_obj),
    )


class PrepareBody(BaseModel):
    intent_id: str = Field(min_length=6, max_length=64)
    product_id: str = Field(min_length=6, max_length=64)
    quantity: int = Field(default=1, ge=1, le=10)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    run_id: str | None = None
    idempotency_key: str | None = None
    mcp_method_tool: str = "complete_authorized_checkout"
    mcp_message_id: str | None = None


class FinalizeBody(BaseModel):
    """Bounded input for the single-execution handoff step."""

    run_id: str = Field(min_length=10, max_length=64)


@router.post("/prepare")
def prepare_acceptance(body: PrepareBody) -> dict[str, Any]:
    """Run the full Phase-4 acceptance pipeline for one transaction."""
    orch = build_orchestrator()
    result = orch.prepare(
        intent_id=body.intent_id,
        product_id=body.product_id,
        quantity=body.quantity,
        currency=body.currency,
        run_id=body.run_id,
        idempotency_key=body.idempotency_key,
        mcp_method_tool=body.mcp_method_tool,
        mcp_message_id=body.mcp_message_id,
    )
    if not result.consumed:
        raise HTTPException(
            status_code=409,
            detail={
                "code": result.rejection_stage or "rejected",
                "reason": result.rejection_reason,
                "run_id": result.run.run_id,
            },
        )
    return {
        "run_id": result.run.run_id,
        "checkout_id": result.run.checkout_id,
        "amount_minor": result.run.amount_minor,
        "currency": result.run.currency,
        "evidence": result.run.evidence.to_dict(),
        "tickets_endpoint": "/buyer/execute",
        "next_step": (
            "POST /phase4/acceptance/finalize with this run_id to "
            "reauthorize and create the Razorpay Test order"
        ),
    }


@router.get("/run/{run_id}")
def get_run(run_id: RunIdPath) -> dict[str, Any]:
    run = REGISTRY.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail={"code": "UNKNOWN_RUN", "run_id": run_id})
    return {
        "run_id": run.run_id,
        "intent_id": run.intent_id,
        "checkout_id": run.checkout_id,
        "idempotency_key": run.idempotency_key,
        "amount_minor": run.amount_minor,
        "currency": run.currency,
        "completed": run.completed,
        "used_at": run.used_at,
        "evidence": run.evidence.to_dict(),
    }


@router.post("/finalize")
def finalize_acceptance(body: FinalizeBody) -> dict[str, Any]:
    """Reauthorize and execute the SAME acceptance_run_id exactly once.

    No second ticket-minting path exists: the orchestrator re-runs the
    production ``CheckoutService.authorize`` (deterministic RazorGuard +
    durable decision row + context-bound single-use ticket) immediately
    before handing that ticket to ``TrustedPaymentExecutor``, which is
    the only provider caller. The reservation, ExecutionAttempt and
    Razorpay order therefore come from the unchanged trusted path.
    """
    orch = build_orchestrator()
    try:
        return orch.finalize_razorpay_handoff(
            run_id=body.run_id,
            executor=build_executor(),
        )
    except (RuntimeError, TicketRejected, SpendError) as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "FINALIZE_REFUSED",
                "reason": str(exc) or type(exc).__name__,
                "run_id": body.run_id,
            },
        ) from exc


@router.get("/handoff/{run_id}")
def get_handoff(run_id: RunIdPath) -> dict[str, Any]:
    """Return the Razorpay launch payload for a finalized acceptance run."""
    settings: Settings = get_settings()
    attempt = _repos(settings=settings).attempts.find_by_acceptance_run_id(run_id)
    if attempt is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NO_HANDOFF", "run_id": run_id},
        )
    return {
        "run_id": run_id,
        "execution_attempt_id": attempt.execution_attempt_id,
        "razorpay_order_id": attempt.razorpay_order_id,
        "state": attempt.state,
        "provider_event": attempt.provider_event,
    }


@router.get("/runs")
def list_runs() -> dict[str, Any]:
    snap = REGISTRY.snapshot()
    return {"runs": snap, "count": len(snap)}


__all__ = ["router"]
