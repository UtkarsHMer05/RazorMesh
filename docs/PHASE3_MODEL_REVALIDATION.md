# Phase-3 fine-tuned model revalidation (v2 corrected checkpoint)

Generated: `2026-08-28T14:09:20.582314+00:00` by `scripts/rzp_revalidate_phase3_v2.py`.

Real inference was re-run from the frozen local checkpoints on this machine;
no historical metric JSON is trusted. There is no blind human-heldout set in
this repository (dataset audit §6), so the untouched OOD set is the only
external evaluation.

## Frozen threshold policy (v3, calibrated on frozen_v2 val ONLY)

`tau_block=0.05`, `tau_entail=0.9` —
objective: F2 of BLOCK subject to false-BLOCK rate on val entailment ≤ 0.05.
Policy sha256 `bd8fea4347e72b6c…`. The historical v2 policy
(tau_block=0.3, tau_entail=0.4,
v1 checkpoint, frozen_v1 val) is retained untouched for the v1 comparison.

## Headline (accuracy / macro F1)

| eval set | n | v2 acc | v2 macro F1 | v1 acc | v1 macro F1 |
|---|---:|---:|---:|---:|---:|
| `frozen_v2_val` | 143 | 0.8671 | 0.8571 | 0.6154 | 0.5349 |
| `frozen_v2_test` | 126 | 0.8254 | 0.8245 | 0.6746 | 0.6593 |
| `untouched_ood_129` | 129 | 0.9457 | 0.946 | 0.5504 | 0.4823 |

## Per-class detail (v2 corrected checkpoint)

### `frozen_v2_val` (n=143)

contradiction P/R/F1 = 0.9057/0.8421/0.8727, entailment = 0.9074/0.9245/0.9159, neutral = 0.75/0.8182/0.7826

confusion (rows=gold): `{"contradiction": {"contradiction": 48, "neutral": 6, "entailment": 3}, "entailment": {"entailment": 49, "neutral": 3, "contradiction": 1}, "neutral": {"neutral": 27, "entailment": 2, "contradiction": 4}}`

### `frozen_v2_test` (n=126)

contradiction P/R/F1 = 0.8462/0.75/0.7952, entailment = 0.7917/0.95/0.8636, neutral = 0.8462/0.7857/0.8148

confusion (rows=gold): `{"contradiction": {"contradiction": 33, "entailment": 5, "neutral": 6}, "entailment": {"entailment": 38, "contradiction": 2}, "neutral": {"neutral": 33, "entailment": 5, "contradiction": 4}}`

### `untouched_ood_129` (n=129)

contradiction P/R/F1 = 0.9302/0.9302/0.9302, entailment = 0.913/0.9767/0.9438, neutral = 1.0/0.9302/0.9639

confusion (rows=gold): `{"contradiction": {"contradiction": 40, "entailment": 3}, "entailment": {"entailment": 42, "contradiction": 1}, "neutral": {"neutral": 40, "contradiction": 2, "entailment": 1}}`

## Payment-safety metrics under the frozen policy

| eval set | model | gold contra → unsafe PASS | contra escaping BLOCK | false BLOCK on entailment | neutral wrongly PASS |
|---|---|---:|---:|---:|---:|
| `frozen_v2_val` | v2 | 3 | 6/57 | 2/53 | 2/33 |
| `frozen_v2_val` | v1 | 3 | 4/57 | 17/53 | 8/33 |
| `frozen_v2_test` | v2 | 3 | 9/44 | 3/40 | 4/42 |
| `frozen_v2_test` | v1 | 7 | 7/44 | 3/40 | 7/42 |
| `untouched_ood_129` | v2 | 2 | 2/43 | 1/43 | 1/43 |
| `untouched_ood_129` | v1 | 4 | 5/43 | 7/43 | 10/43 |

## Action distribution (frozen policy)

- `frozen_v2_val` v2: `{'PASS': 52, 'CHALLENGE': 33, 'BLOCK': 58}`
- `frozen_v2_val` v1: `{'PASS': 39, 'CHALLENGE': 15, 'BLOCK': 89}`
- `frozen_v2_test` v2: `{'PASS': 42, 'CHALLENGE': 42, 'BLOCK': 42}`
- `frozen_v2_test` v1: `{'PASS': 45, 'CHALLENGE': 23, 'BLOCK': 58}`
- `untouched_ood_129` v2: `{'PASS': 45, 'CHALLENGE': 39, 'BLOCK': 45}`
- `untouched_ood_129` v1: `{'PASS': 44, 'CHALLENGE': 10, 'BLOCK': 75}`

## Contamination guards

- Threshold v3 calibration read ONLY `data/phase3/dataset/frozen_v2/val.jsonl`.
- `frozen_v2/test.jsonl` and the untouched OOD set were **not** used for any
  selection or calibration decision; they are reported once, post-freeze.
- The untouched OOD set (`data/phase3/eval/untouched_ood/ood_adversarial_129.jsonl`)
  is fully canonical-orientation, so the v1-vs-v2 comparison on it is fair.

## Artifact provenance

- v2 checkpoint: `artifacts/models/incoming/phase3-finetuned-v2` sha256 `163864e04a07fb56e51526f2f05dab3be742a9f1f290a561fc97fedd8f3c6995` (cold load 2.33s)
- v1 checkpoint: `artifacts/models/incoming/phase3-finetuned` sha256 `77538ffdaaad581d97ed8b04f45df0624777a3c1bee873c093d2070ee4294897` (cold load 0.56s)
- Manifests with full file hashes written next to both checkpoints as `model_manifest.json`.

Historical numbers from earlier milestones remain in their own documents and are
not reproduced here; where they disagree with this run, this run is the
authoritative re-measurement of the current artifacts.
