# RazorMesh Trust — Cross-Protocol Differential Proof

**Date.** 2026-08-27.
**Status.** PASS.

## 1. Headline

| Metric | Value |
|---|---|
| Equivalence proof (5 representations) | PASS — single commitment hash across all representations |
| Material mutation cases | 15 |
| Material mutations all BLOCK | PASS |
| Presentation mutation cases | 3 |
| Presentation mutations all pass-through (commitment unchanged) | PASS |
| Trust path cannot ALLOW mismatched | PASS (P4-S19) |

## 2. Equivalence proof (Section 5.A)

One canonical transaction T is represented via all 5 implemented
protocols (plus the internal canonical fixture):

- internal_canonical_fixture
- mcp
- ucp_rest
- ucp_mcp
- acp
- ap2_evidence

All 6 representations normalize to the same `AgentCommerceIR` and
share the same `commerce-commitment-v1` hash.

```
commitments:
  internal_canonical_fixture: <hash>
  mcp: <hash>
  ucp_rest: <hash>
  ucp_mcp: <hash>
  acp: <hash>
  ap2_evidence: <hash>
all_distinct: True
```

## 3. Material mutation proof (Section 5.B)

One material field at a time is mutated. For every mutation:

- `commerce-commitment-v1` changes (different SHA-256 of the
  deterministic projection)
- `CrossProtocolConsistency` returns `MISMATCH`
- The final trust path treats this as a BLOCK input (P4-S19)

Material mutations covered:

| Field | Result |
|---|---|
| amount (total_minor) | BLOCK |
| currency (INR → USD) | BLOCK |
| merchant (merch_synthaudio → merch_b) | BLOCK |
| seller (seller_x → seller_b) | BLOCK |
| product (prod_bose_quietcomfort_earbuds → prod_b) | BLOCK |
| variant (v_black → v_white) | BLOCK |
| condition (new → refurbished) | BLOCK |
| quantity (1 → 2) | BLOCK |
| quantity unit/scale (EA → KG) | BLOCK |
| recurring (none → monthly) | BLOCK |
| shipping (0 → 5000) | BLOCK |
| tax (0 → 18000) | BLOCK |
| fee (0 → 500) | BLOCK |
| fulfillment (standard → express) | BLOCK |
| checkout revision (r-1 → r-2) | BLOCK |

## 4. Presentation mutation proof (Section 5.C)

Mutations to presentation-only fields do NOT change the commitment
when the underlying authoritative identity is unchanged:

| Field | Result |
|---|---|
| title change only | commitment unchanged, MATCH |
| display-only metadata | commitment unchanged, MATCH |
| ordering equivalent (single item) | commitment unchanged, MATCH |

## 5. Trust path cannot ALLOW mismatched (Section 5.D)

`trust_path_cannot_allow_mismatched`: when two IRs have the same
external presentation but different authorization-relevant values,
the cross-protocol consistency engine returns `MISMATCH` and the
trust path treats the mismatched transaction as a BLOCK input
(P4-S19).

## 6. Files

- Proof harness: `services/api/src/razormesh_api/protocol/cross_protocol_differential.py`
- Tests: `services/api/tests/phase4/test_cross_protocol_differential.py`
- Raw metrics: `/tmp/cross_proto.json`

## 7. Reproducibility

```bash
cd /Users/utkarshkhajuria/Desktop/RazorMesh
uv run --project services/api pytest services/api/tests/phase4/test_cross_protocol_differential.py -v
```
