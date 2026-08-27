"""RazorMesh Phase 4 protocol-domain primitives.

This package introduces the Phase-4 internal models, the protocol
firewall, the cross-protocol consistency engine, and the audit-event
emitters. The boundary is strict: nothing here calls the payment
provider, creates an ExecutionTicket, or weakens any Phase-1/2/3
invariant. The package is consumed by the Phase-4 MCP / UCP / AP2 /
ACP / A2A adapters and the Phase-4 UI surfaces (M48).
"""

from .audit import (
    emit_cross_protocol_checked,
    emit_protocol_normalized,
    emit_protocol_received,
    emit_protocol_verified,
)
from .commitment import commitment_hash, compute_commitment
from .consistency import (
    ConsistencyResult,
    ConsistencyState,
    compare_envelopes,
    compare_ir_to_envelope,
)
from .envelope import (
    MAX_PAYLOAD_BYTES,
    ProtocolEnvelope,
    SourceProtocol,
    VerificationState,
    envelope_from_raw,
    envelope_to_canonical_json,
    hash_payload,
)
from .firewall import (
    SUPPORTED_VERSIONS,
    FirewallDecision,
    FirewallReason,
    FirewallResult,
    evaluate_envelope,
    mark_envelope_state,
)
from .ir import (
    COMMERCE_COMMITMENT_VERSION,
    IR_VERSION,
    AgentCommerceIR,
    CommitmentPayload,
    equal_under_commitment,
)
from .ucp_adapter import (
    RMA_UCP_PROFILE,
    UCP_PROFILE_PATH,
    UCP_TARGET_VERSION,
    build_signed_order_event,
    build_ucp_checkout_complete_response,
    build_ucp_envelope,
    build_ucp_order_get_response,
    serialize_ucp_profile,
    verify_signed_order_event,
)

__all__ = [
    "COMMERCE_COMMITMENT_VERSION",
    "IR_VERSION",
    "MAX_PAYLOAD_BYTES",
    "RMA_UCP_PROFILE",
    "SUPPORTED_VERSIONS",
    "UCP_PROFILE_PATH",
    "UCP_TARGET_VERSION",
    "AgentCommerceIR",
    "CommitmentPayload",
    "ConsistencyResult",
    "ConsistencyState",
    "FirewallDecision",
    "FirewallReason",
    "FirewallResult",
    "ProtocolEnvelope",
    "SourceProtocol",
    "VerificationState",
    "build_signed_order_event",
    "build_ucp_checkout_complete_response",
    "build_ucp_envelope",
    "build_ucp_order_get_response",
    "commitment_hash",
    "compare_envelopes",
    "compare_ir_to_envelope",
    "compute_commitment",
    "emit_cross_protocol_checked",
    "emit_protocol_normalized",
    "emit_protocol_received",
    "emit_protocol_verified",
    "envelope_from_raw",
    "envelope_to_canonical_json",
    "equal_under_commitment",
    "evaluate_envelope",
    "hash_payload",
    "mark_envelope_state",
    "serialize_ucp_profile",
    "verify_signed_order_event",
]
