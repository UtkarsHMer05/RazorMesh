"""Phase-5 (M046-M061) + deep-engine correction (G006-G011): Protocol Playground.

Contract:
- Exposes ONLY protocols actually supported by the real adapters and
  evaluates every packet through the REAL firewall, IR, commitment, and
  cross-protocol consistency engine (the same builders the canonical
  AgentPay-X benchmark uses).
- EVERY mutation builds a REAL mutated artifact (IR and/or envelope). No
  check is painted from the mutation name: verdicts come from running the
  real engines over the real artifacts. Corrupt-signature corrupts actual
  signature evidence and runs the real verifier; replay reuses the actual
  idempotency context; downgrade changes the actual version field.
- Cross-protocol view: one semantic transaction rendered across all five
  protocols with one lane optionally diverged (real consistency engine,
  real per-lane envelope commitments - never compare-base-to-base).
- "Protocol validity is not transaction authority" - the live orchestrator
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
    _ir_with_recurring,
    _ir_with_total,
)
from razormesh_api.protocol.consistency import compare_ir_to_envelope
from razormesh_api.protocol.envelope import ProtocolEnvelope, SourceProtocol
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
    "quantity_plus_one": {"label": "Quantity +1 (quantity field, not total)"},
    "recurring_inserted": {"label": "Recurring term inserted (recurring field)"},
    "corrupt_signature": {"label": "Corrupt signature/digest (real bytes corrupted)"},
    "replay_same_packet": {"label": "Replay the same packet (same idempotency key)"},
    "protocol_downgrade": {"label": "Protocol version downgrade"},
    "merchant_swap": {"label": "Merchant substitution"},
}


class PlaygroundError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class PacketSpec:
    """Inputs for one playground packet run (inputs only - never outcomes)."""

    protocol: str = "ucp"
    mutation: str = "none"
    total_minor: int = 189_900


def _scenario_for(spec: PacketSpec, *, mutation_override: str | None = None):  # type: ignore[no-untyped-def]
    """Build an AgentPayXScenario with the benchmark's own field semantics."""
    from razormesh_api.protocol.agentpay_x import AgentPayXScenario

    mutation = mutation_override or spec.mutation
    safe = mutation == "none"
    return AgentPayXScenario(
        scenario_id=f"playground-{spec.protocol}-{mutation}",
        family="PLAYGROUND",
        source_protocols=[spec.protocol],
        safe_or_attack="safe" if safe else "attack",
        description=f"Playground packet: {spec.protocol} {mutation}",
        mutation=mutation,
        fixture_provenance="phase5-playground",
        idempotency_key=f"idem-playground-{spec.protocol}-{mutation}",
    )


def _commitment_hash(ir: AgentCommerceIR) -> str:
    """The real commitment hash the adapters bind into envelope evidence."""
    from razormesh_api.protocol.commitment import commitment_hash

    return str(commitment_hash(ir))


# ---------------------------------------------------------------------------
# G006/G008/G009: every mutation changes the actual semantic field it names.
# ---------------------------------------------------------------------------


def _ir_with_quantity_plus_one(base: AgentCommerceIR) -> AgentCommerceIR:
    """Quantity 1 → 2 on the actual quantity field; totals recompute as a
    consequence (unit price unchanged), exactly like a real adapter would."""
    from razormesh_api.protocol.ir import (
        _IRItem,
        _IRTotals,
        _Money,
        _Quantity,
    )

    old_item = base.items[0]
    new_qty = int(old_item.quantity.value) + 1
    unit = int(old_item.unit_price.value_minor)
    item = _IRItem(
        product_id=old_item.product_id,
        variant_id=old_item.variant_id,
        merchant_item_id=old_item.merchant_item_id,
        title=old_item.title,
        brand=old_item.brand,
        condition=old_item.condition,
        quantity=_Quantity(
            value=new_qty, unit=old_item.quantity.unit, scale=old_item.quantity.scale
        ),
        unit_price=_Money(value_minor=unit, currency=old_item.unit_price.currency),
    )
    subtotal = unit * new_qty
    old_totals = base.totals
    extras = (
        int(old_totals.tax_minor or 0)
        + int(old_totals.fee_minor or 0)
        + int(old_totals.fulfillment_minor or 0)
        + int(old_totals.discount_minor or 0)
    )
    totals = _IRTotals(
        subtotal_minor=subtotal,
        tax_minor=old_totals.tax_minor,
        fee_minor=old_totals.fee_minor,
        fulfillment_minor=old_totals.fulfillment_minor,
        discount_minor=old_totals.discount_minor,
        total_minor=subtotal + extras,
    )
    return base.model_copy(update={"items": [item], "totals": totals})


