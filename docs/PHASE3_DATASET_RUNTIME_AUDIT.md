# Phase-3 dataset / model / runtime semantic audit

Generated: `2026-08-28T09:03:40.949328+00:00` by `scripts/rzp_audit_phase3_dataset.py`.

Read-only. Every number below is recomputed from bytes on disk.

## 1. Datasets on disk

| dataset | rows | SHA-256 | purpose |
|---|---:|---|---|
| `training/phase3/train.jsonl` | 723 | `13cc5d6f130d61f1…` | bundle copy actually fed to the fine-tune job |
| `training/phase3/val.jsonl` | 171 | `551c8b44752a5b09…` | bundle copy used for checkpoint selection |
| `data/phase3/dataset/frozen_v1/train.jsonl` | 723 | `13cc5d6f130d61f1…` | gradient updates |
| `data/phase3/dataset/frozen_v1/val.jsonl` | 171 | `551c8b44752a5b09…` | checkpoint selection + threshold calibration |
| `data/phase3/dataset/frozen_v1/test.jsonl` | 127 | `1756a4fa9d78a0de…` | previously examined evaluation |
| `data/phase3/eval/untouched_ood/ood_adversarial_129.jsonl` | 129 | `25dfae0ddc429dba…` | out-of-distribution adversarial evaluation |

## 2. Label and family distribution

### `training/phase3/train.jsonl`

- labels: `{"contradiction": 248, "entailment": 243, "neutral": 232}`
- label source: `{"qwen_provisional": 39, "template_truth": 684}`
- difficulty: `{"easy": 519, "hard": 102, "medium": 102}`
- families (18): `{"brand_identity": 99, "budget_ceiling": 264, "bundle_obligation": 3, "condition_new_only": 66, "currency_binding": 66, "delivery_timing": 4, "injection_resistance": 20, "membership_insertion": 3, "merchant_restriction": 27, "quantity_limit": 70, "recurring_forbidden": 39, "return_refund": 3, "safe_lookalike": 8, "seller_alias": 7, "shipping_fee": 6, "trial_renewal_trap": 31, "variant_mismatch": 4, "warranty_claim": 3}`

### `training/phase3/val.jsonl`

- labels: `{"contradiction": 54, "entailment": 61, "neutral": 56}`
- label source: `{"qwen_provisional": 19, "template_truth": 152}`
- difficulty: `{"easy": 150, "hard": 12, "medium": 9}`
- families (9): `{"brand_identity": 26, "budget_ceiling": 67, "condition_new_only": 6, "currency_binding": 33, "injection_resistance": 2, "merchant_restriction": 6, "quantity_limit": 21, "recurring_forbidden": 9, "trial_renewal_trap": 1}`

### `data/phase3/dataset/frozen_v1/train.jsonl`

- labels: `{"contradiction": 248, "entailment": 243, "neutral": 232}`
- label source: `{"qwen_provisional": 39, "template_truth": 684}`
- difficulty: `{"easy": 519, "hard": 102, "medium": 102}`
- families (18): `{"brand_identity": 99, "budget_ceiling": 264, "bundle_obligation": 3, "condition_new_only": 66, "currency_binding": 66, "delivery_timing": 4, "injection_resistance": 20, "membership_insertion": 3, "merchant_restriction": 27, "quantity_limit": 70, "recurring_forbidden": 39, "return_refund": 3, "safe_lookalike": 8, "seller_alias": 7, "shipping_fee": 6, "trial_renewal_trap": 31, "variant_mismatch": 4, "warranty_claim": 3}`

### `data/phase3/dataset/frozen_v1/val.jsonl`

- labels: `{"contradiction": 54, "entailment": 61, "neutral": 56}`
- label source: `{"qwen_provisional": 19, "template_truth": 152}`
- difficulty: `{"easy": 150, "hard": 12, "medium": 9}`
- families (9): `{"brand_identity": 26, "budget_ceiling": 67, "condition_new_only": 6, "currency_binding": 33, "injection_resistance": 2, "merchant_restriction": 6, "quantity_limit": 21, "recurring_forbidden": 9, "trial_renewal_trap": 1}`

### `data/phase3/dataset/frozen_v1/test.jsonl`

