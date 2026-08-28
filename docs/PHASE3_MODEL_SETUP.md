# Phase-3 semantic model setup (runtime DeBERTa)

This document describes how to obtain, verify and run the fine-tuned DeBERTa
artifact that the API uses as its production semantic verifier
(`SEMANTIC_VERIFIER_BACKEND=deberta`, the default).

Model weights are intentionally **not committed** (see `.gitignore`): the
artifact is ~738 MB. This file plus the in-repo manifests are enough to
reproduce and verify it.

---

## 1. Expected path

```
artifacts/models/incoming/phase3-finetuned-v2/
    model.safetensors        # weights, 737,722,356 bytes
    config.json
    tokenizer.json
    tokenizer_config.json
    label_map.json
    base_model.txt
    metrics.json
    training_args.bin
    model_manifest.json      # per-file SHA-256 manifest (committed-adjacent)
```

Configured via backend-only settings (never a `NEXT_PUBLIC_*` variable — the
browser never sees or loads the model):

```
SEMANTIC_VERIFIER_BACKEND=deberta          # default; "deterministic_test_stub" is an explicit test-only backend
SEMANTIC_MODEL_PATH=artifacts/models/incoming/phase3-finetuned-v2
SEMANTIC_POLICY_PATH=data/phase3/policy/semantic_thresholds_v3.json
```

Relative paths are resolved against the repository root, regardless of the
process CWD (`resolve_repo_path` in `services/api/src/razormesh_api/semantic_runtime.py`).

## 2. Expected SHA-256

`model.safetensors`:

```
163864e04a07fb56e51526f2f05dab3be742a9f1f290a561fc97fedd8f3c6995
```

Verify:

```
shasum -a 256 artifacts/models/incoming/phase3-finetuned-v2/model.safetensors
```

`model_manifest.json` records per-file SHA-256 for every artifact file. The
runtime enforces the weights hash on load (`_verify_artifact_integrity` in
`services/api/src/razormesh_api/semantic_verifier.py`): a manifest hash
mismatch **fails closed** (load raises → semantic verdict CHALLENGE), and the
weights never run.

## 3. Base model and label mapping

- Base: `cross-encoder/nli-deberta-v3-base` (also in `base_model.txt`).
- Label map (`label_map.json`, `config.json:id2label`, and the frozen
  threshold policy must all agree):

```
0 -> contradiction
1 -> entailment
2 -> neutral
```

A regression test pins this ordering
(`tests/test_semantic_runtime.py::test_v2_artifact_label_order_is_canonical`)
and fails if the mapping changes.

## 4. Training provenance (no fabricated values)

| field | value |
|---|---|
| dataset | `data/phase3/dataset/frozen_v2` (canonical orientation) |
| orientation | premise = current sanitized commerce evidence; hypothesis = normalized human authorization constraint |
| training seed | 42 |
| epochs (actual run) | 6 (recipe default 3; `training_args.bin` of the saved run records 6) |
| learning rate (actual run) | 3e-05 (recipe default 2e-05; read from `training_args.bin`) |
| effective batch | 8 per device × 2 gradient-accumulation steps (8 GB Apple-silicon CPU box) |
| max length | 256 |
| selected metric | macro F1 (`best_metric` 0.8571 on frozen_v2 val) |

Full details: `model_manifest.json` next to the weights, and
`docs/PHASE3_MODEL_REVALIDATION.md` for re-run inference numbers.

## 5. How to start the backend with DeBERTa

```
# one-time: install the optional runtime group (torch 2.13.0 + transformers 5.15.1)
uv sync --project services/api --group semantic

# run the API (DeBERTa is the default backend)
make dev-api
```

The model loads ONCE per backend process (per-process verifier cache,
correction brief §15) — never per request. Cold load ≈ 0.6 s; warm pair
latency p50 ≈ 52 ms, p95 ≈ 65 ms on CPU (`docs/PHASE3_RUNTIME_PERFORMANCE.md`).

The test gate that exercises the real model end-to-end:

```
cd services/api && uv run --group semantic pytest
```

(`make test-backend` does the same. Without `--group semantic`, tests that
need the real runtime fail closed to CHALLENGE — by design — and the
no-torch environment keeps lightweight installs possible.)

## 6. Failure behavior (fail closed)

If any of the following occurs, the semantic stage returns CHALLENGE with
`fail_closed=true` and records a `SEMANTIC_VERIFICATION_RUN` audit event with
`fail_closed: true`; it NEVER passes and never silently substitutes the
keyword verifier:

- artifact/model directory missing;
- `model_manifest.json` missing or weights hash mismatch;
- tokenizer files missing/incompatible;
- `label_map.json` invalid;
- inference exception, malformed output, NaN probability, or timeout;
- an unknown `SEMANTIC_VERIFIER_BACKEND` value.

A hard RazorGuard BLOCK stays BLOCK even under fail-closed semantics.
The deterministic keyword verifier exists ONLY as the explicitly selected
`deterministic_test_stub` backend and always reports
`model_id=DETERMINISTIC_TEST_STUB` — the UI and audit ledger show the truth.

## 7. Related documents

- `docs/PHASE3_DATASET_RUNTIME_AUDIT.md` — dataset inventory and hashes
- `docs/PHASE3_DATASET_LEAKAGE_REPORT.md` — frozen_v2 leakage gate (PASS)
- `docs/PHASE3_ORIENTATION_DIAGNOSTIC.md` — why the v2 retrain was required
- `docs/PHASE3_MODEL_REVALIDATION.md` — re-run inference metrics (val/test/OOD)
- `docs/PHASE3_RUNTIME_PERFORMANCE.md` — live runtime latency/memory
- `docs/PHASE3_DATASET_AND_RUNTIME_FINAL_AUDIT.md` — final consolidated audit
