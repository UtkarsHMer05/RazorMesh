"""Cross-Protocol Consistency Engine (Phase-4 §10, M18).

Given multiple independently valid artifacts (MCP request, UCP
checkout, AP2 mandate, ACP session, ExecutionTicket), normalize to
AgentCommerceIR and compare.

Returns:
- MATCH
- MISMATCH
- INSUFFICIENT_EVIDENCE

Cross-protocol mismatch is a BLOCK/CHALLENGE input that NLI cannot
override (P4-S19, P4-S20).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from .envelope import ProtocolEnvelope
from .ir import AgentCommerceIR, equal_under_commitment


class ConsistencyState(StrEnum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True)
class ConsistencyResult:
    state: ConsistencyState
    reasons: tuple[str, ...] = ()
    mismatched_fields: tuple[str, ...] = ()

    def is_match(self) -> bool:
        return self.state == ConsistencyState.MATCH


def compare_ir_to_envelope(
    ir: AgentCommerceIR,
    env: ProtocolEnvelope,
) -> ConsistencyResult:
    """Compare an IR to a single envelope.

    The IR is the canonical truth from the protocol adapter's
    normalization. The envelope carries the source. If the envelope
    contains a `commerce_commitment_hash` in its
    `signature_evidence` and that hash equals the IR's commitment
    hash, this returns MATCH.

    If the envelope is missing the commitment, the result is
    INSUFFICIENT_EVIDENCE.
    """
    from .commitment import commitment_hash  # local import to avoid cycle

    evidence = env.signature_evidence or {}
    if "commerce_commitment_hash" not in evidence:
        return ConsistencyResult(
            state=ConsistencyState.INSUFFICIENT_EVIDENCE,
            reasons=("envelope lacks commerce_commitment_hash",),
        )
    expected = commitment_hash(ir)
    if evidence["commerce_commitment_hash"] != expected:
        return ConsistencyResult(
            state=ConsistencyState.MISMATCH,
            reasons=(
                f"envelope commitment hash {evidence['commerce_commitment_hash']!r} "
                f"does not match IR commitment hash {expected!r}",
            ),
            mismatched_fields=("commerce_commitment_hash",),
        )
    return ConsistencyResult(state=ConsistencyState.MATCH)


def compare_envelopes(
    irs: Sequence[AgentCommerceIR],
) -> ConsistencyResult:
    """Compare multiple IRs to each other.

    Used to confirm that independently decoded representations of the
    same authorization-relevant commerce (e.g. a UCP checkout and an
    AP2 closed mandate) agree.

    Empty input is INSUFFICIENT_EVIDENCE (caller's responsibility to
    surface a meaningful reason).
    """
    if not irs:
        return ConsistencyResult(
            state=ConsistencyState.INSUFFICIENT_EVIDENCE,
            reasons=("no IRs provided",),
        )
    if len(irs) == 1:
        return ConsistencyResult(state=ConsistencyState.MATCH)
    base = irs[0]
    mismatched: list[str] = []
    for i, other in enumerate(irs[1:], start=1):
        if not equal_under_commitment(base, other):
            mismatched.append(f"irs[{i}]")
    if mismatched:
        return ConsistencyResult(
            state=ConsistencyState.MISMATCH,
            reasons=(f"commitment mismatch with {','.join(mismatched)}",),
            mismatched_fields=tuple(mismatched),
        )
    return ConsistencyResult(state=ConsistencyState.MATCH)


__all__ = [
    "ConsistencyResult",
    "ConsistencyState",
    "compare_envelopes",
    "compare_ir_to_envelope",
]
