# Phase-3 dataset + semantic runtime final audit

**Status: PHASE-3 DATASET + SEMANTIC RUNTIME CORRECTION COMPLETE**

Generated: 2026-08-28. Consolidates the correction work ordered by the Phase-3
correction brief: dataset audit, AgentPay-IR v2 freeze, orientation diagnostic,
v2 retrain, runtime wiring, and full regression. Every number below was
recomputed from bytes on disk / real inference on this machine during this
correction — no historical JSON is trusted as current truth.

---

## 1. DATASET

### Splits (frozen AgentPay-IR v0.2, canonical orientation)

| split | rows | contradiction | entailment | neutral | SHA-256 |
|---|---:|---:|---:|---:|---|
| `data/phase3/dataset/frozen_v2/train.jsonl` | 648 | 234 | 232 | 182 | `ac3d77ea168988be…` |
| `data/phase3/dataset/frozen_v2/val.jsonl` | 143 | 57 | 53 | 33 | `1ca90288a3c8d251…` |
| `data/phase3/dataset/frozen_v2/test.jsonl` | 126 | 44 | 40 | 42 | `b7d836b7785df4ec…` |
| `data/phase3/eval/untouched_ood/ood_adversarial_129.jsonl` | 129 | 43 | 43 | 43 | `25dfae0ddc429dba…` |

- conceptual parents: 330; families covered: **35 of 35** required categories
- schema: `agentpay-ir-v0.2` (record_id, schema_version, premise, hypothesis,
  label, family, subfamily, authorization_field, evidence_field,
  generator_parent_id, template_family_id, source, safe_or_attack,
  content_sha256, split_group, metadata)
- orientation (uniform, canonical): **premise = current sanitized commerce
  evidence; hypothesis = normalized human authorization constraint**

### Historical (v1) inventory — retained untouched, superseded

| split | rows | note |
|---|---:|---|
| `training/phase3/train.jsonl` (= frozen_v1 train) | 723 | byte-identical bundle copy |
| `training/phase3/val.jsonl` (= frozen_v1 val) | 171 | checkpoint selection + threshold calibration |
| `data/phase3/dataset/frozen_v1/test.jsonl` | 127 | previously examined evaluation |
| OOD adversarial | 129 | never used for training/thresholds |

Human-reviewed terminology: 320 reviewed IDs = 241 train + 43 val + 36 test.
Only subsets that entered training may be called "human-reviewed supervised";
no blind human-heldout evaluation set exists in this repository (disclosed in
`PHASE3_DATASET_RUNTIME_AUDIT.md` §6). The untouched OOD set is the only
external evaluation.

### Leakage

`docs/PHASE3_DATASET_LEAKAGE_REPORT.md` — **gate PASS**: 0 split groups
spanning splits, 0 identical/normalized duplicates across splits, 0
near-duplicate premises (Jaccard ≥ 0.85) across splits.

---

## 2. ORIENTATION DIAGNOSTIC (why retraining was required)

`docs/PHASE3_ORIENTATION_DIAGNOSTIC.md` — paired diagnostic, n=293
(122 stratified train + 171 val), device cpu, torch 2.13.0.

| metric | legacy | canonical | delta |
|---|---:|---:|---:|
| accuracy | 0.9829 | 0.9761 | −0.0068 |
| macro F1 | 0.9832 | 0.9764 | −0.0068 |
| contradiction recall | 0.9896 | 0.9792 | −0.0104 |
| unsafe entailment on gold contradiction | 1 | 2 | +1 |

- gold contradiction, legacy=contradiction → canonical=entailment: **1** (the
  most dangerous flip mode)
- **RETRAIN_REQUIRED = YES** — decision made on development data only; test
  and OOD were not used for any correction decision.

---

## 3. MODEL

| field | value |
|---|---|
| base | `cross-encoder/nli-deberta-v3-base` |
| runtime artifact | `artifacts/models/incoming/phase3-finetuned-v2` |
| `model.safetensors` SHA-256 | `163864e04a07fb56e51526f2f05dab3be742a9f1f290a561fc97fedd8f3c6995` |
| label map | 0=contradiction, 1=entailment, 2=neutral (pinned by unit test) |
| dataset | frozen_v2 (canonical orientation), hashes in `model_manifest.json` |
| training seed | 42; actual run: 6 epochs, lr 3e-05, eff. batch 8×2, max_len 256 (from `training_args.bin`) |
| selection | best macro F1 on frozen_v2 val (0.8571) |
| per-file hashes | `model_manifest.json` next to the weights |

