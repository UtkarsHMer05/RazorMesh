"""P3-M09 (D-038): TokenRouter client — backend-only Intent Compiler transport.

One thin httpx wrapper for the OpenAI-compatible ``POST /v1/chat/completions``
endpoint. Mirrors the Razorpay client's discipline (D-030):

- NO transport-level retries: a mutating-or-billing call is never silently
  re-sent; callers own any retry policy explicitly;
- explicit bounded timeout on every request;
- structured error taxonomy with stable codes; errors NEVER contain the API
  key, raw headers, or response bodies that could embed secrets;
- per-request correlation id (ULID) generated here and surfaced on failures
  for log-safe tracing (P3-S01);
- dependency-injectable: ``transport`` seam accepts httpx.MockTransport so the
  whole suite runs without network.

The client returns raw completion CONTENT only. It has zero knowledge of
IntentDrafts, authority, or payments (P3-S16/S18): higher layers own meaning.
"""

import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from razormesh_api.settings import Settings


class TokenRouterError(Exception):
    """Base class. ``code`` uses documented Phase-3 reason codes."""

    def __init__(self, code: str, detail: str, *, request_id: str | None = None) -> None:
        super().__init__(f"[{code}] {detail}")
        self.code = code
        self.detail = detail
        self.request_id = request_id


class TokenRouterConfigError(TokenRouterError):
    def __init__(self, detail: str) -> None:
        super().__init__("TOKENROUTER_CONFIG_INVALID", detail)


class TokenRouterAuthError(TokenRouterError):
    def __init__(self, detail: str, *, request_id: str | None = None) -> None:
        super().__init__("TOKENROUTER_AUTH_FAILED", detail, request_id=request_id)


class TokenRouterRejectedError(TokenRouterError):
    """Definitive gateway/model refusal (4xx semantics). No retry."""

    def __init__(self, detail: str, *, request_id: str | None = None) -> None:
        super().__init__("TOKENROUTER_REQUEST_REJECTED", detail, request_id=request_id)


class TokenRouterUnknownOutcomeError(TokenRouterError):
    """The request MAY have reached the provider; truth not disproven.

    Covers timeouts, connection failures, 5xx, and malformed responses.
    Never retried automatically.
    """

    def __init__(self, detail: str, *, request_id: str | None = None) -> None:
        super().__init__("TOKENROUTER_UNKNOWN_OUTCOME", detail, request_id=request_id)


@dataclass(frozen=True)
class ChatCompletionResult:
    """Minimal validated projection of a chat-completion response.

    ``reasoning_content``/``reasoning_tokens`` are captured because Qwen3.8
    is a thinking model (M10 probe evidence): callers must treat ``content``
    as the ONLY answer channel and budget ``max_tokens`` for hidden reasoning,
    or the model can end with finish_reason=length and EMPTY content.
    """

    content: str
    model_reported: str
    finish_reason: str
    prompt_tokens: int | None
    completion_tokens: int | None
    request_id: str
    reasoning_content: str | None = None
    reasoning_tokens: int | None = None


