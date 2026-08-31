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
from sqlalchemy import func, select

from razormesh_api.persistence.db import create_db_engine, create_session_factory
from razormesh_api.persistence.models import (
    AuditEvent,
    DemoTrace,
    ExecutionAttempt,
    IntentContract,
    ProviderEvent,
    TransactionBaseline,
)
from razormesh_api.persistence.models import Checkout as RowCheckout
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
    """Smart trace search (M080 + F010): direct indexed lookups for every
    modeled id a judge may paste — display trace id, intent id, checkout id,
    execution attempt id, and provider/Razorpay order id. Direct DB queries,
    never a recent(100) scan, so OLD traces are findable."""
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

    def checkout_to_intent(checkout_id: str) -> str | None:
        """F010: direct row lookups, never the recent(100) registry scan."""
        with session_scope(repos.factory) as session:
            # Direct indexed lookup on the trace registry's own linkage table.
            trace_row = (
                session.execute(
                    select(DemoTrace).where(DemoTrace.checkout_id == checkout_id)
                )
                .scalars()
                .first()
            )
            if trace_row is not None:
                return trace_row.intent_id
            # Baseline carries the proposal-time intent for the checkout.
            baseline = (
                session.execute(
                    select(TransactionBaseline).where(
                        TransactionBaseline.checkout_id == checkout_id
                    )
                )
                .scalars()
                .first()
            )
            if baseline is not None:
                return baseline.intent_id
            # Execution attempts reference checkouts directly.
            attempt = session.execute(
                select(ExecutionAttempt).where(ExecutionAttempt.checkout_id == checkout_id)
            ).scalar_one_or_none()
            if attempt is not None:
                return attempt.intent_id
        return None

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
        # F010: direct checkout-row lookup (outside any recent window).
        intent_id = checkout_to_intent(q)
        if intent_id is None:
            # The checkout row exists but nothing links it to a trace yet.
            with session_scope(repos.factory) as session:
                row = session.get(RowCheckout, q)
            if row is not None:
                raise HTTPException(status_code=404, detail="Checkout not linked to a trace yet")
            raise HTTPException(status_code=404, detail="Unknown checkout")
        result = intent_to_trace(intent_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Unknown checkout")
        return {"match": result}

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

    # F010: provider/Razorpay order id — direct lookups over attempts and the
    # provider-event table (public trace summary only; nothing else exposed).
    with session_scope(repos.factory) as session:
        attempts = (
            session.execute(
                select(ExecutionAttempt).where(ExecutionAttempt.razorpay_order_id == q)
            )
            .scalars()
            .all()
        )
        for attempt in attempts:
            result = intent_to_trace(attempt.intent_id)
            if result is not None:
                return {"match": result}
        provider_events = (
            session.execute(
                select(ProviderEvent).where(ProviderEvent.razorpay_order_id == q)
            )
            .scalars()
            .all()
        )
        for provider_event in provider_events:
            if provider_event.intent_id:
                result = intent_to_trace(provider_event.intent_id)
                if result is not None:
                    return {"match": result}
        raise HTTPException(status_code=404, detail="Unrecognized id shape")


@router.get("/trace/{trace_id}")
def forensic_trace(
    trace_id: str,
    repos: Annotated[Repositories, Depends(_repos)],
    registry: Annotated[TraceRegistry, Depends(_registry)],
) -> dict[str, Any]:
    """One trace's dossier (M082-M085 + G021/G023): timeline + comprehensive
    diff + provider card + selected-trace chain anchors."""
    if not _DISPLAY_RE.match(trace_id):
        raise HTTPException(status_code=404, detail="Unknown trace")
    trace = registry.by_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Unknown trace")

    summary = summarize_trace(repos, trace)
    events = project_events(repos, trace.intent_id)

    # G021: COMPREHENSIVE authorization-vs-current diff. The authorized side
    # is the immutable TransactionBaseline captured at proposal time (G012) —
    # never the current product row. Every modeled auth-relevant dimension:
    # merchant, product, condition, quantity, unit price, fees, shipping,
    # tax, total, currency, recurring terms, display text.
    diff: list[dict[str, Any]] = []
    if trace.checkout_id:
        with session_scope(repos.factory) as session:
            row = session.get(RowCheckout, trace.checkout_id)
            baseline = session.execute(
                select(TransactionBaseline).where(
                    TransactionBaseline.checkout_id == trace.checkout_id
                )
            ).scalar_one_or_none()
            if row is not None and baseline is not None:
                lines = list(row.line_items or [])
                first = dict(lines[0]) if lines and isinstance(lines[0], dict) else {}
                authorized: dict[str, Any] = {
                    "merchant_id": baseline.merchant_id,
                    "product_id": baseline.product_id,
                    "condition": baseline.condition,
                    "quantity": baseline.quantity,
                    "unit_price_minor": baseline.unit_price_minor,
                    "fees_minor": baseline.fees_minor,
                    "shipping_minor": baseline.shipping_minor,
                    "tax_minor": baseline.tax_minor,
                    "total_minor": baseline.total_minor,
                    "currency": baseline.currency,
                    "recurring": bool(baseline.recurring),
                    "subscription_terms": (
                        {"recurring": True, "frequency": baseline.recurring_frequency}
                        if baseline.recurring
                        else None
                    ),
                }
                current_total = (
                    int(first.get("unit_price_minor", 0)) * int(first.get("quantity", 1) or 1)
                    + int(row.fees_minor or 0)
                    + int(row.shipping_minor or 0)
                    + int(row.tax_minor or 0)
                )
                current: dict[str, Any] = {
                    "merchant_id": row.merchant_id,
                    "product_id": first.get("product_id"),
                    "condition": first.get("condition"),
                    "quantity": first.get("quantity"),
                    "unit_price_minor": first.get("unit_price_minor"),
                    "fees_minor": int(row.fees_minor or 0),
                    "shipping_minor": int(row.shipping_minor or 0),
                    "tax_minor": int(row.tax_minor or 0),
                    "total_minor": current_total,
                    "currency": row.currency,
                    "recurring": bool(row.subscription_terms),
                    "subscription_terms": dict(row.subscription_terms)
                    if row.subscription_terms
                    else None,
                }
                diff = [
                    {"field": f, "authorized": authorized.get(f), "current": current.get(f)}
                    for f in authorized
                    if f in current and authorized.get(f) != current.get(f)
                ]

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

    # G023: the SELECTED trace's own hash-chain nodes (event hash heads +
    # prev-hash links, read-only) so the judge can see exactly where tamper
    # would break THIS trace's chain. Global ledger verify stays at /audit/verify.
    # F009: the audit ledger is GLOBAL — a selected trace's events interleave
    # with OTHER traces' events in one hash chain. Two consecutive events of
    # THIS trace are NOT expected to link by prev_hash directly when unrelated
    # global events lie between them. The honest semantics: this trace's
    # ANCHORS in the global chain, with the number of global events between
    # consecutive anchors, and the GLOBAL ledger verify as the cryptographic
    # authority. A trace view must never report "broken" merely because of
    # interleaving.
    with session_scope(repos.factory) as session:
        chain_rows = (
            session.execute(
                select(AuditEvent)
                .where(AuditEvent.intent_id == trace.intent_id)
                .order_by(AuditEvent.seq.asc())
                .limit(200)
            )
            .scalars()
            .all()
        )
        seqs = [e.seq for e in chain_rows]
        min_seq = min(seqs) if seqs else 0
        max_seq = max(seqs) if seqs else 0
        # Contiguous global segment between this trace's first/last anchor —
        # the exact global events that link the anchors (includes other
        # traces' events; that is the truth of a global ledger).
        global_between = int(
            session.execute(
                select(func.count())
                .where(AuditEvent.seq >= min_seq)
                .where(AuditEvent.seq <= max_seq)
            ).scalar()
        ) if seqs else 0
    chain_nodes: list[dict[str, Any]] = []
    prev_row: AuditEvent | None = None
    for e in chain_rows:
        gap = None
        directly_linked = None
        if prev_row is not None:
            # Real global linkage: does e's prev point at the immediately
            # preceding GLOBAL event (which is prev_row only when no other
            # trace's event lies between them)?
            gap = int(e.seq) - int(prev_row.seq) - 1
            directly_linked = (
                e.previous_event_hash is not None
                and e.previous_event_hash == prev_row.current_event_hash
            )
        chain_nodes.append(
            {
                "seq": e.seq,
                "event_type": e.event_type,
                "prev_head": (e.previous_event_hash or "")[:16],
                "hash_head": e.current_event_hash[:16],
                # F009: honest interleaving metadata — how many OTHER global
                # events separate consecutive anchors of THIS trace, and
                # whether the two anchors are ALSO directly linked (gap 0).
                "global_gap_before": gap,
                "directly_linked_to_prev": directly_linked,
            }
        )
        prev_row = e
    # The selected trace is well-anchored in the global chain when every one
    # of its events carries a prev_hash into the chain (it does not require
    # trace-consecutive linkage — that would mislabel interleaving as a
    # break). The cryptographic authority remains /audit/verify.
    chain_anchored = all(n["prev_head"] != "" for n in chain_nodes) and bool(chain_nodes)

    # Chain anchors (M086): heads of the trace's own events.
    return {
        "trace": summary,
        "events": [e.__dict__ for e in events],
        "diff": diff,
        "provider": provider,
        "chain": {
            "nodes": chain_nodes,
            "anchored": chain_anchored,
            "node_count": len(chain_nodes),
            "global_events_between_first_last_anchor": (
                global_between - len(chain_nodes) if seqs else 0
            ),
            "note": (
                "THIS TRACE'S ANCHORS IN THE GLOBAL AUDIT CHAIN. The ledger is "
                "global: unrelated events from other traces may lie between "
                "two anchors (global_gap_before counts them) — that is "
                "expected interleaving, NOT a break. Each anchor links to the "
                "global chain via prev_hash; cryptographic authority is the "
                "GLOBAL CHAIN VERIFY at /audit/verify. Tamper simulation is "
                "non-mutating."
            ),
        },
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
