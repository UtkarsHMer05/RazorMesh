# Cross-Split Near-Duplicate + Template-Family Overlap Report

**Corpus:** AgentPay-IR v2 frozen splits — 13843 train / 2312 val / 2261 test · near-dup rule: Jaccard >= 0.85 (premise+hypothesis tokens) inside shared template families

| direction | exact pair overlap | same premise | same hypothesis | shared TFs | near-dup pairs | max J |
|---|---|---|---|---|---|---|
| train<->val | 0 | 8 | 144 | 30 | 389 | 1.00 |
| train<->test | 0 | 1 | 134 | 26 | 414 | 1.00 |
| val<->test | 0 | 2 | 112 | 22 | 44 | 0.95 |

## ContractNLI fixed-hypothesis exception (documented)

- distinct ContractNLI hypotheses: **17**; appearing in more than one split: **17**.
- Same-hypothesis overlap across splits is therefore EXPECTED for the ContractNLI
  component (fixed clause hypotheses shared by many documents). It cannot be
  template-held-out without discarding the real human NLI data. Per the correction
  contract, **human-gold review cards and the untouched OOD set are the stronger
  generalization benchmarks** for these families.

## Zero-tolerance facts (must be 0)

- train<->val: exact pair overlap = 0, shared split groups = 0, shared entity families = 0
- train<->test: exact pair overlap = 0, shared split groups = 0, shared entity families = 0
- val<->test: exact pair overlap = 0, shared split groups = 0, shared entity families = 0

Near-duplicate pairs inside shared template families remain a TEMPLATE_OVERFIT_RISK
indicator for the v2 training read (see QUALITY_GATES.json); they are disclosed,
not hidden, and are cross-checked against the frozen selection rule at calibration.
