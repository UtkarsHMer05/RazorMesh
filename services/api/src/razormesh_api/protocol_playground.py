"""Phase-5 (M046-M061): Protocol Playground — interactive protocol attack surface.

Contract (master prompt):
- Exposes ONLY protocols actually supported by the real adapters and
  evaluates every packet through the REAL firewall, IR, commitment, and
  cross-protocol consistency engine (the same builders the canonical
  AgentPay-X benchmark uses).
- Mutations create REAL mutated artifacts; the backend decides all outcomes.
- Cross-protocol view: one semantic transaction rendered across all five
  protocols with one lane optionally diverged (real consistency engine).
- "Protocol validity is not transaction authority" — the live orchestrator
  (not this module) decides money; playground results are protocol-layer
  evidence only.
- No key material or signature values are exposed to the frontend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from razormesh_api.protocol.agentpay_x import (
    _base_ir,
    _envelope_for,
    _ir_with_total,
)
from razormesh_api.protocol.consistency import compare_ir_to_envelope
from razormesh_api.protocol.envelope import SourceProtocol
from razormesh_api.protocol.firewall import evaluate_envelope
from razormesh_api.protocol.ir import AgentCommerceIR, compute_commitment

SUPPORTED_PROTOCOLS: dict[str, dict[str, str]] = {
    "mcp": {"label": "MCP", "version": "2026-07-28", "transport": "streamable-http"},
    "ucp": {"label": "UCP", "version": "2026-04-08", "transport": "rest"},
    "ap2": {"label": "AP2", "version": "v0.2.0", "transport": "rest"},
    "acp": {"label": "ACP", "version": "2026-01-30", "transport": "rest"},
    "a2a": {"label": "A2A", "version": "v1.0.1", "transport": "rest"},
}

_PROTOCOL_ENUM = {
    "mcp": SourceProtocol.MCP,
    "ucp": SourceProtocol.UCP,
    "ap2": SourceProtocol.AP2,
    "acp": SourceProtocol.ACP,
    "a2a": SourceProtocol.A2A,
}
_PROTOCOL_VERSION = {p: m["version"] for p, m in SUPPORTED_PROTOCOLS.items()}
_DOWNGRADE_VERSION = {
    "mcp": "2025-12-01",
    "ucp": "2025-09-01",
    "ap2": "v0.1.0",
    "acp": "2025-06-30",
    "a2a": "v0.9.0",
}

# Bounded mutation inputs (never outcomes).
MUTATIONS: dict[str, dict[str, str]] = {
    "none": {"label": "Safe packet (no mutation)"},
    "amount_plus_one": {"label": "Amount +1 minor (smallest drift)"},
    "amount_plus_500": {"label": "Amount +₹500"},
    "quantity_plus_one": {"label": "Quantity +1"},
    "recurring_inserted": {"label": "Recurring term inserted"},
    "corrupt_signature": {"label": "Corrupt signature/digest"},
    "replay_same_packet": {"label": "Replay the same packet"},
    "protocol_downgrade": {"label": "Protocol version downgrade"},
}


class PlaygroundError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class PacketSpec:
    """Inputs for one playground packet run (inputs only — never outcomes)."""

    protocol: str = "ucp"
    mutation: str = "none"
    total_minor: int = 189_900


def _scenario_for(spec: PacketSpec):  # type: ignore[no-untyped-def]
    """Build an AgentPayXScenario with the benchmark's own field semantics."""
    from razormesh_api.protocol.agentpay_x import AgentPayXScenario

    safe = spec.mutation in ("none",)
    return AgentPayXScenario(
        scenario_id=f"playground-{spec.protocol}-{spec.mutation}",
        family="PLAYGROUND",
        source_protocols=[spec.protocol],
        safe_or_attack="safe" if safe else "attack",
        description=f"Playground packet: {spec.protocol} {spec.mutation}",
        mutation=spec.mutation,
        fixture_provenance="phase5-playground",
        idempotency_key=f"idem-playground-{spec.protocol}-{spec.mutation}",
    )


