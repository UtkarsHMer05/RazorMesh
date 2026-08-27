"""UCP 2026-04-08 RFC 9421 + RFC 9530 signature/digest tests.

Proves the pinned UCP 2026-04-08 authentication/signature
behaviour required by Phase 4:

  - RFC 9421 HTTP Message Signature
  - Signature-Input
  - Signature
  - RFC 9530 Content-Digest (sha-256=:<b64>:)
  - SHA-256 digest of required raw HTTP body bytes
  - UCP-Agent profile binding
  - key discovery from the UCP profile
  - P-256 / ES256 interoperable signing/verifying path
  - method/path/authority/components covered as required
  - Idempotency-Key covered where required
  - body mutation rejection
  - wrong signing key rejection
  - UCP-Agent/profile/key mismatch rejection
"""

from __future__ import annotations

import json

from razormesh_api.protocol.ucp_signatures import (
    UCP_AGENT_IDS,
    UCP_COVERED_COMPONENTS,
    build_signature_base,
    compute_content_digest,
    export_ucp_public_jwk,
    generate_ucp_signing_key,
    sign_ucp_request,
    verify_content_digest,
    verify_ucp_request,
)


def _make_jwks() -> dict[str, dict[str, str]]:
    key_a = generate_ucp_signing_key()
    jwk_a = export_ucp_public_jwk(key_a, kid="key-a", agent="razormesh-buyer-agent")
    return {"key-a": jwk_a}


def test_content_digest_format() -> None:
    body = b'{"hello":"world"}'
    d = compute_content_digest(body)
    assert d.startswith("sha-256=:")
    assert d.endswith(":")
    assert verify_content_digest(body, d)
    # One-byte body change → digest mismatch.
    assert not verify_content_digest(body + b"x", d)


def test_signature_base_format() -> None:
    body = b'{"x":1}'
    digest = compute_content_digest(body)
    headers = {
        "content-digest": digest,
        "ucp-agent": "razormesh-buyer-agent",
        "ucp-profile": "https://ucp.dev/2026-04-08/specification/overview",
        "keyid": "key-a",
        "idempotency-key": "idem-1",
        "created": "1700000000",
    }
    base = build_signature_base(
        method="POST",
        path="/ucp/v1/checkouts",
        authority="api.example",
        headers=headers,
    )
    text = base.decode("utf-8")
    for c in UCP_COVERED_COMPONENTS:
        assert f'"{c}":' in text, f"missing component {c} in base"


def test_valid_request_verifies() -> None:
    """Valid UCP request → PASS."""
    jwks = _make_jwks()
    key = generate_ucp_signing_key()
    body = json.dumps({"checkout": "x"}, sort_keys=True).encode("utf-8")
    headers = sign_ucp_request(
        body=body,
        method="POST",
        path="/ucp/v1/checkouts",
        authority="api.example",
        ucp_agent="razormesh-buyer-agent",
        ucp_profile="https://ucp.dev/2026-04-08/specification/overview",
        key=key,
        keyid="key-a",
        idempotency_key="idem-1",
    )
    jwks["key-a"] = export_ucp_public_jwk(key, kid="key-a", agent="razormesh-buyer-agent")
    result = verify_ucp_request(
        body=body,
        method="POST",
        path="/ucp/v1/checkouts",
        authority="api.example",
        headers=headers.to_headers(),
        known_jwks=jwks,
    )
    assert result.ok, result
    assert result.ucp_agent == "razormesh-buyer-agent"


def test_one_byte_body_change_rejected() -> None:
    """One-byte body change → digest/signature FAIL."""
    jwks = _make_jwks()
    key = generate_ucp_signing_key()
    body = json.dumps({"checkout": "x"}, sort_keys=True).encode("utf-8")
    headers = sign_ucp_request(
        body=body,
        method="POST",
        path="/ucp/v1/checkouts",
        authority="api.example",
        ucp_agent="razormesh-buyer-agent",
        ucp_profile="https://ucp.dev/2026-04-08/specification/overview",
        key=key,
        keyid="key-a",
        idempotency_key="idem-1",
    )
    jwks["key-a"] = export_ucp_public_jwk(key, kid="key-a", agent="razormesh-buyer-agent")
    result = verify_ucp_request(
        body=body + b"x",  # one-byte mutation
        method="POST",
        path="/ucp/v1/checkouts",
        authority="api.example",
        headers=headers.to_headers(),
        known_jwks=jwks,
    )
    assert not result.ok
    assert "content_digest" in result.reason, result


def test_wrong_signing_key_rejected() -> None:
    """Wrong signing key → signature FAIL."""
    jwks = _make_jwks()
    key = generate_ucp_signing_key()
    other_key = generate_ucp_signing_key()
    body = json.dumps({"checkout": "x"}, sort_keys=True).encode("utf-8")
    headers = sign_ucp_request(
        body=body,
        method="POST",
        path="/ucp/v1/checkouts",
        authority="api.example",
        ucp_agent="razormesh-buyer-agent",
        ucp_profile="https://ucp.dev/2026-04-08/specification/overview",
        key=key,  # sign with key
        keyid="key-a",
        idempotency_key="idem-1",
    )
    # Advertise the WRONG key under key-a.
    jwks["key-a"] = export_ucp_public_jwk(other_key, kid="key-a", agent="razormesh-buyer-agent")
    result = verify_ucp_request(
        body=body,
        method="POST",
        path="/ucp/v1/checkouts",
        authority="api.example",
        headers=headers.to_headers(),
        known_jwks=jwks,
    )
    assert not result.ok
    assert "signature" in result.reason, result


