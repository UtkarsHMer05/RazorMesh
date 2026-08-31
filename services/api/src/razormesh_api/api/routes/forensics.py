"""Phase-5 (M079-M089): Audit as Transaction Forensics.

- GET /forensics/search?q=...  → smart search accepting display trace ids AND
  supported Intent/Checkout IDs (resolves to the canonical trace)
- GET /forensics/trace/{id}   → one trace's full forensic dossier:
  visual timeline (projected events), authorization-vs-current diff,
  provider-contact card (audit-backed), chain-anchor heads
- GET /forensics/recent       → recent trace cards (bounded backend query)

Read-only. Strict id validation. No secrets, no raw premise text, no
row-level review data. The dense raw event wall stays at /audit/timeline.
"""

from __future__ import annotations

import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from razormesh_api.persistence.db import create_db_engine, create_session_factory
from razormesh_api.persistence.models import Checkout as RowCheckout
from razormesh_api.persistence.models import ExecutionAttempt, IntentContract, Product
from razormesh_api.persistence.repositories import Repositories, session_scope
from razormesh_api.settings import Settings, get_settings
from razormesh_api.trace_registry import (
    TraceRegistry,
    project_events,
    summarize_trace,
)

router = APIRouter(prefix="/forensics", tags=["phase5-forensics"])

_DISPLAY_RE = re.compile(r"^RM-[0-9A-HJKMNP-TV-Z]{6}$")
_INTENT_RE = re.compile(r"^intent_[0-9A-HJKMNP-TV-Z]{26}$")
_CHECKOUT_RE = re.compile(r"^chk_[0-9A-HJKMNP-TV-Z]{26}$")
_ATTEMPT_RE = re.compile(r"^exa_[0-9A-HJKMNP-TV-Z]{26}$")