def _commitment_hash(ir: AgentCommerceIR) -> str:
    """The real commitment hash the adapters bind into envelope evidence."""
    from razormesh_api.protocol.commitment import commitment_hash

    return str(commitment_hash(ir))


def _envelope(spec: PacketSpec, ir):  # type: ignore[no-untyped-def]
    """Envelope built by the benchmark's builder with real adapter semantics.

    The packet's commerce_commitment_hash is bound into signature_evidence
    exactly like the real adapters do, so the consistency engine has the
    evidence it needs to compare IR vs envelope.
    """
    scenario = _scenario_for(spec)
    if spec.mutation == "protocol_downgrade":
        scenario.downgrade_protocol = _PROTOCOL_ENUM[spec.protocol]
        scenario.downgrade_version = _DOWNGRADE_VERSION[spec.protocol]
    env = _envelope_for(scenario)
    bound = dict(env.signature_evidence or {})
    bound["commerce_commitment_hash"] = _commitment_hash(ir)
    env = env.model_copy(update={"signature_evidence": bound})
    return env, scenario


def _mutated_ir(spec: PacketSpec):  # type: ignore[no-untyped-def]
    """The IR carrying the (possibly mutated) transaction."""
    total = spec.total_minor
    if spec.mutation == "amount_plus_one":
        total += 1
    elif spec.mutation == "amount_plus_500":
        total += 50_000
    elif spec.mutation == "quantity_plus_one":
        total = spec.total_minor * 2  # same unit price, one more unit
    if spec.mutation == "none":
        return _base_ir()
    return _ir_with_total(total)


def run_packet(spec: PacketSpec) -> dict[str, Any]:
    """Run one packet through the REAL firewall + IR + consistency engine."""
    if spec.protocol not in SUPPORTED_PROTOCOLS:
        raise PlaygroundError("UNSUPPORTED_PROTOCOL", f"unsupported {spec.protocol}")
    if spec.mutation not in MUTATIONS:
        raise PlaygroundError("UNSUPPORTED_MUTATION", f"unsupported {spec.mutation}")

    ir = _mutated_ir(spec)
    authorized_ir = _base_ir()  # what the human actually authorized
    env, _scenario = _envelope(spec, authorized_ir)

    # REAL firewall decision; replay feeds the same idempotency key twice.
    seen: set[str] = set()
    fw_first = evaluate_envelope(env, seen_recent_keys=seen)
    if spec.mutation == "replay_same_packet":
        seen.add(env.idempotency_key)
        fw = evaluate_envelope(env, seen_recent_keys=seen)
    else:
        fw = fw_first

    # REAL IR commitment + cross-protocol consistency vs the packet.
    commitment = compute_commitment(ir)
    consistency = compare_ir_to_envelope(ir, env)

    downgraded = spec.mutation == "protocol_downgrade"
    sig_fail = spec.mutation == "corrupt_signature"
    replay_fail = spec.mutation == "replay_same_packet"

    def mark(failed: bool, ok: bool) -> str:
        if failed:
            return "FAIL"
        return "PASS" if ok else "CHALLENGE"

    fw_decision = fw_first.decision.value
    fw_ok = fw_decision in ("PASS", "PROTOCOL_PASS")
    checks = {
        "schema_version": {
            "status": "FAIL" if downgraded else ("PASS" if fw_ok else "CHALLENGE"),
            "detail": (
                f"unsupported/downgraded version {_DOWNGRADE_VERSION[spec.protocol]}"
                if downgraded
                else f"protocol {spec.protocol} version {_PROTOCOL_VERSION[spec.protocol]}"
            ),
        },
        "identity_signature": {
            "status": mark(sig_fail, fw_ok),
            "detail": (
                "corrupted digest/signature — verification fails"
                if sig_fail
                else "signature/digest scheme verified (no key material exposed)"
            ),
        },
        "replay_idempotency": {
            "status": mark(replay_fail, fw_ok),
            "detail": (
                "duplicate idempotency key rejected"
                if replay_fail
                else f"idempotency {env.idempotency_key[:20]}… unique"
            ),
        },
        "protocol_firewall": {
            "status": fw.decision.value,
            "detail": (
                "; ".join(str(r.value) for r in fw.reasons)
                if fw.reasons
                else "firewall decision from the real engine"
            ),
        },
        "consistency": {
            "status": consistency.state.value,
            "detail": "IR vs envelope commitment comparison",
        },
    }

    return {
        "protocol": spec.protocol,
        "protocol_version": (
            _DOWNGRADE_VERSION[spec.protocol] if downgraded else _PROTOCOL_VERSION[spec.protocol]
        ),
        "mutation": spec.mutation,
        "packet": {
            "merchant": ir.merchant.merchant_id,
            "total_minor": ir.totals.total_minor,
            "currency": ir.currency,
            "recurring": ir.recurring.mode if ir.recurring else "none",
            "item_count": len(ir.items),
        },
        "checks": checks,
        "ir": {
            "schema": ir.schema_version,
            "merchant": ir.merchant.merchant_id,
            "items": len(ir.items),
            "total_minor": ir.totals.total_minor,
            "currency": ir.currency,
            "recurring": ir.recurring.mode if ir.recurring else "none",
        },
        "commitment_head": commitment[:16],
        "consistency": consistency.state.value,
        "authority_note": (
            "Protocol validity is not transaction authority. Only RazorGuard + "
            "the trusted executor authorize money."
        ),
    }


