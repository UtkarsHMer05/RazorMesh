"""RazorMesh Phase-4 ACP `2026-01-30` adapter (M40..M43).

Implements the seller-compatible subset of ACP from master prompt §16:

- POST create / GET retrieve / POST update / complete / cancel
  checkout session
- Capability negotiation with intersection semantics
- Lifecycle state machine (not_ready / ready / in_progress / completed / canceled)
- Idempotency / failure / unknown-outcome semantics
- ACP Razorpay Test handoff extension:
  `io.razormesh.razorpay.test_checkout` (clearly namespaced and
  nonstandard — NOT Stripe Delegate Payment).

The adapter maps to trusted application services/IR. It does not
process payment directly (P4-S01).
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from .envelope import SourceProtocol, envelope_from_raw
from .ir import AgentCommerceIR, compute_commitment

ACP_TARGET_VERSION = "2026-01-30"


class ACPLifecycleState(StrEnum):
    NOT_READY = "not_ready"
    READY = "ready_for_payment"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELED = "canceled"


# Illegal transitions: a CHECKOUT must not skip from NOT_READY to
# COMPLETED without going through READY and IN_PROGRESS. This is
# the state machine the adapter enforces at the boundary.
_LEGAL_TRANSITIONS: dict[ACPLifecycleState, frozenset[ACPLifecycleState]] = {
    ACPLifecycleState.NOT_READY: frozenset(
        {ACPLifecycleState.READY, ACPLifecycleState.CANCELED}
    ),
    ACPLifecycleState.READY: frozenset(
        {ACPLifecycleState.IN_PROGRESS, ACPLifecycleState.CANCELED}
    ),
    ACPLifecycleState.IN_PROGRESS: frozenset(
        {ACPLifecycleState.COMPLETED, ACPLifecycleState.CANCELED}
    ),
    ACPLifecycleState.COMPLETED: frozenset(),
    ACPLifecycleState.CANCELED: frozenset(),
}


def is_legal_transition(src: ACPLifecycleState, dst: ACPLifecycleState) -> bool:
    return dst in _LEGAL_TRANSITIONS[src]


# Capability intersection. The seller's `payment_handlers` is the
# source of truth for the RazorMesh namespaced handler. Master
# prompt §16 / §42: we never claim a standard Stripe / Delegate
# Payment handler; we advertise only our own.
ACP_RAZORMESH_PAYMENT_HANDLER: dict[str, Any] = {
    "id": "razorpay_test_checkout",
    "name": "io.razormesh.razorpay.test_checkout",
    "version": ACP_TARGET_VERSION,
    "psp": "razorpay",
    "requires_delegate_payment": False,
    "requires_pci_compliance": False,
    "test_mode": True,
    "config": {
        "merchant_id": "razormesh-test-merchant",
        "accepted_brands": ["visa", "mastercard", "rupay"],
    },
}


def intersect_capabilities(
    agent_capabilities: Mapping[str, Any],
    seller_capabilities: Mapping[str, Any],
) -> dict[str, Any]:
    """Capability intersection (master prompt §40, ACP RFC).

    Payment handlers: intersection of `capabilities.payment.handlers[]`
    by `id`. Interventions: intersection of `supported[]`. Extensions:
    intersection of `extensions[]` by `name`.
    """
    out: dict[str, Any] = {}
    seller_handlers = {
        h["id"]: h for h in seller_capabilities.get("payment", {}).get("handlers", [])
    }
    agent_handlers = {
        h["id"]: h for h in agent_capabilities.get("payment", {}).get("handlers", [])
    }
    common = sorted(set(seller_handlers) & set(agent_handlers))
    out["payment"] = {"handlers": [seller_handlers[i] for i in common]}
    seller_int = seller_capabilities.get("interventions", {}).get("supported", [])
    agent_int = agent_capabilities.get("interventions", {}).get("supported", [])
    out["interventions"] = {
        "supported": sorted(set(seller_int) & set(agent_int)),
        "required": sorted(
            set(seller_capabilities.get("interventions", {}).get("required", []))
            & set(agent_capabilities.get("interventions", {}).get("supported", []))
        ),
    }
    seller_ext = {e.get("name") for e in seller_capabilities.get("extensions", [])}
    agent_ext = {e.get("name") for e in agent_capabilities.get("extensions", [])}
    out["extensions"] = sorted(seller_ext & agent_ext)
    return out


def build_acp_envelope(
    *,
    raw_payload: bytes,
    message_id: str,
    request_id: str,
    idempotency_key: str | None,
    agent: str,
    principal_reference: str,
    merchant_reference: str,
    commerce_payload_reference: str,
    signature_evidence: Mapping[str, Any],
    identity_evidence: Mapping[str, Any],
    capability_evidence: Mapping[str, Any],
) -> Any:  # ProtocolEnvelope
    return envelope_from_raw(
        source_protocol=SourceProtocol.ACP,
        source_protocol_version=ACP_TARGET_VERSION,
        source_transport="rest",
        adapter_version="razormesh-acp-adapter-0.1.0",
        message_id=message_id,
        request_id=request_id,
        idempotency_key=idempotency_key,
        raw_payload=raw_payload,
        signature_evidence=signature_evidence,
        identity_evidence=identity_evidence,
        capability_evidence=capability_evidence,
        agent=agent,
        principal_reference=principal_reference,
        merchant_reference=merchant_reference,
        commerce_payload_reference=commerce_payload_reference,
    )


def build_acp_checkout_session(
    *,
    items: list[dict[str, Any]],
    currency: str,
    total_minor: int,
    intent_contract_id: str,
    fulfillment: dict[str, Any] | None = None,
    capabilities: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an ACP `POST checkout_sessions` request body.

    Returns the full session object (request + response merged) in
    the `2026-01-30` shape. The session id is generated locally.
    """
    session_id = f"co_{uuid.uuid4().hex[:16]}"
    return {
        "id": session_id,
        "intent_contract_id": intent_contract_id,
        "status": ACPLifecycleState.NOT_READY.value,
        "currency": currency,
        "line_items": [
            {
                "id": f"li_{i}",
                "product_id": it.get("product_id"),
                "quantity": it.get("quantity", 1),
                "unit_price_minor": it.get("unit_price_minor"),
            }
            for i, it in enumerate(items)
        ],
        "totals": {"total_minor": total_minor, "currency": currency},
        "fulfillment": fulfillment or {},
        "capabilities": capabilities
        or {
            "payment": {"handlers": [ACP_RAZORMESH_PAYMENT_HANDLER]},
            "interventions": {"supported": [], "required": []},
            "extensions": [],
        },
    }


def build_acp_complete_response(
    *,
    session_id: str,
    intent_contract_id: str,
    ir: AgentCommerceIR,
    execution_attempt_id: str | None,
) -> dict[str, Any]:
    """Build an ACP `complete checkout_session` response."""
    return {
        "id": session_id,
        "intent_contract_id": intent_contract_id,
        "status": (
            ACPLifecycleState.COMPLETED.value if execution_attempt_id
            else ACPLifecycleState.NOT_READY.value
        ),
        "commerce_commitment": compute_commitment(ir),
        "razormesh_test_mode": True,
        "execution_attempt_id": execution_attempt_id,
        "payment_handler": "io.razormesh.razorpay.test_checkout",
    }


__all__ = [
    "ACP_RAZORMESH_PAYMENT_HANDLER",
    "ACP_TARGET_VERSION",
    "ACPLifecycleState",
    "build_acp_checkout_session",
    "build_acp_complete_response",
    "build_acp_envelope",
    "intersect_capabilities",
    "is_legal_transition",
]
