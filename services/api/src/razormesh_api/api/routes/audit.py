"""M47: audit dashboard API — timeline, chain verification, states, tamper simulation."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from razormesh_api.domain.ids import IntentId
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.persistence.models import (
    AuthorizationSpend,
    Decision,
    ExecutionAttempt,
    ExecutionTicket,
)
from razormesh_api.persistence.models import (
    IntentContract as RowIntent,
)
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.settings import Settings, get_settings

router = APIRouter(prefix="/audit", tags=["audit"])


def _repos(settings: Annotated[Settings, Depends(get_settings)]) -> Repositories:
    from razormesh_api.persistence.db import create_db_engine, create_session_factory

    return Repositories(create_session_factory(create_db_engine(settings.database_url)))


def _ledger(repos: Annotated[Repositories, Depends(_repos)]) -> EvidenceLedger:
    return EvidenceLedger(repos)


@router.get("/timeline")
def timeline(
    repos: Annotated[Repositories, Depends(_repos)],
    limit: int = 50,
) -> dict:
    limit = max(1, min(limit, 200))
    events = repos.audit.list_recent(limit)
    return {
        "count": len(events),
        "events": [
            {
                "seq": e.seq,
                "event_id": e.event_id,
                "event_type": e.event_type,
                "actor": e.actor,
                "timestamp": e.timestamp.isoformat(),
                "intent_id": e.intent_id,
                "checkout_id": e.checkout_id,
                "decision_id": e.decision_id,
                "ticket_id": e.ticket_id,
                "reason_codes": sorted(e.reason_codes) if e.reason_codes else [],
                "previous_event_hash_head": (e.previous_event_hash or "")[:16],
                "current_event_hash_head": e.current_event_hash[:16],
            }
            for e in reversed(events)  # oldest first = chronological timeline
        ],
    }


@router.get("/verify")
def verify_chain(ledger: Annotated[EvidenceLedger, Depends(_ledger)]) -> dict:
    report = ledger.verify()
    return {
        "valid": report.valid,
        "events_checked": report.events_checked,
        "broken_at_event_id": report.broken_at_event_id,
        "reason": report.reason,
    }


@router.get("/state/{intent_id}")
def authorization_state(
    intent_id: str,
    repos: Annotated[Repositories, Depends(_repos)],
) -> dict:
    try:
        key = IntentId(intent_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="malformed intent id") from exc

    with repos.factory() as session:
        intent = session.get(RowIntent, str(key))
        spend = session.get(AuthorizationSpend, str(key))
        decisions = (
            session.execute(select(Decision).where(Decision.intent_id == str(key))).scalars().all()
        )
        tickets = (
            session.execute(select(ExecutionTicket).where(ExecutionTicket.intent_id == str(key)))
            .scalars()
            .all()
        )
        attempts = (
            session.execute(select(ExecutionAttempt).where(ExecutionAttempt.intent_id == str(key)))
            .scalars()
            .all()
        )

    if intent is None:
        raise HTTPException(status_code=404, detail="unknown intent")

    def _money_view(spend_row: AuthorizationSpend | None) -> dict | None:
        if spend_row is None:
            return None
        return {
            "authorized_minor": spend_row.authorized_minor,
            "reserved_minor": spend_row.reserved_minor,
            "committed_minor": spend_row.committed_minor,
            "available_minor": spend_row.authorized_minor
            - spend_row.reserved_minor
            - spend_row.committed_minor,
        }

    return {
        "intent_id": str(key),
        "status": intent.status,
        "generation": intent.authorization_generation,
        "spend": _money_view(spend),
        "decisions": [
            {
                "decision_id": d.decision_id,
                "decision": d.decision,
                "policy_version": d.policy_version,
                "reason_codes": sorted(d.reason_codes) if d.reason_codes else [],
            }
            for d in decisions
        ],
        "tickets": [
            {
                "ticket_id": t.ticket_id,
                "nonce_present": bool(t.nonce),
                "amount_minor": t.amount_minor,
                "expires_at": t.expires_at.isoformat(),
                "used_at": t.used_at.isoformat() if t.used_at else None,
            }
            for t in tickets
        ],
        "attempts": [
            {
                "attempt_id": a.execution_attempt_id,
                "state": a.state,
                "error_code": a.error_code,
                "checkout_id": a.checkout_id,
            }
            for a in attempts
        ],
    }


@router.post("/tamper-test")
def tamper_test(repos: Annotated[Repositories, Depends(_repos)]) -> dict:
    """Prove a hypothetical mutation breaks the hash without mutating the ledger.

    Real UPDATE/DELETE operations remain unavailable at the application layer;
    DB-trigger bypass is exercised only inside isolated integration tests.
    """
    from razormesh_api.domain.evidence import GENESIS_HASH, compute_event_hash

    ledger = EvidenceLedger(repos)
    if ledger.verify().events_checked == 0:
        ledger.append(event_type="TAMPER_TEST_SEED", actor="audit-dashboard")
    event = repos.audit.list_recent(1)[0]
    tampered_hash = compute_event_hash(
        event.previous_event_hash or GENESIS_HASH,
        event_id=event.event_id,
        event_type=event.event_type,
        actor="ATTACKER",
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
    detected = tampered_hash != event.current_event_hash

    return {
        "simulated_tamper": "actor field rewritten to ATTACKER on newest event",
        "detected": detected,
        "verdict_reason": "hash mismatch: hypothetical record contents were altered",
        "note": "Non-mutating simulation; durable ledger was never changed.",
    }
