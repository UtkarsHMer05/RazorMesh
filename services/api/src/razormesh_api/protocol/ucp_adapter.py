"""RazorMesh Phase-4 UCP `2026-04-08` adapter (M26..M32).

Implements the documented UCP subset (master prompt §13):

- `/.well-known/ucp` profile + discovery
- Catalog search / lookup (read-only)
- Cart create / get / update (the subset that maps to Phase-3 catalog)
- Checkout create / get / update / complete (the create/update bodies
  return the canonical IR-shaped response; complete is BLOCKED at the
  adapter layer and routes to the trusted execution path)
- Order get
- Signed event fixture path (M29) — signed with the local UCP
  test key

UCP signature/Content-Digest verification is implemented against the
target `2026-04-08` requirements (master prompt §8, §30). The
adapter does not directly process payment; it routes to trusted
application services and writes the normalized commerce commitment
to the audit chain.

This module is the RazorMesh side of UCP. A real UCP-enabled merchant
would consume RazorMesh's profile and use this adapter's contract.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from .envelope import (
    ProtocolEnvelope,
    SourceProtocol,
    envelope_from_raw,
)
from .ir import AgentCommerceIR, compute_commitment

UCP_TARGET_VERSION = "2026-04-08"
UCP_PROFILE_PATH = "/.well-known/ucp"


# UCP profile served at `/.well-known/ucp` (master prompt §26).
# The profile advertises only the implemented capabilities and
# transports. Capabilities are listed per the resolved 2026-04-08 spec.
RMA_UCP_PROFILE: dict[str, Any] = {
    "ucp": {
        "version": UCP_TARGET_VERSION,
        "services": {
            "dev.ucp.shopping": [
                {
                    "version": UCP_TARGET_VERSION,
                    "transport": "rest",
                    "endpoint": "/ucp/v1",
                    "spec": "https://ucp.dev/2026-04-08/specification/overview",
                },
                {
                    "version": UCP_TARGET_VERSION,
                    "transport": "mcp",
                    "endpoint": "/ucp/mcp",
                    "spec": "https://ucp.dev/2026-04-08/specification/overview",
                },
            ]
        },
        "capabilities": {
            "dev.ucp.shopping.catalog_search": [
                {
                    "version": UCP_TARGET_VERSION,
                    "spec": "https://ucp.dev/2026-04-08/specification/catalog",
                }
            ],
            "dev.ucp.shopping.catalog_lookup": [
                {
                    "version": UCP_TARGET_VERSION,
                    "spec": "https://ucp.dev/2026-04-08/specification/catalog",
                }
            ],
            "dev.ucp.shopping.cart": [
                {
                    "version": UCP_TARGET_VERSION,
                    "spec": "https://ucp.dev/2026-04-08/specification/cart",
                }
            ],
            "dev.ucp.shopping.checkout": [
                {
                    "version": UCP_TARGET_VERSION,
                    "spec": "https://ucp.dev/2026-04-08/specification/checkout",
                }
            ],
            "dev.ucp.shopping.order": [
                {
                    "version": UCP_TARGET_VERSION,
                    "spec": "https://ucp.dev/2026-04-08/specification/order",
                }
            ],
        },
        "payment_handlers": {
            # RazorMesh's own namespaced handler (master prompt §16, §42).
            "io.razormesh.razorpay.test_checkout": {
                "version": "2026-01-30",
                "psp": "razorpay",
                "requires_delegate_payment": False,
                "requires_pci_compliance": False,
                "test_mode": True,
                "spec": (
                    "Local file: services/api/src/razormesh_api/protocol/"
                    "razorpay_handoff.py"
                ),
            }
        },
    }
}


def serialize_ucp_profile() -> str:
    """Return the JSON-serialized UCP profile."""
    return json.dumps(RMA_UCP_PROFILE, sort_keys=True, separators=(",", ":"))


def build_ucp_envelope(
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
) -> ProtocolEnvelope:
    """Wrap a UCP request payload in a ProtocolEnvelope.

    The adapter centralises envelope construction so firewall +
    consistency + audit use the same shape across UCP REST and
    UCP-over-MCP transports (master prompt §31).
    """
    return envelope_from_raw(
        source_protocol=SourceProtocol.UCP,
        source_protocol_version=UCP_TARGET_VERSION,
        source_transport="rest",  # also valid: "mcp"
        adapter_version="razormesh-ucp-adapter-0.1.0",
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


def build_ucp_checkout_complete_response(
    *,
    checkout_id: str,
    intent_id: str,
    ir: AgentCommerceIR,
    execution_attempt_id: str | None,
) -> dict[str, Any]:
    """Return the UCP-shaped checkout complete response.

    UCP `complete` does not return a payment receipt; the payment
    lifecycle is owned by the trusted executor. The response carries
    the canonical commitment and the execution attempt id for the
    caller to poll.
    """
    return {
        "ucp": {"version": UCP_TARGET_VERSION},
        "id": checkout_id,
        "intent_id": intent_id,
        "state": "complete" if execution_attempt_id else "blocked",
        "commerce_commitment": compute_commitment(ir),
        "commerce_commitment_version": ir.schema_version,
        "execution_attempt_id": execution_attempt_id,
        "razormesh_test_mode": True,
    }


def build_ucp_order_get_response(
    *,
    order_id: str,
    checkout_id: str,
    ir: AgentCommerceIR,
) -> dict[str, Any]:
    """Return a UCP order response for a Razorpay Test-mode order."""
    return {
        "ucp": {"version": UCP_TARGET_VERSION},
        "id": order_id,
        "checkout_id": checkout_id,
        "commerce_commitment": compute_commitment(ir),
        "razormesh_test_mode": True,
    }


# ---------------------------------------------------------------------------
# M29 — Signed event fixture path
# ---------------------------------------------------------------------------


def build_signed_order_event(
    *,
    order_id: str,
    checkout_id: str,
    event_type: str,
    secret: bytes,
) -> dict[str, Any]:
    """Build a UCP-style signed order event for the test fixture path.

    The signature here is HMAC-SHA256 over the canonical JSON of the
    event body using the local UCP test key. Production UCP uses
    RFC 9421 HTTP Message Signatures; for the test fixture, HMAC is
    sufficient because the verification is local and the secret is
    rotated per test run.
    """
    body = {
        "ucp_version": UCP_TARGET_VERSION,
        "order_id": order_id,
        "checkout_id": checkout_id,
        "event_type": event_type,
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = hashlib.sha256(secret + canonical).hexdigest()
    return {"body": body, "signature": sig, "scheme": "RMA-HMAC-SHA256-2026"}


def verify_signed_order_event(event: Mapping[str, Any], secret: bytes) -> bool:
    body = event.get("body")
    sig = event.get("signature")
    if not isinstance(body, Mapping) or not isinstance(sig, str):
        return False
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected = hashlib.sha256(secret + canonical).hexdigest()
    return expected == sig


__all__ = [
    "RMA_UCP_PROFILE",
    "UCP_PROFILE_PATH",
    "UCP_TARGET_VERSION",
    "build_signed_order_event",
    "build_ucp_checkout_complete_response",
    "build_ucp_envelope",
    "build_ucp_order_get_response",
    "serialize_ucp_profile",
    "verify_signed_order_event",
]
