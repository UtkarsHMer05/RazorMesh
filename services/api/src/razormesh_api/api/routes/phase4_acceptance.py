"""Phase-4 acceptance orchestration HTTP surface.

This module exposes the live Phase-4 cross-protocol ingress as HTTP
endpoints so the acceptance client (or the browser-driven UI) can
trigger the full chain:

  POST /phase4/acceptance/prepare   -> run MCP->UCP->AP2->Firewall->IR
                                       ->Consistency->RazorGuard->ALLOW
  GET  /phase4/acceptance/run/{id}  -> inspect a recorded run
  GET  /phase4/acceptance/runs      -> snapshot of the in-memory registry

The route is intentionally thin: it delegates to the
`Phase4AcceptanceOrchestrator` and never re-implements trust logic.
The orchestrator never holds the Razorpay secret, webhook secret,
DB credentials, AP2 private keys, the ExecutionTicket private key,
the payment provider, shell access, or arbitrary networking.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from razormesh_api.api.routes.buyer import (
    _keys,
    _repos,
    _service,
)
from razormesh_api.protocol.acceptance import (
    REGISTRY,
    Phase4AcceptanceOrchestrator,
)
from razormesh_api.settings import Settings, get_settings

router = APIRouter(prefix="/phase4/acceptance", tags=["phase4-acceptance"])


def _orchestrator() -> Phase4AcceptanceOrchestrator:
    """Construct an orchestrator with the real buyer-flow services."""
    settings: Settings = get_settings()
    repos_obj = _repos(settings=settings)  # type: ignore[call-arg]
    keys = _keys(settings=settings)  # type: ignore[call-arg]
    checkout_svc = _service(repos=repos_obj, keys=keys)  # type: ignore[call-arg]
    return Phase4AcceptanceOrchestrator(
        checkout_service=checkout_svc,
        decision_engine=checkout_svc._engine,  # type: ignore[attr-defined]
        semantic_verifier=lambda ir: "ALLOW",
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


@router.post("/prepare")
def prepare_acceptance(body: PrepareBody) -> dict[str, Any]:
    """Run the full Phase-4 acceptance pipeline for one transaction."""
    orch = _orchestrator()
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
            "POST /buyer/execute with checkout_id + ticket_json + "
            "signature_hex from /buyer/propose"
        ),
    }


@router.get("/run/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
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


@router.get("/runs")
def list_runs() -> dict[str, Any]:
    snap = REGISTRY.snapshot()
    return {"runs": snap, "count": len(snap)}


__all__ = ["router"]
