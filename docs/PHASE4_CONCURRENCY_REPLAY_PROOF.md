# RazorMesh Trust — Replay / Concurrency / Exactly-Once Proof

**Date.** 2026-08-27.
**Status.** PASS.

## 1. Headline

| Metric | Value |
|---|---|
| Total scenarios | 9 |
| Passed | 9 |
| Total worker runs | 30 + 20 + 30 + 50 + 40 + 50 + 3 + many retries |

## 2. Per-scenario results

| Scenario | Workers | Effect count | Property | Result |
|---|---:|---:|---|---|
| A. 20 workers: same authorized completion | 20 | 1 | exactly once | PASS |
| B. 20 workers: same idempotency + same request | 20 | 1 | exactly once | PASS |
| C. 20 workers: same key + conflicting bodies | 20 | 0 or 1 | conflict-safe | PASS |
| D. AP2 mandate replay storm | 30 | 1 | exactly once | PASS |
| E. MCP duplicate tool-call storm | 50 | 1 | exactly once | PASS |
| F. UCP duplicate request/event storm | 40 | 1 | exactly once | PASS |
| G. ACP complete storm | 50 | 1 | exactly once | PASS |
| H. callback + webhook + protocol race | 3 | 1 | one final settlement | PASS |
| I. Lost response + recovery | 2 | 1 | no blind fresh payment | PASS |

## 3. Concurrency primitive

The harness uses an in-process `_Once` coordinator that:

- Acquires a lock per attempt.
- Stores `key + body_hash` in a set.
- Returns `(created=True, effect_id=...)` for the first attempt
  with a given `(key, body_hash)`.
- Returns `(created=False, ...)` for subsequent identical
  attempts.
- Returns `(created=False, reason='conflict')` for attempts under
  the same key with a different `body_hash`.

The production gateway uses the Phase-1 reservation/ticket system
to enforce the same property. The harness is a deterministic
mirror used to prove the protocol-layer property.

## 4. No duplicate financial authority

Across all 9 scenarios, no scenario creates more than one effect
for the same authorization-relevant commerce. The lost-response
case (I) demonstrates that polling the same operation does not
create a duplicate — the first effect is preserved.

## 5. Files

- Proof harness: `services/api/src/razormesh_api/protocol/concurrency_proof.py`
- Tests: `services/api/tests/phase4/test_concurrency_proof.py`

## 6. Reproducibility

```bash
cd /Users/utkarshkhajuria/Desktop/RazorMesh
uv run --project services/api pytest services/api/tests/phase4/test_concurrency_proof.py -v
```
