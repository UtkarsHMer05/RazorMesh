# AgentPay-IR v2 Quality Gates

Corpus: `/Users/utkarshkhajuria/Desktop/RazorMesh/data/agentpay_ir_v2/corpus` · train rows: 13843

**Honest composition:** train is 95.3% real/human-derived and 4.7% targeted deterministic internal security/domain data.

- Lexical shortcut tokens (>=12 occurrences, single label): **143** (top: [{'token': 'stripes', 'label': 'entailment', 'count': 77}, {'token': 'lawfully', 'label': 'entailment', 'count': 59}, {'token': 'rightfully', 'label': 'entailment', 'count': 53}, {'token': 'ftwr', 'label': 'entailment', 'count': 52}, {'token': 'scooter', 'label': 'entailment', 'count': 46}])
- Distinct hypothesis templates (80-char normalized): **325**, top-10 share 41.1%
- Max single premise-prefix reuse: **15**
- Near-duplicate (Jaccard>=0.85) within-split, family-bucketed: train=187, val=454, test=528
- Families covered: **34** (in all three splits: 21)

Full machine-readable report: QUALITY_GATES.json
