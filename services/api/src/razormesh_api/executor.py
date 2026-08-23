"""M36: the ONLY component permitted to invoke a payment provider.

Every financial side effect goes through ``TrustedPaymentExecutor.execute``:

1. verify ticket (signature, expiry, all context bindings)  [M34]
2. atomically claim the ticket's single-use nonce           [M35]
3. reuse-or-create the durable ``ExecutionAttempt`` keyed by
   an idempotency identity                                   [M20 schema]
4. call the provider exactly once per attempt
5. persist terminal state: SUCCEEDED / FAILED / PROVIDER_UNKNOWN

If the provider's outcome cannot be determined (timeout, crash-after-send),
the attempt stays PROVIDER_UNKNOWN and retries WITH THE SAME idempotency key
return the same attempt — never a fresh financial operation.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from razormesh_api.domain.ids import ExecutionAttemptId, IntentId
from razormesh_api.keys import DevKeyPair
from razormesh_api.nonce import NonceAlreadyClaimed, NonceRegistry
from razormesh_api.persistence.models import ExecutionAttempt
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.spend import SpendManager
from razormesh_api.tickets import (
    CurrentBinding,
    SignedTicket,
    TicketVerifier,
)


class AttemptState(StrEnum):
    CREATED = "CREATED"
    EXECUTING = "EXECUTING"
    PROVIDER_UNKNOWN = "PROVIDER_UNKNOWN"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ProviderOutcome(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class ChargeRequest(Protocol): ...


@dataclass(frozen=True)
class ChargeCommand:
    execution_attempt_id: str
    intent_id: str
    amount_minor: int
    currency: str
    nonce: str


@dataclass(frozen=True)
class ChargeResult:
    outcome: ProviderOutcome
    provider_reference: str | None = None
    error_code: str | None = None


class PaymentProvider(Protocol):
    """The boundary RazorMesh trusts ONLY the executor to cross."""

    def charge(self, command: ChargeCommand) -> ChargeResult: ...


class IllegalAttemptTransition(Exception):
    pass


_TRANSITIONS: dict[str, set[str]] = {
    AttemptState.CREATED: {AttemptState.EXECUTING},
    AttemptState.EXECUTING: {
        AttemptState.SUCCEEDED,
        AttemptState.FAILED,
        AttemptState.PROVIDER_UNKNOWN,
    },
    # Terminal or awaiting-provider-resolution: no direct exits from here.
    AttemptState.PROVIDER_UNKNOWN: set(),
    AttemptState.SUCCEEDED: set(),
    AttemptState.FAILED: set(),
}


def require_transition(current: str, target: str) -> None:
    if target not in _TRANSITIONS.get(current, set()):
        raise IllegalAttemptTransition(f"illegal attempt transition {current} -> {target}")


class TrustedPaymentExecutor:
    def __init__(
        self,
        repos: Repositories,
        keys: DevKeyPair,
        nonces: NonceRegistry,
        provider: PaymentProvider,
        spend: SpendManager | None = None,
    ) -> None:
        self._repos = repos
        self._keys = keys
        self._nonces = nonces
        self._provider = provider
        self._spend = spend

    def execute(
        self,
        *,
        signed_ticket: SignedTicket,
        binding: CurrentBinding,
        intent_id: IntentId,
        idempotency_key: str,
        now_utc: datetime | None = None,
    ) -> ExecutionAttempt:
        now = now_utc or datetime.now(UTC)

        # Idempotent re-entry FIRST: an existing durable attempt is returned
        # as-is. A provider-unknown outcome can therefore never spawn a fresh
        # financial operation.
        existing = self._repos.attempts.find_by_idempotency(idempotency_key)
        if existing is not None:
            return existing

        # 1. Ticket must be fully valid against current authority.
        verifier = TicketVerifier(self._keys, now_utc=now)
        claims = verifier.verify(signed_ticket, binding)

        # 2. Single-use nonce claim (coordination only).
        try:
            self._nonces.claim(str(claims.nonce), holder_id=idempotency_key)
        except NonceAlreadyClaimed:
            raise

        # 3. Durable CREATED row before touching the provider.
        #    Persist the verified ticket itself so FK/audit integrity holds.
        self._persist_ticket(claims, now)
        attempt = ExecutionAttempt(
            execution_attempt_id=str(ExecutionAttemptId.generate()),
            idempotency_key=idempotency_key,
            ticket_id=str(claims.ticket_id),
            intent_id=str(intent_id),
            checkout_id=str(claims.checkout_id),
            amount_minor=claims.amount_minor,
            currency=claims.currency,
            state=AttemptState.CREATED.value,
            created_at=now,
            updated_at=now,
        )
        attempt = self._repos.attempts.save(attempt)

        # 4. Mark EXECUTING durably, then call the provider once.
        self._transition(attempt, AttemptState.EXECUTING, now)
        command = ChargeCommand(
            execution_attempt_id=attempt.execution_attempt_id,
            intent_id=str(intent_id),
            amount_minor=claims.amount_minor,
            currency=claims.currency,
            nonce=str(claims.nonce),
        )
        try:
            result = self._provider.charge(command)
        except Exception as exc:  # noqa: BLE001 - any blowup means UNKNOWN
            self._transition(
                attempt,
                AttemptState.PROVIDER_UNKNOWN,
                now,
                error_code=f"PROVIDER_EXCEPTION:{type(exc).__name__}",
            )
            return self._refresh(attempt)

        # 5. Persist the resolved terminal state.
        if result.outcome == ProviderOutcome.SUCCEEDED:
            attempt.provider_reference = result.provider_reference
            attempt.provider_event = {"reference": result.provider_reference}
            self._transition(attempt, AttemptState.SUCCEEDED, now)
            if self._spend is not None:
                self._spend.commit(intent_id, claims.amount_minor)
        elif result.outcome == ProviderOutcome.FAILED:
            attempt.error_code = result.error_code
            self._transition(attempt, AttemptState.FAILED, now)
            if self._spend is not None:
                self._spend.release(intent_id, claims.amount_minor)
        else:
            # Provider-unknown: reservation intentionally KEPT (no release).
            self._transition(attempt, AttemptState.PROVIDER_UNKNOWN, now)
        return self._refresh(attempt)

    def resolve_unknown(
        self,
        attempt_id: str,
        outcome: ProviderOutcome,
        provider_reference: str | None = None,
        error_code: str | None = None,
    ) -> ExecutionAttempt:
        """Explicit human/ops resolution of a PROVIDER_UNKNOWN attempt."""
        attempt = self._repos.attempts.get(ExecutionAttemptId(attempt_id))
        if attempt is None:
            raise ValueError(f"unknown attempt {attempt_id}")
        if attempt.state != AttemptState.PROVIDER_UNKNOWN:
            raise IllegalAttemptTransition(
                f"only PROVIDER_UNKNOWN attempts can be resolved, got {attempt.state}"
            )
        target = (
            AttemptState.SUCCEEDED if outcome == ProviderOutcome.SUCCEEDED else AttemptState.FAILED
        )
        now = datetime.now(UTC)
        self._transition(attempt, target, now)
        attempt.provider_reference = provider_reference
        attempt.error_code = error_code
        return self._refresh(attempt)

    def _persist_ticket(self, claims: object, now: datetime) -> None:
        """Store the verified ticket durably (idempotent merge)."""
        from razormesh_api.persistence.models import ExecutionTicket

        ticket = ExecutionTicket(
            ticket_id=str(claims.ticket_id),  # type: ignore[attr-defined]
            principal_id=str(claims.principal_id),  # type: ignore[attr-defined]
            agent_id=str(claims.agent_id),  # type: ignore[attr-defined]
            intent_id=str(claims.intent_id),  # type: ignore[attr-defined]
            intent_hash=str(claims.intent_hash),  # type: ignore[attr-defined]
            authorization_generation=claims.authorization_generation,  # type: ignore[attr-defined]
            checkout_hash=str(claims.checkout_hash),  # type: ignore[attr-defined]
            checkout_revision=claims.checkout_revision,  # type: ignore[attr-defined]
            merchant_id=str(claims.merchant_id),  # type: ignore[attr-defined]
            amount_minor=claims.amount_minor,  # type: ignore[attr-defined]
            currency=str(claims.currency),  # type: ignore[attr-defined]
            decision_id=str(claims.decision_id),  # type: ignore[attr-defined]
            policy_version=str(claims.policy_version),  # type: ignore[attr-defined]
            nonce=str(claims.nonce),  # type: ignore[attr-defined]
            issued_at=claims.issued_at,  # type: ignore[attr-defined]
            expires_at=claims.expires_at,  # type: ignore[attr-defined]
            used_at=None,
            created_at=now,
        )
        with self._repos.transaction() as session:
            session.merge(ticket)

    def _transition(
        self,
        attempt: ExecutionAttempt,
        target: AttemptState,
        now: datetime,
        error_code: str | None = None,
    ) -> None:
        require_transition(attempt.state, target.value)
        attempt.state = target.value
        if error_code is not None:
            attempt.error_code = error_code
        attempt.updated_at = now
        self._repos.attempts.save(attempt)

    def _refresh(self, attempt: ExecutionAttempt) -> ExecutionAttempt:
        refreshed = self._repos.attempts.get(ExecutionAttemptId(attempt.execution_attempt_id))
        if refreshed is None:
            raise ValueError(f"attempt vanished: {attempt.execution_attempt_id}")
        return refreshed
