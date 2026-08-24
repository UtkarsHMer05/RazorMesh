"""M25: append-oriented hash-chained evidence ledger.

Ordinary UPDATE/DELETE is additionally blocked by the ``trg_audit_no_update``
database trigger (M20). This module provides the application-level chain:
append (serialized by a PostgreSQL advisory lock) and verify (walk + recompute).
PostgreSQL remains the durable authority; Redis is never involved here.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from razormesh_api.domain.evidence import (
    GENESIS_HASH,
    LEDGER_ADVISORY_LOCK_KEY,
    compute_event_hash,
)
from razormesh_api.domain.ids import AuditEventId
from razormesh_api.persistence.models import AuditEvent
from razormesh_api.persistence.repositories import Repositories, session_scope


@dataclass(frozen=True)
class ChainReport:
    valid: bool
    events_checked: int
    broken_at_event_id: str | None = None
    reason: str | None = None


class EvidenceLedger:
    def __init__(self, repos: Repositories) -> None:
        self._factory: sessionmaker[Session] = repos.factory

    def append(
        self,
        *,
        event_type: str,
        actor: str,
        timestamp: datetime | None = None,
        intent_id: str | None = None,
        checkout_id: str | None = None,
        decision_id: str | None = None,
        ticket_id: str | None = None,
        intent_hash: str | None = None,
        checkout_hash: str | None = None,
        reason_codes: list[str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Append one tamper-evident event; returns the persisted row."""
        ts_raw = timestamp if timestamp is not None else datetime.now(UTC)
        payload_final = payload if payload is not None else {}
        reason_final = sorted(reason_codes) if reason_codes else None

        with session_scope(self._factory) as s:
            # Serialize appends: every writer must observe the true tip.
            s.execute(select(func.pg_advisory_xact_lock(LEDGER_ADVISORY_LOCK_KEY)))
            tip = (
                s.execute(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(1))
                .scalars()
                .first()
            )
            previous_hash = tip.current_event_hash if tip is not None else GENESIS_HASH
            now = datetime.now(UTC)
            event_id = str(AuditEventId.generate())
            current_hash = compute_event_hash(
                previous_hash,
                event_id=event_id,
                event_type=event_type,
                actor=actor,
                timestamp=ts_raw,
                intent_id=intent_id,
                checkout_id=checkout_id,
                decision_id=decision_id,
                ticket_id=ticket_id,
                intent_hash=intent_hash,
                checkout_hash=checkout_hash,
                reason_codes=reason_final,
                payload=payload_final,
            )
            event = AuditEvent(
                event_id=event_id,
                event_type=event_type,
                actor=actor,
                timestamp=ts_raw,
                intent_id=intent_id,
                checkout_id=checkout_id,
                decision_id=decision_id,
                ticket_id=ticket_id,
                intent_hash=intent_hash,
                checkout_hash=checkout_hash,
                reason_codes=reason_final,
                metadata_json=payload_final,
                previous_event_hash=previous_hash,
                current_event_hash=current_hash,
                created_at=now,
            )
            s.add(event)
            s.flush()
            s.refresh(event)
            return event

    def verify(self) -> ChainReport:
        """Re-walk the whole chain and recompute every hash from stored fields."""
        with self._factory() as s:
            events = list(s.execute(select(AuditEvent).order_by(AuditEvent.seq)).scalars().all())
        if not events:
            # An empty ledger is trivially valid; callers wanting strictness
            # should assert on events_checked.
            return ChainReport(valid=True, events_checked=0)

        expected_previous = GENESIS_HASH
        for event in events:
            if event.previous_event_hash != expected_previous:
                return ChainReport(
                    valid=False,
                    events_checked=len(events),
                    broken_at_event_id=event.event_id,
                    reason=(
                        "broken link: previous_event_hash does not match "
                        f"expected {expected_previous[:16]}..."
                    ),
                )
            recomputed = compute_event_hash(
                event.previous_event_hash or GENESIS_HASH,
                event_id=event.event_id,
                event_type=event.event_type,
                actor=event.actor,
                timestamp=event.timestamp,
                intent_id=event.intent_id,
                checkout_id=event.checkout_id,
                decision_id=event.decision_id,
                ticket_id=event.ticket_id,
                intent_hash=event.intent_hash,
                checkout_hash=event.checkout_hash,
                reason_codes=list(event.reason_codes) if event.reason_codes else None,
                payload=dict(event.metadata_json) if event.metadata_json else {},
            )
            if recomputed != event.current_event_hash:
                return ChainReport(
                    valid=False,
                    events_checked=len(events),
                    broken_at_event_id=event.event_id,
                    reason="hash mismatch: record contents were altered",
                )
            expected_previous = event.current_event_hash
        return ChainReport(valid=True, events_checked=len(events))
