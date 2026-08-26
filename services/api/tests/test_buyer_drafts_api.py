"""P3-M17: human confirmation API surface.

The compile endpoint is exercised with a STUBBED TokenRouter client (no real
Qwen in CI); confirm/reject/replay/stale paths run against the REAL
HumanConfirmationService + dev PostgreSQL. No secrets reach responses.
"""

import json

import pytest
from fastapi.testclient import TestClient

from razormesh_api.api.main import app
from razormesh_api.api.routes import buyer_drafts as drafts_route
from razormesh_api.domain.ids import PrincipalId, new_ulid
from razormesh_api.intent_compilation_service import IntentCompilationService
from razormesh_api.intent_compiler import TokenRouterClient
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
def api():  # type: ignore[no-untyped-def]
    def _override() -> Settings:
        return _settings()

    def _compiler_override() -> IntentCompilationService:
        return IntentCompilationService(_StubClient(), model="stub")

    get_settings.cache_clear()
    app.dependency_overrides[get_settings] = _override
    app.dependency_overrides[drafts_route._compilation_service] = _compiler_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    get_settings.cache_clear()


class _StubClient(TokenRouterClient):
    def __init__(self) -> None:
        pass  # no HTTP client exists in this fixture

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


_LAST_TEXT: dict[str, str] = {"value": ""}
_STUB_CONTENT: dict[str, str] = {
    "value": (
        '{"schema_version":"agentpay-intent-draft-v1",'
        '"product_summary":"wireless headphones",'
        '"hard":{"max_amount":{"amount_minor":500000,"currency":"INR"}}}'
    )
}


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
