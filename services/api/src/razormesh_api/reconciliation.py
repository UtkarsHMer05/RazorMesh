"""P2-M41: reconciliation service for provider-unknown / lost-evidence attempts.

A PROVIDER_UNKNOWN attempt keeps its durable execution identity and its
reservation (P2-S18) until provider truth is established. This service drives
that truth through the ONE reducer; it never creates a second financial
operation and never retries the original order creation (P2-S19).

Semantics (D-036):
1. If the attempt has no correlated razorpay_order_id (create response was
   lost), READ-ONLY receipt discovery recovers the order and — only after the
   discovered amount/currency match durable authority — CLAIMS the order id
   onto the attempt. Claiming binds CORRELATION only; business state is still
   owned exclusively by the reducer.
2. reconcile_attempt() revalidates amount/currency/receipt on every fetch;
   mismatches raise loudly and mutate nothing (P2-S06).
3. Fetched "paid"  -> capture evidence reduced as order.paid: exactly-once
   settlement from EXECUTING/PROVIDER_UNKNOWN, guarded path from FAILED.
   Successful settlement marks reconcile_state=RESOLVED. A provider failure
   stays REQUIRED with its reservation held because a later capture remains a
   documented possibility.
4. Any other status -> snapshot only: keep waiting for outcome evidence
   (webhook/callback). No guess, no transition. Once the order id is claimed,
   later webhooks for that order correlate normally.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from razormesh_api.persistence.repositories import Repositories
from razormesh_api.providers.razorpay import (
    RazorpayOrder,
    RazorpayPaymentProvider,
    RazorpayProviderStateConflict,
    discover_order_by_receipt,
    reconcile_attempt,
)
from razormesh_api.reducer import ProviderStateReducer, VerifiedProviderEvent


@dataclass(frozen=True)
class ReconciliationOutcome:
    """Safe operator-facing result of one reconciliation pass."""

    attempt_id: str
    intent_id: str
    order_id: str
    attempt_state_before: str
    attempt_state_after: str
    reconcile_state_after: str
    provider_order_status: str
    order_discovered_and_claimed: bool
    settled_by_reconciliation: bool
    detail: str


class ReconciliationService:
    """Read-only provider fetch + reducer-driven settlement for ONE attempt."""

    def __init__(
        self,
        *,
        repos: Repositories,
        provider: RazorpayPaymentProvider,
        reducer: ProviderStateReducer,
    ) -> None:
        self._repos = repos
        self._provider = provider
        self._reducer = reducer

    def reconcile(self, attempt_id: str, *, now: datetime | None = None) -> ReconciliationOutcome:
        now = now or datetime.now(UTC)

        from razormesh_api.persistence.models import ExecutionAttempt

        with self._repos.transaction() as session:
            row = session.get(ExecutionAttempt, attempt_id)
            if row is None:
                raise ValueError(f"unknown attempt {attempt_id}")
            before_state = row.state
            intent_id = row.intent_id
            amount_minor = row.amount_minor
            currency = row.currency

        claimed = False
        if not self._order_id_of(attempt_id):
            discovered = discover_order_by_receipt(
                provider=self._provider, receipt=f"r_{attempt_id}"
            )
            if discovered is not None:
                self._validate_against_authority(discovered, amount_minor, currency)
                self._claim(attempt_id, discovered, now)
                claimed = True

        order_id = self._order_id_of(attempt_id)
        if order_id is None:
            return ReconciliationOutcome(
                attempt_id=attempt_id,
                intent_id=intent_id,
                order_id="",
                attempt_state_before=before_state,
                attempt_state_after=self._state_of(attempt_id),
                reconcile_state_after="REQUIRED",
                provider_order_status="",
                order_discovered_and_claimed=False,
                settled_by_reconciliation=False,
                detail=(
                    "no provider order discovered yet; identity+reservation held, "
                    "still awaiting outcome evidence"
                ),
            )

        result = reconcile_attempt(
            repos=self._repos, provider=self._provider, attempt_id=attempt_id, now=now
        )

        settled = False
        if result.payment_status == "captured" and before_state != "SUCCEEDED":
            # Fetch-proven capture evidence flows through the SAME idempotent
            # reducer as webhooks/callbacks — never a bespoke settlement path.
            self._reducer.apply_event(
                VerifiedProviderEvent(kind="order.paid", razorpay_order_id=result.order_id),
                now=now,
            )
            settled = True

        after_state = self._state_of(attempt_id)
        return ReconciliationOutcome(
            attempt_id=attempt_id,
            intent_id=intent_id,
            order_id=result.order_id,
            attempt_state_before=before_state,
            attempt_state_after=after_state,
            reconcile_state_after=self._reconcile_state_of(attempt_id),
            provider_order_status=result.provider_status,
            order_discovered_and_claimed=claimed,
            settled_by_reconciliation=settled and after_state != before_state,
            detail=(
                "capture evidence reduced through provider-state reducer"
                if settled
                else "provider snapshot recorded; awaiting outcome evidence"
            ),
        )

    # ------------------------------------------------------------------
    def _order_id_of(self, attempt_id: str) -> str | None:
        from razormesh_api.persistence.models import ExecutionAttempt

        with self._repos.transaction() as session:
            row = session.get(ExecutionAttempt, attempt_id)
            return row.razorpay_order_id if row else None

    def _state_of(self, attempt_id: str) -> str:
        from razormesh_api.persistence.models import ExecutionAttempt

        with self._repos.transaction() as session:
            row = session.get(ExecutionAttempt, attempt_id)
            if row is None:
                raise ValueError(f"attempt vanished: {attempt_id}")
            return row.state

    def _reconcile_state_of(self, attempt_id: str) -> str:
        from razormesh_api.persistence.models import ExecutionAttempt

        with self._repos.transaction() as session:
            row = session.get(ExecutionAttempt, attempt_id)
            if row is None:
                raise ValueError(f"attempt vanished: {attempt_id}")
            return row.reconcile_state or "NONE"

    @staticmethod
    def _validate_against_authority(
        discovered: RazorpayOrder, amount_minor: int, currency: str
    ) -> None:
        """Authority gate BEFORE any claim: provider never rewrites internal truth."""
        if discovered.amount_minor != amount_minor:
            raise RazorpayProviderStateConflict(
                "RAZORPAY_AMOUNT_MISMATCH",
                f"discovered provider order {discovered.amount_minor} != internal {amount_minor}",
            )
        if discovered.currency != currency:
            raise RazorpayProviderStateConflict(
                "RAZORPAY_CURRENCY_MISMATCH",
                f"discovered provider order currency {discovered.currency} != internal {currency}",
            )
        if discovered.receipt is None:
            raise RazorpayProviderStateConflict(
                "RAZORPAY_ORDER_CONTEXT_MISMATCH",
                "discovered provider order carries no receipt to bind correlation",
            )

    def _claim(self, attempt_id: str, discovered: RazorpayOrder, now: datetime) -> None:
        """Persist the discovered order id under the partial-unique claim."""
        from sqlalchemy.exc import IntegrityError

        from razormesh_api.persistence.models import ExecutionAttempt

        try:
            with self._repos.transaction() as session:
                row = session.get(ExecutionAttempt, attempt_id, with_for_update=True)
                if row is None:
                    raise ValueError(f"attempt vanished: {attempt_id}")
                if row.razorpay_order_id:
                    return  # raced ahead of us; existing claim wins
                row.razorpay_order_id = discovered.order_id
                row.razorpay_order_status = discovered.status
                row.updated_at = now
        except IntegrityError as exc:
            raise RazorpayProviderStateConflict(
                "RAZORPAY_ORDER_CONTEXT_MISMATCH",
                f"another attempt already claims provider order {discovered.order_id}",
            ) from exc
