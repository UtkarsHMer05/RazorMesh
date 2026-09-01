"""F012 + S003: DEMO PREFLIGHT — presenter-only, AUTHORITATIVE readiness check.

Real, lightweight probes of every component the video depends on. The
precondition contract (master prompt S003):
- RAZORPAY mode calls the REAL validate_payment_provider_config; incomplete
  config → NOT READY (never a blanket green);
- the AI Intent Compiler distinguishes CONFIGURED from LIVE REACHABLE — with
  warm_up=true a failed live probe is NOT READY, not "credentials exist";
- the optional v2 challenger NEVER gates the required systems: its absence is
  reported as OPTIONAL DEMO CAPABILITY UNAVAILABLE;
- the Ed25519 dev pair is labeled ExecutionTicket signing keys (they mint
  tickets — they are NOT the UCP/AP2 protocol ES256 flows), and a separate
  Protocol crypto line states the real per-protocol verification capability;
- the audit probe actually verifies the global chain;
- no secrets are exposed: each probe reports ready/not-ready plus a short
  public label.
"""

from __future__ import annotations

import time
from typing import Any

from razormesh_api.settings import get_settings


def _required(component: str, ready: bool, detail: str, **extra: Any) -> dict[str, Any]:
    return {"component": component, "ready": ready, "detail": detail, "required": True, **extra}


def _optional(component: str, ready: bool, detail: str, **extra: Any) -> dict[str, Any]:
    return {"component": component, "ready": ready, "detail": detail, "required": False, **extra}


def _probe_postgres() -> dict[str, Any]:
    try:
        from sqlalchemy import create_engine, text

        settings = get_settings()
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        started = time.monotonic()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return _required(
            "PostgreSQL",
            True,
            "durable authority reachable (SELECT 1)",
            latency_ms=round((time.monotonic() - started) * 1000, 1),
        )
    except Exception as exc:  # noqa: BLE001 - honest not-ready, never a crash
        return _required("PostgreSQL", False, f"{type(exc).__name__}")


def _probe_redis() -> dict[str, Any]:
    try:
        import redis

        settings = get_settings()
        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        started = time.monotonic()
        client.ping()
        client.close()
        return _required(
            "Redis",
            True,
            "coordination store reachable (PING)",
            latency_ms=round((time.monotonic() - started) * 1000, 1),
        )
    except Exception as exc:  # noqa: BLE001
        return _required("Redis", False, f"{type(exc).__name__}")


def _probe_payment_provider() -> dict[str, Any]:
    """S003: the REAL config validator, not an optimistic label."""
    from razormesh_api.settings import validate_payment_provider_config

    settings = get_settings()
    try:
        validate_payment_provider_config(settings)
    except Exception as exc:  # noqa: BLE001 - validator problems list is the truth
        problems = getattr(exc, "problems", None) or [str(exc)]
        label = (
            "RAZORPAY TEST MODE — NOT READY"
            if settings.payment_provider == "razorpay"
            else "LOCAL / MOCK — CONFIG INVALID"
        )
        return _required(
            "Payment environment",
            False,
            f"{label} ({'; '.join(problems)})",
            environment=label,
        )
    if settings.payment_provider == "razorpay":
        label = "RAZORPAY TEST MODE"
        detail = (
            "provider config validated: test-mode key format, key id + secret + "
            "webhook secret present, official API endpoint"
        )
    else:
        label = "LOCAL / MOCK"
        detail = "mock provider selected — no provider credentials required"
    return _required(
        "Payment environment",
        True,
        detail,
        environment=label,
    )


def _probe_intent_compiler(warm_up: bool) -> dict[str, Any]:
    """S003: CONFIGURED vs LIVE REACHABLE.

    warm_up=False → CONFIGURED / NOT PROBED is an honest state.
    warm_up=True → a failed live health request is NOT READY, never "credentials
    exist". Never exposes the key or response bodies.
    """
    settings = get_settings()
    if not settings.tokenrouter_credentials_present:
        return _required(
            "AI Intent Compiler",
            False,
            "not configured — TokenRouter credentials absent (live AI compilation "
            "unavailable; deterministic stack unaffected)",
        )
    if not warm_up:
        return _required(
            "AI Intent Compiler",
            True,
            "CONFIGURED / NOT PROBED (run warm-up for a live reachability check)",
        )
    try:
        from razormesh_api.intent_compiler import build_tokenrouter_client

        started = time.monotonic()
        client = build_tokenrouter_client(settings)
        try:
            client.list_models()  # non-authoritative provider health request
        finally:
            client.close()
        return _required(
            "AI Intent Compiler",
            True,
            "LIVE REACHABLE — provider health request succeeded (non-authoritative)",
            latency_ms=round((time.monotonic() - started) * 1000, 1),
        )
    except Exception as exc:  # noqa: BLE001 - live probe failed → NOT READY
        return _required(
            "AI Intent Compiler",
            False,
            f"CONFIGURED but NOT LIVE REACHABLE — health request failed ({type(exc).__name__})",
        )


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
            return _required(
                "Active Semantic Model",
                False,
                "active PRE_V2 artifact not present at configured path",
            )
        policy_path = resolve_repo_path(POLICY_PATH)
        if not policy_path.exists():
            return _required(
                "Active Semantic Model",
                False,
                "semantic policy file not present at configured path",
            )
        verifier = get_semantic_verifier(model_dir=model_dir, policy_path=policy_path)
        return _required(
            "Active Semantic Model",
            True,
            f"verifier loads: {verifier.model_version} · policy {verifier.policy_version}",
        )
    except Exception as exc:  # noqa: BLE001
        return _required(
            "Active Semantic Model",
            False,
            f"{type(exc).__name__}: unable to load",
        )


