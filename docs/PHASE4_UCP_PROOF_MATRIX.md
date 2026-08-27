# RazorMesh Trust — UCP 2026-04-08 Security & Conformance Proof Matrix

**Date.** 2026-08-27.
**Status.** PASS.
**Pinned version.** `2026-04-08` (the latest released tag).
**Source commit / tag.** tag `v2026-04-08` of the
[Universal-Commerce-Protocol/ucp](https://github.com/Universal-Commerce-Protocol/ucp) repository.
**Forward-compatibility note.** The unversioned docs emit dated
`2026-08-25` is treated as forward-compat only; it is NOT a release.
Any UCP conformance claim for the implementation is bounded to
`2026-04-08`.

## 1. Headline

| Metric | Value |
|---|---|
| Total proof cases | 32 |
| Passed | 32 |
| Failed | 0 |
| Pass rate | 1.00 |

## 2. Evidence by section

### A. Version pin (4/4)

| Case | Result | Evidence |
|---|---|---|
| `A.version_pinned` | PASS | `UCP_TARGET_VERSION == "2026-04-08"` |
| `A.profile_path` | PASS | `UCP_PROFILE_PATH == "/.well-known/ucp"` |
| `A.profile_advertises_only_stable` | PASS | All advertised capability versions are `2026-04-08` |
| `A.unpinned_2099_rejected` | PASS | `evaluate_envelope` returns `PROTOCOL_BLOCK` for `2099-99-99` |

### B. Content-Digest (4/4)

RFC 9530 sha-256 Content-Digest over the raw request body.

| Case | Result | Evidence |
|---|---|---|
| `B.digest_computed_from_bytes` | PASS | `content_digest(b) == verify_content_digest(b, d)` |
| `B.one_byte_body_mutation_fails` | PASS | `body[0] ^= 0x01` → digest mismatch |
| `B.reserialization_changes_bytes_fails` | PASS | `b'{"a":1}'` vs `b'{"a": 1}'` (added space) → digest mismatch |
| `B.digest_verified_before_business_mutation` | PASS | Tampered digest header fails verification before the business layer runs |

### C. HTTP Message Signature (8/8)

RFC 9421-style HMAC-SHA256 signature over the covered components.
The RazorMesh implementation is a wire-surface primitive; the
harness is deterministic and only proves the contract.

| Case | Result | Evidence |
|---|---|---|
| `C.valid_signature_accepted` | PASS | valid signature + correct key → `ok` |
| `C.wrong_key_rejected` | PASS | signed with kid1, verified with kid2 → reject |
| `C.changed_method_rejected` | PASS | POST → PUT after signing → reject |
| `C.changed_authority_rejected` | PASS | `razormesh.local` → `evil.local` → reject |
| `C.changed_path_rejected` | PASS | `/ucp/v1/checkouts` → `/ucp/v1/admin` → reject |
| `C.changed_body_rejected` | PASS | body change invalidates content-digest → reject (`content_digest_invalid`) |
| `C.changed_header_rejected` | PASS | covered `ucp-agent` header tampered → reject |
| `C.signature_verified_before_business_mutation` | PASS | wire layer rejects; business layer never invoked |

### D. Profile / identity (4/4)

| Case | Result | Evidence |
|---|---|---|
| `D.profile_keys_resolvable` | PASS | `io.razormesh.razorpay.test_checkout` present in profile |
| `D.signing_key_in_profile` | PASS | `psp=razorpay`, `requires_delegate_payment=false` |
| `D.mismatched_profile_key_rejected` | PASS | `kid_mismatch` |
| `D.stale_key_safe` | PASS | unknown kid → `kid_mismatch` (no silent allow) |

### E. Idempotency (2/2)

| Case | Result | Evidence |
|---|---|---|
| `E.same_key_same_body_one_effect` | PASS | two IRs with same authorization-relevant projection hash the same |
| `E.same_key_changed_body_rejected` | PASS | `equal_under_commitment` returns False on mutated total |

### F. Normalization (3/3)

| Case | Result | Evidence |
|---|---|---|
| `F.rest_normalizes_to_ir` | PASS | JCS-style canonical JSON produced by `compute_commitment` |
| `F.mcp_normalizes_to_ir` | PASS | `compute_commitment(ir) == compute_commitment(ir.model_copy(deep=True))` |
| `F.rest_mcp_equivalent_commitment` | PASS | `test_rest_and_mcp_transport_produce_same_commitment` in `test_ucp_adapter.py` |

### G. Lifecycle (6/6)

| Case | Result | Evidence |
|---|---|---|
| `G.catalog_lifecycle` | PASS | M27 catalog read-only |
| `G.cart_lifecycle` | PASS | `create_cart`, `get_cart`, `update_cart` in `PHASE4_MCP_TOOL_NAMES` |
| `G.checkout_lifecycle` | PASS | `propose_checkout`, `get_checkout`, `complete_authorized_checkout` present |
| `G.completion_lifecycle` | PASS | `complete_authorized_checkout` present |
| `G.order_lifecycle` | PASS | `get_order` present |
| `G.duplicate_order_event_round_trip` | PASS | HMAC-signed order events round-trip; tampered body rejected |

### H. Unknown / critical extensions (1/1)

| Case | Result | Evidence |
|---|---|---|
| `H.unknown_critical_extension_fails_closed` | PASS | `extension_evidence=[{uri: "unknown.razormesh.evil.v1", required: true}]` → `FirewallReason.UNKNOWN_CRITICAL_EXTENSION` recorded |

## 3. Files

- Proof harness: `services/api/src/razormesh_api/protocol/ucp_proof.py`
- Tests: `services/api/tests/phase4/test_ucp_proof.py`
- JSON metrics: `/tmp/ucp_proof.json` (per-run; values documented here)

## 4. Reproducibility

```bash
cd /Users/utkarshkhajuria/Desktop/RazorMesh
uv run --project services/api pytest services/api/tests/phase4/test_ucp_proof.py -v
```

## 5. Conformance scope (non-claim)

This matrix proves the wire-level invariants the gate requires for
the implemented subset. It does NOT claim:
- Full UCP `2026-04-08` conformance.
- Conformance against the unversioned `2026-08-25` docs emit.
- Conformance against any other protocol version.
- Production-grade signature implementation (the harness uses an
  HMAC-based primitive for the test surface; the production
  signer is RFC 9421 over the same covered components).
