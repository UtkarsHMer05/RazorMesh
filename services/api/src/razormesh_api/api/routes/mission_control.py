"""Phase-5 (M108) + deep-engine correction (G019/G020): Mission Control API.

- POST /mission-control/reset            → bounded demo reset (history kept)
- GET  /mission-control/current-transaction/{trace_id} → the CURRENT
  transaction's authorization-vs-current diff (immutable baseline vs live
  checkout; G020)
- POST /mission-control/mutate-current    → apply a bounded mutation to the
  CURRENT transaction (checkout-local, G013; G019)
- POST /mission-control/revert-current    → restore the CURRENT transaction
  to its exact captured baseline (G014; G019)
- POST /mission-control/execute-current  → run the CURRENT transaction
  through the REAL revalidation boundary (G019)

Every action targets the CURRENT live trace's own checkout - never a
disconnected one. No action mints money authority: tickets stay on the
buyer flow / mock provider; execute-current reports the boundary verdict.
"""

from __future__ import annotations

import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from razormesh_api.catalog import seed_catalog
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.merchant_sandbox import (
    MerchantDemoError,
    MutationKind,
    apply_mutation,
    offer_diff,
)
from razormesh_api.persistence.db import create_db_engine, create_session_factory
from razormesh_api.persistence.models import DemoTrace, TransactionBaseline
from razormesh_api.persistence.repositories import Repositories, session_scope
from razormesh_api.settings import Settings, get_settings
from razormesh_api.trace_registry import TraceRegistry

router = APIRouter(prefix="/mission-control", tags=["phase5-mission-control"])

_DISPLAY_TRACE_RE = re.compile(r"^RM-[0-9A-HJKMNP-TV-Z]{6}$")


def _repos(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Repositories:
    return Repositories(create_session_factory(create_db_engine(settings.database_url)))


def _ledger(repos: Annotated[Repositories, Depends(_repos)]) -> EvidenceLedger:
    return EvidenceLedger(repos)


@router.get("/preflight")
def preflight(warm_up: bool = False) -> dict[str, Any]:
    """F012: DEMO PREFLIGHT — presenter-only readiness check.

    Real lightweight probes over every component the video depends on
    (PostgreSQL, Redis, AI Intent Compiler, active semantic model, v2
    challenger shadow, protocol keys, audit chain, payment environment).
    ``warm_up=true`` performs a NON-AUTHORITATIVE provider health request so
    the 60-75s first compile does not ruin the recording. No secrets exposed;
    no mandate compiled; nothing fabricated.
    """
    from razormesh_api.preflight import run_preflight

    return run_preflight(warm_up_compiler=warm_up)


@router.post("/reset")
def reset_demo(
    repos: Annotated[Repositories, Depends(_repos)],
) -> dict[str, Any]:
    """Bounded demo reset (M108): re-seeds fixtures; audit history and all
    existing traces are NEVER deleted."""
    try:
        with session_scope(repos.factory) as session:
            traces = list(session.execute(select(DemoTrace).order_by(DemoTrace.trace_id)).scalars())
            surviving_traces = len(traces)
        seed_catalog(repos)
        return {
            "reset": "catalog-fixture-reset",
            "audit_history_deleted": False,
            "surviving_traces": surviving_traces,
            "note": (
                "Demo catalog fixtures re-seeded. Audit history is untouched - "
                "every prior mission remains searchable in Audit."
            ),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"reset failed: {exc}") from exc


class TraceActionRequest(BaseModel):
    trace_id: str = Field(pattern=r"^RM-[0-9A-HJKMNP-TV-Z]{6}$")
    kind: str = Field(min_length=4, max_length=32)


def _current_checkout(repos: Repositories, trace_id: str) -> tuple[str, str]:
    """Resolve (intent_id, checkout_id) for the CURRENT live trace."""
    if not _DISPLAY_TRACE_RE.match(trace_id):
        raise HTTPException(status_code=404, detail="Unknown trace")
    trace = TraceRegistry(repos).by_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Unknown trace")
    if not trace.checkout_id:
        raise HTTPException(
            status_code=409,
            detail={"code": "NO_CHECKOUT", "detail": "the current trace has no checkout yet"},
        )
    return trace.intent_id, str(trace.checkout_id)


@router.get("/current-transaction/{trace_id}")
def current_transaction(
    trace_id: str,
    repos: Annotated[Repositories, Depends(_repos)],
) -> dict[str, Any]:
    """G020: the CURRENT transaction's authorization-vs-current diff.

    The authorized side is the immutable TransactionBaseline (G012); the
    current side is the live checkout. Covers every modeled auth-relevant
    dimension: merchant, product, condition, quantity, unit price, fees,
    shipping, total, currency, recurring.
    """
    intent_id, checkout_id = _current_checkout(repos, trace_id)
    try:
        diff = offer_diff(repos, checkout_id)
    except MerchantDemoError as exc:
        raise HTTPException(
            status_code=409, detail={"code": exc.code, "detail": exc.detail}
        ) from exc
    return {
        "trace_id": trace_id,
        "intent_id": intent_id,
        "checkout_id": checkout_id,
        "diff": diff["diff"],
        "clean": len(diff["diff"]) == 0,
    }


@router.post("/mutate-current")
def mutate_current(
    body: TraceActionRequest,
    repos: Annotated[Repositories, Depends(_repos)],
    ledger: Annotated[EvidenceLedger, Depends(_ledger)],
) -> dict[str, Any]:
    """G019: apply a bounded mutation to the CURRENT transaction."""
    intent_id, checkout_id = _current_checkout(repos, body.trace_id)
    try:
        kind = MutationKind(body.kind)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"unknown mutation kind {body.kind}") from exc
    if kind is MutationKind.REVERT:
        raise HTTPException(status_code=422, detail="use /revert-current for revert")
    try:
        result = apply_mutation(
            repos, ledger, intent_id=intent_id, checkout_id=checkout_id, kind=kind
        )
    except MerchantDemoError as exc:
        status = {
            "BASELINE_MISSING": 409,
            "MUTATION_OUT_OF_BOUNDS": 422,
            "NO_OTHER_MERCHANT": 409,
        }.get(exc.code, 400)
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "detail": exc.detail}
        ) from exc
    return {
        "trace_id": body.trace_id,
        "kind": result.kind,
        "label": result.label,
        "changed_fields": list(result.changed_fields),
        "before": result.before,
        "after": result.after,
        "note": result.note,
    }


