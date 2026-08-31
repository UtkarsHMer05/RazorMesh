"""Phase-5 (M046-M061): Protocol Playground API.

- GET  /protocol-playground/protocols   → supported protocol slices
- GET  /protocol-playground/mutations    → bounded mutation inputs
- POST /protocol-playground/run         → run a packet through the REAL engines
- GET  /protocol-playground/cross        → cross-protocol view (optional ?diverge=)
- POST /protocol-playground/scenario-c   → live orchestrator protocol-valid/
                                            intent-invalid proof (D-056 pattern)

All outcomes are computed by the real firewall/IR/consistency/orchestrator —
never preset constants.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from razormesh_api.protocol_playground import (
    MUTATIONS,
    SUPPORTED_PROTOCOLS,
    PacketSpec,
    PlaygroundError,
    cross_protocol_view,
    mutations_catalog,
    protocols_catalog,
    run_packet,
)

router = APIRouter(prefix="/protocol-playground", tags=["phase5-protocols"])


class RunRequest(BaseModel):
    protocol: str = Field(min_length=3, max_length=8)
    mutation: str = Field(default="none", min_length=2, max_length=32)


@router.get("/protocols")
def protocols() -> dict[str, Any]:
    return {"protocols": protocols_catalog()}


@router.get("/mutations")
def mutations() -> dict[str, Any]:
    return {"mutations": mutations_catalog()}


@router.post("/run")
def run(body: RunRequest) -> dict[str, Any]:
    if body.protocol not in SUPPORTED_PROTOCOLS:
        raise HTTPException(status_code=404, detail=f"unsupported protocol {body.protocol}")
    if body.mutation not in MUTATIONS:
        raise HTTPException(status_code=404, detail=f"unsupported mutation {body.mutation}")
    try:
        return run_packet(PacketSpec(protocol=body.protocol, mutation=body.mutation))
    except PlaygroundError as exc:
        raise HTTPException(
            status_code=422, detail={"code": exc.code, "detail": exc.detail}
        ) from exc


@router.get("/cross")
def cross(diverge: str | None = None) -> dict[str, Any]:
    if diverge is not None and diverge not in SUPPORTED_PROTOCOLS:
        raise HTTPException(status_code=404, detail=f"unsupported protocol {diverge}")
    return cross_protocol_view(diverge_protocol=diverge)


@router.post("/scenario-c")
def scenario_c() -> dict[str, Any]:
    """Live-orchestrator proof: protocol PASS + final BLOCK + provider 0.

    Reuses the owner-accepted D-056 demo scenario endpoint logic so the
    playground thesis runs the REAL end-to-end pipeline (DeBERTa in the loop).
    """
    from razormesh_api.api.routes.phase4_acceptance import (
        demo_scenario_c_protocol_valid_intent_invalid,
    )

    return demo_scenario_c_protocol_valid_intent_invalid()
