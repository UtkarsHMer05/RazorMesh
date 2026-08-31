"""F004: protocol crypto claims are technically TRUE.

Proves with the repo's own crypto modules:
- UCP: a real RFC 9421 ES256 signature + RFC 9530 Content-Digest verifies on
  the real signed artifact; mutating the actual signed body bytes makes the
  REAL verifier FAIL; re-signing makes it PASS again. The verdict comes from
  the verifier over real bytes — never from the mutation name.
- AP2: a real ES256 JWS/JWT with checkout-hash binding verifies; tampering
  the signed claim bytes makes the REAL verifier FAIL; re-signing PASSes.
- mcp/acp/a2a carry NO real crypto lane: the playground reports the honest
  commitment-evidence label ("COMMITMENT MATCH — not a cryptographic
  signature"), never a crypto-verification claim.
"""

import pytest

from razormesh_api.protocol.agentpay_x import _base_ir
from razormesh_api.protocol_playground import (
    PacketSpec,
    _ir_body_bytes,
    _run_ap2_real_crypto,
    _run_packet_crypto,
    _run_ucp_real_crypto,
    run_packet,
)

# ---------------------------------------------------------------------------
# UCP: real RFC 9421 + RFC 9530 causality.
# ---------------------------------------------------------------------------


def test_ucp_real_crypto_safe_packet_verifies() -> None:
    ir = _base_ir()
    result = _run_ucp_real_crypto(_ir_body_bytes(ir), corrupt_body=False)
    assert result["verified"] is True, result["reason"]
    assert result["reason"] in ("ok", "verified")
    assert "RFC 9421" in result["scheme"] and "RFC 9530" in result["scheme"]


def test_ucp_real_crypto_corrupted_body_fails_from_real_verifier() -> None:
    ir = _base_ir()
    result = _run_ucp_real_crypto(_ir_body_bytes(ir), corrupt_body=True)
    assert result["verified"] is False
    assert result["reason"] == "content_digest_mismatch"


def test_ucp_crypto_verdict_is_causal_not_name_driven() -> None:
    """The REAL verifier is driven by bytes, not labels.

    Signing a DIFFERENT body and verifying that same body is a valid
    signature (cryptographically correct — the verifier cannot know intent),
    so the meaningful causality is: a signature over the ORIGINAL bytes must
    FAIL against tampered bytes (in-transit tamper), and PASS against the
    bytes it actually signed. Both directions are asserted via the repo's
    real verifier, not the mutation name.
    """
    ir = _base_ir()
    # In-transit tamper: original signature, modified bytes → FAIL.
    tamper = _run_ucp_real_crypto(_ir_body_bytes(ir), corrupt_body=True)
    assert tamper["verified"] is False
    assert tamper["reason"] == "content_digest_mismatch"
    # Bytes the signature actually covers → PASS.
    intact = _run_ucp_real_crypto(_ir_body_bytes(ir), corrupt_body=False)
    assert intact["verified"] is True
    # Direct verifier-level proof (bypassing the helper entirely): RFC 9530
    # digest of the signed bytes vs a mutated body.
    from razormesh_api.protocol.ucp_signatures import (
        compute_content_digest,
        verify_content_digest,
    )

    body = _ir_body_bytes(ir)
    digest = compute_content_digest(body)
    assert verify_content_digest(body, digest) is True
    assert verify_content_digest(body + b"x", digest) is False


def test_ucp_signature_corruption_via_verifier_not_paint() -> None:
    """A run with mutation=corrupt_signature FAILs via the REAL verifier.

    Removing the corruption (corrupt_body=False on the same path) makes the
    same check PASS — the causality contract (G007 style) for crypto.
    """
    corrupt = run_packet(PacketSpec(protocol="ucp", mutation="corrupt_signature"))
    crypto = corrupt["checks"]["packet_crypto"]
    assert crypto["status"] == "FAIL"
    assert crypto["crypto_kind"] == "real_signature_verification"
    safe = run_packet(PacketSpec(protocol="ucp", mutation="none"))
    assert safe["checks"]["packet_crypto"]["status"] == "PASS"


# ---------------------------------------------------------------------------
# AP2: real ES256 JWS + checkout-hash binding causality.
# ---------------------------------------------------------------------------


def test_ap2_real_crypto_safe_packet_verifies() -> None:
    ir = _base_ir()
    result = _run_ap2_real_crypto(ir, corrupt_claim=False)
    assert result["verified"] is True, result["reason"]
    assert result["reason"] == "ok"
    assert result["checkout_hash_bound"] is True


def test_ap2_real_crypto_tampered_claim_fails_from_real_verifier() -> None:
    ir = _base_ir()
    result = _run_ap2_real_crypto(ir, corrupt_claim=True)
    assert result["verified"] is False
    # The real verifier rejects the tampered bytes (signature no longer covers
    # the modified claim segment) — rejected, never a crash.
    assert "signature_invalid" in result["reason"]


def test_ap2_run_packet_crypto_lane_causality() -> None:
    corrupt = run_packet(PacketSpec(protocol="ap2", mutation="corrupt_signature"))
    crypto = corrupt["checks"]["packet_crypto"]
    assert crypto["status"] == "FAIL"
    assert crypto["crypto_kind"] == "real_signature_verification"
    safe = run_packet(PacketSpec(protocol="ap2", mutation="none"))
    assert safe["checks"]["packet_crypto"]["status"] == "PASS"


# ---------------------------------------------------------------------------
# Truthful labels: no fake crypto claims for protocols without real crypto.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("protocol", ["mcp", "acp", "a2a"])
def test_protocols_without_crypto_get_honest_labels(protocol: str) -> None:
    """mcp/acp/a2a must NOT claim cryptographic signature verification."""
    assert _run_packet_crypto(PacketSpec(protocol=protocol, mutation="none"), _base_ir()) is None
    body = run_packet(PacketSpec(protocol=protocol, mutation="none"))
    crypto = body["checks"]["packet_crypto"]
    assert crypto["status"].startswith("N/A")
    assert crypto["crypto_kind"] == "none"
    assert "No cryptographic signature verification is implemented" in crypto["detail"]
    # The identity check itself must say COMMITMENT MATCH, not crypto.
    identity = body["checks"]["identity_signature"]
    assert "COMMITMENT MATCH" in identity["engine"]
    assert identity["crypto_kind"] == "commitment_match"
    blob = str(body).lower()
    assert "cryptographic signature verified" not in blob


def test_firewall_stays_described_as_evidence_consumer() -> None:
    """The firewall consumes adapter verification evidence; it is not the
    cryptographic verifier itself — the playground's authority note and the
    separation of checks (firewall vs packet_crypto) keep that truth."""
    body = run_packet(PacketSpec(protocol="ucp", mutation="none"))
    assert "protocol_firewall" in body["checks"]
    assert "packet_crypto" in body["checks"]
    assert "not transaction authority" in body["authority_note"]


def test_run_packet_response_shape_preserved() -> None:
    """Existing check keys survive (frontend contract), with the new key added."""
    body = run_packet(PacketSpec(protocol="ucp", mutation="amount_plus_one"))
    for key in ("schema_version", "identity_signature", "replay_idempotency",
                "protocol_firewall", "consistency", "packet_crypto"):
        assert key in body["checks"], key
    # A price-drift packet keeps its commitment FAIL (real engine truth).
    assert body["checks"]["identity_signature"]["status"] == "FAIL"
    # ...while its CRYPTO verifies (the signed bytes were fine — the IR
    # commitment drifted; two independent real checks, both truthful).
    assert body["checks"]["packet_crypto"]["status"] == "PASS"