def build_mutated_ir(spec: PacketSpec) -> AgentCommerceIR:
    """The IR carrying the (possibly mutated) transaction.

    Each mutation changes the actual semantic field it claims to change:
    amount → totals; quantity → the quantity field (totals follow);
    recurring → the recurring mode/terms; merchant → the merchant identity.
    """
    base = _base_ir()
    if spec.mutation == "none":
        return base
    if spec.mutation == "amount_plus_one":
        return _ir_with_total(base.totals.total_minor + 1)
    if spec.mutation == "amount_plus_500":
        return _ir_with_total(base.totals.total_minor + 50_000)
    if spec.mutation == "quantity_plus_one":
        return _ir_with_quantity_plus_one(base)
    if spec.mutation == "recurring_inserted":
        return _ir_with_recurring("monthly", interval="1m", amount_minor=base.totals.total_minor)
    if spec.mutation == "merchant_swap":
        from razormesh_api.protocol.agentpay_x import _ir_with_merchant

        return _ir_with_merchant("merch_b")
    return base


# ---------------------------------------------------------------------------
# F004: REAL cryptographic signing/verification where the repo implements it.
#
# UCP: a real RFC 9421 HTTP Message Signature (ES256/P-256) over a real RFC
#      9530 Content-Digest of the packet body — signed with the repo's own
#      UCP signing path, verified with the repo's own UCP verifier.
# AP2: a real ES256 JWS/JWT with checkout-hash binding — signed and verified
#      with the repo's own AP2 merchant-JWT path.
# mcp/acp/a2a: NO equivalent cryptographic verification exists in this repo,
#      so those lanes report the honest, weaker claim (SIGNATURE EVIDENCE
#      PRESENT / COMMITMENT MATCH), never "cryptographic signature verified".
# ---------------------------------------------------------------------------


def _ir_body_bytes(ir: AgentCommerceIR) -> bytes:
    """The canonical JSON bytes of the packet IR — what a real UCP body carries."""
    from razormesh_api.protocol.ir import compute_commitment

    return compute_commitment(ir).encode("utf-8")


def _run_ucp_real_crypto(body: bytes, *, corrupt_body: bool) -> dict[str, Any]:
    """Sign the packet body with the repo's real UCP path, then verify.

    ``corrupt_body`` flips the body AFTER signing (an in-transit tamper) so
    the failure comes from the REAL RFC 9530 digest + RFC 9421 signature
    verification over genuinely different bytes — never from the mutation name.
    """
    from razormesh_api.protocol.ucp_signatures import (
        UCP_COVERED_COMPONENTS,
        export_ucp_public_jwk,
        generate_ucp_signing_key,
        sign_ucp_request,
        verify_ucp_request,
    )

    key = generate_ucp_signing_key()
    kid = "playground-ucp-key"
    jwk = export_ucp_public_jwk(key, kid=kid, agent="razormesh-buyer-agent")
    sig_headers = sign_ucp_request(
        body=body,
        method="POST",
        path="/orders",
        authority="merchant.example",
        ucp_agent="razormesh-buyer-agent",
        ucp_profile="ucp-2026-04-08",
        key=key,
        keyid=kid,
        idempotency_key="idem-playground-ucp",
        components=UCP_COVERED_COMPONENTS,
    )
    verified_body = body + b"\x00tampered" if corrupt_body else body
    result = verify_ucp_request(
        body=verified_body,
        method="POST",
        path="/orders",
        authority="merchant.example",
        headers=sig_headers.to_headers(),
        known_jwks={kid: jwk},
    )
    return {
        "scheme": "ES256/P-256 — RFC 9421 HTTP Message Signature + RFC 9530 Content-Digest",
        "verified": bool(result.ok),
        "reason": result.reason,
        "covered_components": list(UCP_COVERED_COMPONENTS),
    }


