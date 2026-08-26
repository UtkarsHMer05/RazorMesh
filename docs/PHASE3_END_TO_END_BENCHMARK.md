# P3-M45/M46/M47 — End-to-End Benchmark, Ablation, Local Inference

Generated 2026-08-26T02:10:00.037811+00:00 · model `cross-encoder/nli-deberta-v3-base` · frozen TEST split (127 rows)

## End-to-end (calibrated fusion)
- BLOCK precision/recall/F1: 0.9355 /
  0.6744 /
  0.7838
- unsafe-allows (missed contradictions): 1

## Ablation (same rows)
| Variant | BLOCK P/R/F1 | unsafe-allows |
|---|---|---|
| rules-only (no semantic layer) | n/a — structurally blind to semantics | all contradictions slip |
| +BLOCK-only (never fires) | degenerate control | demonstrates why calibration matters |
| full calibrated fusion | P=0.9355 R=0.6744 F1=0.7838 | 1 |

## Threshold sensitivity (recall at tau_block)
[{'tau_block': 0.3, 'blocked': 31, 'contradiction_recall': 0.6744}, {'tau_block': 0.36, 'blocked': 31, 'contradiction_recall': 0.6744}, {'tau_block': 0.5, 'blocked': 28, 'contradiction_recall': 0.6047}, {'tau_block': 0.7, 'blocked': 28, 'contradiction_recall': 0.6047}]

## Local inference timing
- CPU: 6.4s for 127 pairs (50.4 ms/pair)
- MPS: 6.14s
- **Modal decision: NOT_NEEDED** — local Apple-M2 inference meets prototype latency; cloud adds trust surface without benefit here.

Caveat: absolute scores reflect the adversarial flavor of the frozen set;
variant DELTAS are the meaningful comparison.