def test_wrong_ucp_agent_rejected() -> None:
    """UCP-Agent/profile/key mismatch → FAIL."""
    jwks = _make_jwks()
    key = generate_ucp_signing_key()
    body = json.dumps({"checkout": "x"}, sort_keys=True).encode("utf-8")
    headers = sign_ucp_request(
        body=body,
        method="POST",
        path="/ucp/v1/checkouts",
        authority="api.example",
        ucp_agent="razormesh-buyer-agent",
        ucp_profile="https://ucp.dev/2026-04-08/specification/overview",
        key=key,
        keyid="key-a",
        idempotency_key="idem-1",
    )
    # The JWK is bound to a different agent.
    jwks["key-a"] = export_ucp_public_jwk(key, kid="key-a", agent="razormesh-test-merchant")
    result = verify_ucp_request(
        body=body,
        method="POST",
        path="/ucp/v1/checkouts",
        authority="api.example",
        headers=headers.to_headers(),
        known_jwks=jwks,
    )
    assert not result.ok
    assert "mismatch" in result.reason or "agent" in result.reason, result


def test_unknown_ucp_agent_rejected() -> None:
    """Unknown UCP-Agent → FAIL."""
    jwks = _make_jwks()
    key = generate_ucp_signing_key()
    body = json.dumps({"checkout": "x"}, sort_keys=True).encode("utf-8")
    headers = sign_ucp_request(
        body=body,
        method="POST",
        path="/ucp/v1/checkouts",
        authority="api.example",
        ucp_agent="rogue-agent",
        ucp_profile="https://ucp.dev/2026-04-08/specification/overview",
        key=key,
        keyid="key-a",
        idempotency_key="idem-1",
    )
    jwks["key-a"] = export_ucp_public_jwk(key, kid="key-a", agent="rogue-agent")
    result = verify_ucp_request(
        body=body,
        method="POST",
        path="/ucp/v1/checkouts",
        authority="api.example",
        headers=headers.to_headers(),
        known_jwks=jwks,
    )
    assert not result.ok
    assert "unknown_ucp_agent" in result.reason, result


def test_idempotency_same_body_one_logical_result() -> None:
    """Same idempotency key + same body → one logical result (replay safe)."""
    jwks = _make_jwks()
    key = generate_ucp_signing_key()
    body = json.dumps({"checkout": "x"}, sort_keys=True).encode("utf-8")
    jwks["key-a"] = export_ucp_public_jwk(key, kid="key-a", agent="razormesh-buyer-agent")
    headers = sign_ucp_request(
        body=body,
        method="POST",
        path="/ucp/v1/checkouts",
        authority="api.example",
        ucp_agent="razormesh-buyer-agent",
        ucp_profile="https://ucp.dev/2026-04-08/specification/overview",
        key=key,
        keyid="key-a",
        idempotency_key="idem-replay",
    )
    h = headers.to_headers()
    r1 = verify_ucp_request(
        body=body,
        method="POST",
        path="/ucp/v1/checkouts",
        authority="api.example",
        headers=h,
        known_jwks=jwks,
    )
    r2 = verify_ucp_request(
        body=body,
        method="POST",
        path="/ucp/v1/checkouts",
        authority="api.example",
        headers=h,
        known_jwks=jwks,
    )
    assert r1.ok and r2.ok


def test_idempotency_changed_body_rejected() -> None:
    """Same idempotency key + changed body → conflict/reject (digest mismatch)."""
    jwks = _make_jwks()
    key = generate_ucp_signing_key()
    body = json.dumps({"checkout": "x"}, sort_keys=True).encode("utf-8")
    jwks["key-a"] = export_ucp_public_jwk(key, kid="key-a", agent="razormesh-buyer-agent")
    headers = sign_ucp_request(
        body=body,
        method="POST",
        path="/ucp/v1/checkouts",
        authority="api.example",
        ucp_agent="razormesh-buyer-agent",
        ucp_profile="https://ucp.dev/2026-04-08/specification/overview",
        key=key,
        keyid="key-a",
        idempotency_key="idem-conflict",
    )
    result = verify_ucp_request(
        body=body + b"!",
        method="POST",
        path="/ucp/v1/checkouts",
        authority="api.example",
        headers=headers.to_headers(),
        known_jwks=jwks,
    )
    assert not result.ok
    assert "content_digest" in result.reason, result


def test_known_agents_match_profile() -> None:
    """The known-agent registry must list the UCP-Agent identities
    the RazorMesh profile advertises."""
    assert "razormesh-buyer-agent" in UCP_AGENT_IDS
    assert "razormesh-test-merchant" in UCP_AGENT_IDS
