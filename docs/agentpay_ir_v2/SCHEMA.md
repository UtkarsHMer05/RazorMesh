# AgentPay-IR v2 — Record Schema (frozen)

`schema_version: "agentpay-ir-v2"`

Canonical orientation (non-negotiable): premise = current sanitized commerce/merchant/checkout
evidence; hypothesis = normalized human-confirmed authorization constraint.

| field | type | notes |
|---|---|---|
| record_id | string | `ap2_` + 26-hex content-derived |
| schema_version | string | `agentpay-ir-v2` |
| premise | string | evidence only; authorization prose forbidden (validator-enforced) |
| hypothesis | string | normalized human authorization constraint |
| label | enum | contradiction \| entailment \| neutral |
| family / subfamily | string | semantic family; subfamily is rule-level |
| authorization_field | string | trusted field the hypothesis constrains |
| evidence_field | string | evidence field the premise carries |
| source_dataset | string | contractnli \| esci \| razormesh_frozen_v2 \| razormesh_internal_adversarial |
| source_record_id | string | upstream id |
| source_license | string | CC BY 4.0 \| Apache-2.0 \| project-internal |
| source_kind | enum | real_human_nli \| real_commerce \| human_reviewed \| deterministic_derived \| synthetic_adversarial |
| generator_parent_id / template_family_id / entity_family_id / safe_lookalike_family_id | string | provenance + grouping |
| split_group | string | unit that splits must never divide |
| difficulty | enum | easy \| medium \| hard |
| safe_or_attack | enum | safe \| attack \| ambiguous |
| content_sha256 | string | sha256(premise␟hypothesis␟label␟"canonical") |
| metadata | object | provenance extras (never secrets/PII) |

No secrets, raw payment credentials, or personal data may enter any record.
Label map (upstream model): 0=contradiction, 1=entailment, 2=neutral.
