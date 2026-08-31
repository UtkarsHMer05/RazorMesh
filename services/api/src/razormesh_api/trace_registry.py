"""Phase-5 (M009/M010): live-trace registry + judge-facing event projection.

Security contract:
- The registry is a *projection* (trace_id ↔ intent_id linkage); it never
  stores or derives financial authority. Durable Postgres rows + the audit
  ledger remain the only truth.
- The event projection copies safe fields out of audit events; it never
  rewrites them. Stages without evidence stay absent — never fabricated.
- No secrets, signatures, key material, raw commerce text, or model/provider
  branding leak into the normal-flow projection.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from razormesh_api.persistence.models import AuditEvent, DemoTrace
from razormesh_api.persistence.repositories import Repositories, session_scope

# Crockford-ish base32 without I/L/O/U: display-safe, unambiguous capitals.
_TRACE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_DISPLAY_RE = "RM-"
_RECENT_LIMIT = 20

# Audit event types projected to judge-facing stages (source of truth:
# razormesh_api.ledger append call sites; mirrors routes/audit.py constants).
_INTENT_COMPILED = "INTENT_COMPILED"
_AGENT_SEARCH = "AGENT_SEARCH_COMPLETED"
_MERCHANT_MUTATED = "MERCHANT_OFFER_MUTATED"
_MERCHANT_REVERTED = "MERCHANT_OFFER_REVERTED"
_INTENT_CONFIRMED = "INTENT_CONFIRMED"
_INTENT_REJECTED = "INTENT_REJECTED"
_CHECKOUT_PROPOSED = "CHECKOUT_PROPOSED"
_DECISION_RECORDED = "DECISION_RECORDED"
_FUSION_DECIDED = "POLICY_FUSION_DECIDED"
_SEMANTIC_RUN = "SEMANTIC_VERIFICATION_RUN"
_TICKET_ISSUED = "TICKET_ISSUED"
_TICKET_WITHHELD = "TICKET_WITHHELD"
_ACCEPTANCE_REJECTED = "PHASE4_ACCEPTANCE_REJECTED"
_PROVIDER_ORDER_EVENTS = frozenset(
    {"RAZORPAY_ORDER_CREATED", "RAZORPAY_ORDER_REJECTED", "RAZORPAY_ORDER_UNKNOWN"}
)
_CALLBACK_VERIFIED = "RAZORPAY_CALLBACK_VERIFIED"
_WEBHOOK_INGESTED = "RAZORPAY_WEBHOOK_INGESTED"
_RECONCILIATION_RUN = "RAZORPAY_RECONCILIATION_RUN"


def _new_trace_id() -> str:
    return _DISPLAY_RE + "".join(secrets.choice(_TRACE_ALPHABET) for _ in range(6))


class TraceError(RuntimeError):
    """Registry-level failure (collision loop, unknown trace)."""


class TraceRegistry:
    """Linkage-only registry (M009). No financial state lives here."""

    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    def get_or_create_for_intent(
        self,
        intent_id: str,
        *,
        draft_id: str | None = None,
        checkout_id: str | None = None,
        run_id: str | None = None,
    ) -> str:
        """Idempotent: same intent always resolves to the same trace id."""
        with session_scope(self._repos.factory) as session:
            row = session.execute(
                select(DemoTrace).where(DemoTrace.intent_id == intent_id)
            ).scalar_one_or_none()
            if row is not None:
                changed = False
                if draft_id and row.draft_id != draft_id:
                    row.draft_id, changed = draft_id, True
                if checkout_id and row.checkout_id != checkout_id:
                    row.checkout_id, changed = checkout_id, True
                if run_id and row.run_id != run_id:
                    row.run_id, changed = run_id, True
                if changed:
                    row.updated_at = datetime.now(UTC)
                return str(row.trace_id)
            for _ in range(8):  # collision loop (32^6 space; practically none)
                trace_id = _new_trace_id()
                exists = session.get(DemoTrace, trace_id)
                if exists is not None:
                    continue
                now = datetime.now(UTC)
                session.add(
                    DemoTrace(
                        trace_id=trace_id,
                        intent_id=intent_id,
                        draft_id=draft_id,
                        checkout_id=checkout_id,
                        run_id=run_id,
                        created_at=now,
                        updated_at=now,
                    )
                )
                return trace_id
        raise TraceError("trace id collision loop exhausted")

    def by_trace(self, trace_id: str) -> DemoTrace | None:
        with session_scope(self._repos.factory) as session:
            row = session.get(DemoTrace, trace_id)
            if row is None:
                return None
            session.expunge(row)
            return_row: DemoTrace = row
            return return_row

    def by_intent(self, intent_id: str) -> DemoTrace | None:
        with session_scope(self._repos.factory) as session:
            row = session.execute(
                select(DemoTrace).where(DemoTrace.intent_id == intent_id)
            ).scalar_one_or_none()
            if row is None:
                return None
            session.expunge(row)
            return_row: DemoTrace = row
            return return_row

    def recent(self, limit: int = _RECENT_LIMIT) -> list[DemoTrace]:
        with session_scope(self._repos.factory) as session:
            rows = (
                session.execute(
                    select(DemoTrace)
                    .order_by(DemoTrace.updated_at.desc())
                    .limit(max(1, min(limit, 100)))
                )
                .scalars()
                .all()
            )
            for row in rows:
                session.expunge(row)
            return list(rows)


# --------------------------------------------------------------------------
# Event projection (M010) — privacy-safe judge-facing events.
# --------------------------------------------------------------------------

_STAGE_TITLES: dict[str, str] = {
    "human": "Human mandate",
    "razorguard": "Deterministic RazorGuard",
    "semantic": "Semantic Trust Check",
    "fusion": "Conservative fusion",
    "ticket": "Execution ticket",
    "protocol": "Protocol firewall",
    "provider": "Payment provider boundary",
    "reconciliation": "Reconciliation",
    "audit": "Audit ledger",
    "replay": "Replay protection",
}

_REJECTION_EVENT = "PHASE4_ACCEPTANCE_REJECTED"


@dataclass(frozen=True)
class StageEvent:
    seq: int
    ts: str
    stage: str
    kind: str
    title: str
    status: str
    detail: str | None
    source: str
    ids: dict[str, str]
    evidence: dict[str, Any]


def _safe_id(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _project_one(ev: AuditEvent) -> StageEvent | None:
    t = ev.event_type
    payload = dict(ev.metadata_json or {})
    stage = kind = status = ""
    detail: str | None = None
    evidence: dict[str, Any] = {}

    if t == _INTENT_COMPILED:
        stage, kind, status = "human", "mandate.compiled", "DONE"
        detail = "AI Intent Compiler drafted the structured mandate."
    elif t in (_MERCHANT_MUTATED, _MERCHANT_REVERTED):
        stage = "merchant"
        kind = "offer.mutated" if t == _MERCHANT_MUTATED else "offer.reverted"
        status = "DONE"
        detail = (
            "Merchant changed the offer after authorization"
            if t == _MERCHANT_MUTATED
            else "Merchant restored the original offer (audit history preserved)"
        )
        evidence = {
            "kind": payload.get("kind"),
            "changed_fields": payload.get("changed_fields"),
            "provider_contacted": payload.get("provider_contacted"),
        }
    elif t == _CHECKOUT_PROPOSED:
        stage = "agent"
        kind = "checkout.proposed"
        status = "DONE"
        detail = "A checkout was proposed from the real catalog."
    elif t == _AGENT_SEARCH:
        stage = "agent"
        kind = "search.completed"
        status = "DONE"
        detail = "Shopping Agent ranked the real catalog against the confirmed mandate."
        evidence = {
            "inspected": payload.get("inspected"),
            "eligible": payload.get("eligible"),
            "rejected": payload.get("rejected"),
            "top_product_id": payload.get("top_product_id"),
        }
    elif t == _INTENT_CONFIRMED:
        stage, kind, status = "human", "mandate.confirmed", "DONE"
        detail = "Human confirmed authority. The draft became the confirmed mandate."
    elif t == _INTENT_REJECTED:
        stage, kind, status = "human", "mandate.rejected", "DONE"
        detail = "Human rejected the draft."
    elif t == _DECISION_RECORDED:
        decision = str(payload.get("decision", ""))
        stage = "razorguard"
        kind = f"decision.{decision.lower()}"
        status = decision if decision in {"ALLOW", "CHALLENGE", "BLOCK"} else "INFO"
        detail = "Deterministic rule verdict for the current checkout."
        evidence = {"reason_codes": list(ev.reason_codes or [])}
    elif t == _FUSION_DECIDED:
        stage = "fusion"
        kind = "fusion.decided"
        final = str(payload.get("final", ""))
        status = final if final in {"ALLOW", "CHALLENGE", "BLOCK"} else "INFO"
        detail = "Hard rules + semantic result fused (semantic can only tighten)."
        evidence = {
            "deterministic": payload.get("deterministic"),
            "semantic_action": payload.get("semantic_action"),
            "final": payload.get("final"),
        }
    elif t == _SEMANTIC_RUN:
        action = str(payload.get("action", ""))
        stage = "semantic"
        kind = "semantic.checked"
        status = action if action in {"PASS", "CHALLENGE", "BLOCK"} else "INFO"
        detail = "Semantic verifier compared commerce evidence to the mandate."
        evidence = {
            "p_entailment": payload.get("p_entailment"),
            "p_neutral": payload.get("p_neutral"),
            "p_contradiction": payload.get("p_contradiction"),
            "pair_count": payload.get("pair_count"),
            "fail_closed": payload.get("fail_closed"),
        }
    elif t == _TICKET_ISSUED:
        stage, kind, status = "ticket", "ticket.issued", "DONE"
        detail = "Signed, single-use execution ticket issued after ALLOW."
        evidence = {"amount_minor": payload.get("amount_minor")}
    elif t == _TICKET_WITHHELD:
        stage, kind, status = "ticket", "ticket.withheld", "WITHHELD"
        detail = "Ticket WITHHELD — no authority to execute."
        evidence = {
            "ticket_issued": payload.get("ticket_issued", False),
            "provider_contacted": payload.get("provider_contacted", False),
            "reason_codes": list(ev.reason_codes or []),
        }
    elif t == _REJECTION_EVENT:
        stage, kind, status = "protocol", "acceptance.rejected", "BLOCK"
        detail = (
            "Full-evidence rejection: per-stage verdicts recorded, no ticket, no provider contact."
        )
        # F008: real keys as appended by _record_rejection (protocol_firewall,
        # razorguard_decision, final_decision) — the earlier projection read
        # firewall/razorguard/final and always rendered empty evidence.
        evidence = {
            "firewall": payload.get("protocol_firewall"),
            "razorguard": payload.get("razorguard_decision"),
            "final": payload.get("final_decision"),
            "semantic_verifier": payload.get("semantic_verifier"),
        }
    elif t in _PROVIDER_ORDER_EVENTS:
        stage = "provider"
        kind = (
            "provider.order_created"
            if t == "RAZORPAY_ORDER_CREATED"
            else "provider.rejected"
            if t == "RAZORPAY_ORDER_REJECTED"
            else "provider.unknown"
        )
        status = {"RAZORPAY_ORDER_CREATED": "DONE", "RAZORPAY_ORDER_REJECTED": "FAILED"}.get(
            t, "PENDING"
        )
        detail = "Trusted executor contacted the payment provider (Test Mode)."
        evidence = {
            "razorpay_order_id": payload.get("razorpay_order_id"),
            "amount_minor": payload.get("amount_minor"),
            "reason_code": payload.get("reason_code"),
        }
    elif t == _CALLBACK_VERIFIED:
        stage, kind, status = "reconciliation", "callback.verified", "DONE"
        detail = "Checkout callback signature verified by the backend."
    elif t == _WEBHOOK_INGESTED:
        stage = "reconciliation"
        kind = "webhook.ingested"
        status = "DONE" if payload.get("signature_verified") else "FAILED"
        detail = "Provider webhook ingested (deduplicated by event id)."
        evidence = {"provider_event_type": payload.get("event_type")}
    elif t == _RECONCILIATION_RUN:
        stage, kind, status = "reconciliation", "reconciliation.run", "INFO"
        detail = "Reconciliation resolved provider state exactly once."
        evidence = {
            "state_before": payload.get("state_before"),
            "state_after": payload.get("state_after"),
            "settled_by_reconciliation": payload.get("settled_by_reconciliation"),
        }
    else:
        return None  # unknown audit types are never guessed into stages

    ids = {
        key: value
        for key, value in {
            "intent_id": _safe_id(ev.intent_id),
            "checkout_id": _safe_id(ev.checkout_id),
            "ticket_id": _safe_id(ev.ticket_id),
        }.items()
        if value
    }
    return StageEvent(
        seq=ev.seq,
        ts=ev.timestamp.isoformat(),
        stage=stage,
        kind=kind,
        title=_STAGE_TITLES.get(stage, stage),
        status=status,
        detail=detail,
        source=ev.actor,
        ids=ids,
        evidence={k: v for k, v in evidence.items() if v is not None},
    )


def project_events(
    repos: Repositories,
    intent_id: str,
    *,
    after_seq: int = 0,
    limit: int = 200,
) -> list[StageEvent]:
    """Deterministic seq-ordered projection of one intent's audit events."""
    with session_scope(repos.factory) as session:
        rows = (
            session.execute(
                select(AuditEvent)
                .where(AuditEvent.intent_id == intent_id, AuditEvent.seq > after_seq)
                .order_by(AuditEvent.seq.asc())
                .limit(max(1, min(limit, 1000)))
            )
            .scalars()
            .all()
        )
        events = [e for e in (_project_one(r) for r in rows) if e is not None]
    return events


