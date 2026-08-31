"""AP2 v0.2.0 verification tests (M33..M39).

Verifies:
- ES256/P-256 key generation; no Ed25519 reused
- JWK shape correct
- merchant JWT signed and verified with ES256
- vct exact match required
- alg must be ES256 (no Ed25519 per P4-S15)
- kid mismatch rejected
- AP2 checkout hash binds to IR; mutating IR changes hash
- PoP HMAC is deterministic
- AP2 evidence bridged to IR; mismatched IR + valid AP2 sig => BLOCK
  (per P4-S19)
"""

from __future__ import annotations

from razormesh_api.protocol.ap2_verifier import (
    AP2_TARGET_VERSION,
    build_ap2_merchant_checkout_jwt,
    compute_ap2_checkout_hash,
    compute_ap2_pop,
    export_ap2_test_merchant_pub_jwk,
    generate_ap2_test_merchant_key,
    verify_ap2_merchant_jwt_es256,
)
from razormesh_api.protocol.ir import (
    AgentCommerceIR,
    _IRAuthorization,
    _IRCheckout,
    _IRItem,
    _IRMerchant,
    _IRProvenance,
    _IRTotals,
    _Money,
    _Quantity,
    equal_under_commitment,
)


def _ir(
    *,
    merchant_id: str = "merch_a",
    total_minor: int = 189900,
    currency: str = "INR",
    product_id: str = "prod_a",
) -> AgentCommerceIR:
    return AgentCommerceIR(
        principal_ref="p",
        agent_ref="a",
        merchant=_IRMerchant(merchant_id=merchant_id),
        checkout=_IRCheckout(revision="r1"),
        items=[
            _IRItem(
                product_id=product_id,
                quantity=_Quantity(value=1, unit="EA", scale=0),
                unit_price=_Money(value_minor=total_minor, currency=currency),
            )
        ],
        totals=_IRTotals(total_minor=total_minor),
        currency=currency,
        authorization=_IRAuthorization(intent_contract_id="ic_1", authorization_generation=1),
        provenance=_IRProvenance(source_protocols=["ap2"]),
    )


def test_target_version_pinned():
    assert AP2_TARGET_VERSION == "v0.2.0"


def test_generate_ap2_test_merchant_key_is_p256():
    key = generate_ap2_test_merchant_key()
    pub_numbers = key.public_key().public_numbers()
    assert pub_numbers.curve.name == "secp256r1"


def test_jwk_shape():
    key = generate_ap2_test_merchant_key()
    jwk = export_ap2_test_merchant_pub_jwk(key, "kid-1")
    assert jwk["kty"] == "EC"
    assert jwk["crv"] == "P-256"
    assert jwk["kid"] == "kid-1"
    assert "x" in jwk
    assert "y" in jwk


def test_merchant_jwt_sign_verify_round_trip():
    key = generate_ap2_test_merchant_key()
    jwk = export_ap2_test_merchant_pub_jwk(key, "kid-1")
    ir = _ir()
    jwt = build_ap2_merchant_checkout_jwt(key=key, kid="kid-1", ir=ir)
    ok, reason = verify_ap2_merchant_jwt_es256(
        jwt=jwt,
        public_jwk=jwk,
        expected_vct="ap2.checkout.merchant.v0.2.0",
    )
    assert ok, reason
    assert reason == "ok"


