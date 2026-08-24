"""FastAPI application entrypoint: process health vs dependency readiness."""

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
from razormesh_api.api.routes.catalog import router as catalog_router
from razormesh_api.api.routes.security_lab import router as security_lab_router
from razormesh_api.settings import Settings, get_settings

app = FastAPI(
    title="RazorMesh Trust API",
    version="0.1.0",
    description="Phase-1 local trust core. All payments are simulated via MockPaymentProvider.",
)

app.include_router(catalog_router)
app.include_router(buyer_router)
app.include_router(audit_router)
app.include_router(security_lab_router)

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
    mock_payment_provider: bool


@app.get("/health", response_model=HealthBody)
def health() -> HealthBody:
    """Process health: this service is running. Says nothing about dependencies."""
    return HealthBody(status="ok", time_utc=datetime.now(UTC).isoformat())


@app.get("/ready", response_model=ReadyBody)
def ready(
    engine: Annotated[Engine, Depends(_get_engine)],
    redis_client: Annotated[Redis, Depends(_get_redis)],
) -> ReadyBody:
    """Dependency readiness: PostgreSQL and Redis must answer.

    Fails closed (503) when a security-relevant dependency is unavailable,
    because authorization/nonce coordination cannot safely proceed.
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
        mock_payment_provider=True,
    )
    if not overall_ok:
        raise HTTPException(status_code=503, detail=body.model_dump())
    return body
