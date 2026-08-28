# Phase-3 dataset leakage report (AgentPay-IR v0.2)

Generated: `2026-08-28T11:16:50.596176+00:00` by `scripts/rzp_build_agentpay_ir_v2.py`.

**Leakage gate: PASS**

A failing gate blocks use of any reported Phase-3 metric.

## Splits

| split | rows | contradiction | entailment | neutral | SHA-256 |
|---|---:|---:|---:|---:|---|
| `train` | 648 | 234 | 232 | 182 | `ac3d77ea168988be...` |
| `val` | 143 | 57 | 53 | 33 | `1ca90288a3c8d251...` |
| `test` | 126 | 44 | 40 | 42 | `b7d836b7785df4ec...` |

- conceptual parents: 330
- families covered: 35 of 35 required

## Cross-split overlap (all must be zero)

| pair | record_id | content_sha256 | normalized pair | split_group | template family (informational) |
|---|---:|---:|---:|---:|---:|
| `train::val` | 0 | 0 | 0 | 0 | 22 |
| `train::test` | 0 | 0 | 0 | 0 | 9 |
| `val::test` | 0 | 0 | 0 | 0 | 4 |

- template_family_id intentionally spans splits: it names the phrasing shape, not the case. The leakage gate runs on split_group, content and normalized pair instead, which is strictly stronger than v0.1.

## Hard gate results

- split groups spanning splits: 0
- identical content across splits: 0
- identical normalized pair across splits: 0
- near-duplicate premises (Jaccard >= 0.85, same hypothesis, different split): 0
- label-empty splits: []

## Orientation

- records: 917
- premises passing the canonical orientation guard: 917 / 917
- enforced structurally: `AgentPayIRv2Record` rejects a premise containing an authorization frame at construction time, so a regression cannot be reintroduced silently.

## Family distribution

| family | rows |
|---|---:|
| `aliases` | 22 |
| `ambiguous_evidence` | 23 |
| `automatic_renewal` | 19 |
| `brand_identity` | 37 |
| `bundles` | 25 |
| `currency` | 26 |
| `delivery_constraint` | 25 |
| `double_negation` | 17 |
| `equivalent_benign_wording` | 29 |
| `euphemistic_subscription` | 21 |
| `fulfillment_constraint` | 21 |
| `irrelevant_hostile_text` | 18 |
| `membership_insertion` | 23 |
| `merchant_description_manipulation` | 22 |
| `merchant_identity` | 27 |
| `misleading_negation` | 23 |
| `price_constraint` | 39 |
| `product_condition` | 41 |
| `product_equivalence` | 35 |
| `product_identity` | 53 |
| `product_title_manipulation` | 20 |
| `prompt_injection_like_merchant_text` | 27 |
| `quantity` | 27 |
| `quantity_units` | 24 |
| `recurring_subscription` | 29 |
| `return_condition` | 25 |
| `safe_lookalikes` | 20 |
| `safe_paraphrases` | 25 |
| `seller_authorization` | 20 |
| `seller_identity` | 26 |
| `semantic_fees` | 24 |
| `shipping_obligation` | 23 |
| `trial_to_paid_renewal` | 24 |
| `variant` | 36 |
| `warranty_condition` | 21 |

