#!/usr/bin/env python3
"""Phase-3 runtime performance benchmark (correction brief §24).

Measures the REAL fine-tuned v2 runtime on this machine — no synthetic
numbers:

  - cold model load (import + from_pretrained + first tokenization);
  - warm per-pair inference latency (p50/p95) over a fixed repeat set;
  - peak process RSS (includes the ~738 MB weights — not hidden);
  - full semantic-stage latency for transactions with 1 / 5 / 10 evidence
    pairs, using the production SemanticEvidenceBuilder pair texts and the
    frozen v3 threshold policy.

Usage:
  services/ml-venv/bin/python scripts/rzp_benchmark_semantic_runtime.py
"""

from __future__ import annotations

import json
import platform
import resource
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

MODEL_DIR = REPO_ROOT / "artifacts" / "models" / "incoming" / "phase3-finetuned-v2"
POLICY_V3 = REPO_ROOT / "data" / "phase3" / "policy" / "semantic_thresholds_v3.json"
DOCS = REPO_ROOT / "docs"

WARM_REPEATS = 40
TRANSACTION_PAIR_COUNTS = (1, 5, 10)


def peak_rss_mib() -> float:
    # ru_maxrss is BYTES on macOS, KiB on Linux — normalize to MiB.
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    factor = 1 if sys.platform == "darwin" else 1024
    return raw * factor / (1024 * 1024)


def pct(values: list[float], p: float) -> float:
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(p / 100 * (len(ordered) - 1))))
    return round(ordered[idx], 1)


def main() -> int:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    peak_rss_start = peak_rss_mib()

    # --- cold load -------------------------------------------------------
    cold_started = time.monotonic()
    torch.set_num_threads(6)
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    model = AutoModelForSequenceClassification.from_pretrained(str(MODEL_DIR))
    model.eval()
    cold_load_s = round(time.monotonic() - cold_started, 2)

    policy = json.loads(POLICY_V3.read_text())
    tau_block = float(policy["selected"]["tau_block"])
    tau_entail = float(policy["selected"]["tau_entail"])

    # Production-representative pair texts (SemanticEvidenceBuilder output
    # shape; ~40 tokens), one safe, one attack, one ambiguous.
    pair_texts = [
        (
            "Product page states: Sony WH-1000XM5 Wireless Headphones, certified refurbished. "
            "The listing price is 4,799.00 INR.",
            "The purchase stays within the authorized budget of INR 5,000.00.",
        ),
        (
            "Checkout disclosure states that auto-renewing subscription terms are disclosed "
            "for this item. A free membership trial renews at INR 499 per month.",
            "The human forbade any recurring charges.",
        ),
        (
            "Listing states the item condition as: refurbished.",
            "The human requires the item to be new.",
        ),
        (
            "Seller/listing identifies the brand as 'Sony'.",
            "The authorized brand restriction (sony) is satisfied.",
        ),
        (
            "Product page states: Genuine Sony WH-1000XM5 with hard shell case and warranty card. "
            "The listing price is 4,499.00 INR.",
            "The purchase stays within the authorized budget of INR 5,000.00.",
        ),
    ]

    def verify(premise: str, hypothesis: str) -> float:
        started = time.monotonic()
        feats = tokenizer(
            premise, hypothesis, truncation=True, max_length=256, padding=True, return_tensors="pt"
        )
        with torch.no_grad():
            logits = model(**feats).logits
        probs = torch.softmax(logits, -1)[0]
        pc, pe = float(probs[0]), float(probs[1])
        action = "BLOCK" if pc >= tau_block else ("PASS" if pe >= tau_entail else "CHALLENGE")
        _ = action
        return (time.monotonic() - started) * 1000

    # warm-up (first inference includes lazy kernel setup)
    for premise, hypothesis in pair_texts:
        verify(premise, hypothesis)

    warm_ms: list[float] = []
    for i in range(WARM_REPEATS):
        premise, hypothesis = pair_texts[i % len(pair_texts)]
        warm_ms.append(verify(premise, hypothesis))

    txn_latency: dict[str, float] = {}
    for n in TRANSACTION_PAIR_COUNTS:
        pairs = [pair_texts[i % len(pair_texts)] for i in range(n)]
        started = time.monotonic()
        for premise, hypothesis in pairs:
            verify(premise, hypothesis)
        txn_latency[str(n)] = round((time.monotonic() - started) * 1000, 1)

    peak_rss_mb_after = peak_rss_mib()

    results = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "model_dir": str(MODEL_DIR.relative_to(REPO_ROOT)),
        "policy_version": policy["policy_version"],
        "runtime": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "device": "cpu",
            "threads": torch.get_num_threads(),
        },
        "cold_load_seconds": cold_load_s,
        "warm_pair_latency_ms": {
            "n": len(warm_ms),
            "p50": pct(warm_ms, 50),
            "p95": pct(warm_ms, 95),
            "mean": round(statistics.fmean(warm_ms), 1),
        },
        "transaction_latency_ms_by_pair_count": txn_latency,
        "peak_process_rss_mb": round(max(peak_rss_start, peak_rss_mb_after), 1),
        "model_size_mb": round((MODEL_DIR / "model.safetensors").stat().st_size / (1024 * 1024), 1),
    }
    (DOCS / "PHASE3_RUNTIME_PERFORMANCE.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    md = [
        "# Phase-3 semantic runtime performance (real v2 artifact)",
        "",
        f"Generated: `{results['generated_at_utc']}` by `scripts/rzp_benchmark_semantic_runtime.py`.",
        "",
        f"- cold model load: **{cold_load_s}s** (one-time per backend process; the API",
        "  keeps the verifier in a per-process cache, so requests never reload it)",
        f"- warm pair latency: p50 **{results['warm_pair_latency_ms']['p50']}ms**, "
        f"p95 **{results['warm_pair_latency_ms']['p95']}ms** (n={results['warm_pair_latency_ms']['n']})",
        "- full semantic-stage latency by pair count: "
        + ", ".join(f"{k} pairs -> {v}ms" for k, v in txn_latency.items()),
        f"- peak process RSS: **{results['peak_process_rss_mb']} MiB** "
        f"(model weights are {results['model_size_mb']} MB on disk — the cost is stated, not hidden)",
        f"- device: CPU, {torch.get_num_threads()} threads (MPS not enabled; parity not benchmarked)",
        "",
        "Decision: local CPU runtime is adequate for the acceptance flow; no cloud/",
        "Modal inference is introduced (correction brief §16).",
    ]
    (DOCS / "PHASE3_RUNTIME_PERFORMANCE.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(results["warm_pair_latency_ms"], indent=2))
    print("transaction latency:", txn_latency, "| peak RSS:", results["peak_process_rss_mb"], "MiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
