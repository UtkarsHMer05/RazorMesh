"""ProtocolEnvelope (Phase-4 §5).

A ProtocolEnvelope captures the source/provenance of an external commerce
request. It is *evidence*, never authority. The envelope never holds
raw credentials, raw card numbers, or any payment-provider secret.

Conformance:
- P4-S01: a ProtocolEnvelope cannot reach the payment provider directly.
- P4-S23: the raw payload hash is preserved for evidence.
- P4-S29: protocol/model/policy versions are recorded; no secrets.

Strictness:
- extra-fields policy is explicit (`extra = "forbid"` on the versioned
  schema class; the Pydantic 2 `model_config` enforces it).
- payload size bounded via :data:`MAX_PAYLOAD_BYTES`.
- IDs are versioned.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

ENVELOPE_VERSION = "protocol-envelope-v1"
MAX_PAYLOAD_BYTES = 64 * 1024  # 64 KiB; large enough for real UCP/ACP/AP2 messages


class SourceProtocol(StrEnum):
    MCP = "mcp"
    UCP = "ucp"
    AP2 = "ap2"
    ACP = "acp"
    A2A = "a2a"
    INTERNAL = "internal"


class VerificationState(StrEnum):
    RECEIVED = "received"
    VERIFIED = "verified"
    NORMALIZED = "normalized"
    CROSS_PROTOCOL_CHECKED = "cross_protocol_checked"
    REJECTED = "rejected"


class ProtocolEnvelope(BaseModel):
    """Source/provenance record for an external commerce request.

    The envelope is intentionally a *record*, not a decision. Decisions
    are made by the firewall + consistency engine + Phase-3 trust layer
    and recorded back into the envelope's `verification_state` and
    `verification_reasons` fields.
    """

    model_config = ConfigDict(extra="forbid", frozen=False, use_enum_values=False)

    schema_version: str = Field(default=ENVELOPE_VERSION, frozen=True)

    source_protocol: SourceProtocol
    source_protocol_version: str
    source_transport: str
    adapter_version: str

    message_id: str
    request_id: str
    idempotency_key: str | None = None
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )

    raw_payload_hash: str
    signature_evidence: Mapping[str, Any] = Field(default_factory=dict)
    identity_evidence: Mapping[str, Any] = Field(default_factory=dict)
    capability_evidence: Mapping[str, Any] = Field(default_factory=dict)

    agent: str
    principal_reference: str
    merchant_reference: str

    commerce_payload_reference: str
    authorization_evidence: list[Mapping[str, Any]] = Field(default_factory=list)
    extension_evidence: list[Mapping[str, Any]] = Field(default_factory=list)

    verification_state: VerificationState = VerificationState.RECEIVED
    verification_reasons: list[str] = Field(default_factory=list)

    @field_validator("raw_payload_hash")
    @classmethod
    def _hash_shape(cls, v: str) -> str:
        if not v or len(v) < 8 or not all(c in "0123456789abcdef" for c in v.lower()):
            raise ValueError("raw_payload_hash must be a hex digest")
        return v.lower()

    @field_validator("source_protocol_version")
    @classmethod
    def _ver_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("source_protocol_version is required")
        return v.strip()

    @field_validator("agent", "principal_reference", "merchant_reference")
    @classmethod
    def _ref_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("reference is required")
        return v.strip()

    @field_validator("message_id", "request_id")
    @classmethod
    def _id_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("id is required")
        return v.strip()


def hash_payload(raw: bytes) -> str:
    """Return the SHA-256 hex digest of a raw payload.

    Helper for callers constructing :class:`ProtocolEnvelope` instances
    so they don't accidentally mix hash algorithms.
    """
    if not isinstance(raw, (bytes, bytearray)):
        raise TypeError("raw must be bytes")
    if len(raw) > MAX_PAYLOAD_BYTES:
        raise ValueError(
            f"raw payload exceeds MAX_PAYLOAD_BYTES ({MAX_PAYLOAD_BYTES})"
        )
    return hashlib.sha256(bytes(raw)).hexdigest()


def envelope_from_raw(
    *,
    source_protocol: SourceProtocol,
    source_protocol_version: str,
    source_transport: str,
    adapter_version: str,
    message_id: str,
    request_id: str,
    idempotency_key: str | None,
    raw_payload: bytes,
    signature_evidence: Mapping[str, Any],
    identity_evidence: Mapping[str, Any],
    capability_evidence: Mapping[str, Any],
    agent: str,
    principal_reference: str,
    merchant_reference: str,
    commerce_payload_reference: str,
    authorization_evidence: list[Mapping[str, Any]] | None = None,
    extension_evidence: list[Mapping[str, Any]] | None = None,
) -> ProtocolEnvelope:
    """Build a :class:`ProtocolEnvelope` from a raw payload.

    Centralises payload-size enforcement and hashing. Adapter
    implementations should call this rather than instantiating the
    Pydantic model directly so the bounded-payload invariant cannot
    be skipped.
    """
    return ProtocolEnvelope(
        source_protocol=source_protocol,
        source_protocol_version=source_protocol_version,
        source_transport=source_transport,
        adapter_version=adapter_version,
        message_id=message_id,
        request_id=request_id,
        idempotency_key=idempotency_key,
        raw_payload_hash=hash_payload(raw_payload),
        signature_evidence=signature_evidence,
        identity_evidence=identity_evidence,
        capability_evidence=capability_evidence,
        agent=agent,
        principal_reference=principal_reference,
        merchant_reference=merchant_reference,
        commerce_payload_reference=commerce_payload_reference,
        authorization_evidence=list(authorization_evidence or []),
        extension_evidence=list(extension_evidence or []),
    )


def envelope_to_canonical_json(env: ProtocolEnvelope) -> str:
    """RFC 8785 / JCS-friendly canonical JSON for hashing.

    Phase 4 stores this exact string under the audit event's
    `envelope_canonical_hash` so re-verification is deterministic.
    Sorted keys; no whitespace; UTF-8.
    """
    return json.dumps(
        env.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