- labels: `{"contradiction": 43, "entailment": 40, "neutral": 44}`
- label source: `{"qwen_provisional": 10, "template_truth": 117}`
- difficulty: `{"easy": 97, "hard": 12, "medium": 18}`
- families (10): `{"brand_identity": 15, "budget_ceiling": 43, "bundle_obligation": 1, "condition_new_only": 15, "currency_binding": 21, "injection_resistance": 3, "merchant_restriction": 3, "quantity_limit": 12, "recurring_forbidden": 6, "trial_renewal_trap": 8}`

### `data/phase3/eval/untouched_ood/ood_adversarial_129.jsonl`

- labels: `{"contradiction": 43, "entailment": 43, "neutral": 43}`
- label source: `{"template_truth": 129}`
- difficulty: `{"hard": 129}`
- families (18): `{"brand_identity": 3, "budget_ceiling": 3, "bundle_obligation": 12, "condition_new_only": 12, "currency_binding": 6, "delivery_timing": 6, "injection_resistance": 9, "membership_insertion": 3, "merchant_restriction": 6, "quantity_limit": 9, "recurring_forbidden": 6, "return_refund": 6, "safe_lookalike": 12, "seller_alias": 9, "shipping_fee": 3, "trial_renewal_trap": 6, "variant_mismatch": 12, "warranty_claim": 6}`

## 3. NLI orientation contract

CANONICAL: `premise` = current sanitized commerce evidence only; `hypothesis` = normalized human authorization constraint.

| dataset | canonical | authorization folded into premise | canonical fraction |
|---|---:|---:|---:|
| `training/phase3/train.jsonl` | 66 | 657 | 0.0913 |
| `training/phase3/val.jsonl` | 11 | 160 | 0.0643 |
| `data/phase3/dataset/frozen_v1/train.jsonl` | 66 | 657 | 0.0913 |
| `data/phase3/dataset/frozen_v1/val.jsonl` | 11 | 160 | 0.0643 |
| `data/phase3/dataset/frozen_v1/test.jsonl` | 11 | 116 | 0.0866 |
| `data/phase3/eval/untouched_ood/ood_adversarial_129.jsonl` | 129 | 0 | 1.0 |

## 4. AgentPay-IR field contract

- `training/phase3/train.jsonl`: missing required `[]`; v0.2 fields absent `['schema_version', 'subfamily', 'authorization_field', 'evidence_field', 'generator_parent_id', 'template_family_id', 'source', 'safe_or_attack', 'split_group']`
- `training/phase3/val.jsonl`: missing required `[]`; v0.2 fields absent `['schema_version', 'subfamily', 'authorization_field', 'evidence_field', 'generator_parent_id', 'template_family_id', 'source', 'safe_or_attack', 'split_group']`
- `data/phase3/dataset/frozen_v1/train.jsonl`: missing required `[]`; v0.2 fields absent `['schema_version', 'subfamily', 'authorization_field', 'evidence_field', 'generator_parent_id', 'template_family_id', 'source', 'safe_or_attack', 'split_group']`
- `data/phase3/dataset/frozen_v1/val.jsonl`: missing required `[]`; v0.2 fields absent `['schema_version', 'subfamily', 'authorization_field', 'evidence_field', 'generator_parent_id', 'template_family_id', 'source', 'safe_or_attack', 'split_group']`
- `data/phase3/dataset/frozen_v1/test.jsonl`: missing required `[]`; v0.2 fields absent `['schema_version', 'subfamily', 'authorization_field', 'evidence_field', 'generator_parent_id', 'template_family_id', 'source', 'safe_or_attack', 'split_group']`
- `data/phase3/eval/untouched_ood/ood_adversarial_129.jsonl`: missing required `[]`; v0.2 fields absent `['schema_version', 'subfamily', 'authorization_field', 'evidence_field', 'generator_parent_id', 'template_family_id', 'source', 'safe_or_attack', 'split_group']`

## 5. Split isolation / leakage

Training bundle byte-identical to frozen: `{"train": true, "val": true}`