Threshold policy: `data/phase3/policy/semantic_thresholds_v3.json` —
calibrated on **frozen_v2 val ONLY** (rows_used 143), objective F2 of BLOCK
subject to false-BLOCK-on-entailment ≤ 0.05; frozen result **tau_block=0.05,
tau_entail=0.9**. Action rule: BLOCK if p_contradiction ≥ tau_block; else
PASS if p_entailment ≥ tau_entail; else CHALLENGE. Test/OOD/human-gold were
never used for calibration. The v2 policy supersedes (and does not modify)
the historical v1 policy file.

---

## 4. METRICS (re-run real inference, 2026-08-28)

`docs/PHASE3_MODEL_REVALIDATION.md` has the full tables. Headline (accuracy /
macro F1), v2 corrected checkpoint vs v1 historical checkpoint:

| eval set | n | v2 | v1 |
|---|---:|---|---|
| frozen_v2 val | 143 | 0.8671 / 0.8571 | 0.6154 / 0.5349 |
| frozen_v2 test | 126 | 0.8254 / 0.8245 | 0.6746 / 0.6593 |
| untouched OOD | 129 | 0.9457 / 0.9460 | 0.5504 / 0.4823 |

Per-class (v2): contradiction recall 0.842 (val) / 0.750 (test) / **0.930
(OOD)**; entailment recall 0.925 / 0.950 / 0.977; neutral recall 0.818 /
0.786 / 0.930.

Payment-safety metrics under the frozen policy (gold-contradiction escaping
BLOCK; false BLOCK on entailment):

| eval set | contra escaping BLOCK | false BLOCK on entailment | neutral wrongly PASS |
|---|---:|---:|---:|
| val (v2) | 6/57 | 2/53 | 2/33 |
| test (v2) | 9/44 | 3/40 | 4/42 |
| OOD (v2) | **2/43** | **1/43** | **1/43** |

On the untouched OOD set the v2 model cuts unsafe contradictions (5→2), false
BLOCKs (7→1) and neutral-mispasses (10→1) relative to the v1 checkpoint.
Known residual: 3 unsafe-entailment misses on val contradictions (the v1
model had the same count); these map to CHALLENGE-or-worse only via
p_contradiction ≥ tau_block — they are disclosed, not hidden.

---

## 5. RUNTIME (wired and verified live)

| field | value |
|---|---|
| backend | `DebertaNLISemanticVerifier` via `SEMANTIC_VERIFIER_BACKEND=deberta` (default) |
| model path | `artifacts/models/incoming/phase3-finetuned-v2` (repo-root-anchored) |
| policy | `semantic-thresholds-v3` |
| load mode | per-process singleton; weights hash enforced on load (§15) |
| fail-closed | any load/config/inference failure → CHALLENGE, `fail_closed=true`; keyword verifier never silently substituted |
| dependency model | optional uv group `semantic` (torch 2.13.0 + transformers 5.15.1); no-torch environments fail closed, never crash |
| performance | cold load 0.61 s; warm pair p50 51.9 ms / p95 65.1 ms; peak RSS 792.3 MiB; 1/5/10-pair stages ≈ 51/242/525 ms (`PHASE3_RUNTIME_PERFORMANCE.md`) |
| device | CPU (MPS not enabled; parity not benchmarked) |

Runtime pair construction (`SemanticEvidenceBuilder`) emits corpus-aligned,
model-calibrated atomic pairs ONLY for aspects the confirmed authorization
actually constrains (correction brief §17):

- `budget_ceiling` — final tax-inclusive checkout total vs authorized cap;
- `recurring_forbidden` — only when the intent forbids recurring charges;
- `brand_identity` — only when the intent carries a brand allowlist;
- `condition_new_only` — only when the intent constrains condition (a
  permissive intent yields no condition pair, so "unknown" evidence cannot
  manufacture a NEUTRAL → CHALLENGE on legit transactions).

Measured on the real runtime (p_entailment / p_contradiction): budget
safe 1.00 / 0.00 → PASS, over-budget 0.00 / 1.00 → BLOCK; condition
new→PASS, refurbished→BLOCK, unknown→CHALLENGE; recurring
disclosed→BLOCK, absent→PASS; brand match→PASS, lookalike→BLOCK.

Audit truth: live ALLOW-path `SEMANTIC_VERIFICATION_RUN` records
`semantic_backend=deberta`, `model_version=phase3-finetuned-v2`,
`model_artifact_hash=163864e0…`, `policy_version=semantic-thresholds-v3`,
`pair_count`, class probabilities, `fail_closed`, `duration_ms`,
`text_stored=false`. `POLICY_FUSION_DECIDED` records the fusion with the
invariant `semantics only STRICTEN hard decisions`.

## 6. SECURITY

- Deterministic RazorGuard remains the financial authority; the semantic
  stage can only keep or tighten (ALLOW<CHALLENGE<BLOCK), enforced by
  `fuse` and tested exhaustively (all 3×3 hard×semantic combinations).
- The model never creates tickets, never calls Razorpay, never mutates
  amounts/merchants, and never derives the hypothesis from merchant text
  (hostile text reaches the PREMISE side only — tested).
