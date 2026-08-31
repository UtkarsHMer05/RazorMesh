"""Phase-5 (M025/M026): Shopping Agent search API — real fetch/filter/rank/propose.

The agent READS the confirmed mandate; it never mutates authority. Ranking is
deterministic and explainable; every count is computed from real catalog rows.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from razormesh_api.agent_search import SearchError, rank_catalog_for_intent
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.persistence.db import create_db_engine, create_session_factory
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.settings import Settings, get_settings

router = APIRouter(prefix="/agent", tags=["phase5-agent"])


def _repos(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Repositories:
    return Repositories(create_session_factory(create_db_engine(settings.database_url)))


class SearchQuery(BaseModel):
    intent_id: str = Field(min_length=6, max_length=64)
    quantity: int = Field(default=1, ge=1, le=10)
    limit: int = Field(default=5, ge=1, le=10)


@router.post("/search")
def search(
    body: SearchQuery,
    repos: Annotated[Repositories, Depends(_repos)],
) -> dict[str, Any]:
    try:
        report = rank_catalog_for_intent(
            repos,
            body.intent_id,
            quantity=body.quantity,
            limit=body.limit,
        )
    except SearchError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Real trace evidence for the Shopping Agent activity panel (M025):
    # an audit event recording the search the agent actually performed.
    try:
        ledger = EvidenceLedger(repos)
        ledger.append(
            event_type="AGENT_SEARCH_COMPLETED",
            actor="shopping-agent",
            intent_id=report.intent_id,
            payload={
                "inspected": report.inspected,
                "eligible": report.eligible,
                "rejected": report.rejected,
                "top_product_id": report.candidates[0].product_id if report.candidates else None,
            },
        )
    except Exception:  # noqa: BLE001, S110 - evidence append must not break search
        pass

    return {
        "intent_id": report.intent_id,
        "inspected": report.inspected,
        "eligible": report.eligible,
        "rejected": report.rejected,
        "candidates": [c.__dict__ for c in report.candidates],
        "rejected_samples": [r.__dict__ for r in report.rejected_samples],
    }