def _probe_challenger_shadow() -> dict[str, Any]:
    """OPTIONAL: the rejected v2 shadow is useful for the video but never gates
    payment safety."""
    try:
        from razormesh_api.challenger_shadow import get_challenger_shadow

        shadow = get_challenger_shadow()
        if shadow.available:
            return _optional(
                "V2 Challenger Shadow",
                True,
                f"real v2 artifact loaded (candidate {shadow._candidate or 'A_2ep'}, shadow-only)",
            )
        return _optional(
            "V2 Challenger Shadow",
            False,
            "CHALLENGER UNAVAILABLE — verified model artifact not present at "
            "the configured path (optional demo capability; payment safety "
            "does not depend on it)",
        )
    except Exception as exc:  # noqa: BLE001
        return _optional(
            "V2 Challenger Shadow",
            False,
            f"CHALLENGER UNAVAILABLE ({type(exc).__name__}) — optional demo capability",
        )


def _probe_ticket_signing_keys() -> dict[str, Any]:
    """S003: these Ed25519 keys mint ExecutionTickets — labeled correctly
    (they are NOT the UCP/AP2 protocol ES256 flows)."""
    try:
        from razormesh_api.keys import default_from_settings

        keys = default_from_settings()
        if keys.both_present:
            return _required(
                "ExecutionTicket signing keys",
                True,
                "dev Ed25519 signing pair present (mints the context-bound tickets)",
            )
        return _required(
            "ExecutionTicket signing keys",
            False,
            "dev signing keys missing (would be generated on first use)",
        )
    except Exception as exc:  # noqa: BLE001
        return _required(
            "ExecutionTicket signing keys", False, f"{type(exc).__name__}"
        )


def _probe_protocol_crypto() -> dict[str, Any]:
    """S003: real per-protocol verification capability, truthfully labeled."""
    try:
        from razormesh_api.protocol.ap2_verifier import generate_ap2_test_merchant_key
        from razormesh_api.protocol.ucp_signatures import generate_ucp_signing_key

        generate_ucp_signing_key()
        generate_ap2_test_merchant_key()
        return _required(
            "Protocol crypto",
            True,
            "UCP RFC 9421 / RFC 9530 READY · AP2 ES256 READY · "
            "MCP/ACP/A2A binding evidence only",
        )
    except Exception as exc:  # noqa: BLE001
        return _required(
            "Protocol crypto",
            False,
            f"crypto self-test failed ({type(exc).__name__})",
        )


def _probe_audit_chain() -> dict[str, Any]:
    """S003: actually verify the global chain."""
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
        return _required(
            "Audit chain",
            bool(report.valid),
            (
                f"global hash chain verified valid over {report.events_checked} events"
                if report.valid
                else f"CHAIN BROKEN at event {report.broken_at_event_id} ({report.reason})"
            ),
        )
    except Exception as exc:  # noqa: BLE001
        return _required("Audit chain", False, f"{type(exc).__name__}")


def run_preflight(*, warm_up_compiler: bool = False) -> dict[str, Any]:
    """Execute all probes and return the authoritative readiness report."""
    checks = [
        _probe_postgres(),
        _probe_redis(),
        _probe_payment_provider(),
        _probe_intent_compiler(warm_up_compiler),
        _probe_semantic_model(),
        _probe_ticket_signing_keys(),
        _probe_protocol_crypto(),
        _probe_audit_chain(),
        _probe_challenger_shadow(),
    ]
    required = [c for c in checks if c["required"]]
    optional = [c for c in checks if not c["required"]]
    required_ready = all(c["ready"] for c in required)
    optional_unavailable = [c["component"] for c in optional if not c["ready"]]
    return {
        "label": "DEMO PREFLIGHT",
        "checks": checks,
        # S003: required systems gate the recording; the optional challenger
        # never does. No misleading blanket green.
        "required_systems_ready": required_ready,
        "all_ready": required_ready and all(c["ready"] for c in optional),
        "optional_unavailable": optional_unavailable,
        "state": (
            "REQUIRED SYSTEMS READY"
            + (
                f" — OPTIONAL DEMO CAPABILITY UNAVAILABLE: {', '.join(optional_unavailable)}"
                if optional_unavailable and required_ready
                else ""
            )
            if required_ready
            else "NOT READY — FIX BEFORE RECORDING"
        ),
        "secrets_exposed": False,
        "note": (
            "Authoritative lightweight probes: the Razorpay lane runs the real "
            "config validator; the compiler distinguishes CONFIGURED from LIVE "
            "REACHABLE (warm-up performs a non-authoritative health request only); "
            "the optional v2 challenger never gates payment safety; the audit "
            "probe verifies the global chain. No secrets, no mandate compilation, "
            "no fabricated results."
        ),
    }
