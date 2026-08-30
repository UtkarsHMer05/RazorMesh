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

from datetime import UTC, datetime, timedelta
from pathlib import Path as FilePath
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
    through ``CheckoutService``, and the semantic stage defaults to the
    fine-tuned DeBERTa NLI verifier (``SEMANTIC_VERIFIER_BACKEND=deberta``).
    The deterministic keyword verifier is used only when explicitly selected
    via ``deterministic_test_stub`` and is reported as such.
    """
    settings: Settings = get_settings()
    repos_obj = _repos(settings=settings)
    keys_obj = _keys(settings=settings)
    return Phase4AcceptanceOrchestrator(
        checkout_service=_service(repos=repos_obj, keys=keys_obj),
        semantic_model_dir=FilePath(settings.semantic_model_path),
        semantic_model_dir_v2=FilePath(settings.semantic_model_path_v2),
        semantic_policy_path=FilePath(settings.semantic_policy_path),
        semantic_backend=settings.semantic_verifier_backend,
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
                "rejection_stage": result.rejection_stage,
                "final_decision": result.run.evidence.final_decision or None,
                # Full-evidence rejection (M5): per-stage verdicts when the
                # orchestrator gathered them (firewall/razorguard/semantic).
                "evidence": result.run.evidence.to_dict()["razormesh"],
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


# ---------------------------------------------------------------------------
# Security Lab demo scenarios (M5). Each route provisions its own fixtures,
# then drives the REAL acceptance pipeline. They are evidence views over the
# production path — no new trust decisions, no new payment path, no provider
# call on any rejection.
# ---------------------------------------------------------------------------

_DEMO_MERCHANT_ID = "mrc_10000000000000000000000000"
_DEMO_HIDDEN_PRODUCT_ID = "prd_20000000000000000000000000"
_DEMO_STANDARD_PRODUCT_ID = "prd_30000000000000000000000000"


def _ensure_demo_catalog(repos: Any) -> None:
    """Idempotently provision the demo merchant/products (fixed ids)."""
    from razormesh_api.persistence.models import Merchant as RowMerchant
    from razormesh_api.persistence.models import Product as RowProduct

    now = datetime.now(UTC)
    with repos.transaction() as session:
        session.merge(
            RowMerchant(
                id=_DEMO_MERCHANT_ID,
                name="RazorMesh Security Lab",
                display_name="RazorMesh Security Lab",
                description="Synthetic demo merchant for the Security Lab scenarios (not a real offer).",
                created_at=now,
                updated_at=now,
            )
        )
        # Products are UPSERTED so fixture changes self-heal across runs.
        # Structured recurring term: the checkout line item itself carries
        # the renewal, so the deterministic rule and the semantic recurring
        # pair both see it. (A term hidden ONLY in untrusted listing text
        # is NOT visible to the structured evidence builder — a disclosed
        # limitation motivating the AgentPay-IR v2 corpus work.)
        session.merge(
            RowProduct(
                id=_DEMO_HIDDEN_PRODUCT_ID,
                merchant_id=_DEMO_MERCHANT_ID,
                title=(
                    "CloudFit Annual Pass — includes membership that auto-renews "
                    "every quarter unless cancelled before day 30"
                ),
                description="Synthetic Security Lab demo product with a recurring membership term.",
                brand="CloudFit",
                category="fitness",
                condition="new",
                price_minor=249_900,
                currency="INR",
                shipping_minor=0,
                tax_minor=0,
                fees_minor=0,
                recurring=True,
                recurring_frequency="quarterly",
                image_url=None,
                created_at=now,
                updated_at=now,
            )
        )
        session.merge(
            RowProduct(
                id=_DEMO_STANDARD_PRODUCT_ID,
                merchant_id=_DEMO_MERCHANT_ID,
                title="Aurora Bluetooth Speaker",
                description="Synthetic Security Lab demo product (one-time purchase, no recurring terms).",
                brand="Aurora",
                category="audio",
                condition="new",
                price_minor=249_900,
                currency="INR",
                shipping_minor=0,
                tax_minor=0,
                fees_minor=0,
                recurring=False,
                recurring_frequency=None,
                image_url=None,
                created_at=now,
                updated_at=now,
            )
        )


def _create_demo_intent(repos: Any, *, max_quantity: int, max_total_minor: int) -> str:
    """Strict demo authorization: one-time only, quantity- and budget-capped."""
    from razormesh_api.domain.ids import IntentId, new_ulid
    from razormesh_api.persistence.models import IntentContract as RowIntent

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
                max_total_minor=max_total_minor,
                aggregate_budget_minor=max_total_minor * 2,
                max_quantity=max_quantity,
                approval_threshold_minor=max_total_minor,
                issued_at=now,
                authorized_at=now,
                expires_at=now + timedelta(minutes=30),
                created_at=now,
                updated_at=now,
            )
        )
    return str(iid)


def _demo_response(result: Any, scenario: str) -> dict[str, Any]:
    ev = result.run.evidence
    return {
        "scenario": scenario,
        "run_id": result.run.run_id,
        "rejection_stage": result.rejection_stage,
        "rejection_reason": result.rejection_reason,
        "protocol_firewall": ev.protocol_firewall or "NOT_RUN",
        "protocol_firewall_reasons": list(ev.protocol_firewall_reasons),
        "razorguard_decision": ev.razorguard_decision or "NOT_RUN",
        "semantic_verifier": ev.semantic_verifier or "NOT_RUN",
        "semantic_backend": ev.semantic_backend,
        "semantic_model_version": ev.semantic_model_version,
        "semantic_probabilities": {
            "contradiction": ev.semantic_probabilities[0],
            "entailment": ev.semantic_probabilities[1],
            "neutral": ev.semantic_probabilities[2],
        },
        "semantic_fail_closed": ev.semantic_fail_closed,
        "final_decision": ev.final_decision,
        "ticket_issued": bool(result.run.ticket_id),
        "provider_contacted": False,
        "consumed": result.consumed,
        "evidence": ev.to_dict()["razormesh"],
    }


@router.post("/demo/scenario-b-semantic-violation")
def demo_scenario_b_semantic_violation() -> dict[str, Any]:
    """SCENARIO B — semantic intent violation: the checkout line carries a
    recurring membership term the human never authorized. Expected: protocol
    PASS, deterministic RazorGuard BLOCK (recurring not allowed), semantic
    BLOCK (contradiction confirmed by the full-evidence rejection path),
    final BLOCK, no ticket, Razorpay NOT contacted. A term hidden ONLY in
    untrusted listing text is a disclosed limitation of the structured
    evidence builder."""
    repos = _repos(settings=get_settings())
    _ensure_demo_catalog(repos)
    intent_id = _create_demo_intent(repos, max_quantity=1, max_total_minor=300_000)
    orch = build_orchestrator()
    result = orch.prepare(
        intent_id=intent_id,
        product_id=_DEMO_HIDDEN_PRODUCT_ID,
        quantity=1,
        currency="INR",
    )
    return _demo_response(result, "B_semantic_intent_violation")


@router.post("/demo/scenario-c-protocol-valid-intent-invalid")
def demo_scenario_c_protocol_valid_intent_invalid() -> dict[str, Any]:
    """SCENARIO C — protocol valid, human intent invalid: a schema-valid,
    signature-valid, replay-safe protocol message whose transaction (2 units
    = ₹4,998) exceeds the human authorization (≤ ₹3,000). Expected: protocol
    PASS, deterministic RazorGuard BLOCK, semantic contradiction, final BLOCK,
    Razorpay NOT contacted — proving protocol validity is not transaction
    authority."""
    repos = _repos(settings=get_settings())
    _ensure_demo_catalog(repos)
    intent_id = _create_demo_intent(repos, max_quantity=3, max_total_minor=300_000)
    orch = build_orchestrator()
    result = orch.prepare(
        intent_id=intent_id,
        product_id=_DEMO_STANDARD_PRODUCT_ID,
        quantity=2,
        currency="INR",
    )
    return _demo_response(result, "C_protocol_valid_intent_invalid")


__all__ = ["router"]
