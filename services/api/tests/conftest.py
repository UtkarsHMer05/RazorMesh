"""Shared pytest fixtures. Integration tests use the local Docker infrastructure."""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from razormesh_api.api.main import app
from razormesh_api.settings import Settings


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(
        database_url=os.environ.get(
            "RAZORMESH_TEST_DATABASE_URL",
            "postgresql+psycopg://razormesh:razormesh_local_dev@127.0.0.1:15432/razormesh",
        ),
        redis_url=os.environ.get("RAZORMESH_TEST_REDIS_URL", "redis://127.0.0.1:16379/0"),
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