- Fail-closed everywhere: missing model, hash mismatch, unknown backend,
  inference exception → CHALLENGE; hard BLOCK stays BLOCK.
- No model weights or secrets through the browser: backend-only settings,
  no `NEXT_PUBLIC_*` model path, `text_stored=false` in the ledger.
- Prompt-injection isolation tests green (Phase-1 seam + live Phase-4 path).

## 7. PHASE 4 WIRING

The Phase-4 acceptance path now runs the REAL semantic runtime:

```
protocol receive → schema/version → signature/digest → replay/idempotency
→ normalize → cross-protocol consistency → deterministic RazorGuard
→ SemanticEvidenceBuilder pairs → DeBERTa → fusion → final
```

- `build_orchestrator()` wires the settings-declared backend, model path and
  policy path (tested).
- Live-ingress E2E (real FastAPI app, real MCP/UCP/AP2, real DB):
  **13/13 passed with the fine-tuned model deciding the semantic stage** —
  including positive chain → ALLOW with semantic PASS, and negative flows.
- The final acceptance evidence records the semantic backend/version/hash/
  probabilities/policy/decision (fields verified in the live audit ledger).
- If the Protocol Firewall already blocks, the semantic stage is not asked to
  rescue the transaction; the model cannot revive a structurally invalid one.

## 8. TESTS (final counts, 2026-08-28)

| gate | result |
|---|---|
| backend `uv run --group semantic pytest` | **755 passed**, 0 failed |
| ruff check / format | clean (195 files) |
| mypy strict (`-p razormesh_api`) | clean (97 source files) |
| pip-audit (incl. torch/transformers) | no known vulnerabilities |
| frontend tsc | 0 errors |
| frontend eslint | 0 errors (1 pre-existing warning in IntentDraftPanel useCallback deps, out of correction scope) |
| vitest | 15 passed (4 files) |
| `next build` | 6 static routes + API routes |
| Playwright | 11 passed; 6 failures all pre-existing/carried-forward: 4 gold-reviewer (known debt), 2 snapshot one-off capture utility (not a regression gate); checkout.spec repaired for the auto-create fixture-intent UI (3/3) |
| new permanent tests | label-map ordering, singleton verifier cache, artifact-hash enforcement, fail-closed matrix (missing model/unknown backend/inference error), §17 conditional pairs, §18 conservative aggregation, stub labeling (`DETERMINISTIC_TEST_STUB`), orchestrator wiring |

Clean-room behavior verified on this machine:

- model present (`--group semantic`): live Phase-4 chain runs the real
  DeBERTa verifier end-to-end (13/13 live-ingress E2E green);
- model absent (no semantic group): the same tests fail CLOSED to
  CHALLENGE — no crash, no silent keyword-verifier substitution (this exact
  fail-closed behavior was observed and asserted before the group was
  installed).

## 9. DOCUMENTATION TRUTH

- `ARCHITECTURE.md`, `SECURITY.md`, `PRD.md`, `DECISIONS.md`: updated so the
  final architecture reads "fine-tuned DeBERTa is an ACTIVE runtime semantic
  verifier; deterministic RazorGuard remains financial authority; ML can only
  tighten" — the old "DeBERTa is evaluation-only by design" phrasing now
  refers explicitly to the historical intermediate state.
- `PHASE3_COMPLETION_REPORT.md`: correction addendum pointing here.
- `docs/PHASE3_MODEL_SETUP.md`: artifact path/SHA-256/verification/runtime
  instructions (new).
- `Makefile` + `TESTING.md`: the backend gate and local API run with the
  optional `semantic` group.
- `VERSION_MANIFEST.md`: torch 2.13.0 / transformers 5.15.1 recorded as an
  optional runtime group (pip-audited).
- Historical documents were not rewritten; where they describe the keyword
  verifier as the runtime, they describe the historical intermediate
  implementation.

## 10. STOP-CONDITION CHECKLIST (correction brief §31)

- [x] dataset orientation verified (uniform canonical in frozen_v2)
- [x] leakage checks green (gate PASS)
- [x] heldout terminology corrected (241 supervised / no blind heldout; OOD untouched)
- [x] actual fine-tuned artifact revalidated (real inference, val/test/OOD)
- [x] DeBERTa runtime wired (per-process singleton, hash-enforced)
- [x] keyword verifier removed as silent production replacement (explicit
      `deterministic_test_stub` only, visibly labeled)
- [x] fail-closed behavior tested (artifact/manifest/backend/inference paths)
- [x] exhaustive fusion tests green (3×3 matrix + strictness property)
- [x] Phase-4 uses real DeBERTa (live E2E + audit evidence)
- [x] full regression green (backend 755, frontend tsc/lint/vitest/build)
- [x] docs accurately describe runtime
