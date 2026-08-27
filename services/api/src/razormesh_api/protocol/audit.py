"""Phase-4 audit-event emitters (M19).

Phase 4 emits four new audit events:
- PROTOCOL_RECEIVED
- PROTOCOL_VERIFIED
- PROTOCOL_NORMALIZED
- CROSS_PROTOCOL_CHECKED

The existing append-only JCS-canonical hash-chained audit ledger is
re-used (no new ledger). The new event types are recorded with the
same chain-head semantics. No raw credentials or secrets.

These emitters are *adapters* over the existing
:mod:`razormesh_api.ledger`. They never bypass the audit chain.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .consistency import ConsistencyResult
from .envelope import ProtocolEnvelope
from .firewall import FirewallResult
from .ir import AgentCommerceIR, compute_commitment

PROTOCOL_RECEIVED = "PROTOCOL_RECEIVED"
PROTOCOL_VERIFIED = "PROTOCOL_VERIFIED"
PROTOCOL_NORMALIZED = "PROTOCOL_NORMALIZED"
CROSS_PROTOCOL_CHECKED = "CROSS_PROTOCOL_CHECKED"


def _compact_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _envelope_canonical_hash(env: ProtocolEnvelope) -> str:
    """Return a deterministic hash of the envelope's serialized form.

    Phase 4 stores this exact hash on every audit event so the ledger
    can later verify the envelope that produced a given decision.
    """
    import hashlib

    from .envelope import envelope_to_canonical_json

    return hashlib.sha256(envelope_to_canonical_json(env).encode("utf-8")).hexdigest()


def emit_protocol_received(env: ProtocolEnvelope) -> Mapping[str, Any]:
    """Build the audit event body for a freshly-received protocol envelope."""
    return {
        "event_type": PROTOCOL_RECEIVED,
        "envelope_canonical_hash": _envelope_canonical_hash(env),
        "source_protocol": env.source_protocol,
        "source_protocol_version": env.source_protocol_version,
        "source_transport": env.source_transport,
        "message_id": env.message_id,
        "request_id": env.request_id,
        "idempotency_key": env.idempotency_key,
        "raw_payload_hash": env.raw_payload_hash,
        "agent": env.agent,
        "principal_reference": env.principal_reference,
        "merchant_reference": env.merchant_reference,
    }


def emit_protocol_verified(env: ProtocolEnvelope, result: FirewallResult) -> Mapping[str, Any]:
    """Build the audit event body for a firewall verification outcome."""
    return {
        "event_type": PROTOCOL_VERIFIED,
        "envelope_canonical_hash": _envelope_canonical_hash(env),
        "firewall_decision": result.decision,
        "firewall_reasons": [r.value for r in result.reasons],
    }


def emit_protocol_normalized(env: ProtocolEnvelope, ir: AgentCommerceIR) -> Mapping[str, Any]:
    """Build the audit event body for a successful IR normalization."""
    return {
        "event_type": PROTOCOL_NORMALIZED,
        "envelope_canonical_hash": _envelope_canonical_hash(env),
        "ir_schema_version": ir.schema_version,
        "commerce_commitment": compute_commitment(ir),
        "merchant_id": ir.merchant.merchant_id,
        "currency": ir.currency,
        "total_minor": ir.totals.total_minor,
        "item_count": len(ir.items),
        "intent_contract_id": ir.authorization.intent_contract_id,
        "authorization_generation": ir.authorization.authorization_generation,
    }


def emit_cross_protocol_checked(
    irs: list[AgentCommerceIR], result: ConsistencyResult
) -> Mapping[str, Any]:
    """Build the audit event body for a cross-protocol consistency check."""
    commitments = [compute_commitment(ir) for ir in irs]
    return {
        "event_type": CROSS_PROTOCOL_CHECKED,
        "consistency_state": result.state,
        "consistency_reasons": list(result.reasons),
        "mismatched_fields": list(result.mismatched_fields),
        "ir_commitments": commitments,
    }


__all__ = [
    "CROSS_PROTOCOL_CHECKED",
    "PROTOCOL_NORMALIZED",
    "PROTOCOL_RECEIVED",
    "PROTOCOL_VERIFIED",
    "emit_cross_protocol_checked",
    "emit_protocol_normalized",
    "emit_protocol_received",
    "emit_protocol_verified",
]
