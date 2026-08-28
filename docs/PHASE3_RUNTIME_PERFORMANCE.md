# Phase-3 semantic runtime performance (real v2 artifact)

Generated: `2026-08-28T14:40:14.904984+00:00` by `scripts/rzp_benchmark_semantic_runtime.py`.

- cold model load: **0.61s** (one-time per backend process; the API
  keeps the verifier in a per-process cache, so requests never reload it)
- warm pair latency: p50 **51.9ms**, p95 **65.1ms** (n=40)
- full semantic-stage latency by pair count: 1 pairs -> 51.0ms, 5 pairs -> 242.4ms, 10 pairs -> 524.5ms
- peak process RSS: **792.3 MiB** (model weights are 703.5 MB on disk — the cost is stated, not hidden)
- device: CPU, 6 threads (MPS not enabled; parity not benchmarked)

Decision: local CPU runtime is adequate for the acceptance flow; no cloud/
Modal inference is introduced (correction brief §16).
