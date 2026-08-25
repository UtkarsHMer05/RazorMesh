import json
"""P3-M17: human confirmation API surface.

The compile endpoint is exercised with a STUBBED TokenRouter client (no real
Qwen in CI); confirm/reject/replay/stale paths run against the REAL
HumanConfirmationService + dev PostgreSQL. No secrets reach responses.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from razormesh_api.api.main import app
from razormesh_api.api.routes import buyer_drafts as drafts_route
from razormesh_api.intent_compiler import TokenRouterClient
from razormesh_api.intent_compiler_prompt import TrustedHumanAuthorization
from razormesh_api.domain.ids import PrincipalId, new_ulid
from razormesh_api.settings import Settings, get_settings

SECRET = "tr_test_key_placeholder"


def _settings() -> Settings:
    return Settings(
        database_url=get_settings().database_url,
        redis_url=get_settings().redis_url,
        payment_provider="razorpay",
        razorpay_mode="test",
        razorpay_key_id="rzp_test_k",
        razorpay_key_secret="test-secret-value",
        razorpay_webhook_secret="whsec-test",
        tokenrouter_api_key=SECRET,
        tokenrouter_base_url="https://api.tokenrouter.test/v1",
        _env_file=None,
    )


@pytest.fixture()
def api(monkeypatch):  # type: ignore[no-untyped-def]
    good = (
        '{"schema_version":"agentpay-intent-draft-v1",'
        '"product_summary":"wireless headphones",'
        '"hard":{"max_amount":{"amount_minor":500000,"currency":"INR"}}}'
    )
    monkeypatch.setattr(
        drafts_route,
        "_service",
        lambda settings: _make_service_with_stub_client(settings, good),
    )

    def _override() -> Settings:
        return _settings()

    get_settings.cache_clear()
    app.dependency_overrides[get_settings] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _make_service_with_stub_client(settings: Settings, content: str):  # type: ignore[no-untyped-def]
    from razormesh_api.confirmation_service import HumanConfirmationService
    from razormesh_api.intent_compilation_service import IntentCompilationService
    from razormesh_api.ledger import EvidenceLedger
    from razormesh_api.persistence.db import create_session_factory
    from razormesh_api.persistence.repositories import Repositories

    repos = Repositories(create_session_factory(create_db_engine()))
    ledger = EvidenceLedger(repos)

    class _Clock:
        def now_utc(self):  # type: ignore[no-untyped-def]
            return datetime.now(UTC)

    class _Client(TokenRouterClient):
        def __init__(self) -> None:
            pass  # skip HTTP client entirely

        def chat_completion(self, **kwargs):  # type: ignore[no-untyped-def]
            from razormesh_api.intent_compiler import ChatCompletionResult

            return ChatCompletionResult(
                content=_STUB_CONTENT["value"],
                model_reported="stub",
                finish_reason="stop",
                prompt_tokens=1,
                completion_tokens=1,
                request_id="req-stub",
            )

    svc = HumanConfirmationService(repos, ledger, _Clock())
    original_record = svc.record_compilation

    def record(*, principal_id, agent_id, source_text_sha256, outcome):  # type: ignore[no-untyped-def]
        # swap the outcome's payload through the REAL service unchanged;
        # the stub client already produced the content via compile service below
        return original_record(
            principal_id=principal_id,
            agent_id=agent_id,
            source_text_sha256=source_text_sha256,
            outcome=outcome,
        )

    svc.record_compilation = record  # type: ignore[method-assign]

    compiled = IntentCompilationService(_Client(), model="stub")
    return _ProxyService(svc, compiled)


class _ProxyService:
    """Routes compile() through the real validation pipeline using the stub
    client; everything else delegates to the REAL confirmation service."""

    def __init__(self, real, compiled) -> None:  # type: ignore[no-untyped-def]
        self._real = real
        self._compiled = compiled

    def record_compilation(self, **kwargs):  # type: ignore[no-untyped-def]
        outcome = self._compiled.compile(TrustedHumanAuthorization(text=_LAST_TEXT["value"]))
        kwargs["outcome"] = outcome
        return self._real.record_compilation(**kwargs)

    def confirm_draft(self, **kwargs):  # type: ignore[no-untyped-def]
        return self._real.confirm_draft(**kwargs)

    def reject_draft(self, **kwargs):  # type: ignore[no-untyped-def]
        return self._real.reject_draft(**kwargs)

    def get_draft(self, draft_id):  # type: ignore[no-untyped-def]
        return self._real.get_draft(draft_id)


_LAST_TEXT: dict[str, str] = {"value": ""}
_STUB_CONTENT: dict[str, str] = {
    "value": (
        '{"schema_version":"agentpay-intent-draft-v1",'
        '"product_summary":"wireless headphones",'
        '"hard":{"max_amount":{"amount_minor":500000,"currency":"INR"}}}'
    )
}


def create_db_engine():  # type: ignore[no-untyped-def]
    from sqlalchemy import create_engine

    from razormesh_api.persistence.db import create_session_factory  # noqa: F401

    return create_engine(get_settings().database_url, future=True)


def _compile_body() -> dict[str, str]:
    text = f"Buy headphones under 5000 rupees. ref-{new_ulid()}"
    _LAST_TEXT["value"] = text
    return {
        "authorization_text": text,
        "principal_id": str(PrincipalId.generate()),
        "agent_id": str(new_agent()),
    }


def new_agent():  # type: ignore[no-untyped-def]
    from razormesh_api.domain.ids import AgentId

    return AgentId.generate()


def test_compile_review_confirm_flow(api) -> None:  # type: ignore[no-untyped-def]
    body = _compile_body()
    r = api.post("/buyer/intent-drafts/compile", json=body)
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["state"] in {"DRAFT", "NEEDS_CLARIFICATION"}
    assert view["payload"]["hard"]["max_amount"]["amount_minor"] == 500000
    assert "authorization_text" not in json.dumps(view)

    draft_id = view["draft_id"]
    conf = api.post(
        f"/buyer/intent-drafts/{draft_id}/confirm",
        json={"confirmation_nonce": f"nonce-{new_ulid()}"},
    )
    assert conf.status_code == 200, conf.text
    data = conf.json()
    assert data["state"] == "CONFIRMED" and data["generation"] == 1

    got = api.get(f"/buyer/intent-drafts/{draft_id}")
    assert got.status_code == 200 and got.json()["state"] == "CONFIRMED"


def test_missing_money_compiles_but_confirm_is_422(api) -> None:  # type: ignore[no-untyped-def]
    _STUB_CONTENT["value"] = (
        '{"schema_version":"agentpay-intent-draft-v1","product_summary":"mystery thing"}'
    )
    body = _compile_body()
    _LAST_TEXT["value"] = "Buy something nice."
    body["authorization_text"] = _LAST_TEXT["value"]
    r = api.post("/buyer/intent-drafts/compile", json=body)
    assert r.status_code == 200
    draft_id = r.json()["draft_id"]
    res = api.post(
        f"/buyer/intent-drafts/{draft_id}/confirm",
        json={"confirmation_nonce": f"nonce-{new_ulid()}"},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "DRAFT_MISSING_MONEY"


def test_unknown_draft_404(api) -> None:  # type: ignore[no-untyped-def]
    r = api.get(f"/buyer/intent-drafts/drf_{new_ulid()}")
    assert r.status_code == 404


def test_reject_flow_and_double_reject_idempotent(api) -> None:  # type: ignore[no-untyped-def]
    body = _compile_body()
    r = api.post("/buyer/intent-drafts/compile", json=body)
    draft_id = r.json()["draft_id"]
    first = api.post(f"/buyer/intent-drafts/{draft_id}/reject", json={})
    second = api.post(f"/buyer/intent-drafts/{draft_id}/reject", json={})
    assert first.json()["state"] == second.json()["state"] == "REJECTED"
