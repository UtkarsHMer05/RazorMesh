"""Phase-5 (M108): bounded demo reset.

Fresh mission + demo merchant fixture reset WITHOUT deleting previous audit
history: the reset creates new state going forward; the audit ledger and all
existing traces remain intact and searchable. Destructive wipes are not
exposed (the only sanctioned wipe lives in the test harness).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from razormesh_api.catalog import seed_catalog
from razormesh_api.persistence.db import create_db_engine, create_session_factory
from razormesh_api.persistence.models import DemoTrace
from razormesh_api.persistence.repositories import Repositories, session_scope
from razormesh_api.settings import Settings, get_settings

router = APIRouter(prefix="/mission-control", tags=["phase5-mission-control"])


def _repos(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Repositories:
    return Repositories(create_session_factory(create_db_engine(settings.database_url)))


class ResetRequest:
    """Marker for body-free reset (POST with no payload)."""


@router.post("/reset")
def reset_demo(
    repos: Annotated[Repositories, Depends(_repos)],
) -> dict[str, Any]:
    """Bounded demo reset (M108):

    - re-seeds the synthetic catalog fixtures (idempotent);
    - audit history and existing traces are NEVER deleted;
    - returns counts proving what survived.
    """
    try:
        with session_scope(repos.factory) as session:
            traces = list(session.execute(select(DemoTrace).order_by(DemoTrace.trace_id)).scalars())
            surviving_traces = len(traces)
        seed_catalog(repos)
        # The reset does NOT pick or clear the active mission: starting a new
        # mission mints a new trace on the buyer flow; old traces stay.
        return {
            "reset": "catalog-fixture-reset",
            "audit_history_deleted": False,
            "surviving_traces": surviving_traces,
            "note": (
                "Demo catalog fixtures re-seeded. Audit history is untouched — "
                "every prior mission remains searchable in Audit."
            ),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"reset failed: {exc}") from exc