def _repos(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Repositories:
    return Repositories(create_session_factory(create_db_engine(settings.database_url)))


def _registry(repos: Annotated[Repositories, Depends(_repos)]) -> TraceRegistry:
    return TraceRegistry(repos)


@router.get("/search")
def search(
    q: Annotated[str, Query(min_length=4, max_length=64)],
    repos: Annotated[Repositories, Depends(_repos)],
    registry: Annotated[TraceRegistry, Depends(_registry)],
) -> dict[str, Any]:
    """Smart trace search (M080): display trace or Intent/Checkout/Attempt id."""
    q = q.strip()

    def intent_to_trace(intent_id: str) -> dict[str, Any] | None:
        with session_scope(repos.factory) as session:
            exists = session.get(IntentContract, intent_id)
        if exists is None:
            return None
        trace_id = registry.get_or_create_for_intent(intent_id)
        trace = registry.by_trace(trace_id)
        if trace is None:  # pragma: no cover
            return None
        return summarize_trace(repos, trace)

    if _DISPLAY_RE.match(q):
        trace = registry.by_trace(q)
        if trace is None:
            raise HTTPException(status_code=404, detail="Unknown trace")
        return {"match": summarize_trace(repos, trace)}

    if _INTENT_RE.match(q):
        result = intent_to_trace(q)
        if result is None:
            raise HTTPException(status_code=404, detail="Unknown intent")
        return {"match": result}

    if _CHECKOUT_RE.match(q):
        with session_scope(repos.factory) as session:
            row = session.execute(
                select(RowCheckout).where(RowCheckout.checkout_id == q)
            ).scalar_one_or_none()
            if row is None:
                raise HTTPException(status_code=404, detail="Unknown checkout")
        # find the trace whose checkout_id matches
        traces = registry.recent(100)
        for t in traces:
            if t.checkout_id == q:
                return {"match": summarize_trace(repos, t)}
        # fall back: locate the intent via decisions/attempts referencing it
        with session_scope(repos.factory) as session:
            attempt = session.execute(
                select(ExecutionAttempt).where(ExecutionAttempt.checkout_id == q)
            ).scalar_one_or_none()
            if attempt is not None:
                result = intent_to_trace(attempt.intent_id)
                if result is not None:
                    return {"match": result}
        raise HTTPException(status_code=404, detail="Checkout not linked to a trace yet")

    if _ATTEMPT_RE.match(q):
        with session_scope(repos.factory) as session:
            attempt = session.get(ExecutionAttempt, q)
            if attempt is None:
                raise HTTPException(status_code=404, detail="Unknown attempt")
            intent_id = attempt.intent_id
        result = intent_to_trace(intent_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Unknown attempt")
        return {"match": result}

    raise HTTPException(status_code=404, detail="Unrecognized id shape")


@router.get("/trace/{trace_id}")
def forensic_trace(
    trace_id: str,
    repos: Annotated[Repositories, Depends(_repos)],
    registry: Annotated[TraceRegistry, Depends(_registry)],
) -> dict[str, Any]:
    """One trace's dossier (M082-M085): timeline + diff + provider card."""
    if not _DISPLAY_RE.match(trace_id):
        raise HTTPException(status_code=404, detail="Unknown trace")
    trace = registry.by_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Unknown trace")

    summary = summarize_trace(repos, trace)
    events = project_events(repos, trace.intent_id)

    # Authorization-vs-current diff (M084): durable truth vs the mandate.
    diff: list[dict[str, Any]] = []
    if trace.checkout_id:
        with session_scope(repos.factory) as session:
            row = session.get(RowCheckout, trace.checkout_id)
            intent = session.get(IntentContract, trace.intent_id)
            if row is not None and intent is not None:
                lines = list(row.line_items or [])
                first = dict(lines[0]) if lines and isinstance(lines[0], dict) else {}
                pid = str(first.get("product_id", ""))
                product = session.get(Product, pid)
                authorized_total = (
                    product.price_minor * int(first.get("quantity", 1) or 1)
                    + product.shipping_minor
                    if product
                    else None
                )
                # Recompute the CURRENT total the way the envelope would:
                # mutated line items + current fees/shipping — never the
                # stale stored total, which a drift may not have updated.
                current_total = (
                    int(first.get("unit_price_minor", 0)) * int(first.get("quantity", 1) or 1)
                    + int(row.fees_minor or 0)
                    + int(row.shipping_minor or 0)
                )
                if authorized_total is not None and authorized_total != current_total:
                    diff.append(
                        {
                            "field": "total_minor",
                            "authorized": authorized_total,
                            "current": current_total,
                        }
                    )
                if row.subscription_terms and not intent.recurring_allowed:
                    diff.append(
                        {
                            "field": "subscription_terms",
                            "authorized": None,
                            "current": row.subscription_terms,
                        }
                    )
                if (
                    intent.max_total_minor
                    and current_total
                    and current_total > intent.max_total_minor
                ):
                    already = any(d["field"] == "total_minor" for d in diff)
                    if not already:
                        diff.append(
                            {
                                "field": "total_vs_max_total",
                                "authorized": intent.max_total_minor,
                                "current": current_total,
                            }
                        )

    # Provider-contact card (M085): audit evidence only.
    provider = {
        "contacted": summary["provider_contacted"],
        "call_count": summary["provider_call_count"],
        "order_id": None,
        "attempt_state": None,
        "reconcile_state": None,
    }
    with session_scope(repos.factory) as session:
        attempt = (
            session.execute(
                select(ExecutionAttempt).where(ExecutionAttempt.intent_id == trace.intent_id)
            )
            .scalars()
            .first()
        )
        if attempt is not None:
            provider["order_id"] = attempt.razorpay_order_id
            provider["attempt_state"] = attempt.state
            provider["reconcile_state"] = attempt.reconcile_state

    # Chain anchors (M086): heads of the trace's own events.
    return {
        "trace": summary,
        "events": [e.__dict__ for e in events],
        "diff": diff,
        "provider": provider,
        "raw_view": "/audit/timeline",
    }


@router.get("/recent")
def recent(
    repos: Annotated[Repositories, Depends(_repos)],
    registry: Annotated[TraceRegistry, Depends(_registry)],
    limit: int = Query(default=8, ge=1, le=40),
) -> dict[str, Any]:
    traces = registry.recent(limit)
    return {"count": len(traces), "traces": [summarize_trace(repos, t) for t in traces]}
