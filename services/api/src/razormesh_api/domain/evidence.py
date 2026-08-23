"""M25: canonical hashing for the append-oriented evidence ledger.

Hashes are computed over a JCS (RFC 8785) serialization of the event's logical
fields plus the previous hash, so the chain is deterministic and cross-language
friendly. Physical ordering (``seq``) and storage timestamps are deliberately
NOT part of the hashed material.
"""

import hashlib
from datetime import UTC, datetime
from typing import Any

import rfc8785

GENESIS_HASH = "0" * 64

# PostgreSQL advisory-lock key serializing concurrent appends so each append
# observes the true chain tip. Redis is never consulted for durable truth.
LEDGER_ADVISORY_LOCK_KEY = 727_001


def canonical_event_timestamp(ts: datetime) -> str:
    """Stable textual form of an event timestamp (UTC, microsecond precision)."""
    if ts.tzinfo is None:
        raise ValueError("event timestamp must be timezone-aware")
    return ts.astimezone(UTC).isoformat()


def compute_event_hash(
    previous_hash: str,
    *,
    event_id: str,
    event_type: str,
    actor: str,
    timestamp: datetime,
    intent_id: str | None = None,
    checkout_id: str | None = None,
    decision_id: str | None = None,
    ticket_id: str | None = None,
    intent_hash: str | None = None,
    checkout_hash: str | None = None,
    reason_codes: list[str] | None = None,
    payload: dict[str, Any] | None = None,
) -> str:
    """SHA-256 over the JCS-canonicalized authorization-relevant record."""
    material: dict[str, Any] = {
        "schema": "razormesh.evidence.v1",
        "previous_event_hash": previous_hash,
        "event_id": event_id,
        "event_type": event_type,
        "actor": actor,
        "timestamp": canonical_event_timestamp(timestamp),
        "intent_id": intent_id,
        "checkout_id": checkout_id,
        "decision_id": decision_id,
        "ticket_id": ticket_id,
        "intent_hash": intent_hash,
        "checkout_hash": checkout_hash,
        "reason_codes": sorted(reason_codes) if reason_codes else None,
        "payload": payload if payload is not None else {},
    }
    return hashlib.sha256(rfc8785.dumps(material)).hexdigest()
