# Phase-3 paired orientation diagnostic

Generated: `2026-08-28T17:57:44.834449+00:00` by `scripts/rzp_orientation_diagnostic.py`.

**Question:** does the existing frozen checkpoint generalize to the canonical runtime NLI
orientation? Read-only. No retraining, no runtime wiring, no threshold or dataset change.

## RETRAIN_REQUIRED = YES

- 1 gold contradictions flipped contradiction->entailment
- policy unsafe-allow on contradictions rose by 1
- gold contradictions escaping BLOCK rose by 1

## Headline

| metric | legacy (training) | canonical (runtime) | delta |
|---|---:|---:|---:|
| accuracy | 0.9829 | 0.9761 | -0.0068 |
| macro F1 | 0.9832 | 0.9764 | -0.0068 |
| contradiction recall | 0.9896 | 0.9792 | -0.0104 |
| unsafe entailment on gold contradiction | 1 | 2 | 1 |

## Paired diagnostic set

- paired cases: **293** (rows skipped: 0)
- by source: `{"train_stratified": 122, "val": 171}`
- by transform: `{"noop_control": 29, "stripped": 264}`
- by label: `{"contradiction": 96, "entailment": 102, "neutral": 95}`
- families covered: 18
- evidence-determinable: 162 / not determinable: 131
- device `cpu`, torch `2.13.0`, cold load `3.37s`

The hypothesis string is byte-identical across the two representations; only the premise
orientation changes. Ground-truth labels are carried over unchanged.

## Per-class detail

| class | support | legacy P/R/F1 | canonical P/R/F1 |
|---|---:|---|---|
| contradiction | 96 | 0.9596/0.9896/0.9744 | 0.9592/0.9792/0.9691 |
| entailment | 102 | 0.9899/0.9608/0.9751 | 0.9703/0.9608/0.9655 |
| neutral | 95 | 1.0/1.0/1.0 | 1.0/0.9895/0.9947 |

### Confusion matrices (rows = gold, cols = predicted)

- **legacy**: `{"contradiction": {"contradiction": 95, "entailment": 1, "neutral": 0}, "entailment": {"contradiction": 4, "entailment": 98, "neutral": 0}, "neutral": {"contradiction": 0, "entailment": 0, "neutral": 95}}`
- **canonical**: `{"contradiction": {"contradiction": 94, "entailment": 2, "neutral": 0}, "entailment": {"contradiction": 4, "entailment": 98, "neutral": 0}, "neutral": {"contradiction": 0, "entailment": 1, "neutral": 94}}`

### Where gold contradictions went

- **legacy**: `{"contradiction": 95, "neutral": 0, "entailment": 1}`
- **canonical**: `{"contradiction": 94, "neutral": 0, "entailment": 2}`

## Frozen threshold policy (unchanged)

`tau_block=0.3`, `tau_entail=0.4`, policy `semantic-thresholds-v2`.

| policy outcome | legacy | canonical |
|---|---:|---:|
| PASS | 99 | 101 |
| CHALLENGE | 95 | 94 |
| BLOCK | 99 | 98 |
| gold contradiction → unsafe PASS | 1 | 2 |
| gold contradiction escaping BLOCK | 1/96 | 2/96 |
| gold entailment false BLOCK | 4/102 | 4/102 |
| gold neutral wrongly PASS | 0/95 | 1/95 |

## Paired flips (same case, orientation is the only variable)

- unchanged: **291**, changed: **2** (change rate 0.0068)
- correct → incorrect: **2**
- incorrect → correct: **0**
- **gold contradiction, legacy=contradiction, canonical=entailment: 1** (most dangerous failure mode)
- no-op control flips: 0 of 29

| gold class | unchanged | changed | correct→incorrect | incorrect→correct |
|---|---:|---:|---:|---:|
| contradiction | 95 | 1 | 1 | 0 |
| entailment | 102 | 0 | 0 | 0 |
| neutral | 94 | 1 | 1 | 0 |

## Per-family degradation

