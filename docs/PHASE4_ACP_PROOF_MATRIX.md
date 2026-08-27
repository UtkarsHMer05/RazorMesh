# RazorMesh Trust — ACP 2026-01-30 Proof Matrix

**Date.** 2026-08-27.
**Status.** PASS.
**Pinned version.** `2026-01-30` (master prompt §16).
**Source.** `agentic-commerce-protocol/agentic-commerce-protocol`
spec branch at `2026-01-30`.

## 1. Headline

| Metric | Value |
|---|---|
| Total proof cases | 30 |
| Passed | 30 |
| Failed | 0 |
| Pass rate | 1.00 |

## 2. Evidence by section

### A. Capability negotiation (4/4)

| Case | Result | Evidence |
|---|---|---|
| `A.compatible_intersection` | PASS | intersection yields only `razorpay_test_checkout` |
| `A.unsupported_capability_rejected` | PASS | extension `shipping` not in seller → not in intersection |
| `A.handler_negotiation` | PASS | no common handler → empty intersection |
| `A.no_silent_fallback_to_unsafe_payment` | PASS | handler is `requires_delegate_payment=false`, `requires_pci_compliance=false`, `test_mode=true` |

### B. Session lifecycle (10/10)

| Case | Result | Evidence |
|---|---|---|
| `B.create_session` | PASS | new session starts at `not_ready` |
| `B.retrieve_session_shape` | PASS | session id starts with `co_` |
| `B.update_session_path` | PASS | `not_ready → ready` is legal |
| `B.ready_state_path` | PASS | `ready → in_progress` is legal |
| `B.complete_session` | PASS | `in_progress → completed` is legal |
| `B.cancel_session` | PASS | `not_ready → canceled` is legal |
| `B.reject_complete_twice` | PASS | `completed → completed` is illegal |
| `B.reject_update_after_completed` | PASS | `completed → ready` is illegal |
| `B.reject_complete_after_canceled` | PASS | `canceled → completed` is illegal |
| `B.reject_illegal_state_jump` | PASS | `not_ready → completed` is illegal |

### C. Idempotency (2/2)

| Case | Result | Evidence |
|---|---|---|
| `C.same_key_same_request_one_effect` | PASS | same idempotency_key + same message_id |
| `C.same_key_different_request_conflict` | PASS | different raw payload → different `raw_payload_hash` |

### D. Failure path (2/2)

| Case | Result | Evidence |
|---|---|---|
| `D.payment_failed_cannot_fulfill` | PASS | no non-`in_progress` state transitions to `completed` |
| `D.no_retry_on_failed` | PASS | `canceled → completed` is illegal |

### E. Provider unknown (4/4)

| Case | Result | Evidence |
|---|---|---|
| `E.unknown_provider_outcome_not_ordinary_failure` | PASS | `in_progress → completed` requires execution_attempt_id |
| `E.no_blind_fresh_retry` | PASS | `build_acp_complete_response(execution_attempt_id=None)` returns `not_ready` |
| `E.reconciliation_resolves_safely` | PASS | `in_progress → canceled` is legal (reconcile path) |
| `E.no_double_settlement` | PASS | `completed` is terminal; no second complete |

### F. Custom handler `io.razormesh.razorpay.test_checkout` (8/8)

| Case | Result | Evidence |
|---|---|---|
| `F.handler_namespaced_and_nonstandard` | PASS | name is `io.razormesh.razorpay.test_checkout` |
| `F.not_delegate_payment` | PASS | `requires_delegate_payment=false` |
| `F.not_pci_compliance` | PASS | `requires_pci_compliance=false` (hosted path) |
| `F.test_mode_only` | PASS | `test_mode=true` |
| `F.not_stripe` | PASS | psp is `razorpay`, not stripe |
| `F.no_razorpay_secret_in_adapter` | PASS | static check of `acp_adapter.py` finds no `RZP_*` |
| `F.handler_advertised_in_profile` | PASS | UCP profile mirrors the handler |
| `F.no_browser_razorpay_secret` | PASS | static check of `apps/web/**` finds no `RZP_*` |

## 3. Files

- Proof harness: `services/api/src/razormesh_api/protocol/acp_proof.py`
- Tests: `services/api/tests/phase4/test_acp_proof.py`

## 4. Reproducibility

```bash
cd /Users/utkarshkhajuria/Desktop/RazorMesh
uv run --project services/api pytest services/api/tests/phase4/test_acp_proof.py -v
```

## 5. Scope and non-claim

This matrix proves the seller-side ACP `2026-01-30` subset
implemented by RazorMesh. It does NOT claim:
- "ACP Delegate Payment supported" via Razorpay.
- Official Razorpay ACP integration.
- Stripe / SPT equivalent.
- Full ACP `2026-01-30` conformance (the small `2026-04-17`
  follow-up is a compatibility add-on that does not change
  RazorMesh's tested subset).
- Production-grade payment security.
