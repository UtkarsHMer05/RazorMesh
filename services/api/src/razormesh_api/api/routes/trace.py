"""Phase-5 (M011): trace read API — read-only, privacy-safe.

- GET /trace/{trace_id}      → summary + staged events for one trace
- GET /trace/recent          → bounded recent-trace summaries
- GET /trace/events?trace_id=&after_seq= → incremental event poll (M012)
- GET /trace/by-intent/{intent_id} → resolve a trace for deep-linking

Strict id validation; unknown trace → clean 404. No secrets, no raw review
data, no signatures. The projection derives everything from audit evidence.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from razormesh_api.persistence.repositories import Repositories
from razormesh_api.settings import Settings, get_settings
from razormesh_api.trace_registry import (
    TraceRegistry,
    project_events,
    summarize_trace,
)

router = APIRouter(prefix="/trace", tags=["phase5-trace"])

_DISPLAY_TRACE_RE = "RM-[0-9A-HJKMNP-TV-Z]{6}"


class TraceResponse(BaseModel):
    trace: dict[str, Any]
    events: list[dict[str, Any]]


def _repos(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Repositories:
    from razormesh_api.persistence.db import create_db_engine, create_session_factory

    return Repositories(create_session_factory(create_db_engine(settings.database_url)))


def _registry(repos: Annotated[Repositories, Depends(_repos)]) -> TraceRegistry:
    return TraceRegistry(repos)


def _validate_trace_id(trace_id: str) -> str:
    import re

    if not re.fullmatch(_DISPLAY_TRACE_RE, trace_id):
        raise HTTPException(status_code=404, detail="Unknown trace")
    return trace_id


@router.get("/recent")
def recent(
    registry: Annotated[TraceRegistry, Depends(_registry)],
    repos: Annotated[Repositories, Depends(_repos)],
    limit: Annotated[int, Query(ge=1, le=100)] = 12,
) -> dict[str, Any]:
    traces = registry.recent(limit)
    items = [summarize_trace(repos, t) for t in traces]
    return {"count": len(items), "traces": items}


@router.get("/{trace_id}")
def read_trace(
    trace_id: str,
    registry: Annotated[TraceRegistry, Depends(_registry)],
    repos: Annotated[Repositories, Depends(_repos)],
) -> TraceResponse:
    trace_id = _validate_trace_id(trace_id)
    trace = registry.by_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Unknown trace")
    summary = summarize_trace(repos, trace)
    events = project_events(repos, trace.intent_id)
    return TraceResponse(
        trace=summary,
        events=[e.__dict__ for e in events],
    )


@router.get("/events/{trace_id}")
def trace_events(
    trace_id: str,
    registry: Annotated[TraceRegistry, Depends(_registry)],
    repos: Annotated[Repositories, Depends(_repos)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    trace_id = _validate_trace_id(trace_id)
    trace = registry.by_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Unknown trace")
    events = project_events(repos, trace.intent_id, after_seq=after_seq)
    return {
        "trace_id": trace.trace_id,
        "intent_id": trace.intent_id,
        "after_seq": after_seq,
        "count": len(events),
        "events": [e.__dict__ for e in events],
    }


@router.get("/by-intent/{intent_id}")
def by_intent(
    intent_id: str,
    registry: Annotated[TraceRegistry, Depends(_registry)],
    repos: Annotated[Repositories, Depends(_repos)],
) -> dict[str, Any]:
    """Resolve (lazily minting) the display trace for an existing intent."""
    import re

    if not re.fullmatch(r"intent_[0-9A-HJKMNP-TV-Z]{26}", intent_id):
        raise HTTPException(status_code=404, detail="Unknown intent")
    trace = registry.by_intent(intent_id)
    if trace is None:
        # Lazy mint for pre-Phase-5 intents: linkage only, audit untouched.
        from razormesh_api.persistence.models import IntentContract
        from razormesh_api.persistence.repositories import session_scope

        with session_scope(repos.factory) as session:
            exists = session.get(IntentContract, intent_id)
        if exists is None:
            raise HTTPException(status_code=404, detail="Unknown intent")
        trace_id = registry.get_or_create_for_intent(intent_id)
        trace = registry.by_trace(trace_id)
        if trace is None:  # pragma: no cover — registry just created it
            raise HTTPException(status_code=500, detail="Registry inconsistency")
    return summarize_trace(repos, trace)