def _run_ap2_real_crypto(ir: AgentCommerceIR, *, corrupt_claim: bool) -> dict[str, Any]:
    """Sign a real AP2 ES256 merchant JWT binding the checkout hash, then verify.

    ``corrupt_claim`` modifies the SIGNED claim bytes after signing so the
    failure comes from the REAL ES256 verifier over genuinely tampered bytes.
    """
    import base64
    import json as _json

    from razormesh_api.protocol.ap2_verifier import (
        compute_ap2_checkout_hash,
        export_ap2_test_merchant_pub_jwk,
        generate_ap2_test_merchant_key,
        sign_ap2_merchant_jwt_es256,
        verify_ap2_merchant_jwt_es256,
    )

    key = generate_ap2_test_merchant_key()
    kid = "playground-ap2-merchant"
    checkout_hash = compute_ap2_checkout_hash(ir)
    payload = {
        "vct": "ap2-checkout-authorization",
        "checkout_hash": checkout_hash,
        "merchant": ir.merchant.merchant_id,
        "total_minor": ir.totals.total_minor,
    }
    jwt = sign_ap2_merchant_jwt_es256(key=key, kid=kid, payload=payload)
    pub_jwk = export_ap2_test_merchant_pub_jwk(key, kid)

    if corrupt_claim:
        # Tamper the signed payload segment (an in-transit claim mutation).
        header_b64, payload_b64, sig_b64 = jwt.split(".")
        pad = "=" * (-len(payload_b64) % 4)
        claims = _json.loads(base64.urlsafe_b64decode(payload_b64 + pad))
        claims["total_minor"] = int(claims["total_minor"]) + 1
        tampered_payload = base64.urlsafe_b64encode(
            _json.dumps(claims, sort_keys=True, separators=(",", ":")).encode()
        ).rstrip(b"=")
        jwt = f"{header_b64}.{tampered_payload.decode('ascii')}.{sig_b64}"

    ok, reason = verify_ap2_merchant_jwt_es256(
        jwt=jwt,
        public_jwk=pub_jwk,
        expected_vct="ap2-checkout-authorization",
    )
    checkout_ok = payload["checkout_hash"] == compute_ap2_checkout_hash(ir)
    return {
        "scheme": "ES256/P-256 — JWS/JWT + checkout-hash key binding",
        "verified": bool(ok and checkout_ok),
        "reason": reason if not ok else ("ok" if checkout_ok else "checkout_hash_mismatch"),
        "checkout_hash_bound": bool(checkout_ok),
    }


def _run_packet_crypto(spec: PacketSpec, ir: AgentCommerceIR) -> dict[str, Any] | None:
    """Real cryptographic verification for protocols the repo actually implements.

    Returns None for protocols without a real crypto implementation (mcp, acp,
    a2a) so their lane keeps the honest commitment-evidence label instead.
    """
    if spec.protocol == "ucp":
        return _run_ucp_real_crypto(
            _ir_body_bytes(ir), corrupt_body=spec.mutation == "corrupt_signature"
        )
    if spec.protocol == "ap2":
        return _run_ap2_real_crypto(ir, corrupt_claim=spec.mutation == "corrupt_signature")
    return None


# ---------------------------------------------------------------------------
# G007: real signature/digest corruption + the real UCP verifier.
# ---------------------------------------------------------------------------


