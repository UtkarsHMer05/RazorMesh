"""M11 acceptance: /health process health vs /ready dependency readiness."""

from typing import Any

from fastapi.testclient import TestClient


def test_health_reports_process_ok(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "time_utc" in body


def test_openapi_generates(client: TestClient) -> None:
    res = client.get("/openapi.json")
    assert res.status_code == 200
    schema: dict[str, Any] = res.json()
    assert "/health" in schema["paths"]
    assert "/ready" in schema["paths"]


def test_ready_ok_when_infra_available(client: TestClient) -> None:
    res = client.get("/ready")
    if res.status_code == 503:
        raise AssertionError(f"expected ready when infra is up: {res.json()}")
    body = res.json()
    assert body["status"] == "ok"
    assert body["checks"]["postgres"] == "ok"
    assert body["checks"]["redis"] == "ok"
    # Phase-1 honesty: readiness must advertise the mock provider.
    assert body["mock_payment_provider"] is True


def test_ready_fails_closed_when_redis_unavailable(client: TestClient, settings: Any) -> None:
    broken = settings.model_copy(update={"redis_url": "redis://127.0.0.1:1/0"})

    from razormesh_api import api as api_pkg

    def _broken_settings() -> Any:
        return broken

    client.app.dependency_overrides[api_pkg.main.get_settings] = _broken_settings  # type: ignore[attr-defined]
    try:
        res = client.get("/ready")
    finally:
        client.app.dependency_overrides.pop(api_pkg.main.get_settings, None)  # type: ignore[attr-defined]
    assert res.status_code == 503
    body = res.json()["detail"]
    assert body["status"] == "degraded"
    assert body["checks"]["postgres"] == "ok"
    assert body["checks"]["redis"].startswith("unavailable")


def test_ready_fails_closed_when_db_unavailable(client: TestClient, settings: Any) -> None:
    broken = settings.model_copy(
        update={"database_url": "postgresql+psycopg://x:y@127.0.0.1:1/none"}
    )

    from razormesh_api import api as api_pkg

    def _broken_settings() -> Any:
        return broken

    client.app.dependency_overrides[api_pkg.main.get_settings] = _broken_settings  # type: ignore[attr-defined]
    try:
        res = client.get("/ready")
    finally:
        client.app.dependency_overrides.pop(api_pkg.main.get_settings, None)  # type: ignore[attr-defined]
    assert res.status_code == 503
    body = res.json()["detail"]
    assert body["status"] == "degraded"
    assert body["checks"]["postgres"].startswith("unavailable")
