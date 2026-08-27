"""Shared pytest fixtures. Integration tests use the local Docker infrastructure."""

import os

# P2-M38 (test isolation, hard): the suite must NEVER see the developer's real
# environment. Many test modules call `razormesh_api.settings.get_settings()`
# directly, which reads the root `.env` (dev DB URL, PAYMENT_PROVIDER=razorpay,
# real Test credentials). Pinning these variables HERE — before any
# razormesh_api import — makes env vars win over dotenv (pydantic-settings
# precedence: init kwargs > env vars > .env), so every Settings constructed
# anywhere in the suite targets the DEDICATED razormesh_test database with the
# mock provider and no Razorpay credentials (P2-S20). A pre-isolation pytest
# run (2026-08-24) reached the dev DB through this hole and wiped business
# tables, destroying real Test Mode payment evidence; this block plus the
# session guard below makes that class of loss impossible.
os.environ["DATABASE_URL"] = os.environ.get(
    "RAZORMESH_TEST_DATABASE_URL",
    "postgresql+psycopg://razormesh:razormesh_local_dev@127.0.0.1:15432/razormesh_test",
)
os.environ["REDIS_URL"] = os.environ.get("RAZORMESH_TEST_REDIS_URL", "redis://127.0.0.1:16379/0")
os.environ["PAYMENT_PROVIDER"] = "mock"
os.environ["MOCK_PAYMENT_PROVIDER"] = "true"
# Phase-4 live-ingress closure: skip the MCP mount at import time so
# the SDK's once-per-instance session manager rule doesn't conflict
# across reused TestClient lifespans. The live-ingress E2E suite
# enables it explicitly for its own server.
os.environ.setdefault("RAZORMESH_MCP_MOUNT", "0")
# Pinned to EMPTY STRINGS, not popped: an absent env var would let the root
# .env dotenv values (real Test credentials) through, and env vars take
# precedence over dotenv. Empty => razorpay_credentials_present is False.
for _secret_name in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET"):
    os.environ[_secret_name] = ""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from razormesh_api.api.main import app
from razormesh_api.settings import Settings, get_settings


def wipe_business_tables(engine: Engine) -> None:
    """FK-safe full wipe of all business tables (shared by integration fixtures)."""
    statements = (
        "DELETE FROM execution_attempts",
        "DELETE FROM execution_tickets",
        "DELETE FROM decisions",
        "DELETE FROM authorization_spend",
        "DELETE FROM intent_drafts",
        "DELETE FROM checkouts",
        "DELETE FROM intent_contracts",
        "DELETE FROM products",
        "DELETE FROM merchants",
    )
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
        conn.execute(text("ALTER TABLE audit_events DISABLE TRIGGER trg_audit_no_update"))
        conn.execute(text("DELETE FROM audit_events"))
        conn.execute(text("ALTER SEQUENCE audit_events_seq_seq RESTART WITH 1"))
        conn.execute(text("ALTER TABLE audit_events ENABLE TRIGGER trg_audit_no_update"))


@pytest.fixture(scope="session", autouse=True)
def _test_db_isolation_guard() -> Iterator[None]:
    """Fail the ENTIRE suite instantly if any settings path reaches the dev DB.

    Belt-and-braces for the env pinning above: whatever `get_settings()`
    resolves to must not be the dev database, must stay mock-provider and must
    carry no Razorpay credentials. Any future code path that bypasses the
    pinning fails here loudly instead of silently mutating dev state.
    """
    get_settings.cache_clear()
    resolved = get_settings()
    db_url = resolved.database_url.split("?")[0].rstrip("/")
    assert not db_url.endswith("/razormesh"), (
        "test isolation broken: get_settings() resolved to the DEV database "
        f"({resolved.database_url!r}); tests must only touch razormesh_test"
    )
    assert resolved.payment_provider == "mock", "tests must run with the mock provider"
    assert not resolved.razorpay_credentials_present, (
        "Razorpay credentials leaked into the test environment (P2-S20)"
    )
    yield
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def settings() -> Settings:
    # Tests must be deterministic and credential-free (P2-S20): the real root
    # .env is NEVER read, so a local PAYMENT_PROVIDER=razorpay selection (or
    # real Test credentials) can never leak into the suite or trigger real
    # provider calls. DB/Redis URLs stay overridable for CI.
    #
    # P2-M38: the suite defaults to the DEDICATED razormesh_test database, not
    # the dev database. The integration fixtures wipe business tables; pointing
    # them at the dev DB destroyed real Test Mode payment evidence (payments
    # #1 and #2) during post-payment gate runs. Dev state and test state are
    # isolated by the module-level env pinning above plus this fixture.
    return Settings(
        _env_file=None,
        database_url=os.environ["DATABASE_URL"],
        redis_url=os.environ["REDIS_URL"],
    )


@pytest.fixture()
def client(settings: Settings) -> Iterator[TestClient]:
    from razormesh_api import api

    api.main.get_settings.cache_clear()

    def _override() -> Settings:
        return settings

    app.dependency_overrides[api.main.get_settings] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