def summarize_trace(repos: Repositories, trace: DemoTrace) -> dict[str, Any]:
    """Derive the display summary from audit evidence only (never stored authority)."""
    with session_scope(repos.factory) as session:
        events = (
            session.execute(
                select(AuditEvent)
                .where(AuditEvent.intent_id == trace.intent_id)
                .order_by(AuditEvent.seq.desc())
                .limit(200)
            )
            .scalars()
            .all()
        )
    final: str | None = None
    provider_contacted = False
    provider_calls = 0
    ticket_state: str | None = None
    amount_minor: int | None = None
    currency: str | None = None
    decision_status: str | None = None
    for ev in reversed(events):  # chronological
        payload = dict(ev.metadata_json or {})
        if ev.event_type == _DECISION_RECORDED:
            decision_status = str(payload.get("decision") or decision_status)
        elif ev.event_type == _FUSION_DECIDED:
            final = str(payload.get("final") or final)
        elif ev.event_type == _TICKET_ISSUED:
            ticket_state = "ISSUED"
            amount_minor = payload.get("amount_minor", amount_minor)
        elif ev.event_type == _TICKET_WITHHELD:
            ticket_state = "WITHHELD"
        elif ev.event_type in _PROVIDER_ORDER_EVENTS:
            provider_contacted = True
            provider_calls += 1
        elif ev.event_type == _REJECTION_EVENT:
            final = str(payload.get("final_decision") or final)
            if payload.get("provider_contacted") is False:
                provider_contacted = provider_contacted or False

    state: str
    if ticket_state == "ISSUED" and provider_contacted:
        state = "EXECUTING"
    elif ticket_state == "WITHHELD" or final == "BLOCK":
        state = "WITHHELD"
    elif final == "CHALLENGE":
        state = "CHALLENGED"
    elif final == "ALLOW" and ticket_state == "ISSUED":
        state = "AUTHORIZED"
    elif decision_status:
        state = "DECIDED"
    else:
        state = "CONFIRMED"

    return {
        "trace_id": trace.trace_id,
        "intent_id": trace.intent_id,
        "draft_id": trace.draft_id,
        "checkout_id": trace.checkout_id,
        "run_id": trace.run_id,
        "created_at": trace.created_at.isoformat(),
        "updated_at": trace.updated_at.isoformat(),
        "state": state,
        "final_decision": final or decision_status,
        "ticket_state": ticket_state,
        "provider_contacted": provider_contacted,
        "provider_call_count": provider_calls,
        "amount_minor": amount_minor,
        "currency": currency,
    }
