"""UCP 2026-04-08 HTTP Message Signature (RFC 9421) + Content-Digest (RFC 9530).

Implements the pinned UCP 2026-04-08 authentication/signature
behaviour for the RazorMesh acceptance ingress:

  - RFC 9421 HTTP Message Signature
  - Signature-Input (the signature parameters)
  - Signature (the base64url-encoded ES256 signature)
  - RFC 9530 Content-Digest (sha-256=... of the raw HTTP body)
  - SHA-256 digest of required raw HTTP body bytes
  - UCP-Agent profile binding
  - key discovery from the UCP profile
  - P-256 / ES256 interoperable signing/verifying path
  - method/path/authority/components covered as required by the
    pinned spec/profile
  - Idempotency-Key covered where required
  - body mutation rejection
  - wrong signing key rejection
  - UCP-Agent/profile/key mismatch rejection

This module is the **only** UCP signature/digest path. The legacy
``build_signed_order_event`` HMAC remains in :mod:`ucp_adapter` as
``RAZORMESH_INTERNAL_ENVELOPE_INTEGRITY`` and is **not** a UCP
signature verification.
"""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

UCP_SIGNATURE_SCHEME = "ucp-http-message-signatures-es256-2026"
UCP_DIGEST_SCHEME = "ucp-content-digest-sha256-2026"
UCP_AGENT_HEADER = "UCP-Agent"
UCP_PROFILE_HEADER = "UCP-Profile"
UCP_SIGNATURE_INPUT_HEADER = "Signature-Input"
UCP_SIGNATURE_HEADER = "Signature"
UCP_CONTENT_DIGEST_HEADER = "Content-Digest"
UCP_IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"

# The set of HTTP components the UCP 2026-04-08 profile requires
# to be covered by the signature. The pinned profile dictates these
# for RazorMesh; changing them is a protocol change.
UCP_COVERED_COMPONENTS: tuple[str, ...] = (
    "@method",
    "@path",
    "@authority",
    "content-digest",
    "ucp-agent",
    "ucp-profile",
    "idempotency-key",
)

# The set of key IDs the RazorMesh UCP profile advertises. The
# key discovery from the profile is the binding between the
# UCP-Agent identity and the verification key.
UCP_AGENT_IDS: dict[str, dict[str, str]] = {
    "razormesh-buyer-agent": {
        "kty": "EC",
        "crv": "P-256",
        "use": "sig",
        "alg": "ES256",
    },
    "razormesh-test-merchant": {
        "kty": "EC",
        "crv": "P-256",
        "use": "sig",
        "alg": "ES256",
    },
}


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def compute_content_digest(body: bytes) -> str:
    """RFC 9530 Content-Digest: ``sha-256=:<base64-digest>:``."""
    digest = hashlib.sha256(body).digest()
    return f"sha-256=:{base64.b64encode(digest).decode('ascii')}:"


def verify_content_digest(body: bytes, header_value: str) -> bool:
    """Return True iff the ``Content-Digest`` header covers ``body``."""
    expected = compute_content_digest(body)
    return header_value.strip() == expected


# ---------------------------------------------------------------------
# Key generation / serialization
# ---------------------------------------------------------------------


def generate_ucp_signing_key() -> ec.EllipticCurvePrivateKey:
    """Return a fresh P-256 private key for the UCP signing path."""
    return ec.generate_private_key(ec.SECP256R1())


def export_ucp_public_jwk(
    key: ec.EllipticCurvePrivateKey, *, kid: str, agent: str
) -> dict[str, str]:
    """Export the public half as a JWK with the UCP-Agent binding."""
    pub = key.public_key().public_numbers()
    n_bytes = (pub.curve.key_size + 7) // 8
    x = pub.x.to_bytes(n_bytes, "big")
    y = pub.y.to_bytes(n_bytes, "big")
    return {
        "kty": "EC",
        "crv": "P-256",
        "use": "sig",
        "alg": "ES256",
        "kid": kid,
        "ucp-agent": agent,
        "x": _b64url_encode(x),
        "y": _b64url_encode(y),
    }


def load_ucp_public_jwk(jwk: Mapping[str, str]) -> ec.EllipticCurvePublicKey:
    """Reconstruct a P-256 public key from a JWK."""
    if jwk.get("kty") != "EC" or jwk.get("crv") != "P-256":
        raise ValueError("unsupported JWK for UCP signing")
    x = int.from_bytes(_b64url_decode(jwk["x"]), "big")
    y = int.from_bytes(_b64url_decode(jwk["y"]), "big")
    pub_numbers = ec.EllipticCurvePublicNumbers(x=x, y=y, curve=ec.SECP256R1())
    return pub_numbers.public_key()


# ---------------------------------------------------------------------
# RFC 9421 signature base construction
# ---------------------------------------------------------------------


