"""M5 Security Lab demo scenarios — full-evidence rejections (Scenarios B/C).

These tests drive the REAL acceptance pipeline through the demo routes and
pin the judge-facing evidence contract:

- a deterministic rejection gathers READ-ONLY evidence from the remaining
  pure-validation stages (protocol firewall + semantic verifier);
- the final decision stays the strictest (BLOCK is never loosened);
- no ExecutionTicket is minted, no provider is contacted, the idempotency
  key is not consumed;
- PHASE4_ACCEPTANCE_REJECTED (and TICKET_WITHHELD) are appended with verdict
  payloads only — never raw premise/hypothesis text.

The semantic stage runs the ACTIVE model (backend ``deberta`` /
phase3-finetuned-v2, policy semantic-thresholds-v3). AgentPay-IR v2 was
evaluated and NOT activated (docs/agentpay_ir_v2/FINAL_FROZEN_EVALUATION.md).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from razormesh_api.api.routes.phase4_acceptance import (
    demo_scenario_b_semantic_violation,
    demo_scenario_c_protocol_valid_intent_invalid,
)
from razormesh_api.persistence.db import create_db_engine
from razormesh_api.persistence.models import AuditEvent
from razormesh_api.settings import get_settings


def _audit_events(event_type: str) -> list[dict[str, Any]]:
    settings = get_settings()
    engine = create_db_engine(database_url=settings.database_url)
    try:
        from sqlalchemy.orm import Session

        with Session(engine) as session:
            rows = (
                session.execute(
                    select(AuditEvent)
                    .where(AuditEvent.event_type == event_type)
                    .order_by(AuditEvent.seq.desc())
                    .limit(5)
                )
                .scalars()
                .all()
            )
            return [
                {
                    "seq": r.seq,
                    "intent_id": r.intent_id,
                    "payload": r.metadata_json or {},
                }
                for r in rows
            ]
    finally:
        engine.dispose()


def test_scenario_b_semantic_violation_demo() -> None:
    """Recurring membership term on the checkout line: the deterministic rule
    blocks AND the full-evidence rejection shows the semantic verifier's
    contradiction. Expected: protocol PASS, RazorGuard BLOCK, semantic BLOCK,
    final BLOCK, no ticket, no provider call, idempotency not consumed."""
    body = demo_scenario_b_semantic_violation()
    assert body["scenario"] == "B_semantic_intent_violation"
    assert body["protocol_firewall"] == "PROTOCOL_PASS"
    assert body["razorguard_decision"] == "BLOCK"
    assert body["semantic_verifier"] == "BLOCK"
    assert body["semantic_fail_closed"] is False
    assert body["final_decision"] == "BLOCK"
    assert body["ticket_issued"] is False
    assert body["provider_contacted"] is False
    assert body["consumed"] is False
    probs = body["semantic_probabilities"]
    assert probs["contradiction"] >= 0.05, f"expected a contradiction BLOCK, got {probs}"
    # no raw commerce text may leak into the rejection evidence
    flat = repr(body["evidence"])
    assert "auto-renew" not in flat and "CloudFit" not in flat


def test_scenario_c_protocol_valid_intent_invalid_demo() -> None:
    """Two units (₹4,998) against a ≤ ₹3,000 authorization: the protocol layer
    passes, deterministic RazorGuard blocks the budget breach, and the response
    still proves protocol validity is not transaction authority."""
    body = demo_scenario_c_protocol_valid_intent_invalid()
    assert body["scenario"] == "C_protocol_valid_intent_invalid"
    assert body["protocol_firewall"] == "PROTOCOL_PASS"
    assert body["razorguard_decision"] in {"BLOCK", "CHALLENGE"}
    assert body["final_decision"] == "BLOCK"
    assert body["ticket_issued"] is False
    assert body["provider_contacted"] is False
    assert body["consumed"] is False


def test_scenario_c_records_rejection_event_without_raw_text() -> None:
    demo_scenario_c_protocol_valid_intent_invalid()
    events = _audit_events("PHASE4_ACCEPTANCE_REJECTED")
    assert events, "PHASE4_ACCEPTANCE_REJECTED must be appended"
    payload = events[0]["payload"]
    assert payload["ticket_issued"] is False
    assert payload["provider_contacted"] is False
    assert payload["final_decision"] == "BLOCK"
    flat = repr(payload)
    assert "premise" not in flat.lower() and "hypothesis" not in flat.lower()


def test_ticket_withheld_marker_recorded_on_non_allow() -> None:
    demo_scenario_c_protocol_valid_intent_invalid()
    events = _audit_events("TICKET_WITHHELD")
    assert events, "TICKET_WITHHELD must be appended on non-ALLOW decisions"
    payload = events[0]["payload"]
    assert payload["decision"] in {"BLOCK", "CHALLENGE"}
    assert payload["ticket_issued"] is False
    assert payload["provider_contacted"] is False
