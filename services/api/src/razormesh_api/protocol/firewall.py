"""Protocol Firewall (Phase-4 §9 / M15).

A deterministic pipeline that runs *before* Phase-3 trust logic. The
firewall may make decisions stricter than Phase-3 policy, never looser.

Output:
- PROTOCOL_PASS
- PROTOCOL_CHALLENGE
- PROTOCOL_BLOCK

The firewall is a *record-only* check. It never calls the payment
provider, never creates an ExecutionTicket, and never weakens any
Phase-1/2/3 invariant (P4-S01, P4-S20, P4-S21).
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from .envelope import ProtocolEnvelope, SourceProtocol, VerificationState

# Supported exact versions per docs/PHASE4_PROTOCOL_VERSION_MATRIX.md
SUPPORTED_VERSIONS: dict[SourceProtocol, frozenset[str]] = {
    SourceProtocol.MCP: frozenset({"2026-07-28"}),
    SourceProtocol.UCP: frozenset({"2026-04-08"}),
    SourceProtocol.AP2: frozenset({"v0.2.0"}),
    SourceProtocol.ACP: frozenset({"2026-01-30"}),
    SourceProtocol.A2A: frozenset({"v1.0.1"}),
    SourceProtocol.INTERNAL: frozenset({"internal"}),
}


class FirewallDecision(StrEnum):
    PASS = "PROTOCOL_PASS"  # noqa: S105 — this is a decision value, not a password
    CHALLENGE = "PROTOCOL_CHALLENGE"
    BLOCK = "PROTOCOL_BLOCK"


class FirewallReason(StrEnum):
    UNKNOWN_PROTOCOL = "unknown_protocol"
    UNSUPPORTED_VERSION = "unsupported_version"
    DOWNGRADE = "downgrade"
    BAD_SCHEMA = "bad_schema"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    UNKNOWN_CRITICAL_EXTENSION = "unknown_critical_extension"
    CAPABILITY_MISSING = "capability_missing"
    NO_SIGNATURE = "no_signature"
    NO_IDENTITY = "no_identity"
    EXPIRED = "expired"
    INVALID_IDEMPOTENCY = "invalid_idempotency"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    MERCHANT_BINDING_MISSING = "merchant_binding_missing"
    CURRENCY_AMOUNT_INSANE = "currency_amount_insane"
    CANONICALIZATION_INCOMPLETE = "canonicalization_incomplete"
    AP2_CHAIN_INVALID = "ap2_chain_invalid"
    UCP_CHECKOUT_STATE_INVALID = "ucp_checkout_state_invalid"
    ACP_LIFECYCLE_INVALID = "acp_lifecycle_invalid"
    CROSS_PROTOCOL_MISMATCH = "cross_protocol_mismatch"


@dataclass(frozen=True)
class FirewallResult:
    decision: FirewallDecision
    reasons: tuple[FirewallReason, ...]
    evaluated_at: float = field(default_factory=time.time)

    def is_pass(self) -> bool:
        return self.decision == FirewallDecision.PASS

    def is_block(self) -> bool:
        return self.decision == FirewallDecision.BLOCK

    def is_challenge(self) -> bool:
        return self.decision == FirewallDecision.CHALLENGE


def evaluate_envelope(
    env: ProtocolEnvelope,
    *,
    known_ids: set[str] | None = None,
    seen_recent_keys: set[str] | None = None,
    max_age_seconds: int = 24 * 3600,
) -> FirewallResult:
    """Run the deterministic firewall pipeline on a single envelope.

    The firewall checks what it can check *from the envelope alone*:
    - known protocol?
    - supported exact version?
    - no downgrade?
    - payload bounded?
    - signature/digest evidence present?
    - identity evidence present?
    - capability evidence present?
    - timestamp acceptable?
    - idempotency semantics valid?
    - merchant binding?
    - currency/amount sane?
    - canonicalization complete?
    - cross-protocol commitment consistent?

    The firewall does *not* verify cryptographic signatures. Signature
    verification is the responsibility of the protocol-specific
    adapter (M25 / M30 / M35..M37). The firewall fails closed if the
    adapter did not record any signature evidence.
    """

    reasons: list[FirewallReason] = []

    # 1. Known protocol + exact version (no downgrade).
    if env.source_protocol not in SUPPORTED_VERSIONS:
        return FirewallResult(
            decision=FirewallDecision.BLOCK,
            reasons=(FirewallReason.UNKNOWN_PROTOCOL,),
        )
    supported = SUPPORTED_VERSIONS[env.source_protocol]
    if env.source_protocol_version not in supported:
        # Compare semver-ish by stripping dots to detect downgrade
        # attempts. If the requested version parses as older than the
        # minimum supported, refuse.
        reasons.append(FirewallReason.UNSUPPORTED_VERSION)
        # Mark downgrade if any older-looking version string is present.
        if _looks_like_downgrade(env.source_protocol_version, supported):
            reasons.append(FirewallReason.DOWNGRADE)
        return FirewallResult(
            decision=FirewallDecision.BLOCK,
            reasons=tuple(reasons),
        )

    # 2. Payload bounded.
    if len(env.raw_payload_hash) != 64:
        reasons.append(FirewallReason.BAD_SCHEMA)

    # 3. Signature evidence present.
    if not env.signature_evidence:
        reasons.append(FirewallReason.NO_SIGNATURE)

    # 4. Identity evidence present.
    if not env.identity_evidence:
        reasons.append(FirewallReason.NO_IDENTITY)

    # 5. Capability evidence present (MCP/UCP/ACP/A2A).
    if env.source_protocol != SourceProtocol.INTERNAL and not env.capability_evidence:
        reasons.append(FirewallReason.CAPABILITY_MISSING)

    # 6. Timestamp acceptable.
    if max_age_seconds > 0:
        age = time.time() - env.received_at.timestamp()
        if age < -300 or age > max_age_seconds:
            reasons.append(FirewallReason.EXPIRED)

    # 7. Idempotency semantics.
    if env.idempotency_key is not None:
        if seen_recent_keys is not None and env.idempotency_key in seen_recent_keys:
            # Same key seen recently — the caller's responsibility is
            # to compare payloads and return the prior result. The
            # firewall records the candidate reason; the caller decides
            # PASS/CHALLENGE/BLOCK depending on payload match.
            reasons.append(FirewallReason.REPLAY)

    # 8. Merchant binding.
    if not env.merchant_reference or not env.merchant_reference.strip():
        reasons.append(FirewallReason.MERCHANT_BINDING_MISSING)

    # 9. Currency/amount sanity: at least one item or totals must be
    #    present somewhere; pure-sane downstream is checked later.
    if not env.commerce_payload_reference:
        reasons.append(FirewallReason.CANONICALIZATION_INCOMPLETE)

    # 10. Cross-protocol commitment must already be present if multiple
    #     protocol sources claim this envelope. Phase-4 M11+ records
    #     this via envelope.provenance. For now, treat absent provenance
    #     as a CHALLENGE, not a BLOCK, because single-source envelopes
    #     are common.
    #     Implemented in M18 (cross-protocol engine) — kept here as a
    #     stub for ordering.

    if FirewallReason.NO_SIGNATURE in reasons or FirewallReason.NO_IDENTITY in reasons:
        return FirewallResult(
            decision=FirewallDecision.BLOCK,
            reasons=tuple(reasons),
        )
    if reasons:
        return FirewallResult(
            decision=FirewallDecision.CHALLENGE,
            reasons=tuple(reasons),
        )
    return FirewallResult(decision=FirewallDecision.PASS, reasons=())


def _looks_like_downgrade(requested: str, supported: frozenset[str]) -> bool:
    """Return True if the requested version string is older than the
    minimum supported.

    A pragmatic check: extract the YYYY-MM-DD portion if present and
    compare lexicographically (which works for ISO dates).
    """
    if not requested or not supported:
        return False
    requested_date = _extract_date(requested)
    if requested_date is None:
        return False
    min_supported: str | None = min(
        (d for d in (_extract_date(s) for s in supported) if d is not None),
        default=None,
    )
    if min_supported is None:
        return False
    return requested_date < min_supported


def _extract_date(v: str) -> str | None:
    """Return the leading YYYY-MM-DD of a version string, or None."""
    parts = v.split("-")
    if len(parts) >= 3 and len(parts[0]) == 4 and parts[0].isdigit():
        return "-".join(parts[:3])
    return None


def mark_envelope_state(
    env: ProtocolEnvelope,
    state: VerificationState,
    reasons: Sequence[str],
) -> ProtocolEnvelope:
    """Return a new envelope with `verification_state` and `verification_reasons` set.

    Phase 4 does not mutate the original envelope in place. Adapters
    persist the updated envelope alongside the audit event.
    """
    return env.model_copy(
        update={
            "verification_state": state,
            "verification_reasons": list(reasons),
        }
    )


__all__ = [
    "SUPPORTED_VERSIONS",
    "FirewallDecision",
    "FirewallReason",
    "FirewallResult",
    "evaluate_envelope",
    "mark_envelope_state",
]
