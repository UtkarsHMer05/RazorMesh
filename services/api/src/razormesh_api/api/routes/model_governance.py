"""Phase-5 (M091-M094): Model Governance API.

- GET /model-governance          → active vs challenger summary (committed facts)
- GET /model-governance/evidence → committed frozen evaluation (redacted-safe)
- POST /model-governance/shadow  → NON-AUTHORITATIVE demo shadow (test stub)

Read-only, never reruns frozen evaluation, never recalibrates, never feeds
fusion/tickets/provider.
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from razormesh_api.model_governance import (
    governance_summary,
    load_committed_metrics,
    shadow_verdict,
)

router = APIRouter(prefix="/model-governance", tags=["phase5-governance"])


@router.get("")
def summary() -> dict[str, Any]:
    return governance_summary()


@router.get("/evidence")
def evidence() -> dict[str, Any]:
    return {"committed": load_committed_metrics()}


class ShadowRequest(BaseModel):
    hypothesis: str = Field(min_length=4, max_length=400)


@router.post("/shadow")
def shadow(body: ShadowRequest) -> dict[str, Any]:
    return shadow_verdict(body.hypothesis)
