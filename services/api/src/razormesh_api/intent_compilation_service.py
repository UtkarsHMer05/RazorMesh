"""P3-M13: compiler output pipeline — extract → validate → ONE repair → fail closed.

Failure policy (master prompt §22): invalid schema gets exactly one bounded
repair call that feeds back the validation summary; anything still invalid,
any provider failure, or an unusable/oversized output resolves to a controlled
non-authoritative status. This layer NEVER creates authority (P3-S03) and
never raises past its caller for provider/schema issues — it returns a
CompilerOutcome the UI can render honestly.
"""

import json
from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from razormesh_api.domain.intent_draft import CompilerIntentPayload
from razormesh_api.intent_compiler import (
    TokenRouterClient,
    TokenRouterError,
)
from razormesh_api.intent_compiler_prompt import build_compiler_messages

_MAX_CONTENT_CHARS = 20_000
_MAX_REPAIR_ERROR_CHARS = 600

_REPAIR_SYSTEM_PROMPT = """\
Your previous JSON failed schema validation. Emit the CORRECTED object only — \
one JSON object, no prose, no fences, matching the same \
agentpay-intent-draft-v1 contract. Fix EXACTLY the reported problems without \
inventing new content.
"""


@dataclass(frozen=True)
class CompilerOutcome:
    """Honest, renderable result of a compilation attempt."""

    status: Literal["OK", "NEEDS_CLARIFICATION", "FAILED"]
    payload: CompilerIntentPayload | None
    attempts: int
    error_code: str | None
    detail: str | None
    request_ids: tuple[str, ...]

    @property
    def is_authoritative_candidate(self) -> bool:
        return self.status == "OK" and self.payload is not None


def extract_json_object(content: str) -> dict[str, object]:
    """Pull the FIRST balanced JSON object out of arbitrary model prose.

    Handles bare objects, ```json fences, and surrounding chatter. Raises
    ValueError when no parseable object exists.
    """
    stripped = content.strip()
    candidates: list[str] = [stripped]
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end > start:
        candidates.append(stripped[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("no JSON object found in model output")


def parse_compiler_output(content: str) -> CompilerIntentPayload:
    """Strict parse: JSON extraction + full domain validation (extra=forbid)."""
    if len(content) > _MAX_CONTENT_CHARS:
        raise ValueError("model output exceeds the maximum accepted size")
    raw = extract_json_object(content)
    return CompilerIntentPayload.model_validate(raw)


class IntentCompilationService:
    """Orchestrates compile-with-one-repair against a TokenRouterClient."""

    def __init__(
        self,
        client: TokenRouterClient,
        *,
        model: str | None = None,
        max_output_tokens: int = 1500,
        temperature: float = 0.0,
    ) -> None:
        self._client = client
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature

    def compile(
        self,
        trusted: object,  # TrustedHumanAuthorization (typed loosely to avoid cycle)
    ) -> CompilerOutcome:
        messages = build_compiler_messages(trusted)  # type: ignore[arg-type]
        request_ids: list[str] = []

        try:
            first = self._client.chat_completion(
                model=self._model or self._client_default_model(),
                messages=messages,
                temperature=self._temperature,
                max_tokens=self._max_output_tokens,
            )
        except TokenRouterError as exc:
            return CompilerOutcome(
                status="FAILED",
                payload=None,
                attempts=1,
                error_code="COMPILER_UNAVAILABLE",
                detail=f"{exc.code}:{exc.request_id}",
                request_ids=(*request_ids, exc.request_id or ""),
            )
        request_ids.append(first.request_id)

        try:
            payload = parse_compiler_output(first.content)
            return CompilerOutcome(
                status="OK",
                payload=payload,
                attempts=1,
                error_code=None,
                detail=None,
                request_ids=tuple(request_ids),
            )
        except (ValueError, ValidationError) as exc:
            first_error = f"{type(exc).__name__}: {str(exc)[:_MAX_REPAIR_ERROR_CHARS]}"

        # ---- ONE bounded repair ---------------------------------------
        repair_messages = [
            *messages,
            {"role": "assistant", "content": first.content[:4000]},
            {
                "role": "user",
                "content": (
                    "Your JSON failed validation. Problems:\n"
                    f"{first_error}\n"
                    "Return the corrected single JSON object only."
                ),
            },
        ]
        try:
            second = self._client.chat_completion(
                model=self._model or self._client_default_model(),
                messages=repair_messages,
                temperature=self._temperature,
                max_tokens=self._max_output_tokens,
                response_format={"type": "json_object"},
            )
        except TokenRouterError as exc:
            return CompilerOutcome(
                status="FAILED",
                payload=None,
                attempts=2,
                error_code="COMPILER_UNAVAILABLE",
                detail=f"repair:{exc.code}:{exc.request_id}",
                request_ids=(*request_ids, exc.request_id or ""),
            )
        request_ids.append(second.request_id)

        try:
            payload = parse_compiler_output(second.content)
        except (ValueError, ValidationError) as exc:
            return CompilerOutcome(
                status="FAILED",
                payload=None,
                attempts=2,
                error_code="SCHEMA_INVALID_AFTER_REPAIR",
                detail=f"{type(exc).__name__}: {str(exc)[:_MAX_REPAIR_ERROR_CHARS]}",
                request_ids=tuple(request_ids),
            )
        return CompilerOutcome(
            status="OK",
            payload=payload,
            attempts=2,
            error_code=None,
            detail=None,
            request_ids=tuple(request_ids),
        )

    def _client_default_model(self) -> str:
        from razormesh_api.settings import get_settings

        return get_settings().planner_model