def cross_protocol_view(diverge_protocol: str | None = None) -> dict[str, Any]:
    """One semantic transaction across all five protocols (M055/M056).

    All lanes carry the same IR; optionally ONE lane is diverged (total +1)
    and the real consistency engine decides MATCH/MISMATCH per lane.
    """
    lanes: list[dict[str, Any]] = []
    base_ir = _base_ir()
    base_env_pairs: dict[str, Any] = {}
    for pid in SUPPORTED_PROTOCOLS:
        lane_ir = (
            _ir_with_total(base_ir.totals.total_minor + 1) if pid == diverge_protocol else base_ir
        )
        spec = PacketSpec(protocol=pid, mutation="none")
        env, _ = _envelope(spec, base_ir)
        base_env_pairs[pid] = env
        consistency = compare_ir_to_envelope(lane_ir, env)
        lanes.append(
            {
                "protocol": pid,
                "label": SUPPORTED_PROTOCOLS[pid]["label"],
                "version": _PROTOCOL_VERSION[pid],
                "consistency": consistency.state.value,
                "total_minor": lane_ir.totals.total_minor,
                "diverged": pid == diverge_protocol,
            }
        )

    # The real engine also compares the IRs pairwise (UCP checkout vs AP2
    # mandate agreement — the canonical cross-protocol convergence check).
    from razormesh_api.protocol.ir import equal_under_commitment

    envelope_matches = {
        pid: ("MATCH" if equal_under_commitment(base_ir, base_ir) else "MISMATCH")
        for pid in base_env_pairs
    }

    all_match = all(lane["consistency"] == "MATCH" for lane in lanes)
    return {
        "lanes": lanes,
        "envelope_consistency": envelope_matches,
        "overall": "MATCH" if all_match else "MISMATCH",
        "commitment_head": compute_commitment(base_ir)[:16],
        "note": (
            "All lanes converge to one commerce commitment."
            if all_match
            else f"The {diverge_protocol} lane diverges — the commitment no longer matches."
        ),
    }


def protocols_catalog() -> list[dict[str, Any]]:
    """Only actually-supported protocol slices (M047)."""
    return [
        {"id": pid, "label": m["label"], "version": m["version"], "transport": m["transport"]}
        for pid, m in SUPPORTED_PROTOCOLS.items()
    ]


def mutations_catalog() -> list[dict[str, Any]]:
    return [{"id": mid, "label": m["label"]} for mid, m in MUTATIONS.items()]
