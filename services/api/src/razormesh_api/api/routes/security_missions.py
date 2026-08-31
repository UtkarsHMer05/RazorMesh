"""Deep-engine correction (G016-G018): dedicated security-mission API.

- GET  /security-missions                     → mission catalog (inputs only)
- POST /security-missions/{mission_id}/run    → run THAT mission only
- POST /security-missions/suite                → the full 22-scenario suite
                                                 (explicitly separate action)
- GET  /security-missions/trace/{trace_id}/replay → read-only movie replay

Every mission runs through the ONE orchestration in security_missions.py
(create -> mutate -> execute -> observe). Clicking Price Drift runs the
price-drift mission, never the whole suite. The movie renders from trace
events only (G017).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from razormesh_api.evaluation import AdversarialRunner
from razormesh_api.persistence.db import create_db_engine, create_session_factory
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.security_missions import (
    MissionError,
    mission_catalog,
    replay_mission_trace,
    run_mission,
)
from razormesh_api.settings import Settings, get_settings

router = APIRouter(prefix="/security-missions", tags=["phase5-security-missions"])


def _repos(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Repositories:
    return Repositories(create_session_factory(create_db_engine(settings.database_url)))


class RunRequest(BaseModel):
    product_id: str | None = Field(default=None, min_length=6, max_length=64)
    quantity: int = Field(default=1, ge=1, le=2)
    # G015/G019: bind the mission to the CURRENT live trace's intent.
    intent_id: str | None = Field(default=None, pattern=r"^intent_[0-9A-HJKMNP-TV-Z]{26}$")


@router.get("")
def catalog() -> dict[str, Any]:
    return {"missions": mission_catalog()}


@router.post("/{mission_id}/run")
def run_one(
    mission_id: str,
    repos: Annotated[Repositories, Depends(_repos)],
    body: RunRequest | None = None,
) -> dict[str, Any]:
    """Run ONE mission only (G016)."""
    request = body or RunRequest()
    try:
        return run_mission(
            repos,
            mission_id=mission_id,
            product_id=request.product_id,
            quantity=request.quantity,
            intent_id=request.intent_id,
        )
    except MissionError as exc:
        status = {"UNKNOWN_MISSION": 404, "NO_PRODUCTS": 409, "BAD_RECIPE": 500}.get(exc.code, 400)
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "detail": exc.detail}
        ) from exc


@router.post("/suite")
def run_suite(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """The FULL 22-scenario suite — a separate explicit action (G016)."""
    runner = AdversarialRunner(create_db_engine(settings.database_url))
    results = [
        {
            "scenario_id": res.scenario_id,
            "family": res.family.value,
            "actual": res.actual,
            "passed": res.passed,
            "detail": res.detail,
            "amount_minor": res.amount_minor,
        }
        for res in runner.run_all()
    ]
    return {
        "note": "Full synthetic red-team suite (22 scenarios, mock provider).",
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "results": results,
    }


@router.get("/trace/{trace_id}/replay")
def trace_replay(
    trace_id: str,
    repos: Annotated[Repositories, Depends(_repos)],
) -> dict[str, Any]:
    """Read-only mission-movie replay from stored trace events (G017/G022)."""
    try:
        return replay_mission_trace(repos, trace_id)
    except MissionError as exc:
        raise HTTPException(
            status_code=404, detail={"code": exc.code, "detail": exc.detail}
        ) from exc
