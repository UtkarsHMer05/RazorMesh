# P3-M45/M46/M47 — End-to-End Benchmark, Ablation, Local Inference

Generated 2026-08-26T18:01:12.616170+00:00 · model `phase3-finetuned-cross-encoder` · frozen TEST split (127 rows)

## End-to-end (calibrated fusion)
- BLOCK precision/recall/F1: 0.9773 /
  1.0 /
  0.9885
- unsafe-allows (missed contradictions — model allowed a human contradiction): **0**
- conservative over-blocks (gold=neutral, model=BLOCK, fusion BLOCK — safe
  refusal, NOT an allow): 1

> Terminology correction (closure audit): the earlier "1 unsafe-allow" wording
> was wrong. The single remaining error is gold=neutral / model=BLOCK, i.e. a
> conservative false block. BLOCK is the fail-closed safe outcome; it is never
> counted as an unsafe allow.

## Ablation (same rows)
| Variant | BLOCK P/R/F1 | unsafe-allows |
|---|---|---|
| rules-only (no semantic layer) | n/a — structurally blind to semantics | all contradictions slip |
| +BLOCK-only (never fires) | degenerate control | demonstrates why calibration matters |
| full calibrated fusion | P=0.9773 R=1.0 F1=0.9885 | 0 unsafe / 1 over-block |

## Threshold sensitivity (recall at tau_block)
[{'tau_block': 0.3, 'blocked': 44, 'contradiction_recall': 1.0}, {'tau_block': 0.4, 'blocked': 44, 'contradiction_recall': 1.0}, {'tau_block': 0.5, 'blocked': 44, 'contradiction_recall': 1.0}, {'tau_block': 0.6, 'blocked': 44, 'contradiction_recall': 1.0}, {'tau_block': 0.7, 'blocked': 44, 'contradiction_recall': 1.0}, {'tau_block': 0.8, 'blocked': 44, 'contradiction_recall': 1.0}, {'tau_block': 0.9, 'blocked': 44, 'contradiction_recall': 1.0}]

## Local inference timing
- CPU: 8.24s for 127 pairs (64.9 ms/pair)
- MPS: 5.81s
- **Modal decision: NOT_NEEDED** — local Apple-M2 inference meets prototype latency; cloud adds trust surface without benefit here.

Caveat: absolute scores reflect the adversarial flavor of the frozen set;
variant DELTAS are the meaningful comparison.
