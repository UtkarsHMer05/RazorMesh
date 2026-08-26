# Phase-3 Adversarial/OOD Dataset Review — P3-M24

Date: 2026-08-27  
Status: PASS (standalone closure re-audit)  
Artifact: `data/phase3/dataset/adversarial/adversarial_dataset.jsonl`  
SHA-256: `25dfae0ddc429dbaa0d3ed722da23fa511499f9a6049dc01aacd07c12e1e89d2`

## Closure finding

The prior artifact was not a defensible adversarial expansion: it contained 38
rows, had no neutral relation, placed 32/38 rows in only injection and renewal
templates, and did not identify sibling source groups. It was replaced rather
than relabeled PASS.

The v2 artifact contains 129 hard, human-authored, truth-by-construction rows:
43 independent semantic scenarios × one entailment, neutral and contradiction
relation. Each three-row sibling set has one `source_case_id`, so group splitting
cannot place relation siblings in different splits.

## Coverage and anti-dominance evidence

| Measure | Result |
|---|---:|
| Records | 129 |
| Independent scenario/subfamily groups | 43 |
| Labels | 43 entailment / 43 neutral / 43 contradiction |
| AgentPay semantic families | 18/18 |
| Difficulty | 129 hard |
| Largest semantic-family share | 9.3023% |
| Rows per authored scenario | 3 |
| Exact/near duplicate rejections at Jaccard 0.90 | 0 |
| Cross-class near collisions | 0 |
| Fatal M21 quality findings | 0 |
| Leakage-safe split preview | PASS (train 87 / val 9 / test 33) |
| Secret scan | 0 findings |

The 43 scenario families include euphemistic recurring care, no-charge-today
conversion, cancellation-window traps, double negation, membership insertion,
mandatory service/accessory/gift obligations, Unicode seller homoglyphs, legal
entity aliases, fulfilled-vs-sold ambiguity, reseller chains, refurbished/open-
box/renewed/demo disguises, storage/region/model/color variants, late shipping,
tax-excluded totals, dynamic conversion, localized separators, coupon/pack/BOGO
quantity traps, three prompt-injection-style authority overrides, four benign
lookalike controls, return/refund ambiguity, signature/preorder delivery,
third-party/double-negative warranty and parent-brand confusion.

Three expected non-fatal validator warnings come from the `fake_system_approval`
premises. Those premises deliberately contain false merchant authority claims;
the hypotheses remain human-authorization statements. This preserves the
trusted-evidence/untrusted-content orientation.

## Volume and use boundary

The master prompt originally suggested 2k–4k M24 rows. The owner's closure
instruction explicitly prioritizes genuinely new adversarial/OOD families over
a numerical quota and rejects volume dominated by deterministic siblings. The
closure therefore uses 43 independently authored groups and a hard maximum of
three relation siblings per group rather than inflating the same text patterns.

These labels are `template_truth`, not human gold, and this artifact is not the
additional untouched human-reviewed OOD evaluation requested by the owner. It
may support training/validation only through the M22/M23/M27 gates. A separate
untouched OOD review set must be frozen and reviewed without retraining on it
before final Phase-3 acceptance.