| pair | record_id | content_sha256 | normalized pair | template_id | source_case_id |
|---|---:|---:|---:|---:|---:|
| `frozen_test::frozen_train` | 0 | 0 | 0 | 0 | 0 |
| `frozen_test::frozen_val` | 0 | 0 | 0 | 0 | 0 |
| `frozen_test::ood` | 0 | 0 | 0 | 0 | 0 |
| `frozen_train::frozen_val` | 0 | 0 | 0 | 0 | 0 |
| `frozen_train::ood` | 0 | 0 | 0 | 0 | 0 |
| `frozen_val::ood` | 0 | 0 | 0 | 0 | 0 |

## 6. Human gold: honest split roles

- reviewed entries: 320
- by frozen split: `{"test": 36, "train": 241, "val": 43}`
- human label vs frozen label: `{"differs_from_frozen_label": 7, "matches_frozen_label": 313}`
- disagreements: 7

```json
{
  "human_reviewed_supervised": 241,
  "human_reviewed_validation_influenced_selection": 43,
  "human_reviewed_test_previously_examined": 36,
  "human_reviewed_blind_heldout": 0,
  "note": "No subset of the reviewed cards is a blind holdout: the val cards drove checkpoint selection and threshold calibration, and the test cards were already inspected in earlier milestones. Only a NEW human-reviewed set, collected after this correction freezes, may be called human-held-out."
}
```

## 7. Fine-tuned artifact

- directory: `artifacts/models/incoming/phase3-finetuned` (exists: True)
- `model_manifest.json` present: False

| file | bytes | SHA-256 |
|---|---:|---|
| `base_model.txt` | 33 | `6cbf984ccc45d3c4…` |
| `config.json` | 1111 | `64a92db4b9481338…` |
| `label_map.json` | 65 | `165a8610bee89a75…` |
| `metrics.json` | 116 | `c812d46792b87069…` |
| `model.safetensors` | 737722356 | `77538ffdaaad581d…` |
| `tokenizer.json` | 8339973 | `561fd1b229749e08…` |
| `tokenizer_config.json` | 505 | `3dd09fcbf87e99e2…` |
| `training_args.bin` | 5201 | `2b92b244c4a9b0ed…` |

```json
{
  "label_map_matches_config_id2label": true,
  "config_architectures": [
    "DebertaV2ForSequenceClassification"
  ],
  "config_model_type": "deberta-v2",
  "config_num_labels": 3,
  "transformers_version_in_config": "5.15.1",
  "declared_base_model": "cross-encoder/nli-deberta-v3-base"
}
```

## 8. Frozen threshold policy

```json
{
  "path": "data/phase3/policy/semantic_thresholds.json",
  "sha256": "3005cc315c08505f969ada3bbefda3cc5831dfd177c002dff7b1033ac70ba279",
  "policy_version": "semantic-thresholds-v2",
  "model": "phase3-finetuned-cross-encoder",
  "base_model": "cross-encoder/nli-deberta-v3-base",
  "label_map": {
    "0": "contradiction",
    "1": "entailment",
    "2": "neutral"
  },
  "tau_block": 0.3,
  "tau_entail": 0.4,
  "calibrated_on": "validation split ONLY (never gold, never test)",
  "rows_used": 171,
  "gold_validation_status": "GOLD_VALIDATED",
  "heldout_claim": {
    "note": "post-calibration honest validation: 79 human-gold cards in val/test (never seen during training)",
    "heldout_n": 79,
    "action_distribution": {
      "BLOCK": 35,
      "ENTAIL": 23,
      "CHALLENGE": 21
    },
    "contradiction_recall_on_heldout": 1.0,
    "false_block_rate_on_heldout_entailment": 0.1538,
    "neutral_correctly_handled_on_heldout": 0.9545,
    "interpretation": "All 31 human contradictions correctly BLOCKED. 4/26 human entailments received BLOCK (above 0.05 cap on this holdout) \u2014 these are conservative refusals, not unsafe allows; the conservative fusion (P3-M40) routes them through deterministic rules and human-in-the-loop review (P3-S15). The cap is the calibration constraint, satisfied on val (2/61 = 0.033); the heldout is reported for transparency, not as a relaxed constraint."
  }
}
```

## 9. Runtime wiring as found

```json
{
  "keyword_verifier_instantiations": {
    "services/api/src/razormesh_api/protocol/acceptance.py": [
      496
    ]
  },
  "deberta_instantiated_in_server_source": false,
  "semantic_backend_setting_declared": false,
  "semantic_model_path_setting_declared": false
}
```

