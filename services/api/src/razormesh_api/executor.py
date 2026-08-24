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

from razormesh_api.domain.authz_hash import (
    checkout_authorization_hash,
    intent_authorization_hash,
)
from razormesh_api.domain.ids import CheckoutId, DecisionId, ExecutionAttemptId, IntentId
from razormesh_api.domain.intent import IntentStatus
from razormesh_api.keys import DevKeyPair
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.nonce import NonceRegistry
from razormesh_api.persistence.models import AuthorizationSpend, ExecutionAttempt
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.providers.razorpay import (
    RazorpayError,
    RazorpayPaymentProvider,
    RazorpayUnknownOutcomeError,
    build_order_correlation,
)
from razormesh_api.spend import SpendManager
from razormesh_api.tickets import (
    CurrentBinding,
    ExecutionTicketClaims,
    SignedTicket,
    TicketRejected,
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
    # Awaiting provider truth: only explicit reconciliation (resolve_unknown)
    # may exit, applying the authoritative outcome.
    AttemptState.PROVIDER_UNKNOWN: {AttemptState.SUCCEEDED, AttemptState.FAILED},
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
        now_utc: datetime | None = None,
    ) -> ExecutionAttempt:
        now = now_utc or datetime.now(UTC)

        # 1. Ticket must be fully valid against current authority.
        verifier = TicketVerifier(self._keys, now_utc=now)
        claims = verifier.verify(signed_ticket, binding)
        if claims.intent_id != intent_id:
            raise TicketRejected("INTENT_MISMATCH", "executor intent does not match ticket")
        self._validate_durable_authority(claims, now)

        # The durable idempotency identity is derived from signed authority,
        # never supplied by an untrusted caller. This remains safe if Redis is
        # restarted because one ticket always maps to one attempt identity.
        idempotency_key = f"ticket:{claims.ticket_id}"
        existing = self._repos.attempts.find_by_idempotency(idempotency_key)
        if existing is not None:
            return existing

        # 2. Single-use nonce claim (coordination only).
        self._nonces.claim(str(claims.nonce), holder_id=idempotency_key)

        # 3. Hold durable authorization capacity only after every ticket and
        # current-authority check has passed. Compensate safely if creation
        # fails before any provider effect is possible.
        reserved = False
        attempt: ExecutionAttempt | None = None
        try:
            if self._spend is not None:
                self._spend.reserve(intent_id, claims.amount_minor)
                reserved = True

            # Durable CREATED row before touching the provider.
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
            self._mark_ticket_used(claims, now)
            EvidenceLedger(self._repos).append(
                event_type="EXECUTION_ATTEMPT_CREATED",
                actor="trusted-payment-executor",
                intent_id=str(claims.intent_id),
                checkout_id=str(claims.checkout_id),
                decision_id=str(claims.decision_id),
                ticket_id=str(claims.ticket_id),
                intent_hash=claims.intent_hash,
                checkout_hash=claims.checkout_hash,
                payload={
                    "execution_attempt_id": attempt.execution_attempt_id,
                    "amount_minor": claims.amount_minor,
                    "currency": claims.currency,
                },
            )
        except Exception:
            released_atomically = False
            if attempt is not None:
                released_atomically = self._abort_created_attempt(
                    attempt.execution_attempt_id, now, release_reservation=reserved
                )
            if reserved and not released_atomically and self._spend is not None:
                self._spend.release(intent_id, claims.amount_minor)
            self._nonces.release(str(claims.nonce), idempotency_key)
            raise

        # 4. Mark EXECUTING durably, then call the provider once.
        self._transition(attempt, AttemptState.EXECUTING, now)

        # Phase-2 real-provider path (P2-M15): Standard Checkout replaces the
        # synchronous charge with a server-created order; the attempt stays
        # EXECUTING until verified captured/paid evidence arrives.
        if isinstance(self._provider, RazorpayPaymentProvider):
            return self._execute_razorpay_order(attempt, claims, now)

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
            return self._settle(
                attempt.execution_attempt_id,
                AttemptState.PROVIDER_UNKNOWN,
                now,
                error_code=f"PROVIDER_EXCEPTION:{type(exc).__name__}",
            )

        # 5. Persist the resolved terminal state.
        if result.outcome == ProviderOutcome.SUCCEEDED:
            return self._settle(
                attempt.execution_attempt_id,
                AttemptState.SUCCEEDED,
                now,
                provider_reference=result.provider_reference,
            )
        elif result.outcome == ProviderOutcome.FAILED:
            return self._settle(
                attempt.execution_attempt_id,
                AttemptState.FAILED,
                now,
                error_code=result.error_code,
            )
        # Provider-unknown: reservation intentionally KEPT (no release).
        return self._settle(attempt.execution_attempt_id, AttemptState.PROVIDER_UNKNOWN, now)

    def _execute_razorpay_order(
        self,
        attempt: ExecutionAttempt,
        claims: ExecutionTicketClaims,
        now: datetime,
    ) -> ExecutionAttempt:
        """Create the server-authoritative Razorpay order for this execution.

        Amount/currency come exclusively from the verified durable claims — the
        browser never supplies them (P2-S05/S06). Outcome mapping (P2-S17..S19):
        - definitive rejection/auth failure -> FAILED, reservation released;
        - timeout/5xx/malformed            -> PROVIDER_UNKNOWN, reservation KEPT,
          reconcile_state=REQUIRED; never retried as a fresh order;
        - success                          -> attempt stays EXECUTING with the
          razorpay_order_id durably correlated until capture evidence arrives.
        """
        assert isinstance(self._provider, RazorpayPaymentProvider)
        receipt, notes = build_order_correlation(
            execution_attempt_id=attempt.execution_attempt_id,
            intent_id=str(claims.intent_id),
            checkout_id=str(claims.checkout_id),
            decision_id=str(claims.decision_id),
            ticket_id=str(claims.ticket_id),
            authorization_generation=claims.authorization_generation,
        )
        try:
            order = self._provider.create_order(
                amount_minor=attempt.amount_minor,
                currency=attempt.currency,
                receipt=receipt,
                notes=notes,
            )
        except RazorpayUnknownOutcomeError as exc:
            settled = self._settle(
                attempt.execution_attempt_id,
                AttemptState.PROVIDER_UNKNOWN,
                now,
                error_code=exc.code,
                reconcile_state="REQUIRED",
            )
            EvidenceLedger(self._repos).append(
                event_type="RAZORPAY_ORDER_UNKNOWN",
                actor="trusted-payment-executor",
                intent_id=settled.intent_id,
                checkout_id=settled.checkout_id,
                ticket_id=settled.ticket_id,
                payload={
                    "execution_attempt_id": settled.execution_attempt_id,
                    "reason_code": exc.code,
                },
            )
            return settled
        except RazorpayError as exc:
            settled = self._settle(
                attempt.execution_attempt_id,
                AttemptState.FAILED,
                now,
                error_code=exc.code,
            )
            EvidenceLedger(self._repos).append(
                event_type="RAZORPAY_ORDER_REJECTED",
                actor="trusted-payment-executor",
                intent_id=settled.intent_id,
                checkout_id=settled.checkout_id,
                ticket_id=settled.ticket_id,
                payload={
                    "execution_attempt_id": settled.execution_attempt_id,
                    "reason_code": exc.code,
                },
            )
            return settled

        with self._repos.transaction() as session:
            row = session.get(ExecutionAttempt, attempt.execution_attempt_id, with_for_update=True)
            if row is None:
                raise ValueError(f"attempt vanished: {attempt.execution_attempt_id}")
            if row.razorpay_order_id not in (None, order.order_id):
                raise ValueError("attempt already claims a different provider order")
            row.razorpay_order_id = order.order_id
            row.razorpay_order_status = order.status
            row.provider_reference = order.order_id
            row.updated_at = now

        EvidenceLedger(self._repos).append(
            event_type="RAZORPAY_ORDER_CREATED",
            actor="trusted-payment-executor",
            intent_id=str(claims.intent_id),
            checkout_id=str(claims.checkout_id),
            ticket_id=str(claims.ticket_id),
            payload={
                "execution_attempt_id": attempt.execution_attempt_id,
                "razorpay_order_id": order.order_id,
                "receipt": receipt,
                "amount_minor": attempt.amount_minor,
                "currency": attempt.currency,
            },
        )
        return self._refresh_by_id(attempt.execution_attempt_id)

    def _abort_created_attempt(
        self,
        attempt_id: str,
        now: datetime,
        *,
        release_reservation: bool,
    ) -> bool:
        """Durably close pre-provider work so a partial setup cannot look executable."""
        with self._repos.transaction() as session:
            attempt = session.get(ExecutionAttempt, attempt_id, with_for_update=True)
            if attempt is None or attempt.state != AttemptState.CREATED.value:
                return False
            if release_reservation and self._spend is not None:
                spend = session.get(AuthorizationSpend, attempt.intent_id, with_for_update=True)
                if spend is None or spend.reserved_minor < attempt.amount_minor:
                    raise ValueError("pre-provider reservation cannot be compensated")
                spend.reserved_minor -= attempt.amount_minor
                spend.version += 1
                spend.updated_at = now
            attempt.state = AttemptState.FAILED.value
            attempt.error_code = "PRE_PROVIDER_ABORTED"
            attempt.updated_at = now
        return release_reservation

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
        if outcome == ProviderOutcome.UNKNOWN:
            raise IllegalAttemptTransition("UNKNOWN is not a reconciliation resolution")
        target = (
            AttemptState.SUCCEEDED if outcome == ProviderOutcome.SUCCEEDED else AttemptState.FAILED
        )
        now = datetime.now(UTC)
        return self._settle(
            attempt.execution_attempt_id,
            target,
            now,
            provider_reference=provider_reference,
            error_code=error_code,
        )

    def _persist_ticket(self, claims: ExecutionTicketClaims, now: datetime) -> None:
        """Store the verified ticket durably (idempotent merge)."""
        from razormesh_api.persistence.models import ExecutionTicket

        ticket = ExecutionTicket(
            ticket_id=str(claims.ticket_id),
            principal_id=str(claims.principal_id),
            agent_id=str(claims.agent_id),
            intent_id=str(claims.intent_id),
            intent_hash=str(claims.intent_hash),
            authorization_generation=claims.authorization_generation,
            checkout_hash=str(claims.checkout_hash),
            checkout_revision=claims.checkout_revision,
            merchant_id=str(claims.merchant_id),
            amount_minor=claims.amount_minor,
            currency=str(claims.currency),
            decision_id=str(claims.decision_id),
            policy_version=str(claims.policy_version),
            nonce=str(claims.nonce),
            issued_at=claims.issued_at,
            expires_at=claims.expires_at,
            used_at=None,
            created_at=now,
        )
        with self._repos.transaction() as session:
            session.merge(ticket)

    def _mark_ticket_used(self, claims: ExecutionTicketClaims, now: datetime) -> None:
        from razormesh_api.persistence.models import ExecutionTicket

        with self._repos.transaction() as session:
            row = session.get(ExecutionTicket, str(claims.ticket_id), with_for_update=True)
            if row is None:
                raise TicketRejected("UNKNOWN_TICKET", "durable ticket metadata is missing")
            row.used_at = now

    def _validate_durable_authority(self, claims: ExecutionTicketClaims, now: datetime) -> None:
        """Re-read PostgreSQL authority at the provider boundary and fail closed."""
        from razormesh_api.revalidation import Revalidator, domain_intent_from_row

        intent_row = self._repos.intents.get(claims.intent_id)
        if intent_row is None:
            raise TicketRejected("AUTHORIZATION_MISSING", "durable intent is missing")
        contract = domain_intent_from_row(intent_row)
        if contract.status is not IntentStatus.AUTHORIZED:
            raise TicketRejected(
                "STATUS_NOT_EXECUTABLE", f"authorization status is {contract.status.value}"
            )
        if now >= contract.expires_at:
            raise TicketRejected("AUTHORIZATION_EXPIRED", "human authorization has expired")
        if intent_authorization_hash(contract) != claims.intent_hash:
            raise TicketRejected("AUTHORIZATION_SUPERSEDED", "durable intent terms changed")

        checkout_row = self._repos.checkouts.get(CheckoutId(str(claims.checkout_id)))
        if checkout_row is None:
            raise TicketRejected("CHECKOUT_MISSING", "durable checkout is missing")
        try:
            checkout = Revalidator(self._repos).rebuild_envelope(checkout_row)
        except Exception as exc:
            raise TicketRejected(
                "CHECKOUT_CHANGED", f"durable checkout cannot be rebuilt: {type(exc).__name__}"
            ) from exc
        if checkout_authorization_hash(checkout) != claims.checkout_hash:
            raise TicketRejected("CHECKOUT_CHANGED", "durable checkout hash changed")

        decision = self._repos.decisions.get(DecisionId(str(claims.decision_id)))
        if decision is None:
            raise TicketRejected("UNKNOWN_DECISION", "durable decision is missing")
        decision_matches = (
            decision.decision == "ALLOW"
            and decision.intent_id == str(claims.intent_id)
            and decision.checkout_id == str(claims.checkout_id)
            and decision.intent_generation == claims.authorization_generation
            and decision.checkout_hash == claims.checkout_hash
            and decision.policy_version == claims.policy_version
        )
        if not decision_matches:
            raise TicketRejected(
                "DECISION_NOT_EXECUTABLE", "durable decision is not the ticket's current ALLOW"
            )

    def _settle(
        self,
        attempt_id: str,
        target: AttemptState,
        now: datetime,
        *,
        provider_reference: str | None = None,
        error_code: str | None = None,
        reconcile_state: str | None = None,
    ) -> ExecutionAttempt:
        """Atomically settle attempt state and its reservation in PostgreSQL."""
        with self._repos.transaction() as session:
            attempt = session.get(ExecutionAttempt, attempt_id, with_for_update=True)
            if attempt is None:
                raise ValueError(f"attempt vanished: {attempt_id}")
            require_transition(attempt.state, target.value)
            if self._spend is not None:
                spend = session.get(AuthorizationSpend, attempt.intent_id, with_for_update=True)
                if spend is None:
                    raise ValueError(f"reservation vanished for {attempt.intent_id}")
                if target in (AttemptState.SUCCEEDED, AttemptState.FAILED):
                    if spend.reserved_minor < attempt.amount_minor:
                        raise ValueError("reservation is smaller than the execution attempt")
                    spend.reserved_minor -= attempt.amount_minor
                    if target is AttemptState.SUCCEEDED:
                        spend.committed_minor += attempt.amount_minor
                    spend.version += 1
                    spend.updated_at = now
            attempt.state = target.value
            attempt.provider_reference = provider_reference
            attempt.provider_event = (
                {"reference": provider_reference} if provider_reference is not None else None
            )
            attempt.error_code = error_code
            if reconcile_state is not None:
                attempt.reconcile_state = reconcile_state
            attempt.updated_at = now
        settled = self._refresh_by_id(attempt_id)
        EvidenceLedger(self._repos).append(
            event_type=f"PAYMENT_{target.value}",
            actor="trusted-payment-executor",
            intent_id=settled.intent_id,
            checkout_id=settled.checkout_id,
            ticket_id=settled.ticket_id,
            payload={
                "execution_attempt_id": settled.execution_attempt_id,
                "provider_reference": provider_reference,
                "error_code": error_code,
            },
        )
        return settled

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
        return self._refresh_by_id(attempt.execution_attempt_id)

    def _refresh_by_id(self, attempt_id: str) -> ExecutionAttempt:
        refreshed = self._repos.attempts.get(ExecutionAttemptId(attempt_id))
        if refreshed is None:
            raise ValueError(f"attempt vanished: {attempt_id}")
        return refreshed