def _corrupt_signature_evidence(env: ProtocolEnvelope) -> ProtocolEnvelope:
    """Corrupt the ACTUAL signed/digest material on the envelope.

    The playground packet's signature evidence carries the commerce
    commitment hash the adapter bound at signing time. Corrupting it models a
    tampered signed artifact: the commitment bytes change, so the real
    consistency verifier (which re-derives the IR commitment and compares it
    against the envelope's signed evidence) must FAIL/MISMATCH on its own.
    """
    import hashlib
    import json

    bound = dict(env.signature_evidence or {})
    original = str(bound.get("commerce_commitment_hash", ""))
    if original:
        # Flip the committed bytes the way an in-transit tamper would.
        tampered = hashlib.sha256(
            (original.encode("utf-8") + b":corrupted").decode("utf-8").encode("utf-8")
        ).hexdigest()
        bound["commerce_commitment_hash"] = tampered
        bound["signature_scheme"] = "ed25519"
        bound["corruption"] = json.dumps(
            {"field": "commerce_commitment_hash", "bytes_flipped": True}
        )
    return env.model_copy(update={"signature_evidence": bound})


def _verify_signature_evidence(ir: AgentCommerceIR, env) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Run the REAL verification over the envelope's signed evidence.

    The verifier re-computes the IR's commitment and compares it against the
    commitment hash bound in the envelope's signature evidence - the same
    comparison `compare_ir_to_envelope` performs, reported here as the
    identity/signature check with verifier-derived reasons.
    """
    expected = _commitment_hash(ir)
    evidence = dict(env.signature_evidence or {})
    bound = evidence.get("commerce_commitment_hash")
    if bound is None:
        return {"verified": False, "reason": "no_signature_evidence"}
    if not str(bound).startswith("sha256:"):
        # commitment_hash() already returns the bare sha256 hex.
        bound_hex = str(bound)
    else:
        bound_hex = str(bound).split(":", 1)[1]
    if bound_hex != expected:
        return {
            "verified": False,
            "reason": "signature_covers_corrupted_commitment",
            "expected_head": expected[:16],
            "bound_head": bound_hex[:16],
        }
    return {"verified": True, "reason": "signature_covers_ir_commitment"}


# ---------------------------------------------------------------------------
# G010: real cross-protocol consistency (never compare-base-to-base).
# ---------------------------------------------------------------------------


def _packet_envelope(spec: PacketSpec, bound_ir: AgentCommerceIR):  # type: ignore[no-untyped-def]
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
    bound["commerce_commitment_hash"] = _commitment_hash(bound_ir)
    env = env.model_copy(update={"signature_evidence": bound})
    return env, scenario


def run_packet(spec: PacketSpec) -> dict[str, Any]:
    """Run one packet through the REAL firewall + IR + consistency engine.

    Artifacts: the packet carries the (possibly mutated) IR; the envelope
    binds the AUTHORIZED IR's commitment (what the human approved) except
    for corruption/downgrade mutations, which alter the packet itself.
    Every displayed check is derived by running a real engine over these
    artifacts - nothing is painted from the mutation name.
    """
    if spec.protocol not in SUPPORTED_PROTOCOLS:
        raise PlaygroundError("UNSUPPORTED_PROTOCOL", f"unsupported {spec.protocol}")
    if spec.mutation not in MUTATIONS:
        raise PlaygroundError("UNSUPPORTED_MUTATION", f"unsupported {spec.mutation}")

    # The human-authorized IR is the baseline every packet is judged against.
    authorized_ir = _base_ir()
    ir = build_mutated_ir(spec)

    # Downgrade: the packet's envelope really carries the downgraded version.
    if spec.mutation == "protocol_downgrade":
        env, _scenario = _packet_envelope(spec, authorized_ir)
        # _packet_envelope already applied the downgrade fields via the
        # scenario; the version the firewall sees is the downgraded one.
    elif spec.mutation == "corrupt_signature":
        env, _scenario = _packet_envelope(spec, authorized_ir)
        env = _corrupt_signature_evidence(env)
    else:
        env, _scenario = _packet_envelope(spec, authorized_ir)

    # REAL firewall decision. Replay feeds the same idempotency key twice.
    seen: set[str] = set()
    fw_first = evaluate_envelope(env, seen_recent_keys=seen)
    fw = fw_first
    if spec.mutation == "replay_same_packet":
        seen.add(str(env.idempotency_key))
        fw = evaluate_envelope(env, seen_recent_keys=seen)

    # REAL identity/signature verification over the envelope's signed bytes.
    sig = _verify_signature_evidence(ir, env)
    # F004: REAL cryptographic verification where the repo implements it
    # (UCP: RFC 9421 + RFC 9530; AP2: ES256 JWS + checkout-hash binding).
    # For mcp/acp/a2a this returns None — those lanes keep the honest
    # commitment-evidence label, never a crypto-verification claim.
    crypto = _run_packet_crypto(spec, ir)
    # REAL IR commitment + cross-protocol consistency vs the packet.
    commitment = compute_commitment(ir)
    consistency = compare_ir_to_envelope(ir, env)

    fw_decision = fw.decision.value
    fw_ok = fw_decision in ("PASS", "PROTOCOL_PASS")
    # FirewallReason values are the lowercase enum names (unsupported_version,
    # downgrade, replay, …).
    fw_reasons = {str(r.value) for r in fw.reasons}

    def mark(failed: bool, ok: bool) -> str:
        if failed:
            return "FAIL"
        return "PASS" if ok else "CHALLENGE"

    sig_fail = not sig["verified"]
    # The real replay verdict: the firewall recorded replay on the second
    # evaluation of the same idempotency key.
    replay_fail = "replay" in fw_reasons
    downgraded = spec.mutation == "protocol_downgrade"
    # The real downgrade verdict: the firewall rejected the version.
    version_rejected = "unsupported_version" in fw_reasons or "downgrade" in fw_reasons

    checks = {
        "schema_version": {
            "status": ("FAIL" if version_rejected else ("PASS" if fw_ok else "CHALLENGE")),
            "detail": (
                "firewall rejected unsupported/downgraded version "
                + _DOWNGRADE_VERSION[spec.protocol]
                if version_rejected
                else "firewall accepted protocol "
                + spec.protocol
                + " version "
                + _PROTOCOL_VERSION[spec.protocol]
            ),
            # verifier-derived: the real firewall's version verdict is the
            # engine's own decision for this envelope.
            "engine": "protocol firewall (version policy)",
        },
        "identity_signature": {
            "status": mark(sig_fail, True),
            "detail": (
                f"verifier: {sig['reason']} - the signed commitment no longer covers the IR"
                if sig_fail
                else f"verifier: {sig['reason']} (no key material exposed)"
            ),
            # F004 truthful label: this check is a COMMITMENT re-derivation
            # (binding consistency), not a cryptographic signature
            # verification. The real crypto lane is `packet_crypto`.
            "engine": (
                "commitment re-derivation vs envelope signature evidence "
                "(COMMITMENT MATCH — not a cryptographic signature)"
            ),
            "crypto_kind": "commitment_match",
        },
        "packet_crypto": {
            "status": (
                # Real verifier verdict — PASS/FAIL derived from the real
                # crypto verification over real bytes, never the name.
                ("PASS" if crypto["verified"] else "FAIL")
                if crypto is not None
                else "N/A — not implemented for this protocol"
            ),
            "detail": (
                (
                    f"real {crypto['scheme']}: verifier returned '{crypto['reason']}'"
                    if crypto is not None
                    else "No cryptographic signature verification is implemented for this "
                    "protocol in this repository — the identity check above is a "
                    "commitment/binding comparison only (SIGNATURE EVIDENCE PRESENT)."
                )
            ),
            "engine": (
                (
                    "real cryptographic verification "
                    f"({crypto['scheme']}, repo's own signer+verifier)"
                )
                if crypto is not None
                else "not implemented — honest absence"
            ),
            "crypto_kind": "real_signature_verification" if crypto is not None else "none",
        },
        "replay_idempotency": {
            "status": mark(replay_fail, fw_ok),
            "detail": (
                "real idempotency engine: duplicate key rejected on second evaluation"
                if replay_fail
                else "real idempotency engine: key "
                + str(env.idempotency_key)[:20]
                + " unique on first evaluation"
            ),
            "engine": "protocol firewall (idempotency/replay policy)",
        },
        "protocol_firewall": {
            "status": fw_decision,
            "detail": (
                "; ".join(str(r.value) for r in fw.reasons)
                if fw.reasons
                else "firewall decision from the real engine"
            ),
            "engine": "evaluate_envelope",
        },
        "consistency": {
            "status": consistency.state.value,
            "detail": (f"IR vs envelope commitment: {'; '.join(consistency.reasons) or 'match'}"),
            "engine": "compare_ir_to_envelope",
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
            "quantity": int(ir.items[0].quantity.value) if ir.items else 0,
        },
        "checks": checks,
        "ir": {
            "schema": ir.schema_version,
            "merchant": ir.merchant.merchant_id,
            "items": len(ir.items),
            "total_minor": ir.totals.total_minor,
            "currency": ir.currency,
            "recurring": ir.recurring.mode if ir.recurring else "none",
            "quantity": int(ir.items[0].quantity.value) if ir.items else 0,
        },
        "commitment_head": commitment[:16],
        "consistency": consistency.state.value,
        "authority_note": (
            "Protocol validity is not transaction authority. Only RazorGuard + "
            "the trusted executor authorize money."
        ),
    }


def cross_protocol_view(diverge_protocol: str | None = None) -> dict[str, Any]:
    """One semantic transaction across all five protocols (M055/M056 + G010).

    Each lane builds its OWN envelope with the lane's actual bound
    commitment. With no divergence every lane's IR equals the authorized IR;
    with a divergence exactly ONE lane carries the mutated IR (total +1) and
    is judged against the authorized baseline the other lanes still carry.
    Per-lane verdicts come from compare_ir_to_envelope - the pairs are
    (lane_ir, lane_envelope), never (base, base).
    """
    lanes: list[dict[str, Any]] = []
    base_ir = _base_ir()
    for pid in SUPPORTED_PROTOCOLS:
        spec = PacketSpec(protocol=pid, mutation="none")
        env, _ = _packet_envelope(spec, base_ir)
        lane_ir = (
            _ir_with_total(base_ir.totals.total_minor + 1)
            if pid == diverge_protocol
            else base_ir.model_copy(deep=True)
        )
        consistency = compare_ir_to_envelope(lane_ir, env)
        lanes.append(
            {
                "protocol": pid,
                "label": SUPPORTED_PROTOCOLS[pid]["label"],
                "version": _PROTOCOL_VERSION[pid],
                "consistency": consistency.state.value,
                "total_minor": lane_ir.totals.total_minor,
                "diverged": pid == diverge_protocol,
                "commitment_head": _commitment_hash(lane_ir)[:16],
            }
        )

    # Real IR-vs-IR convergence: the authorized baseline against each lane's
    # IR (the canonical cross-protocol convergence check, correct pairs).
    from razormesh_api.protocol.ir import equal_under_commitment

    ir_agreement: dict[str, str] = {}
    for pid in SUPPORTED_PROTOCOLS:
        same = equal_under_commitment(
            base_ir.model_copy(deep=True), _lane_ir_for(pid, diverge_protocol)
        )
        ir_agreement[pid] = "MATCH" if same else "MISMATCH"

    all_match = all(lane["consistency"] == "MATCH" for lane in lanes)
    return {
        "lanes": lanes,
        "envelope_consistency": ir_agreement,
        "overall": "MATCH" if all_match else "MISMATCH",
        "commitment_head": compute_commitment(base_ir)[:16],
        "note": (
            "All lanes converge to one commerce commitment."
            if all_match
            else "The "
            + str(diverge_protocol)
            + " lane diverges - its commitment no longer matches the authorized baseline."
        ),
    }


def _lane_ir_for(pid: str, diverge_protocol: str | None) -> AgentCommerceIR:
    base = _base_ir()
    if pid == diverge_protocol:
        return _ir_with_total(base.totals.total_minor + 1)
    return base.model_copy(deep=True)


def protocols_catalog() -> list[dict[str, Any]]:
    """Only actually-supported protocol slices (M047)."""
    return [
        {"id": pid, "label": m["label"], "version": m["version"], "transport": m["transport"]}
        for pid, m in SUPPORTED_PROTOCOLS.items()
    ]


def mutations_catalog() -> list[dict[str, Any]]:
    return [{"id": mid, "label": m["label"]} for mid, m in MUTATIONS.items()]