| family | n | legacy acc | canonical acc | Δacc | Δcontradiction recall |
|---|---:|---:|---:|---:|---:|
| `budget_ceiling` | 76 | 1.0 | 0.9737 | -0.0263 | -0.0435 |
| `brand_identity` | 35 | 1.0 | 1.0 | 0.0 | 0.0 |
| `bundle_obligation` | 3 | 1.0 | 1.0 | 0.0 | 0.0 |
| `condition_new_only` | 15 | 1.0 | 1.0 | 0.0 | 0.0 |
| `currency_binding` | 42 | 1.0 | 1.0 | 0.0 | 0.0 |
| `delivery_timing` | 4 | 1.0 | 1.0 | 0.0 | 0.0 |
| `injection_resistance` | 11 | 0.6364 | 0.6364 | 0.0 | 0.0 |
| `membership_insertion` | 3 | 1.0 | 1.0 | 0.0 | 0.0 |
| `merchant_restriction` | 15 | 1.0 | 1.0 | 0.0 | 0.0 |
| `quantity_limit` | 30 | 1.0 | 1.0 | 0.0 | 0.0 |
| `recurring_forbidden` | 18 | 1.0 | 1.0 | 0.0 | 0.0 |
| `return_refund` | 3 | 1.0 | 1.0 | 0.0 | 0.0 |
| `safe_lookalike` | 8 | 1.0 | 1.0 | 0.0 | 0.0 |
| `seller_alias` | 7 | 1.0 | 1.0 | 0.0 | 0.0 |
| `shipping_fee` | 6 | 1.0 | 1.0 | 0.0 | 0.0 |
| `trial_renewal_trap` | 10 | 0.9 | 0.9 | 0.0 | 0.0 |
| `variant_mismatch` | 4 | 1.0 | 1.0 | 0.0 | 0.0 |
| `warranty_claim` | 3 | 1.0 | 1.0 | 0.0 | 0.0 |

## Held-out contamination guards

- `data/phase3/eval/untouched_ood/ood_adversarial_129.jsonl`: **not loaded** by this run.
- `data/phase3/dataset/frozen_v1/test.jsonl`: **not loaded** by this run.
- Train-derived cells measure generalization on already-seen cases, which can only
  *understate* orientation risk. Val-only numbers are reported separately for that reason.

## Val-only and train-only slices

- `metrics_val_only`: legacy acc 0.9825 / F1 0.9826 / contra-recall 0.9815 (n=171); canonical acc 0.9708 / F1 0.9711 / contra-recall 0.963
- `metrics_train_stratified_only`: legacy acc 0.9836 / F1 0.9839 / contra-recall 1.0 (n=122); canonical acc 0.9836 / F1 0.9839 / contra-recall 1.0
- `metrics_determinable_subset`: legacy acc 1.0 / F1 1.0 / contra-recall 1.0 (n=162); canonical acc 0.9938 / F1 0.9947 / contra-recall 1.0

## Artifact provenance

- declared base model: `cross-encoder/nli-deberta-v3-base`
- architectures: `['DebertaV2ForSequenceClassification']`, model_type `deberta-v2`
- label map: `{"0": "contradiction", "1": "entailment", "2": "neutral"}` (agrees with `config.id2label`)
- `transformers` version recorded in config: `5.15.1`

| file | bytes | SHA-256 |
|---|---:|---|
| `base_model.txt` | 33 | `6cbf984ccc45d3c487b80b8459b9ca13663d2296186b85868b757f5f1810cd7d` |
| `config.json` | 1111 | `64a92db4b94813386f0b54fecfc56b0e2dae2aed3c15fa78868988b9623ccf31` |
| `label_map.json` | 65 | `165a8610bee89a759fa5909b87ed5c67044c44f8bf672ac5db1a2b0f0da3b1e4` |
| `model.safetensors` | 737722356 | `77538ffdaaad581d97ed8b04f45df0624777a3c1bee873c093d2070ee4294897` |
| `tokenizer.json` | 8339973 | `561fd1b229749e08cc8b9b0a77e467b07ac5549418682e603925753429a8cd3e` |
| `tokenizer_config.json` | 505 | `3dd09fcbf87e99e22a6e9d359ab7ecaceca29dd3774e509df9de6a16ecdaa394` |

Per-case predictions are in `docs/PHASE3_ORIENTATION_DIAGNOSTIC.json` under `cases`.