def _validate_payload(payload: Any, *, request_id: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TokenRouterUnknownOutcomeError(
            "malformed JSON in provider response", request_id=request_id
        )
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise TokenRouterUnknownOutcomeError("response missing choices", request_id=request_id)
    first = choices[0]
    if not isinstance(first, dict):
        raise TokenRouterUnknownOutcomeError("malformed choice entry", request_id=request_id)
    message = first.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise TokenRouterUnknownOutcomeError(
            "response message content missing", request_id=request_id
        )
    return payload


class TokenRouterClient:
    """Single project-standard HTTP client for TokenRouter (D-038)."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise TokenRouterConfigError("missing TokenRouter API key")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------------
    def chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 800,
        response_format: dict[str, str] | None = None,
    ) -> ChatCompletionResult:
        request_id = uuid.uuid4().hex
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            body["response_format"] = response_format

        try:
            response = self._client.post(
                "/chat/completions",
                json=body,
                headers={"X-Request-Id": request_id},
            )
        except httpx.TimeoutException as exc:
            raise TokenRouterUnknownOutcomeError(
                "provider timeout; outcome unknown", request_id=request_id
            ) from exc
        except httpx.TransportError as exc:
            raise TokenRouterUnknownOutcomeError(
                "connection failure; outcome unknown", request_id=request_id
            ) from exc

        if response.status_code in (401, 403):
            raise TokenRouterAuthError("credential rejected by gateway", request_id=request_id)
        if response.status_code >= 500:
            raise TokenRouterUnknownOutcomeError(
                f"gateway server error {response.status_code}", request_id=request_id
            )
        if response.status_code == 429:
            raise TokenRouterRejectedError("rate limited by gateway", request_id=request_id)
        if 400 <= response.status_code < 500 and response.status_code != 429:
            # 4xx other than auth/429: definitive rejection for THIS request.
            raise TokenRouterRejectedError(
                f"request rejected ({response.status_code})", request_id=request_id
            )
        if response.status_code not in (200, 201):
            raise TokenRouterUnknownOutcomeError(
                f"unexpected gateway status {response.status_code}",
                request_id=request_id,
            )

        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise TokenRouterUnknownOutcomeError(
                "malformed JSON from gateway", request_id=request_id
            ) from exc

        data = _validate_payload(payload, request_id=request_id)
        first = data["choices"][0]
        message = first["message"]
        raw_usage = data.get("usage")
        usage: dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
        reasoning = message.get("reasoning_content")
        return ChatCompletionResult(
            content=str(message["content"]),
            model_reported=str(data.get("model") or model),
            finish_reason=str(first.get("finish_reason") or ""),
            prompt_tokens=usage.get("prompt_tokens")
            if isinstance(usage.get("prompt_tokens"), int)
            else None,
            completion_tokens=usage.get("completion_tokens")
            if isinstance(usage.get("completion_tokens"), int)
            else None,
            request_id=request_id,
            reasoning_content=reasoning if isinstance(reasoning, str) else None,
            reasoning_tokens=usage.get("reasoning_tokens")
            if isinstance(usage.get("reasoning_tokens"), int)
            else None,
        )

    # ------------------------------------------------------------------
    def list_models(self) -> list[str]:
        """READ-ONLY capability probe (GET /v1/models), M10."""
        request_id = uuid.uuid4().hex
        try:
            response = self._client.get("/models", headers={"X-Request-Id": request_id})
        except httpx.TimeoutException as exc:
            raise TokenRouterUnknownOutcomeError(
                "provider timeout during models listing", request_id=request_id
            ) from exc
        except httpx.TransportError as exc:
            raise TokenRouterUnknownOutcomeError(
                "connection failure during models listing", request_id=request_id
            ) from exc
        if response.status_code in (401, 403):
            raise TokenRouterAuthError("credential rejected by gateway", request_id=request_id)
        if response.status_code != 200:
            raise TokenRouterRejectedError(
                f"models listing refused ({response.status_code})",
                request_id=request_id,
            )
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise TokenRouterUnknownOutcomeError(
                "malformed JSON from gateway", request_id=request_id
            ) from exc
        items = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            raise TokenRouterUnknownOutcomeError("malformed models listing", request_id=request_id)
        ids: list[str] = []
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                ids.append(item["id"])
        return ids


def build_tokenrouter_client(settings: Settings) -> TokenRouterClient:
    """DI factory: fail-safe construction from typed settings (P2-S21 analog).

    No silent fallbacks: missing credentials raise a config error naming the
    variable — never a value.
    """
    key = settings.tokenrouter_api_key.get_secret_value()
    if not key:
        raise TokenRouterConfigError("TOKENROUTER_API_KEY is required for the intent compiler")
    return TokenRouterClient(
        api_key=key,
        base_url=settings.tokenrouter_base_url,
        timeout_seconds=settings.tokenrouter_timeout_seconds,
    )
