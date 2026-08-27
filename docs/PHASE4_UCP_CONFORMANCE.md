# RazorMesh Trust — UCP 2026-04-08 Conformance

> **Status: PASS — pinned UCP 2026-04-08 RFC 9421 + RFC 9530 + ES256/P-256**

Phase 4 implements the pinned UCP 2026-04-08 authentication / signature
behaviour for the live acceptance ingress:

  - **RFC 9421 HTTP Message Signature**
  - `Signature-Input` (the signature parameters)
  - `Signature` (the base64url-encoded ES256 signature)
  - **RFC 9530 Content-Digest** (`sha-256=:<b64>:`)
  - SHA-256 digest of the required raw HTTP body bytes
  - UCP-Agent profile binding
  - Key discovery from the UCP profile
  - P-256 / ES256 interoperable signing / verifying path
  - `method` / `path` / `authority` components covered
  - `Idempotency-Key` covered
  - Body mutation rejection
  - Wrong signing key rejection
  - UCP-Agent / profile / key mismatch rejection

Implementation: `services/api/src/razormesh_api/protocol/ucp_signatures.py`.

## Proof matrix

| # | Scenario | Expected | Actual | Test |
| - | -------- | -------- | ------ | ---- |
| 1 | Valid UCP request | PASS | PASS | `test_valid_request_verifies` |
| 2 | One-byte body change | digest/signature FAIL | content_digest_mismatch | `test_one_byte_body_change_rejected` |
| 3 | Wrong signing key | signature FAIL | signature_invalid | `test_wrong_signing_key_rejected` |
| 4 | UCP-Agent / profile / key mismatch | FAIL | ucp_agent_key_mismatch | `test_wrong_ucp_agent_rejected` |
| 5 | Unknown UCP-Agent | FAIL | unknown_ucp_agent | `test_unknown_ucp_agent_rejected` |
| 6 | Same idempotency + same body | one logical result | replay-safe | `test_idempotency_same_body_one_logical_result` |
| 7 | Same idempotency + changed body | conflict / reject | content_digest_mismatch | `test_idempotency_changed_body_rejected` |
| 8 | Content-Digest format | `sha-256=:<b64>:` | matches | `test_content_digest_format` |
| 9 | Signature base covers all required components | yes | yes | `test_signature_base_format` |
| 10 | Known agents match profile | yes | yes | `test_known_agents_match_profile` |

## RAZORMESH_INTERNAL_ENVELOPE_INTEGRITY (separate)

The legacy `build_signed_order_event` / `verify_signed_order_event`
helpers in `services/api/src/razormesh_api/protocol/ucp_adapter.py`
compute a HMAC-SHA256 over the canonical JSON of an event body. This
HMAC is **RAZORMESH_INTERNAL_ENVELOPE_INTEGRITY** and is **not** a
UCP signature verification. It is retained for local event-fixture
tests and is never used to authenticate UCP requests.

The Phase-4 acceptance ingress authenticates UCP requests exclusively
via the RFC 9421 / RFC 9530 path above.

## Required components covered by the signature

`@method`, `@path`, `@authority`, `content-digest`, `ucp-agent`,
`ucp-profile`, `idempotency-key`. Any request missing one of these
components in its `Signature-Input` is rejected.

## Live integration

`Phase4AcceptanceOrchestrator.prepare` produces a real UCP
RFC 9421 + RFC 9530 signed request for the live acceptance run and
verifies it through `verify_ucp_request`. The verified status is
recorded on `AcceptanceProtocolEvidence.ucp_signature_digest_verified`
and surfaced in the `/phase4/acceptance/runs` response.
