"""P3-M16 (D-042): HumanConfirmationService — the ONLY path from AI proposal
to durable authority.

The AI proposes (compiler outcome); the human confirms; only the CONFIRMED
transition creates/supersedes an IntentContract authorization_generation
(P3-S03). A compiler outage produces no draft and therefore no confirmation
path at all — outage can never bypass the human (P3-S14).

Concurrency model (PostgreSQL is the durable authority; Redis is uninvolved):
every mutating operation first takes a transaction-scoped advisory lock keyed
by the (principal, agent) authorization lineage, then row-locks the drafts and
contract it touches. Lock order is always advisory -> rows, so concurrent
compiles/confirmations for one lineage serialize without deadlock.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from razormesh_api.clock import Clock
from razormesh_api.domain.confirmation import (
    REJECTABLE_STATES,
    ConfirmationError,
    DraftState,
    build_confirmed_contract,
    initial_state_for,
)
from razormesh_api.domain.ids import AgentId, DraftId, IntentId, PrincipalId
from razormesh_api.domain.intent import IntentContract
from razormesh_api.domain.intent_draft import SCHEMA_VERSION_VALUE, CompilerIntentPayload
from razormesh_api.intent_compilation_service import CompilerOutcome
from razormesh_api.intent_compiler_prompt import COMPILER_PROMPT_VERSION, prompt_sha256
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.persistence.models import (
    AuthorizationSpend,
    IntentDraftRecord,
)
from razormesh_api.persistence.models import (
    IntentContract as IntentContractRow,
)
from razormesh_api.persistence.repositories import Repositories

_MAX_NONCE_LEN = 128
_SERVICE_ACTOR = "confirmation-service"


@dataclass(frozen=True)
class CompilationRecord:
    """Durable result of recording one compiler outcome."""

    draft_id: DraftId | None
    state: DraftState | None
    error_code: str | None
    attempts: int
    request_ids: tuple[str, ...]
    superseded_draft_ids: tuple[DraftId, ...]


@dataclass(frozen=True)
class ConfirmationResult:
    draft_id: DraftId
    intent_id: IntentId
    generation: int
    replayed: bool


def _lineage_lock_key(principal_id: str, agent_id: str) -> int:
    digest = hashlib.sha256(f"p3-confirmation:{principal_id}:{agent_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def _lock_lineage(session: Session, principal_id: str, agent_id: str) -> None:
    session.execute(select(func.pg_advisory_xact_lock(_lineage_lock_key(principal_id, agent_id))))


class HumanConfirmationService:
    def __init__(self, repos: Repositories, ledger: EvidenceLedger, clock: Clock) -> None:
        self._repos = repos
        self._ledger = ledger
        self._clock = clock

    # ------------------------------------------------------------------
    # compile recording
    # ------------------------------------------------------------------

    def record_compilation(
        self,
        *,
        principal_id: PrincipalId,
        agent_id: AgentId,
        source_text_sha256: str,
        outcome: CompilerOutcome,
    ) -> CompilationRecord:
        """Persist one compiler outcome. FAILED outcomes create NO draft (the
        only honest result: nothing to confirm, nothing can become authority).
        A valid payload supersedes any prior open draft for the lineage."""
        if outcome.status == "FAILED" or outcome.payload is None:
            self._ledger.append(
                event_type="INTENT_COMPILE_FAILED",
                actor=_SERVICE_ACTOR,
                timestamp=self._clock.now_utc(),
                payload={
                    "principal_id": str(principal_id),
                    "agent_id": str(agent_id),
                    "source_text_sha256": source_text_sha256,
                    "error_code": outcome.error_code,
                    "attempts": outcome.attempts,
                    "request_ids": list(outcome.request_ids),
                    "prompt_version": COMPILER_PROMPT_VERSION,
                    "prompt_sha256": prompt_sha256(),
                },
            )
            return CompilationRecord(
                draft_id=None,
                state=None,
                error_code=outcome.error_code,
                attempts=outcome.attempts,
                request_ids=outcome.request_ids,
                superseded_draft_ids=(),
            )

        payload = outcome.payload
        state = initial_state_for(payload)
        now = self._clock.now_utc()
        draft_id = DraftId.generate()
        superseded: list[DraftId] = []

        with self._repos.transaction() as session:
            _lock_lineage(session, str(principal_id), str(agent_id))
            for stale in self._repos.drafts.open_for_update(
                str(principal_id), str(agent_id), session
            ):
                stale.superseded_by = str(draft_id)
                stale.updated_at = now
                superseded.append(DraftId(stale.draft_id))
            session.add(
                IntentDraftRecord(
                    draft_id=str(draft_id),
                    principal_id=str(principal_id),
                    agent_id=str(agent_id),
                    state=state.value,
                    schema_version=SCHEMA_VERSION_VALUE,
                    source_text_sha256=source_text_sha256,
                    payload=payload.model_dump(mode="json"),
                    compiler_model=self._planner_model(),
                    prompt_version=COMPILER_PROMPT_VERSION,
                    prompt_sha256=prompt_sha256(),
                    compile_attempts=outcome.attempts,
                    request_ids=list(outcome.request_ids),
                    created_at=now,
                    updated_at=now,
                )
            )
            session.flush()

        for old in superseded:
            self._ledger.append(
                event_type="INTENT_DRAFT_SUPERSEDED",
                actor=_SERVICE_ACTOR,
                timestamp=self._clock.now_utc(),
                payload={"superseded_draft_id": str(old), "draft_id": str(draft_id)},
            )
        self._ledger.append(
            event_type="INTENT_COMPILED",
            actor=_SERVICE_ACTOR,
            timestamp=self._clock.now_utc(),
            payload={
                "draft_id": str(draft_id),
                "principal_id": str(principal_id),
                "agent_id": str(agent_id),
                "state": state.value,
                "schema_version": SCHEMA_VERSION_VALUE,
                "source_text_sha256": source_text_sha256,
                "compiler_model": self._planner_model(),
                "prompt_version": COMPILER_PROMPT_VERSION,
                "prompt_sha256": prompt_sha256(),
                "attempts": outcome.attempts,
                "request_ids": list(outcome.request_ids),
                "ambiguity_count": len(payload.ambiguities),
            },
        )
        return CompilationRecord(
            draft_id=draft_id,
            state=state,
            error_code=None,
            attempts=outcome.attempts,
            request_ids=outcome.request_ids,
            superseded_draft_ids=tuple(superseded),
        )

    # ------------------------------------------------------------------
    # human decisions
    # ------------------------------------------------------------------

    def confirm_draft(
        self, *, draft_id: DraftId, confirmation_nonce: str, actor: str
    ) -> ConfirmationResult:
        """The single authority-creating transition (P3-S03).

        Exactly-once is enforced by the DATABASE, not by optimistic code paths:
        ``uq_draft_confirmation_nonce`` admits exactly one confirming UPDATE per
        draft. Under a same-nonce race the losing transaction receives an
        IntegrityError and re-reads the winner's durable result (honest
        replay); a DIFFERENT nonce surfacing the same conflict raises
        CONFIRMATION_REPLAY_MISMATCH.
        """
        try:
            return self._confirm_draft_inner(
                draft_id=draft_id,
                confirmation_nonce=confirmation_nonce,
                actor=actor,
            )
        except IntegrityError as exc:
            final = self.get_draft(draft_id)
            if (
                final is not None
                and final.state == DraftState.CONFIRMED.value
                and final.confirmation_nonce == confirmation_nonce
                and final.intent_id is not None
                and final.confirmed_generation is not None
            ):
                return ConfirmationResult(
                    draft_id=draft_id,
                    intent_id=IntentId(final.intent_id),
                    generation=final.confirmed_generation,
                    replayed=True,
                )
            raise ConfirmationError(
                "CONFIRMATION_REPLAY_MISMATCH",
                "confirmation lost a durability race",
            ) from exc

    def _confirm_draft_inner(
        self, *, draft_id: DraftId, confirmation_nonce: str, actor: str
    ) -> ConfirmationResult:
        if not confirmation_nonce or len(confirmation_nonce) > _MAX_NONCE_LEN:
            raise ConfirmationError("INVALID_NONCE", "confirmation nonce missing or oversized")

        now = self._clock.now_utc()
        with self._repos.transaction() as session:
            probe = session.get(IntentDraftRecord, str(draft_id))
            if probe is None:
                raise ConfirmationError("DRAFT_NOT_FOUND", f"unknown draft {draft_id}")
            _lock_lineage(session, probe.principal_id, probe.agent_id)
            row = self._repos.drafts.get_for_update(draft_id, session)
            assert row is not None  # locked probe row cannot vanish mid-transaction

            if row.state == DraftState.CONFIRMED.value:
                if row.confirmation_nonce == confirmation_nonce:
                    # Idempotent replay: same nonce, same result, no new authority.
                    assert row.intent_id is not None and row.confirmed_generation is not None
                    return ConfirmationResult(
                        draft_id=draft_id,
                        intent_id=IntentId(row.intent_id),
                        generation=row.confirmed_generation,
                        replayed=True,
                    )
                raise ConfirmationError(
                    "CONFIRMATION_REPLAY_MISMATCH",
                    "draft already confirmed with a different nonce",
                )
            if row.state == DraftState.REJECTED.value:
                raise ConfirmationError("DRAFT_NOT_CONFIRMABLE", "rejected draft is terminal")
            if row.state == DraftState.NEEDS_CLARIFICATION.value:
                raise ConfirmationError(
                    "DRAFT_NOT_CONFIRMABLE",
                    "ambiguities must be resolved by a fresh compilation first",
                )
            if row.superseded_by is not None:
                raise ConfirmationError("DRAFT_STALE", f"draft superseded by {row.superseded_by}")

            payload = CompilerIntentPayload.model_validate(row.payload)
            latest = self._repos.intents.latest_for_lineage_for_update(
                row.principal_id, row.agent_id, session
            )
            if latest is None:
                intent_id = IntentId.generate()
                generation = 1
            else:
                intent_id = IntentId(latest.intent_id)
                generation = latest.authorization_generation + 1

            contract = build_confirmed_contract(
                payload,
                principal_id=PrincipalId(row.principal_id),
                agent_id=AgentId(row.agent_id),
                intent_id=intent_id,
                generation=generation,
                now=now,
            )

            if latest is None:
                session.add(_contract_row(contract))
            else:
                _apply_supersession(session, latest, contract, now)

            row.state = DraftState.CONFIRMED.value
            row.confirmation_nonce = confirmation_nonce
            row.confirmed_generation = generation
            row.intent_id = str(intent_id)
            row.actor = actor
            row.decided_at = now
            row.updated_at = now
            session.flush()
            provenance = {
                "compiler_model": row.compiler_model,
                "prompt_version": row.prompt_version,
                "prompt_sha256": row.prompt_sha256,
                "source_text_sha256": row.source_text_sha256,
            }

        self._ledger.append(
            event_type="INTENT_CONFIRMED",
            actor=actor,
            timestamp=self._clock.now_utc(),
            intent_id=str(intent_id),
            payload={
                "draft_id": str(draft_id),
                "generation": generation,
                "schema_version": SCHEMA_VERSION_VALUE,
                **provenance,
            },
        )
        return ConfirmationResult(
            draft_id=draft_id, intent_id=intent_id, generation=generation, replayed=False
        )

    def reject_draft(self, *, draft_id: DraftId, actor: str) -> DraftState:
        now = self._clock.now_utc()
        with self._repos.transaction() as session:
            probe = session.get(IntentDraftRecord, str(draft_id))
            if probe is None:
                raise ConfirmationError("DRAFT_NOT_FOUND", f"unknown draft {draft_id}")
            _lock_lineage(session, probe.principal_id, probe.agent_id)
            row = self._repos.drafts.get_for_update(draft_id, session)
            assert row is not None

            if row.state == DraftState.REJECTED.value:
                return DraftState.REJECTED  # idempotent
            if row.state == DraftState.CONFIRMED.value:
                raise ConfirmationError(
                    "DRAFT_NOT_REJECTABLE",
                    "confirmed draft already created authority; revoke separately",
                )
            if row.superseded_by is not None:
                raise ConfirmationError("DRAFT_STALE", f"draft superseded by {row.superseded_by}")
            if DraftState(row.state) not in REJECTABLE_STATES:  # pragma: no cover - belt+braces
                raise ConfirmationError("DRAFT_NOT_REJECTABLE", f"state {row.state} final")

            prior_state = row.state
            row.state = DraftState.REJECTED.value
            row.actor = actor
            row.decided_at = now
            row.updated_at = now
            session.flush()

        self._ledger.append(
            event_type="INTENT_REJECTED",
            actor=actor,
            timestamp=self._clock.now_utc(),
            payload={"draft_id": str(draft_id), "prior_state": prior_state},
        )
        return DraftState.REJECTED

    def get_draft(self, draft_id: DraftId) -> IntentDraftRecord | None:
        return self._repos.drafts.get(draft_id)

    @staticmethod
    def _planner_model() -> str:
        from razormesh_api.settings import get_settings

        return get_settings().planner_model


def _contract_row(contract: IntentContract) -> IntentContractRow:
    return IntentContractRow(
        intent_id=str(contract.intent_id),
        principal_id=str(contract.principal_id),
        agent_id=str(contract.agent_id),
        authorization_generation=contract.authorization_generation,
        status=contract.status.value,
        allowed_merchant_ids=None,
        allowed_product_ids=None,
        allowed_categories=None,
        brand_restriction=(
            None
            if contract.brand_restriction is None
            else contract.brand_restriction.model_dump(mode="json")
        ),
        condition_restriction=(
            None
            if contract.condition_restriction is None
            else contract.condition_restriction.model_dump(mode="json")
        ),
        currency=contract.currency,
        max_total_minor=contract.max_total.amount_minor,
        aggregate_budget_minor=contract.aggregate_budget.amount_minor,
        max_quantity=contract.max_quantity,
        recurring_allowed=contract.recurring_allowed,
        approval_threshold_minor=contract.approval_threshold.amount_minor,
        issued_at=contract.issued_at,
        authorized_at=contract.authorized_at,
        expires_at=contract.expires_at,
        created_at=contract.issued_at,
        updated_at=contract.issued_at,
    )


def _apply_supersession(
    session: Session,
    latest: IntentContractRow,
    contract: IntentContract,
    now: datetime,
) -> None:
    """Bump the lineage generation in place; old tickets fail revalidation on
    the generation mismatch (existing AUTHORIZATION_SUPERSEDED path)."""
    spend = session.get(AuthorizationSpend, latest.intent_id, with_for_update=True)
    if spend is not None:
        committed_capacity = spend.reserved_minor + spend.committed_minor
        if committed_capacity > contract.max_total.amount_minor:
            raise ConfirmationError(
                "DRAFT_BELOW_COMMITTED_SPEND",
                f"new cap {contract.max_total.amount_minor} is below "
                f"reserved+committed {committed_capacity}",
            )
        spend.authorized_minor = contract.max_total.amount_minor
        spend.updated_at = now

    latest.authorization_generation = contract.authorization_generation
    latest.status = contract.status.value
    latest.currency = contract.currency
    latest.max_total_minor = contract.max_total.amount_minor
    latest.aggregate_budget_minor = contract.aggregate_budget.amount_minor
    latest.max_quantity = contract.max_quantity
    latest.recurring_allowed = contract.recurring_allowed
    latest.approval_threshold_minor = contract.approval_threshold.amount_minor
    latest.brand_restriction = (
        None
        if contract.brand_restriction is None
        else contract.brand_restriction.model_dump(mode="json")
    )
    latest.condition_restriction = (
        None
        if contract.condition_restriction is None
        else contract.condition_restriction.model_dump(mode="json")
    )
    latest.authorized_at = contract.authorized_at
    latest.expires_at = contract.expires_at
    latest.updated_at = now
