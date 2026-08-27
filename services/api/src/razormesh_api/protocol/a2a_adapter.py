"""A2A `v1.0.1` compatibility slice (M44).

Implements only what Phase-4 interoperability needs per master prompt
§17 and §44:

- Agent Card / profile fixture
- advertise UCP extension metadata
- map UCP checkout DataPart
- bind `messageId` to idempotency
- represent AP2 evidence references

Not a full A2A platform. (master prompt §17)
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from .envelope import SourceProtocol, envelope_from_raw

A2A_TARGET_VERSION = "v1.0.1"


RMA_A2A_AGENT_CARD: dict[str, Any] = {
    "name": "razormesh-trust-agent",
    "description": (
        "RazorMesh Trust cross-protocol agentic-commerce gateway. Phase-4 compatibility slice only."
    ),
    "supportedInterfaces": [
        {
            "url": "https://localhost:8000/a2a/v1",
            "protocolBinding": "HTTP+JSON",
            "protocolVersion": A2A_TARGET_VERSION,
        }
    ],
    "capabilities": {
        "streaming": False,
        "pushNotifications": False,
        "extensions": [
            {
                "uri": "https://razormesh.dev/extensions/ucp/v1",
                "description": (
                    "UCP 2026-04-08 capability advertisement for the "
                    "RazorMesh Phase-4 protocol gateway."
                ),
                "required": False,
            },
            {
                "uri": "https://razormesh.dev/extensions/ap2/v0.2.0",
                "description": (
                    "AP2 v0.2.0 mandate evidence reference for cross-protocol consistency checks."
                ),
                "required": False,
            },
        ],
    },
    "defaultInputModes": ["text/plain"],
    "defaultOutputModes": ["application/a2a+json"],
    "skills": [
        {
            "id": "razormesh-protocol-gateway",
            "name": "RazorMesh Protocol Gateway",
            "description": (
                "Accepts MCP/UCP/AP2/ACP/A2A inputs, verifies protocol "
                "firewall, normalizes to AgentCommerceIR, runs the "
                "cross-protocol consistency engine, and routes to the "
                "Phase-3 trust layer."
            ),
        }
    ],
}


def build_a2a_envelope(
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
    authorization_evidence: list[Mapping[str, Any]] | None = None,
    extension_evidence: list[Mapping[str, Any]] | None = None,
) -> Any:
    return envelope_from_raw(
        source_protocol=SourceProtocol.A2A,
        source_protocol_version=A2A_TARGET_VERSION,
        source_transport="http+json",
        adapter_version="razormesh-a2a-adapter-0.1.0",
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
        authorization_evidence=authorization_evidence,
        extension_evidence=extension_evidence,
    )


def build_a2a_message_with_ucp_datapart(
    *,
    message_text: str,
    ucp_checkout_payload: Mapping[str, Any],
    ap2_mandate_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Build an A2A message that carries a UCP checkout DataPart.

    The DataPart shape binds the UCP commerce payload to the A2A
    message id so the protocol firewall can treat them as the same
    authorization context.
    """
    message_id = f"msg_{uuid.uuid4().hex[:16]}"
    parts: list[dict[str, Any]] = [{"kind": "text", "text": message_text}]
    parts.append(
        {
            "kind": "data",
            "data": {
                "ucp": {
                    "version": "2026-04-08",
                    "checkout": dict(ucp_checkout_payload),
                },
                "ap2": {"mandate_refs": list(ap2_mandate_refs or [])},
            },
            "metadata": {
                "https://razormesh.dev/extensions/ucp/v1": {
                    "checkout_revision": ucp_checkout_payload.get("revision"),
                },
            },
        }
    )
    return {
        "id": message_id,
        "role": "ROLE_USER",
        "parts": parts,
        "extensions": [
            "https://razormesh.dev/extensions/ucp/v1",
            "https://razormesh.dev/extensions/ap2/v0.2.0",
        ],
    }


def a2a_message_id_is_idempotency_key(message: Mapping[str, Any]) -> str:
    """Bind an A2A message id to the protocol firewall's idempotency key.

    Master prompt §44: `messageId` is the idempotency anchor for
    A2A-derived traffic. The firewall's `idempotency_key` field is
    set to this value by the adapter.
    """
    return str(message.get("id") or "")


__all__ = [
    "A2A_TARGET_VERSION",
    "RMA_A2A_AGENT_CARD",
    "a2a_message_id_is_idempotency_key",
    "build_a2a_envelope",
    "build_a2a_message_with_ucp_datapart",
]