def _canonical_component_value(
    component: str, method: str, path: str, authority: str, headers: Mapping[str, str]
) -> bytes:
    """Return the canonical component value per RFC 9421 §2.2."""
    if component == "@method":
        return method.lower().encode("ascii")
    if component == "@path":
        return path.encode("ascii")
    if component == "@authority":
        return authority.encode("ascii")
    # Regular header: lowercased name → value, with internal whitespace
    # preserved (RFC 9421 §2.2).
    return headers[component.lower()].encode("utf-8")


def build_signature_base(
    *,
    method: str,
    path: str,
    authority: str,
    headers: Mapping[str, str],
    components: Iterable[str] = UCP_COVERED_COMPONENTS,
) -> bytes:
    """Build the RFC 9421 signature base.

    Format::

        "<component>": <value>
        "<component>": <value>
        ...
        "@signature-params": <params>

    Each line ends with a single newline. The final line is the
    signature params (covered components + keyid + alg + created).
    """
    lines: list[str] = []
    comps = list(components)
    for c in comps:
        lines.append(
            f'"{c}": '
            f"{_canonical_component_value(c, method, path, authority, headers).decode('utf-8', errors='replace')}"
        )
    # We include keyid + alg + created so a verifier can reproduce.
    kid = headers.get("keyid", "razormesh-buyer-agent-key-1")
    created = int(headers.get("created", "0"))
    params_str = f'({";".join(comps)});keyid="{kid}";alg="ecdsa-p256-sha256";created={created}'
    lines.append(f'"@signature-params": {params_str}')
    return ("\n".join(lines) + "\n").encode("utf-8")


# ---------------------------------------------------------------------
# Sign + verify
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class UcpSignatureHeaders:
    """The headers a client must send to authenticate a UCP request."""

    ucp_agent: str
    ucp_profile: str
    keyid: str
    content_digest: str
    signature_input: str
    signature: str
    idempotency_key: str | None = None

    def to_headers(self) -> dict[str, str]:
        out = {
            UCP_AGENT_HEADER: self.ucp_agent,
            UCP_PROFILE_HEADER: self.ucp_profile,
            "keyid": self.keyid,
            UCP_CONTENT_DIGEST_HEADER: self.content_digest,
            UCP_SIGNATURE_INPUT_HEADER: self.signature_input,
            UCP_SIGNATURE_HEADER: self.signature,
        }
        if self.idempotency_key:
            out[UCP_IDEMPOTENCY_KEY_HEADER] = self.idempotency_key
        return out


def sign_ucp_request(
    *,
    body: bytes,
    method: str,
    path: str,
    authority: str,
    ucp_agent: str,
    ucp_profile: str,
    key: ec.EllipticCurvePrivateKey,
    keyid: str,
    idempotency_key: str | None = None,
    components: tuple[str, ...] = UCP_COVERED_COMPONENTS,
) -> UcpSignatureHeaders:
    """Produce the UCP signature headers for an outbound request.

    This is the interop-side helper: it computes the RFC 9530
    Content-Digest, constructs the RFC 9421 signature base, and
    signs it with the supplied P-256 key (ES256, raw IEEE-P1363
    R||S form per RFC 9421 §3.3.2).
    """
    import time as _time

    if ucp_agent not in UCP_AGENT_IDS:
        # The signer is permissive: an unknown UCP-Agent can still be
        # signed (the verifier rejects it). This lets tests exercise
        # the "unknown UCP-Agent" rejection path without the signer
        # itself raising.
        pass
    digest = compute_content_digest(body)
    headers: dict[str, str] = {
        "content-digest": digest,
        "ucp-agent": ucp_agent,
        "ucp-profile": ucp_profile,
        "keyid": keyid,
        "created": str(int(_time.time())),
    }
    if idempotency_key:
        headers["idempotency-key"] = idempotency_key
    base = build_signature_base(
        method=method,
        path=path,
        authority=authority,
        headers=headers,
        components=components,
    )
    # Build Signature-Input listing the components in the same order.
    sig_input = (
        f"sig1=({' '.join(components)})"
        f';keyid="{keyid}";alg="ecdsa-p256-sha256"'
        f";created={headers['created']}"
    )
    # Sign and convert DER → IEEE-P1363 (R||S, 32 bytes each).
    der_sig = key.sign(base, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der_sig)
    raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    sig_b64 = _b64url_encode(raw)
    sig_header = f"sig1=:{sig_b64}:"
    return UcpSignatureHeaders(
        ucp_agent=ucp_agent,
        ucp_profile=ucp_profile,
        keyid=keyid,
        content_digest=digest,
        signature_input=sig_input,
        signature=sig_header,
        idempotency_key=idempotency_key,
    )


@dataclass(frozen=True)
class UcpVerificationResult:
    """Result of verifying a UCP request signature."""

    ok: bool
    reason: str
    ucp_agent: str | None = None
    ucp_profile: str | None = None
    keyid: str | None = None


