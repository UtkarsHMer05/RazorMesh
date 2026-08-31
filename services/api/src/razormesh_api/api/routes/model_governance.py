"""Phase-5 (M091-M094) + correction G003: Model Governance API.

- GET /model-governance          → active vs challenger summary (committed facts)
- GET /model-governance/evidence → committed frozen evaluation (redacted-safe)
- POST /model-governance/shadow  → REAL v2 challenger shadow (NON-AUTHORITATIVE)

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
    """Canonical NLI orientation (F002): premise = CURRENT COMMERCE EVIDENCE,
    hypothesis = HUMAN-CONFIRMED AUTHORIZATION. The legacy field pair keeps
    working for existing callers, but new callers should send
    commerce_evidence/authorization which cannot be transposed by accident."""

    commerce_evidence: str | None = Field(default=None, min_length=4, max_length=512)
    authorization: str | None = Field(default=None, min_length=4, max_length=400)
    premise: str | None = Field(default=None, min_length=4, max_length=512)
    hypothesis: str | None = Field(default=None, min_length=4, max_length=400)


@router.post("/shadow")
def shadow(body: ShadowRequest) -> dict[str, Any]:
    evidence = body.commerce_evidence if body.commerce_evidence is not None else body.premise
    authorization = body.authorization if body.authorization is not None else body.hypothesis
    return shadow_verdict(evidence, authorization=authorization)
