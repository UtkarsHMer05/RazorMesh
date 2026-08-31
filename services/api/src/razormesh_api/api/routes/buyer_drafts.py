"""P3-M17: human confirmation API for AI-proposed intent drafts.

Endpoints (all backend-only; the browser never sees any secret):
- POST /buyer/intent-drafts/compile   trusted NL text -> durable draft;
- GET  /buyer/intent-drafts/{id}      draft review payload (safe fields);
- POST /buyer/intent-drafts/{id}/confirm  THE authority-creating transition;
- POST /buyer/intent-drafts/{id}/reject   terminal, non-authoritative.

The compiler path receives ONLY the dedicated authorization-text field
(P3-S02); merchant/product data cannot reach it by construction (M12).
"""

from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from razormesh_api.api.routes.webhooks import _repos_for
from razormesh_api.confirmation_service import HumanConfirmationService
from razormesh_api.domain.confirmation import ConfirmationError
from razormesh_api.domain.ids import DraftId
from razormesh_api.intent_compilation_service import IntentCompilationService
from razormesh_api.intent_compiler import build_tokenrouter_client
from razormesh_api.intent_compiler_prompt import TrustedHumanAuthorization
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.settings import Settings, get_settings

router = APIRouter(prefix="/buyer/intent-drafts", tags=["buyer-intent-drafts"])


def _service(settings: Annotated[Settings, Depends(get_settings)]):  # type: ignore[no-untyped-def]
    """Test seam: monkeypatched in the suite to stub the compiler client."""
    repos = _repos_for(settings)
    ledger = EvidenceLedger(repos)

    from datetime import UTC, datetime

    class _SystemClock:
        def now_utc(self) -> datetime:
            return datetime.now(UTC)

    return HumanConfirmationService(repos, ledger, _SystemClock())


def _compilation_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Iterator[IntentCompilationService]:
    """Request-scoped compiler dependency with deterministic client cleanup.

    Keeping provider construction behind this dependency is also the test seam:
    M17 API tests replace it with a fixture compiler, so the suite can prove the
    complete route without making an accidental external request.
    """
    if not settings.tokenrouter_credentials_present:
        raise HTTPException(status_code=503, detail={"code": "COMPILER_UNAVAILABLE"})
    client = build_tokenrouter_client(settings)
    try:
        yield IntentCompilationService(
            client,
            model=settings.planner_model,
            max_output_tokens=4000,
        )
    finally:
        client.close()


class CompileRequest(BaseModel):
    authorization_text: str = Field(min_length=3, max_length=2000)
    principal_id: str = Field(min_length=6, max_length=64)
    agent_id: str = Field(min_length=6, max_length=64)


class ConfirmRequest(BaseModel):
    confirmation_nonce: str = Field(min_length=8, max_length=128)
    actor: str = Field(default="human", max_length=64)


class RejectRequest(BaseModel):
    actor: str = Field(default="human", max_length=64)


@router.post("/compile")
def compile_draft(
    body: CompileRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    compiler: Annotated[IntentCompilationService, Depends(_compilation_service)],
) -> dict[str, Any]:
    """Compile trusted human text into a reviewable draft (P3-S03: proposal)."""
    outcome = compiler.compile(TrustedHumanAuthorization(text=body.authorization_text))

    rec = _service(settings).record_compilation(
        principal_id=_pid(body.principal_id),
        agent_id=_aid(body.agent_id),
        source_text_sha256=__import__("hashlib")
        .sha256(body.authorization_text.encode())
        .hexdigest(),
        outcome=outcome,
    )
    if rec.draft_id is None:
        raise HTTPException(
            status_code=502,
            detail={"code": rec.error_code or "COMPILER_FAILED"},
        )
    row = _service(settings).get_draft(rec.draft_id)
    assert row is not None
    return _draft_view(row)


@router.get("/{draft_id}")
def get_draft(
    draft_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    row = _service(settings).get_draft(DraftId(draft_id))
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "DRAFT_NOT_FOUND"})
    return _draft_view(row)


@router.post("/{draft_id}/confirm")
def confirm_draft(
    draft_id: str,
    body: ConfirmRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    try:
        result = _service(settings).confirm_draft(
            draft_id=DraftId(draft_id),
            confirmation_nonce=body.confirmation_nonce,
            actor=body.actor,
        )
    except ConfirmationError as exc:
        raise _http_from(exc) from exc
    # Phase-5: link the display trace (projection only; failure never blocks confirmation).
    try:
        from razormesh_api.persistence.db import create_db_engine, create_session_factory
        from razormesh_api.trace_registry import TraceRegistry

        TraceRegistry(
            Repositories(create_session_factory(create_db_engine(get_settings().database_url)))
        ).get_or_create_for_intent(str(result.intent_id), draft_id=str(result.draft_id))
    except Exception:  # noqa: BLE001, S110 - projection linkage is best-effort, never authoritative
        pass
    return {
        "draft_id": str(result.draft_id),
        "intent_id": str(result.intent_id),
        "generation": result.generation,
        "replayed": result.replayed,
        "state": "CONFIRMED",
    }


@router.post("/{draft_id}/reject")
def reject_draft(
    draft_id: str,
    body: RejectRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    try:
        state = _service(settings).reject_draft(draft_id=DraftId(draft_id), actor=body.actor)
    except ConfirmationError as exc:
        raise _http_from(exc) from exc
    return {"draft_id": draft_id, "state": state.value}


# ---------------------------------------------------------------------------
def _http_from(exc: ConfirmationError) -> HTTPException:
    status = {
        "DRAFT_NOT_FOUND": 404,
        "INVALID_NONCE": 400,
        "CONFIRMATION_REPLAY_MISMATCH": 409,
        "DRAFT_NOT_CONFIRMABLE": 409,
        "DRAFT_NOT_REJECTABLE": 409,
        "DRAFT_STALE": 409,
        "DRAFT_BELOW_COMMITTED_SPEND": 409,
    }.get(exc.code, 422)
    return HTTPException(status_code=status, detail={"code": exc.code, "detail": exc.detail})


def _pid(raw: str):  # type: ignore[no-untyped-def]
    from razormesh_api.domain.ids import PrincipalId

    return PrincipalId(raw)


def _aid(raw: str):  # type: ignore[no-untyped-def]
    from razormesh_api.domain.ids import AgentId

    return AgentId(raw)


def _draft_view(row: Any) -> dict[str, Any]:
    """Safe review projection — no secrets exist on this row, and raw human
    text is not persisted at all."""
    return {
        "draft_id": row.draft_id,
        "state": row.state,
        "schema_version": row.schema_version,
        "payload": row.payload,
        "ambiguities": row.payload.get("ambiguities", []),
        "compiler_model": row.compiler_model,
        "prompt_version": row.prompt_version,
        "superseded_by": row.superseded_by,
        "intent_id": row.intent_id,
        "confirmed_generation": row.confirmed_generation,
    }