def verify_ucp_request(
    *,
    body: bytes,
    method: str,
    path: str,
    authority: str,
    headers: Mapping[str, str],
    known_jwks: Mapping[str, Mapping[str, str]],
) -> UcpVerificationResult:
    """Verify a UCP request's RFC 9421 signature + RFC 9530 Content-Digest.

    The verifier rejects:
      - missing or wrong Content-Digest
      - missing UCP-Agent / UCP-Profile / Signature-Input / Signature
      - unknown UCP-Agent (not in the UCP profile)
      - keyid not in the known_jwks set
      - signature that does not verify against the bound JWK
      - signature missing required components

    The known_jwks mapping is keyed by ``kid``; the verifier binds
    the keyid to a JWK and the JWK's ``ucp-agent`` must match the
    request's UCP-Agent header.
    """
    # Normalise header names to lowercase for case-insensitive lookup.
    headers = {k.lower(): v for k, v in headers.items()}
    agent = headers.get(UCP_AGENT_HEADER.lower())
    profile = headers.get(UCP_PROFILE_HEADER.lower())
    keyid = headers.get("keyid")
    digest = headers.get(UCP_CONTENT_DIGEST_HEADER.lower())
    sig_input = headers.get(UCP_SIGNATURE_INPUT_HEADER.lower())
    sig = headers.get(UCP_SIGNATURE_HEADER.lower())
    if not (agent and profile and keyid and digest and sig_input and sig):
        return UcpVerificationResult(ok=False, reason="missing_headers")
    if agent not in UCP_AGENT_IDS:
        return UcpVerificationResult(ok=False, reason="unknown_ucp_agent", ucp_agent=agent)
    if not verify_content_digest(body, digest):
        return UcpVerificationResult(ok=False, reason="content_digest_mismatch", ucp_agent=agent)
    jwk = known_jwks.get(keyid)
    if jwk is None:
        return UcpVerificationResult(ok=False, reason="unknown_keyid", ucp_agent=agent, keyid=keyid)
    # The JWK's ucp-agent must match the request's UCP-Agent header.
    if jwk.get("ucp-agent") != agent:
        return UcpVerificationResult(
            ok=False,
            reason="ucp_agent_key_mismatch",
            ucp_agent=agent,
            keyid=keyid,
        )
    # Required components must all appear in Signature-Input.
    missing = [c for c in UCP_COVERED_COMPONENTS if c not in sig_input]
    if missing:
        return UcpVerificationResult(
            ok=False,
            reason=f"missing_components:{','.join(missing)}",
            ucp_agent=agent,
            keyid=keyid,
        )
    # Reconstruct the signature base.
    import re as _re

    m = _re.search(r"created=(\d+)", sig_input)
    if m is None:
        return UcpVerificationResult(
            ok=False, reason="missing_created", ucp_agent=agent, keyid=keyid
        )
    headers_for_base = {
        "content-digest": digest,
        "ucp-agent": agent,
        "ucp-profile": profile,
        "keyid": keyid,
        "idempotency-key": headers.get(UCP_IDEMPOTENCY_KEY_HEADER.lower(), ""),
        "created": m.group(1),
    }
    base = build_signature_base(
        method=method,
        path=path,
        authority=authority,
        headers=headers_for_base,
    )
    # Extract the signature value: sig1=:...:
    m2 = _re.search(r"sig1=:([A-Za-z0-9_-]+):", sig)
    if m2 is None:
        return UcpVerificationResult(
            ok=False, reason="malformed_signature", ucp_agent=agent, keyid=keyid
        )
    raw_sig = _b64url_decode(m2.group(1))
    if len(raw_sig) != 64:
        return UcpVerificationResult(
            ok=False, reason="bad_signature_length", ucp_agent=agent, keyid=keyid
        )
    r = int.from_bytes(raw_sig[:32], "big")
    s = int.from_bytes(raw_sig[32:], "big")
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

    der_sig = encode_dss_signature(r, s)
    try:
        pub = load_ucp_public_jwk(jwk)
        pub.verify(der_sig, base, ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, ValueError, TypeError) as exc:
        return UcpVerificationResult(
            ok=False,
            reason=f"signature_invalid:{type(exc).__name__}",
            ucp_agent=agent,
            keyid=keyid,
        )
    return UcpVerificationResult(
        ok=True, reason="verified", ucp_agent=agent, ucp_profile=profile, keyid=keyid
    )


__all__ = [
    "UCP_AGENT_HEADER",
    "UCP_AGENT_IDS",
    "UCP_CONTENT_DIGEST_HEADER",
    "UCP_COVERED_COMPONENTS",
    "UCP_DIGEST_SCHEME",
    "UCP_IDEMPOTENCY_KEY_HEADER",
    "UCP_PROFILE_HEADER",
    "UCP_SIGNATURE_HEADER",
    "UCP_SIGNATURE_INPUT_HEADER",
    "UCP_SIGNATURE_SCHEME",
    "UcpSignatureHeaders",
    "UcpVerificationResult",
    "build_signature_base",
    "compute_content_digest",
    "export_ucp_public_jwk",
    "generate_ucp_signing_key",
    "load_ucp_public_jwk",
    "sign_ucp_request",
    "verify_content_digest",
    "verify_ucp_request",
]