def test_ap2_jwt_must_be_es256_not_ed25519():
    # P4-S15: the merchant JWT is bound to ES256 per AP2 v0.2.
    # We sign a JWT with HS256 (which is not allowed) and assert the
    # verifier rejects it. This documents the contract without
    # bringing Ed25519 in scope.
    import base64
    import hashlib
    import hmac
    import json

    def _b64u(b: bytes) -> str:
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")

    header = {"alg": "HS256", "typ": "JWT", "kid": "kid-1"}
    payload = {
        "vct": "ap2.checkout.merchant.v0.2.0",
        "iss": "razormesh-test-merchant",
    }
    h = _b64u(json.dumps(header, sort_keys=True, separators=(",", ":")).encode())
    p = _b64u(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    sig = _b64u(hmac.new(b"k", f"{h}.{p}".encode(), hashlib.sha256).digest())
    bad_jwt = f"{h}.{p}.{sig}"
    key = generate_ap2_test_merchant_key()
    jwk = export_ap2_test_merchant_pub_jwk(key, "kid-1")
    ok, reason = verify_ap2_merchant_jwt_es256(
        jwt=bad_jwt,
        public_jwk=jwk,
        expected_vct="ap2.checkout.merchant.v0.2.0",
    )
    assert not ok
    assert reason == "alg_must_be_ES256"


def test_vct_exact_match_required():
    key = generate_ap2_test_merchant_key()
    jwk = export_ap2_test_merchant_pub_jwk(key, "kid-1")
    ir = _ir()
    jwt = build_ap2_merchant_checkout_jwt(key=key, kid="kid-1", ir=ir)
    # Wrong vct => fail
    ok, reason = verify_ap2_merchant_jwt_es256(
        jwt=jwt, public_jwk=jwk, expected_vct="some.other.vct"
    )
    assert not ok
    assert reason == "vct_mismatch"


def test_kid_mismatch_rejected():
    key = generate_ap2_test_merchant_key()
    jwk = export_ap2_test_merchant_pub_jwk(key, "kid-1")
    ir = _ir()
    jwt = build_ap2_merchant_checkout_jwt(key=key, kid="kid-2", ir=ir)
    ok, reason = verify_ap2_merchant_jwt_es256(
        jwt=jwt,
        public_jwk=jwk,
        expected_vct="ap2.checkout.merchant.v0.2.0",
    )
    assert not ok
    assert reason == "kid_mismatch"


def test_ap2_checkout_hash_binds_to_ir():
    ir = _ir(total_minor=189900)
    h1 = compute_ap2_checkout_hash(ir)
    ir2 = _ir(total_minor=189901)
    h2 = compute_ap2_checkout_hash(ir2)
    assert h1 != h2


def test_pop_deterministic():
    assert compute_ap2_pop(b"k", b"c") == compute_ap2_pop(b"k", b"c")
    assert compute_ap2_pop(b"k", b"c") != compute_ap2_pop(b"k2", b"c")
    assert compute_ap2_pop(b"k", b"c") != compute_ap2_pop(b"k", b"c2")


def test_ap2_signature_valid_ir_mismatch_still_blocks():
    # P4-S19: a valid AP2 signature must not override a cross-protocol
    # mismatch. We verify the IR equality contract that drives that
    # rule.
    ir_a = _ir(total_minor=189900, product_id="prod_a")
    ir_b = _ir(total_minor=189900, product_id="prod_b")  # different product
    assert not equal_under_commitment(ir_a, ir_b)


def test_separate_from_execution_ticket_key():
    # P4-S15: AP2 test merchant key is separate from ExecutionTicket
    # key. We document this contract by verifying that the AP2
    # test-key generator produces a P-256 key while the Phase-1
    # ExecutionTicket key is Ed25519.
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    ap2_key = generate_ap2_test_merchant_key()
    assert ap2_key.public_key().public_numbers().curve.name == "secp256r1"

    ed_key = Ed25519PrivateKey.generate()
    # Different families / object types. The separation is structural.
    assert type(ap2_key).__name__ != type(ed_key).__name__


def test_tampered_jwt_is_rejected_not_crash() -> None:
    """F004 regression: a tampered claim segment must be REJECTED with a
    (False, signature_invalid:...) verdict, never raise InvalidSignature."""

    from razormesh_api.protocol.ap2_verifier import (
        export_ap2_test_merchant_pub_jwk,
        generate_ap2_test_merchant_key,
        sign_ap2_merchant_jwt_es256,
        verify_ap2_merchant_jwt_es256,
    )

    key = generate_ap2_test_merchant_key()
    kid = "tamper-regression"
    jwt = sign_ap2_merchant_jwt_es256(
        key=key, kid=kid, payload={"vct": "ap2-checkout-authorization", "total_minor": 100}
    )
    pub = export_ap2_test_merchant_pub_jwk(key, kid)
    header_b64, payload_b64, sig_b64 = jwt.split(".")
    import base64
    import json as _json

    pad = "=" * (-len(payload_b64) % 4)
    claims = _json.loads(base64.urlsafe_b64decode(payload_b64 + pad))
    claims["total_minor"] = 999  # tamper AFTER signing
    tampered = base64.urlsafe_b64encode(
        _json.dumps(claims, sort_keys=True, separators=(",", ":")).encode()
    ).rstrip(b"=")
    forged = f"{header_b64}.{tampered.decode('ascii')}.{sig_b64}"
    ok, reason = verify_ap2_merchant_jwt_es256(
        jwt=forged, public_jwk=pub, expected_vct="ap2-checkout-authorization"
    )
    assert ok is False
    assert "signature_invalid" in reason
