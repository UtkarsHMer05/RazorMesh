"""FastAPI application entrypoint: process health vs dependency readiness."""

import os
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from redis import Redis
from sqlalchemy import text
from sqlalchemy.engine import Engine

from razormesh_api.api.routes.audit import router as audit_router
from razormesh_api.api.routes.buyer import router as buyer_router
from razormesh_api.api.routes.buyer_drafts import router as buyer_drafts_router
from razormesh_api.api.routes.catalog import router as catalog_router
from razormesh_api.api.routes.ops import router as ops_router
from razormesh_api.api.routes.phase4_acceptance import router as phase4_acceptance_router
from razormesh_api.api.routes.security_lab import router as security_lab_router
from razormesh_api.api.routes.webhooks import router as webhooks_router
from razormesh_api.protocol.ap2_verifier import (
    AP2_TARGET_VERSION,
    export_ap2_test_merchant_pub_jwk,
    generate_ap2_test_merchant_key,
)
from razormesh_api.protocol.mcp_server import mount_mcp
from razormesh_api.protocol.ucp_adapter import (
    RMA_UCP_PROFILE,
    UCP_PROFILE_PATH,
    UCP_TARGET_VERSION,
)
from razormesh_api.settings import Settings, get_settings

app = FastAPI(
    title="RazorMesh Trust API",
    version="0.1.0",
    description=(
        "Phase-2 trust core: Razorpay Test Mode payments through the trusted "
        "executor; MockPaymentProvider remains for local tests/fault injection."
    ),
)

app.include_router(catalog_router)
app.include_router(webhooks_router)
app.include_router(buyer_router)
app.include_router(buyer_drafts_router)
app.include_router(audit_router)
app.include_router(security_lab_router)
app.include_router(ops_router)
app.include_router(phase4_acceptance_router)

settings_dep = Annotated[Settings, Depends(get_settings)]

# Dev-only CORS to the local frontend origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().web_origin],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _get_engine(settings: settings_dep) -> Engine:
    from razormesh_api.persistence.db import create_db_engine

    return create_db_engine(settings.database_url)


def _get_redis(settings: settings_dep) -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


class HealthBody(BaseModel):
    status: str
    time_utc: str


class ReadyBody(BaseModel):
    status: str
    checks: dict[str, str]
    payment_provider: str
    mock_payment_provider: bool


@app.get("/health", response_model=HealthBody)
def health() -> HealthBody:
    """Process health: this service is running. Says nothing about dependencies."""
    return HealthBody(status="ok", time_utc=datetime.now(UTC).isoformat())


@app.get("/ready", response_model=ReadyBody)
def ready(
    engine: Annotated[Engine, Depends(_get_engine)],
    redis_client: Annotated[Redis, Depends(_get_redis)],
    settings: settings_dep,
) -> ReadyBody:
    """Dependency readiness: PostgreSQL and Redis must answer.

    Fails closed (503) when a security-relevant dependency is unavailable,
    because authorization/nonce coordination cannot safely proceed. Reports
    the provider selector actually loaded from settings (Phase 2), so
    operators can distinguish mock from Razorpay Test Mode at a glance.
    """
    checks: dict[str, str] = {}
    overall_ok = True

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:  # noqa: BLE001 - readiness must classify any failure
        checks["postgres"] = f"unavailable: {type(exc).__name__}"
        overall_ok = False

    try:
        pong = redis_client.ping()
        checks["redis"] = "ok" if pong else "unavailable: no pong"
        overall_ok = overall_ok and bool(pong)
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"unavailable: {type(exc).__name__}"
        overall_ok = False

    body = ReadyBody(
        status="ok" if overall_ok else "degraded",
        checks=checks,
        payment_provider=settings.payment_provider,
        mock_payment_provider=settings.payment_provider == "mock",
    )
    if not overall_ok:
        raise HTTPException(status_code=503, detail=body.model_dump())
    return body


# Phase-4 live cross-protocol ingress (M48..M50 + live-ingress closure).
# The MCP 2026-07-28 server is mounted at /mcp using the modern
# Streamable HTTP transport. UCP 2026-04-08 and AP2 v0.2.0 are exposed
# as discovery endpoints; the actual verifiers run during the
# /phase4/acceptance/prepare orchestrator path.
#
# We skip the MCP mount when running under TestClient / unit tests so
# the SDK's once-per-instance session manager rule doesn't conflict
# across reused app instances. Tests that need MCP mount the
# live-ingress E2E fixture instead.
if os.environ.get("RAZORMESH_MCP_MOUNT", "1") != "0":
    mount_mcp(app, base_path="/mcp-mount")


@app.get(UCP_PROFILE_PATH, include_in_schema=False)
def ucp_well_known() -> dict[str, object]:
    """UCP 2026-04-08 well-known profile + discovery."""
    return dict(RMA_UCP_PROFILE)


@app.get("/ucp/profile", include_in_schema=False)
def ucp_profile() -> dict[str, object]:
    """UCP 2026-04-08 profile (alternate path)."""
    return dict(RMA_UCP_PROFILE)


@app.get("/ucp/version", include_in_schema=False)
def ucp_version() -> dict[str, str]:
    """Return the pinned UCP target version."""
    return {"version": UCP_TARGET_VERSION}


@app.get("/ap2/jwks", include_in_schema=False)
def ap2_jwks() -> dict[str, object]:
    """AP2 v0.2.0 test merchant JWK set.

    The key is generated fresh per process. Real AP2 verification uses
    the test merchant key bound to the acceptance-run orchestrator.
    """
    key = generate_ap2_test_merchant_key()
    jwk = export_ap2_test_merchant_pub_jwk(key, kid="razormesh-ap2-test-merchant")
    return {
        "ap2_version": AP2_TARGET_VERSION,
        "keys": [jwk],
    }


@app.get("/ap2/version", include_in_schema=False)
def ap2_version() -> dict[str, str]:
    """Return the pinned AP2 target version."""
    return {"version": AP2_TARGET_VERSION}
