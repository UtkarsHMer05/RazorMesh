"""P3-M09: TokenRouter client abstraction — transport, taxonomy, no-retry.

All network behavior is exercised through httpx.MockTransport fixtures; the
real gateway is never contacted here (that is the M10 probe's job).
"""

import httpx
import pytest

from razormesh_api.intent_compiler import (
    TokenRouterAuthError,
    TokenRouterClient,
    TokenRouterConfigError,
    TokenRouterRejectedError,
    TokenRouterUnknownOutcomeError,
    build_tokenrouter_client,
)
from razormesh_api.settings import get_settings

MESSAGES = [
    {"role": "system", "content": "You are a strict schema compiler."},
    {"role": "user", "content": "Buy headphones under 5000 INR."},
]


def _client(transport: httpx.BaseTransport) -> TokenRouterClient:
    return TokenRouterClient(
        api_key="tr_test_key_placeholder",
        base_url=get_settings().tokenrouter_base_url,
        timeout_seconds=5,
        transport=transport,
    )


def _ok_body() -> dict[str, object]:
    return {
        "id": "chatcmpl_x",
        "model": "qwen/qwen3.8-max-free",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": '{"ok": true}'},
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 5},
    }


class _Counting(httpx.BaseTransport):
    def __init__(self, responder) -> None:  # type: ignore[no-untyped-def]
        self._responder = responder
        self.calls = 0
        self.last_headers: dict[str, str] = {}

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        self.last_headers = {k.lower(): v for k, v in request.headers.items()}
        return self._responder(request)


def test_happy_path_returns_validated_projection() -> None:
    transport = _Counting(lambda r: httpx.Response(200, json=_ok_body()))
    result = _client(transport).chat_completion(model="m", messages=MESSAGES)
    assert result.content == '{"ok": true}'
    assert result.model_reported == "qwen/qwen3.8-max-free"
    assert result.finish_reason == "stop"
    assert result.prompt_tokens == 12 and result.completion_tokens == 5
    assert result.request_id and len(result.request_id) == 32


def test_auth_header_present_and_request_id_correlated() -> None:
    seen: dict[str, str] = {}
    captured_id = {"v": ""}

    def responder(request: httpx.Request) -> httpx.Response:
        seen.update({k.lower(): v for k, v in request.headers.items()})
        captured_id["v"] = seen.get("x-request-id", "")
        return httpx.Response(401)

    with pytest.raises(TokenRouterAuthError) as excinfo:
        _client(_Counting(responder)).chat_completion(model="m", messages=MESSAGES)
    assert seen.get("authorization") == "Bearer tr_test_key_placeholder"
    assert excinfo.value.request_id == captured_id["v"]
    assert "tr_test_key_placeholder" not in str(excinfo.value)


def test_timeout_maps_unknown_and_never_retries() -> None:
    def dropped(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated", request=request)

    transport = _Counting(dropped)
    with pytest.raises(TokenRouterUnknownOutcomeError):
        _client(transport).chat_completion(model="m", messages=MESSAGES)
    assert transport.calls == 1  # NO transport-level retry (D-030 discipline)


def test_5xx_and_connect_errors_are_unknown_calls_eq_one() -> None:
    for responder in (
        lambda r: httpx.Response(503),
        lambda r: (_ for _ in ()).throw(httpx.ConnectError("boom", request=r)),
    ):
        transport = _Counting(responder)
        with pytest.raises(TokenRouterUnknownOutcomeError):
            _client(transport).chat_completion(model="m", messages=MESSAGES)
        assert transport.calls == 1


def test_429_and_400_are_definitive_rejections_no_retry() -> None:
    for status in (429, 400):
        transport = _Counting(lambda r, s=status: httpx.Response(s))
        with pytest.raises(TokenRouterRejectedError):
            _client(transport).chat_completion(model="m", messages=MESSAGES)
        assert transport.calls == 1


@pytest.mark.parametrize(
    "payload",
    [
        "not-json-at-all",
        {},
        {"choices": []},
        {"choices": [{"message": {"role": "assistant"}}]},
        {"choices": [{"message": {"content": 42}}]},
    ],
)
def test_malformed_payloads_are_unknown(payload: object) -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        if isinstance(payload, str):
            return httpx.Response(200, text=payload)
        return httpx.Response(200, json=payload)  # type: ignore[arg-type]

    with pytest.raises(TokenRouterUnknownOutcomeError):
        _client(_Counting(responder)).chat_completion(model="m", messages=MESSAGES)


def test_response_format_forwarded_when_provided() -> None:
    bodies: list[bytes] = []

    def responder(request: httpx.Request) -> httpx.Response:
        bodies.append(request.read())
        return httpx.Response(200, json=_ok_body())

    _client(_Counting(responder)).chat_completion(
        model="m", messages=MESSAGES, response_format={"type": "json_object"}
    )
    assert b'"response_format"' in bodies[0]
    assert b"json_object" in bodies[0]


def test_models_listing_parses_ids_and_errors_map() -> None:
    ok = _Counting(
        lambda r: httpx.Response(
            200, json={"data": [{"id": "qwen/qwen3.8-max-free"}, {"id": "other/m"}]}
        )
    )
    assert _client(ok).list_models() == ["qwen/qwen3.8-max-free", "other/m"]

    bad = _Counting(lambda r: httpx.Response(200, text="nope"))
    with pytest.raises(TokenRouterUnknownOutcomeError):
        _client(bad).list_models()


def test_factory_requires_credentials_and_names_variable_only() -> None:
    from razormesh_api.settings import Settings

    s = Settings(_env_file=None)  # defaults: empty TokenRouter key
    assert s.tokenrouter_credentials_present is False
    with pytest.raises(TokenRouterConfigError) as excinfo:
        build_tokenrouter_client(s)
    assert "TOKENROUTER_API_KEY" in str(excinfo.value)
