"""P2-M26: ONE idempotent reducer over VERIFIED provider events.

Inputs are only events whose authenticity was already established (verified
callback signature, HMAC-valid webhook, or direct provider fetch). The reducer
owns every business transition; callbacks/webhooks/fetches never mutate state
directly.

State dimensions stay separate (master prompt §23):
- internal execution attempt : CREATED/EXECUTING/PROVIDER_UNKNOWN/SUCCEEDED/FAILED
- provider order/payment     : snapshot strings stored on the attempt row
- reservation                : RESERVED -> COMMITTED | RELEASED (SpendManager)
- fulfilment                 : NOT_ELIGIBLE -> ELIGIBLE (synthetic only)

Key semantics (P2-S13..S16):
- duplicate evidence            -> no-op
- captured / order.paid         -> exactly-once settlement (commit + ELIGIBLE)
- payment.failed                -> definitive for THAT payment: settle FAILED,
                                   reservation RELEASED — but NOT unrecoverable:
                                   a later verified capture for the same order
                                   reconciles via guarded FAILED->SUCCEEDED
                                   (RAZORPAY_RECONCILED_LATE_CAPTURE).
- authorized                    -> informative only; never fulfils.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from razormesh_api.executor import (
    AttemptState,
    IllegalAttemptTransition,
    PaymentProvider,
    ProviderOutcome,
    TrustedPaymentExecutor,
)
from razormesh_api.keys import DevKeyPair
from razormesh_api.nonce import NonceRegistry
from razormesh_api.persistence.models import ExecutionAttempt
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.providers.razorpay import RazorpayError, RazorpayPaymentProvider
from razormesh_api.spend import SpendManager

EventKind = Literal[
    "payment.authorized",
    "payment.captured",
    "payment.failed",
    "order.paid",
]


@dataclass(frozen=True)
class VerifiedProviderEvent:
    """A provider event AFTER authenticity verification (signature checked)."""

    kind: EventKind
    razorpay_order_id: str
    razorpay_payment_id: str | None = None


_CAPTURED_EVIDENCE: tuple[str, ...] = ("payment.captured", "order.paid")


class ProviderStateReducer:
    """Applies verified events to durable attempts through the trusted executor."""

    def __init__(
        self,
        repos: Repositories,
        keys: DevKeyPair,
        nonces: NonceRegistry,
        *,
        provider: RazorpayPaymentProvider | PaymentProvider | None = None,
        spend: SpendManager | None = None,
    ) -> None:
        self._executor = TrustedPaymentExecutor(
            repos=repos, keys=keys, nonces=nonces, provider=provider, spend=spend
        )
        self._repos = repos
        self._keys = keys

    # ------------------------------------------------------------------
    def apply_event(
        self, event: VerifiedProviderEvent, *, now: datetime | None = None
    ) -> ExecutionAttempt:
        """Reduce one verified event to a safe durable state. Idempotent."""
        now = now or datetime.now(UTC)
        attempt = self._find_by_order(event.razorpay_order_id)

        if event.kind == "payment.authorized":
            # Informative only in EVERY attempt state (M27/D-031): authorized
            # snapshots lag and may arrive after a failure or reconciliation
            # (live M38 evidence: authorized for the retry payment arrived
            # while the attempt was FAILED). Never settles, never errors.
            return attempt
        if attempt.state == AttemptState.SUCCEEDED.value:
            return attempt  # duplicate evidence: exactly-once already satisfied

        if event.kind in _CAPTURED_EVIDENCE:
            return self._apply_capture_evidence(attempt, event, now)

        if event.kind == "payment.failed":
            return self._apply_failure(attempt, event, now)

        raise ValueError(f"unsupported provider event kind: {event.kind}")

    # ------------------------------------------------------------------
    def _apply_capture_evidence(
        self, attempt: ExecutionAttempt, event: VerifiedProviderEvent, now: datetime
    ) -> ExecutionAttempt:
        payment_id = event.razorpay_payment_id or f"order:{event.razorpay_order_id}"

        if attempt.state == AttemptState.EXECUTING.value:
            return self._executor.confirm_captured(
                attempt.execution_attempt_id, provider_payment_id=payment_id, now=now
            )

        if attempt.state == AttemptState.PROVIDER_UNKNOWN.value:
            settled = self._executor.resolve_unknown(
                attempt.execution_attempt_id,
                ProviderOutcome.SUCCEEDED,
                provider_reference=payment_id,
            )
            self._mark_payment_fields(settled.execution_attempt_id, payment_id, "captured")
            self._mark_fulfilment(settled.execution_attempt_id)
            self._audit("RAZORPAY_UNKNOWN_RESOLVED_CAPTURED", settled, payment_id)
            return self._refresh(settled.execution_attempt_id)

        if attempt.state == AttemptState.FAILED.value:
            # P2-S16: documented failed->captured reconciliation. Guarded:
            # requires remaining authorized capacity; audited loudly.
            return self._reconcile_late_capture(attempt, payment_id, now)

        raise IllegalAttemptTransition(f"capture evidence cannot apply to {attempt.state}")

    def _apply_failure(
        self, attempt: ExecutionAttempt, event: VerifiedProviderEvent, now: datetime
    ) -> ExecutionAttempt:
        if attempt.state == AttemptState.PROVIDER_UNKNOWN.value:
            settled = self._executor.resolve_unknown(
                attempt.execution_attempt_id,
                ProviderOutcome.FAILED,
                error_code="RAZORPAY_PAYMENT_FAILED",
            )
            self._mark_payment_fields(
                settled.execution_attempt_id, event.razorpay_payment_id, "failed"
            )
            return self._refresh(settled.execution_attempt_id)
        if attempt.state == AttemptState.FAILED.value:
            return attempt  # duplicate failure: already definitive

        # EXECUTING: failure of the payment is definitive for this attempt;
        # atomic settlement releases the reservation (D-028). A later capture
        # reconciles through _reconcile_late_capture.
        settled = self._executor.record_provider_failure(
            attempt.execution_attempt_id,
            error_code="RAZORPAY_PAYMENT_FAILED",
            now=now,
        )
        self._mark_payment_fields(settled.execution_attempt_id, event.razorpay_payment_id, "failed")
        return self._refresh(settled.execution_attempt_id)

    # ------------------------------------------------------------------
    def _reconcile_late_capture(
        self, attempt: ExecutionAttempt, payment_id: str, now: datetime
    ) -> ExecutionAttempt:
        """Guarded FAILED->SUCCEEDED reconciliation after verified late capture."""
        from razormesh_api.ledger import EvidenceLedger

        settled = self._executor.reconcile_failed_to_succeeded(
            attempt.execution_attempt_id,
            provider_reference=payment_id,
            now=now,
        )
        EvidenceLedger(self._repos).append(
            event_type="RAZORPAY_RECONCILED_LATE_CAPTURE",
            actor="provider-state-reducer",
            intent_id=settled.intent_id,
            checkout_id=settled.checkout_id,
            ticket_id=settled.ticket_id,
            payload={
                "execution_attempt_id": settled.execution_attempt_id,
                "razorpay_payment_id": payment_id,
                "reason_code": "RAZORPAY_RECONCILIATION_REQUIRED_RESOLVED",
            },
        )
        return settled

    # ------------------------------------------------------------------
    def _find_by_order(self, razorpay_order_id: str) -> ExecutionAttempt:

        with self._repos.transaction() as session:
            row = (
                session.query(ExecutionAttempt)
                .filter(ExecutionAttempt.razorpay_order_id == razorpay_order_id)
                .first()
            )
            if row is None:
                raise RazorpayError(
                    "RAZORPAY_ORDER_CONTEXT_MISMATCH",
                    f"no execution context claims order {razorpay_order_id}",
                )
            session.expunge(row)
        return row

    def _refresh(self, attempt_id: str) -> ExecutionAttempt:
        from razormesh_api.domain.ids import ExecutionAttemptId

        refreshed: ExecutionAttempt | None = self._repos.attempts.get(
            ExecutionAttemptId(attempt_id)
        )
        if refreshed is None:
            raise ValueError(f"attempt vanished: {attempt_id}")
        return refreshed

    def _mark_payment_fields(self, attempt_id: str, payment_id: str | None, status: str) -> None:
        from razormesh_api.domain.ids import ExecutionAttemptId

        with self._repos.transaction() as session:
            row = (
                session.get(
                    ExecutionAttemptId and ExecutionAttempt, attempt_id, with_for_update=True
                )
                if False
                else session.get(ExecutionAttempt, attempt_id, with_for_update=True)
            )
            if row is not None:
                if payment_id:
                    row.razorpay_payment_id = payment_id
                row.razorpay_payment_status = status
                row.updated_at = datetime.now(UTC)

    def _mark_fulfilment(self, attempt_id: str) -> None:
        with self._repos.transaction() as session:
            row = session.get(ExecutionAttempt, attempt_id, with_for_update=True)
            if row is not None:
                row.fulfilment_state = "ELIGIBLE"

    def _audit(self, event_type: str, attempt: ExecutionAttempt, payment_id: str) -> None:
        from razormesh_api.ledger import EvidenceLedger

        EvidenceLedger(self._repos).append(
            event_type=event_type,
            actor="provider-state-reducer",
            intent_id=attempt.intent_id,
            checkout_id=attempt.checkout_id,
            ticket_id=attempt.ticket_id,
            payload={
                "execution_attempt_id": attempt.execution_attempt_id,
                "razorpay_payment_id": payment_id,
            },
        )
