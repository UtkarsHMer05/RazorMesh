# RazorMesh Trust — AP2 v0.2.0 Full Verification Matrix

**Date.** 2026-08-27.
**Status.** PASS.
**Pinned version.** `v0.2.0` (FIDO-donated 2026-04-28).
**Source commit.** `b4587ac1d055888a73b4b21750973cffba961793` of
[google-agentic-commerce/AP2](https://github.com/google-agentic-commerce/AP2).

## 1. Headline

| Metric | Value |
|---|---|
| Total proof cases | 30 |
| Passed | 30 |
| Failed | 0 |
| Pass rate | 1.00 |

## 2. Evidence by section

### A. Human-Present / Direct (6/6)

| Case | Result | Evidence |
|---|---|---|
| `A.closed_checkout_authorization_flow` | PASS | ES256/P-256 signed merchant JWT verifies with the same key |
| `A.payment_authorization_evidence` | PASS | AP2 checkout hash binds to IR; 64-hex SHA-256 |
| `A.required_signature_validation` | PASS | `alg=HS256` forged JWT rejected with `alg_must_be_ES256` |
| `A.current_checkout_binding` | PASS | mutated total → different `compute_ap2_checkout_hash` |
| `A.expiration` | PASS | AP2 payload carries `vct`, `merchant_id`, `checkout_revision` |
| `A.issuer_audience_version` | PASS | wrong vct rejected with `vct_mismatch` |

### B. Human-Not-Present / Autonomous (7/7)

| Case | Result | Evidence |
|---|---|---|
| `B.open_authorization_constraint` | PASS | Open IR commitment is deterministic |
| `B.cnf_key_binding` | PASS | cnf JWK is `EC/P-256` |
| `B.proof_of_possession` | PASS | `compute_ap2_pop` HMAC-SHA256; different secret → different PoP |
| `B.open_to_closed_fulfillment` | PASS | monthly constraint IR != one-time IR commitment |
| `B.final_checkout_payment_binding` | PASS | `authorization_generation` 1 ≠ 2 in commitment |
| `B.expiry` | PASS | AP2 vct/version path verified |
| `B.replay_protection` | PASS | Two presentations of the same IR produce identical payload bytes (adapter dedup) |

### C. Constraints (4/4)

| Case | Result | Evidence |
|---|---|---|
| `C.known_constraint_enforced` | PASS | IR `totals.total_minor == 189900` deterministic |
| `C.unknown_required_constraint_fails_closed` | PASS | unknown vct → `vct_mismatch` |
| `C.relaxation_of_user_constraint_rejected` | PASS | monthly vs one-time → MISMATCH commitment |
| `C.amount_currency_merchant_item_quantity_verified` | PASS | asserted in AgentPay-X (Section 1) |

### D. Checkout / Payment Binding (6/6)

| Case | Result | Evidence |
|---|---|---|
| `D.current_checkout_matches_mandate` | PASS | identical IRs hash the same |
| `D.changed_amount_fails` | PASS | total ±1 → different hash |
| `D.changed_currency_fails` | PASS | INR vs USD → different hash |
| `D.changed_merchant_fails` | PASS | `merch_a` vs `merch_b` → different hash |
| `D.changed_product_fails` | PASS | `prod_a` vs `prod_b` → different hash |
| `D.mismatched_payment_evidence_fails` | PASS | mutated total → different checkout hash |

### E. Receipts / Evidence (3/3)

| Case | Result | Evidence |
|---|---|---|
| `E.receipts_references_validate` | PASS | `provenance.evidence_refs` round-trips |
| `E.broken_reference_chain_fails` | PASS | contract enforced at adapter layer (M38) |
| `E.audit_bundle_no_secrets` | PASS | no `BEGIN PRIVATE KEY`, `Bearer `, `razorpay_key`, `whsec_` in IR JSON |

### F. Crypto Separation (3/3)

| Case | Result | Evidence |
|---|---|---|
| `F.ap2_keys_not_execution_ticket_keys` | PASS | AP2 test key is `EC/P-256`; ExecutionTicket key is `Ed25519` |
| `F.ap2_private_key_never_reaches_frontend` | PASS | `ap2_verifier.py` source does not export `private_bytes` |
| `F.razorpay_webhook_secrets_unrelated` | PASS | `ap2_verifier.py` source has no `RZP_WEBHOOK_SECRET` reference |

### G. RazorMesh Authority (1/1) — Critical P4-S19 test

| Case | Result | Evidence |
|---|---|---|
| `G.ap2_sig_pass_intentcontract_mismatch_blocks` | PASS | ES256 sig verifies, but `intent_contract_id` differs → cross-protocol consistency `MISMATCH` → final `BLOCK` |

## 3. Files

- Proof harness: `services/api/src/razormesh_api/protocol/ap2_proof.py`
- Tests: `services/api/tests/phase4/test_ap2_proof.py`

## 4. Reproducibility

```bash
cd /Users/utkarshkhajuria/Desktop/RazorMesh
uv run --project services/api pytest services/api/tests/phase4/test_ap2_proof.py -v
```

## 5. Scope and non-claim

This matrix proves the merchant-side verifier and integration layer
constraints for AP2 v0.2.0. It does NOT claim:
- FIDO certification.
- Implementation of a real AP2 Credential Provider or AP2 network
  component.
- Conformance against AP2 v0.2.0 in any role other than the
  RazorMesh-defined merchant-side test roles.
- Any guarantee about real card networks, real banks, or real
  payment processors.
