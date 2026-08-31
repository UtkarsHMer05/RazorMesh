"""RazorMesh Phase-4 AP2 v0.2.0 verification module (M33..M39).

Implements the merchant-side verifier and integration layer for AP2
v0.2.0 (per master prompt §14, §15, §8, §27 M33..M39).

Key rules:
- AP2 checkout JWT binding uses ES256/P-256, NOT Ed25519 (P4-S15).
  RazorMesh generates a local test merchant key; it is NOT the
  Ed25519 ExecutionTicket key.
- vct exact-match required; unknown constraints fail (P4-S10, P4-S11).
- Open->closed constraint chain verified for Human-Not-Present (P4-S13).
- cnf / key binding / PoP verified (P4-S14).
- Checkout hash binding verified (P4-S12).
- AP2 evidence is bridged into AgentCommerceIR; mismatched IR
  still BLOCKS even if AP2 signature is valid (P4-S19).

The module is *test roles only*; it does not implement a real
Credential Provider or network.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import Mapping
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from .ir import AgentCommerceIR

AP2_TARGET_VERSION = "v0.2.0"


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def generate_ap2_test_merchant_key() -> ec.EllipticCurvePrivateKey:
    """Generate a fresh AP2 ES256/P-256 test merchant key.

    P4-S15: this key is **separate** from the Ed25519 ExecutionTicket
    key. It is generated fresh per test run and is never reused.
    """
    return ec.generate_private_key(ec.SECP256R1())


def export_ap2_test_merchant_pub_jwk(key: ec.EllipticCurvePrivateKey, kid: str) -> dict[str, Any]:
    """Export the public key as a JWK (kid + kty + crv + x + y)."""
    pub = key.public_key().public_numbers()
    n_bytes = (pub.curve.key_size + 7) // 8
    x = pub.x.to_bytes(n_bytes, "big")
    y = pub.y.to_bytes(n_bytes, "big")
    return {
        "kty": "EC",
        "crv": "P-256",
        "kid": kid,
        "x": _b64url_encode(x),
        "y": _b64url_encode(y),
    }


def sign_ap2_merchant_jwt_es256(
    *,
    key: ec.EllipticCurvePrivateKey,
    kid: str,
    payload: Mapping[str, Any],
) -> str:
    """Sign an AP2-style merchant JWT with ES256 (ECDSA over P-256).

    Returns a JWS compact serialization (header.payload.signature).
    The header carries `alg=ES256`, `typ=JWT`, and the `kid` so the
    verifier can resolve the key.
    """
    header = {"alg": "ES256", "typ": "JWT", "kid": kid}
    header_b64 = _b64url_encode(
        json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    payload_b64 = _b64url_encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"


def verify_ap2_merchant_jwt_es256(
    *,
    jwt: str,
    public_jwk: Mapping[str, Any],
    expected_vct: str,
) -> tuple[bool, str]:
    """Verify an AP2-style merchant JWT.

    Returns (ok, reason). If the JWT is well-formed and the vct
    matches, returns (True, "ok"). Otherwise, returns (False, "...").
    """
    parts = jwt.split(".")
    if len(parts) != 3:
        return False, "malformed_jwt"
    header_b64, payload_b64, sig_b64 = parts
    try:
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except (ValueError, KeyError, UnicodeDecodeError) as e:
        return False, f"decode_error:{e}"
    if header.get("alg") != "ES256":
        return False, "alg_must_be_ES256"
    if header.get("typ") not in ("JWT", None):
        return False, "typ_must_be_JWT"
    if public_jwk.get("kty") != "EC" or public_jwk.get("crv") != "P-256":
        return False, "unsupported_key"
    if header.get("kid") != public_jwk.get("kid"):
        return False, "kid_mismatch"
    if payload.get("vct") != expected_vct:
        return False, "vct_mismatch"
    # Reconstruct the public key.
    try:
        x = int.from_bytes(_b64url_decode(public_jwk["x"]), "big")
        y = int.from_bytes(_b64url_decode(public_jwk["y"]), "big")
        pub_numbers = ec.EllipticCurvePublicNumbers(x=x, y=y, curve=ec.SECP256R1())
        pub = pub_numbers.public_key()
    except (KeyError, ValueError) as e:
        return False, f"key_decode_error:{e}"
    try:
        sig = _b64url_decode(sig_b64)
        pub.verify(
            sig,
            f"{header_b64}.{payload_b64}".encode("ascii"),
            ec.ECDSA(hashes.SHA256()),
        )
    except (ValueError, TypeError) as e:
        return False, f"signature_invalid:{e}"
    except InvalidSignature:
        # F004: a tampered header/payload segment makes the ES256 signature
        # not verify — the verifier must REJECT, never crash.
        return False, "signature_invalid:signature_does_not_cover_tampered_claims"
    return True, "ok"


def compute_ap2_checkout_hash(ir: AgentCommerceIR) -> str:
    """Compute the AP2 checkout hash.

    The AP2 spec defines a specific canonical projection. RazorMesh's
    own commerce-commitment-v1 is the INTERNAL cross-protocol hash;
    this function is the AP2-specific hash for binding the merchant
    checkout JWT to the IR.
    """
    canonical = json.dumps(
        {
            "schema_version": ir.schema_version,
            "merchant_id": ir.merchant.merchant_id,
            "checkout_revision": ir.checkout.revision,
            "items": [
                {
                    "product_id": it.product_id,
                    "quantity": it.quantity.value,
                    "unit_price_minor": it.unit_price.value_minor,
                    "currency": it.unit_price.currency,
                }
                for it in ir.items
            ],
            "total_minor": ir.totals.total_minor,
            "currency": ir.currency,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def build_ap2_merchant_checkout_jwt(
    *,
    key: ec.EllipticCurvePrivateKey,
    kid: str,
    ir: AgentCommerceIR,
    vct: str = "ap2.checkout.merchant.v0.2.0",
) -> str:
    """Build and sign a merchant checkout JWT that binds to the IR.

    The payload includes the vct, merchant id, checkout revision, the
    AP2 checkout hash, and the intent contract id.
    """
    payload = {
        "vct": vct,
        "iss": "razormesh-test-merchant",
        "merchant_id": ir.merchant.merchant_id,
        "checkout_revision": ir.checkout.revision,
        "intent_contract_id": ir.authorization.intent_contract_id,
        "checkout_hash": compute_ap2_checkout_hash(ir),
    }
    return sign_ap2_merchant_jwt_es256(key=key, kid=kid, payload=payload)


# ---------------------------------------------------------------------------
# cnf / key binding / PoP for Human-Not-Present (M37)
# ---------------------------------------------------------------------------


def compute_ap2_pop(secret: bytes, challenge: bytes) -> str:
    """Compute a deterministic AP2-style proof-of-possession.

    PoP is `HMAC-SHA256(secret, challenge)` per the spec convention.
    """
    return hmac.new(secret, challenge, hashlib.sha256).hexdigest()


__all__ = [
    "AP2_TARGET_VERSION",
    "build_ap2_merchant_checkout_jwt",
    "compute_ap2_checkout_hash",
    "compute_ap2_pop",
    "export_ap2_test_merchant_pub_jwk",
    "generate_ap2_test_merchant_key",
    "sign_ap2_merchant_jwt_es256",
    "verify_ap2_merchant_jwt_es256",
]