@router.post("/revert-current")
def revert_current(
    body: TraceActionRequest,
    repos: Annotated[Repositories, Depends(_repos)],
    ledger: Annotated[EvidenceLedger, Depends(_ledger)],
) -> dict[str, Any]:
    """G019: revert the CURRENT transaction to its exact captured baseline."""
    intent_id, checkout_id = _current_checkout(repos, body.trace_id)
    try:
        result = apply_mutation(
            repos, ledger, intent_id=intent_id, checkout_id=checkout_id, kind=MutationKind.REVERT
        )
    except MerchantDemoError as exc:
        status = {"BASELINE_MISSING": 409}.get(exc.code, 400)
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "detail": exc.detail}
        ) from exc
    return {
        "trace_id": body.trace_id,
        "kind": result.kind,
        "label": result.label,
        "changed_fields": list(result.changed_fields),
        "note": result.note,
    }


def _baseline_hashes(repos: Repositories, checkout_id: str) -> tuple[str, str]:
    """The proposal-time authorization hashes stored on the baseline (G019).

    Refuses pre-G019 baselines rather than guessing: a missing stored hash
    can never be safely reconstructed after the checkout row changed.
    """
    with session_scope(repos.factory) as session:
        base = session.execute(
            select(TransactionBaseline).where(TransactionBaseline.checkout_id == checkout_id)
        ).scalar_one_or_none()
    if base is None or not base.expected_checkout_hash or not base.expected_intent_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "BASELINE_HASH_MISSING",
                "detail": "this checkout predates the captured-hash contract",
            },
        )
    return base.expected_checkout_hash, base.expected_intent_hash


@router.post("/execute-current")
def execute_current(
    body: TraceActionRequest,
    repos: Annotated[Repositories, Depends(_repos)],
) -> dict[str, Any]:
    """G019: run the CURRENT transaction through the REAL revalidation
    boundary - the exact check the trusted executor performs before any
    provider call. A drifted checkout STALE_DETECTs; a clean one passes.
    No ticket is minted and the provider is never contacted by this control
    (money paths stay on the buyer flow / mock provider)."""
    intent_id, checkout_id = _current_checkout(repos, body.trace_id)
    from razormesh_api.revalidation import Revalidator

    expected_checkout_hash, expected_intent_hash = _baseline_hashes(repos, checkout_id)
    verdict = Revalidator(repos).revalidate(
        intent_id=intent_id,
        checkout_id=checkout_id,
        expected_checkout_hash=expected_checkout_hash,
        expected_revision=1,
        expected_intent_hash=expected_intent_hash,
        expected_generation=1,
    )
    outcome = "REVALIDATION_PASS" if verdict.ok else verdict.code
    return {
        "trace_id": body.trace_id,
        "outcome": outcome,
        "detail": verdict.detail,
        "ticket_minted": False,
        "provider_contacted": False,
        "note": (
            "The transaction passed the executor's revalidation contract."
            if verdict.ok
            else "The transaction FAILED the executor's revalidation contract - "
            "it would never reach the provider."
        ),
    }
