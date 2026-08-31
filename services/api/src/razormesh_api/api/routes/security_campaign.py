"""Phase-5 (M074-M077): AgentPay-X campaign API.

- GET /security-campaign/summary  → canonical benchmark counters (rates)
- GET /security-campaign/families → attack taxonomy from the real registry
- GET /security-campaign/cases?family=&outcome= → filterable case explorer
- GET /security-campaign/case/{id}/replay → read-only stage replay

The campaign runs the CANONICAL benchmark engine, unmodified. The pytest
gate remains the authoritative run; counters here are run_benchmark()'s own.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from razormesh_api.security_campaign import (
    attack_families,
    campaign_cases,
    campaign_summary,
    case_replay,
)

router = APIRouter(prefix="/security-campaign", tags=["phase5-security"])


@router.get("/summary")
def summary() -> dict[str, Any]:
    return campaign_summary()


@router.get("/families")
def families() -> dict[str, Any]:
    return {"families": attack_families()}


@router.get("/cases")
def cases(
    family: str | None = None,
    outcome: str | None = Query(default=None, pattern="^(ALLOW|CHALLENGE|BLOCK)$"),
) -> dict[str, Any]:
    items = campaign_cases(family=family, outcome=outcome)
    return {"count": len(items), "cases": items}


@router.get("/case/{scenario_id}/replay")
def replay(scenario_id: str) -> dict[str, Any]:
    try:
        result = case_replay(scenario_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown scenario") from None
    return result
