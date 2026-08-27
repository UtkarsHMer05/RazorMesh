"""RazorMesh Phase 4 protocol-domain primitives.

This package introduces the Phase-4 internal models, the protocol
firewall, the cross-protocol consistency engine, the audit-event
emitters, and the MCP / UCP / AP2 / ACP / A2A adapters (M20..M44).

The boundary is strict: nothing here calls the payment provider,
creates an ExecutionTicket, or weakens any Phase-1/2/3 invariant.
The package is consumed by the Phase-4 MCP / UCP / AP2 / ACP / A2A
adapters and the Phase-4 UI surfaces (M48).
"""

from .a2a_adapter import (
    A2A_TARGET_VERSION,
    RMA_A2A_AGENT_CARD,
    a2a_message_id_is_idempotency_key,
    build_a2a_envelope,
    build_a2a_message_with_ucp_datapart,
)
from .acp_adapter import (
    ACP_RAZORMESH_PAYMENT_HANDLER,
    ACP_TARGET_VERSION,
    ACPLifecycleState,
    build_acp_checkout_session,
    build_acp_complete_response,
    build_acp_envelope,
    intersect_capabilities,
    is_legal_transition,
)
from .ap2_verifier import (
    AP2_TARGET_VERSION,
    build_ap2_merchant_checkout_jwt,
    compute_ap2_checkout_hash,
    compute_ap2_pop,
    export_ap2_test_merchant_pub_jwk,
    generate_ap2_test_merchant_key,
    sign_ap2_merchant_jwt_es256,
    verify_ap2_merchant_jwt_es256,
)
from .audit import (
    emit_cross_protocol_checked,
    emit_protocol_normalized,
    emit_protocol_received,
    emit_protocol_verified,
)
from .commitment import commitment_hash as commitment_hash
from .commitment import compute_commitment as compute_commitment
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
from .mcp_server import (
    EMPTY_INPUT_SCHEMA,
    PHASE4_MCP_TOOL_NAMES,
    build_mcp_server,
    mount_mcp,
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
    "A2A_TARGET_VERSION",
    "ACP_RAZORMESH_PAYMENT_HANDLER",
    "ACP_TARGET_VERSION",
    "AP2_TARGET_VERSION",
    "COMMERCE_COMMITMENT_VERSION",
    "EMPTY_INPUT_SCHEMA",
    "IR_VERSION",
    "MAX_PAYLOAD_BYTES",
    "PHASE4_MCP_TOOL_NAMES",
    "RMA_A2A_AGENT_CARD",
    "RMA_UCP_PROFILE",
    "SUPPORTED_VERSIONS",
    "UCP_PROFILE_PATH",
    "UCP_TARGET_VERSION",
    "ACPLifecycleState",
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
    "a2a_message_id_is_idempotency_key",
    "build_a2a_envelope",
    "build_a2a_message_with_ucp_datapart",
    "build_acp_checkout_session",
    "build_acp_complete_response",
    "build_acp_envelope",
    "build_ap2_merchant_checkout_jwt",
    "build_mcp_server",
    "build_signed_order_event",
    "build_ucp_checkout_complete_response",
    "build_ucp_envelope",
    "build_ucp_order_get_response",
    "commitment_hash",
    "compare_envelopes",
    "compare_ir_to_envelope",
    "compute_ap2_checkout_hash",
    "compute_ap2_pop",
    "compute_commitment",
    "emit_cross_protocol_checked",
    "emit_protocol_normalized",
    "emit_protocol_received",
    "emit_protocol_verified",
    "envelope_from_raw",
    "envelope_to_canonical_json",
    "equal_under_commitment",
    "evaluate_envelope",
    "export_ap2_test_merchant_pub_jwk",
    "generate_ap2_test_merchant_key",
    "hash_payload",
    "intersect_capabilities",
    "is_legal_transition",
    "mark_envelope_state",
    "mount_mcp",
    "serialize_ucp_profile",
    "sign_ap2_merchant_jwt_es256",
    "verify_ap2_merchant_jwt_es256",
    "verify_signed_order_event",
]
