"""F012: DEMO PREFLIGHT — presenter-only readiness check.

Real, lightweight probes of every component the video depends on. No secrets
are exposed: each probe reports ready/not-ready plus a short public label.
The optional AI-compiler warm-up performs a NON-AUTHORITATIVE health request
(the provider's own model list) so the 60-75s first-compile does not ruin the
video — it never compiles or fabricates the owner's mandate.
"""

from __future__ import annotations

import time
from typing import Any

from razormesh_api.settings import get_settings


def _probe_postgres() -> dict[str, Any]:
    try:
        from sqlalchemy import create_engine, text

        settings = get_settings()
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        started = time.monotonic()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return {
            "component": "PostgreSQL",
            "ready": True,
            "detail": "durable authority reachable (SELECT 1)",
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
        }
    except Exception as exc:  # noqa: BLE001 - honest not-ready, never a crash
        return {"component": "PostgreSQL", "ready": False, "detail": f"{type(exc).__name__}"}


def _probe_redis() -> dict[str, Any]:
    try:
        import redis

        settings = get_settings()
        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        started = time.monotonic()
        client.ping()
        client.close()
        return {
            "component": "Redis",
            "ready": True,
            "detail": "coordination store reachable (PING)",
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
        }
    except Exception as exc:  # noqa: BLE001
        return {"component": "Redis", "ready": False, "detail": f"{type(exc).__name__}"}


def _probe_intent_compiler(warm_up: bool) -> dict[str, Any]:
    """Compiler configuration presence + optional NON-AUTHORITATIVE warm-up.

    The warm-up hits the provider's model-list endpoint (no mandate text, no
    draft, no fabricated result) so the first real compile is faster. It never
    claims the owner's real mandate result.
    """
    settings = get_settings()
    if not settings.tokenrouter_credentials_present:
        return {
            "component": "AI Intent Compiler",
            "ready": False,
            "detail": "compiler credentials not configured",
        }
    detail = "configured (TokenRouter credentials present)"
    latency_ms: float | None = None
    if warm_up:
        try:
            from razormesh_api.intent_compiler import build_tokenrouter_client

            started = time.monotonic()
            client = build_tokenrouter_client(settings)
            try:
                client.list_models()  # non-authoritative provider health request
            finally:
                client.close()
            latency_ms = round((time.monotonic() - started) * 1000, 1)
            detail = "configured + warm-up request completed (non-authoritative)"
        except Exception as exc:  # noqa: BLE001 - warm-up is best-effort
            detail = f"configured; warm-up skipped ({type(exc).__name__})"
    return {
        "component": "AI Intent Compiler",
        "ready": True,
        "detail": detail,
        "latency_ms": latency_ms,
    }


def _probe_semantic_model() -> dict[str, Any]:
    try:
        from razormesh_api.semantic_runtime import (
            MODEL_DIR,
            POLICY_PATH,
            get_semantic_verifier,
            resolve_repo_path,
        )

        model_dir = resolve_repo_path(MODEL_DIR)
        if not (model_dir / "model.safetensors").exists():
            return {
                "component": "Active Semantic Model",
                "ready": False,
                "detail": "active PRE_V2 artifact not present at configured path",
            }
        verifier = get_semantic_verifier(
            model_dir=model_dir, policy_path=resolve_repo_path(POLICY_PATH)
        )
        return {
            "component": "Active Semantic Model",
            "ready": True,
            "detail": f"{verifier.model_version} · policy {verifier.policy_version}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "component": "Active Semantic Model",
            "ready": False,
            "detail": f"{type(exc).__name__}: unable to load",
        }


def _probe_challenger_shadow() -> dict[str, Any]:
    try:
        from razormesh_api.challenger_shadow import get_challenger_shadow

        shadow = get_challenger_shadow()
        if shadow.available:
            return {
                "component": "V2 Challenger Shadow",
                "ready": True,
                "detail": (
                    f"real v2 artifact loaded (candidate {shadow._candidate or 'A_2ep'},"
                    " shadow-only)"
                ),
            }
        return {
            "component": "V2 Challenger Shadow",
            "ready": False,
            "detail": (
                "Verified model artifact not present at configured path — "
                "shadow lane unavailable (honest absence)"
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "component": "V2 Challenger Shadow",
            "ready": False,
            "detail": f"{type(exc).__name__}: probe failed",
        }


def _probe_protocol_keys() -> dict[str, Any]:
    try:
        from razormesh_api.keys import default_from_settings

        keys = default_from_settings()
        if keys.both_present:
            return {
                "component": "Protocol keys",
                "ready": True,
                "detail": "dev Ed25519 signing pair present",
            }
        return {
            "component": "Protocol keys",
            "ready": False,
            "detail": "dev signing keys missing (will be generated on first use)",
        }
    except Exception as exc:  # noqa: BLE001
        return {"component": "Protocol keys", "ready": False, "detail": f"{type(exc).__name__}"}


def _probe_audit_chain() -> dict[str, Any]:
    try:
        from sqlalchemy import create_engine

        from razormesh_api.ledger import EvidenceLedger
        from razormesh_api.persistence.db import create_session_factory
        from razormesh_api.persistence.repositories import Repositories

        settings = get_settings()
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        repos = Repositories(create_session_factory(engine))
        report = EvidenceLedger(repos).verify()
        engine.dispose()
        return {
            "component": "Audit chain",
            "ready": bool(report.valid),
            "detail": (
                f"global hash chain valid over {report.events_checked} events"
                if report.valid
                else f"CHAIN BROKEN at event {report.broken_at_event_id}"
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {"component": "Audit chain", "ready": False, "detail": f"{type(exc).__name__}"}


def _payment_environment() -> dict[str, Any]:
    settings = get_settings()
    if settings.payment_provider == "razorpay":
        label = (
            "RAZORPAY TEST MODE"
            if settings.razorpay_credentials_present
            else "RAZORPAY TEST (credentials incomplete)"
        )
    else:
        label = "LOCAL / MOCK"
    return {
        "component": "Payment environment",
        "ready": True,  # the configured environment is itself the truth
        "detail": label,
        "environment": label,
    }


def run_preflight(*, warm_up_compiler: bool = False) -> dict[str, Any]:
    """Execute all probes and return the readiness report."""
    checks = [
        _probe_postgres(),
        _probe_redis(),
        _probe_intent_compiler(warm_up_compiler),
        _probe_semantic_model(),
        _probe_challenger_shadow(),
        _probe_protocol_keys(),
        _probe_audit_chain(),
        _payment_environment(),
    ]
    return {
        "label": "DEMO PREFLIGHT",
        "checks": checks,
        "all_ready": all(c["ready"] for c in checks),
        "secrets_exposed": False,
        "note": (
            "Lightweight live probes only. No secrets, no mandate compilation, "
            "no fabricated results. The payment environment line states which "
            "environment traces execute in so a local security mission is "
            "never presented as a live provider transaction."
        ),
    }
