"""P2-M33: durable webhook event inbox — dedup at the database level.

One row per x-razorpay-event-id (primary key). Concurrent duplicate deliveries
serialize on the unique constraint: exactly one wins ingestion and drives
processing; the loser is classified DUPLICATE without any business mutation.
Processing failures are recorded on the row for operators while still returning
a controlled 200 to Razorpay (business safety never depends on retries).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from razormesh_api.persistence.models import ProviderEvent
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.providers.razorpay import RazorpayError


@dataclass(frozen=True)
class IngestResult:
    duplicate: bool
    processed: bool
    reason: str | None = None


def ingest_verified_event(
    repos: Repositories,
    *,
    event_id: str,
    event_type: str,
    payload_sha256: str,
    razorpay_order_id: str | None,
    razorpay_payment_id: str | None,
    process: Callable[[], None],
) -> IngestResult:
    """Claim the event durably, then process exactly once.

    ``process`` runs ONLY for the delivery that won the insert claim.
    """
    now = datetime.now(UTC)
    claimed = False
    try:
        with repos.transaction() as session:
            session.add(
                ProviderEvent(
                    event_id=event_id,
                    provider_name="razorpay",
                    event_type=event_type,
                    received_at=now,
                    verified=True,
                    processing_state="RECEIVED",
                    payload_sha256=payload_sha256,
                    razorpay_order_id=razorpay_order_id,
                    razorpay_payment_id=razorpay_payment_id,
                )
            )
            session.flush()
        claimed = True
    except IntegrityError:
        claimed = False

    if not claimed:
        return IngestResult(duplicate=True, processed=False, reason="DUPLICATE_EVENT")

    try:
        process()
    except RazorpayError as exc:
        if exc.code == "RAZORPAY_ORDER_CONTEXT_MISMATCH":
            # Expected operational state, not a processing failure: a verified
            # event for an order this database has no execution context for
            # (e.g. retries for payments predating a state reset). Recorded
            # for operators; zero business mutation (M31 documented behavior).
            _mark(repos, event_id, "UNMATCHED", str(exc)[:500])
            return IngestResult(duplicate=False, processed=False, reason="UNMATCHED_CONTEXT")
        _mark(repos, event_id, "ERROR", str(exc)[:500])
        return IngestResult(duplicate=False, processed=False, reason="PROCESSING_ERROR")
    except Exception as exc:  # noqa: BLE001 - recorded for operators
        _mark(repos, event_id, "ERROR", str(exc)[:500])
        return IngestResult(duplicate=False, processed=False, reason="PROCESSING_ERROR")

    _mark(repos, event_id, "PROCESSED", None)
    return IngestResult(duplicate=False, processed=True)


def _mark(repos: Repositories, event_id: str, state: str, error: str | None) -> None:
    with repos.transaction() as session:
        row = session.get(ProviderEvent, event_id, with_for_update=True)
        if row is not None:
            row.processing_state = state
            if error is not None:
                row.error = error
