#!/usr/bin/env python3
"""P3-M15: aggregate compiler-eval results into summary.json.

Reads data/phase3/compiler_eval/results.jsonl (resumable runner output,
last-row-per-case wins) plus the golden manifest, and computes the metrics
required by the master prompt M15: schema validity, field precision/recall,
numeric correctness, unsafe omission, hallucinated/over constraints,
ambiguity handling, repair/failure rate and latency.

No model calls, no network, no authority. Run from the repository root:

    uv run --project services/api python scripts/rzp_summarize_compiler_eval.py [N]

With no argument, metrics cover every final row (full-set mode). With N,
metrics are restricted to the deterministic stratified-N sample (D-041) —
the same round-robin selection the runner uses.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN = REPO_ROOT / "data" / "phase3" / "compiler_golden" / "golden_set.jsonl"
MANIFEST = REPO_ROOT / "data" / "phase3" / "compiler_golden" / "manifest.json"
RESULTS = REPO_ROOT / "data" / "phase3" / "compiler_eval" / "results.jsonl"
OUT = REPO_ROOT / "data" / "phase3" / "compiler_eval" / "summary.json"

OMISSION_KEYS = (
    "max_amount_minor",
    "currency",
    "quantity_max",
    "brands",
    "merchants",
    "recurring_forbidden",
    "semantic",
    "unspecified",
)


def _load_rows() -> list[dict]:
    rows: dict[str, dict] = {}
    for line in RESULTS.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows[row["case_id"]] = row  # last row wins
    return sorted(rows.values(), key=lambda r: r["case_id"])


def _load_golden() -> list[dict]:
    cases = []
    for line in GOLDEN.read_text().splitlines():
        if line.strip():
            cases.append(json.loads(line))
    return cases


def _key(problem: str) -> str:
    for k in OMISSION_KEYS:
        if problem.startswith(k):
            return k
    if problem.startswith("invented:"):
        return problem.split(":", 1)[1]
    if problem.startswith("money_without_human_statement"):
        return "money_unstated"
    return problem.split(":", 1)[0]


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, round(pct / 100.0 * (len(ordered) - 1)))
    return ordered[idx]


def _stratified_ids(cases: list[dict], n: int) -> set[str]:
    """Same deterministic round-robin selection as the runner's stratified()."""
    by_cat: dict[str, list[dict]] = {}
    for c in cases:
        by_cat.setdefault(c["category"], []).append(c)
    picked: list[dict] = []
    cats = sorted(by_cat)
    i = 0
    while len(picked) < n:
        progressed = False
        for cat in cats:
            bucket = by_cat[cat]
            if i < len(bucket):
                picked.append(bucket[i])
                progressed = True
                if len(picked) >= n:
                    break
        if not progressed:
            break
        i += 1
    return {c["case_id"] for c in picked}


def main() -> int:
    sample_n = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = _load_rows()
    golden = _load_golden()
    manifest = json.loads(MANIFEST.read_text())
    golden_by_id = {c["case_id"]: c for c in golden}
    if sample_n is not None:
        selection = _stratified_ids(golden, sample_n)
        rows = [r for r in rows if r["case_id"] in selection]

    # Provider-noise rows (COMPILER_UNAVAILABLE) are retryable non-results;
    # they are excluded from metrics and reported separately.
    noise = [r for r in rows if r.get("error_code") == "COMPILER_UNAVAILABLE"]
    final = [r for r in rows if r.get("error_code") != "COMPILER_UNAVAILABLE"]

    n = len(final)
    ok = [r for r in final if r["status"] == "OK"]
    failed = [r for r in final if r["status"] != "OK"]
    passed = [r for r in final if r["passed"]]
    repaired = [r for r in ok if r["attempts"] > 1]
    latencies = [r["latency_ms"] for r in ok]

    omission_counter: Counter[str] = Counter()
    invention_counter: Counter[str] = Counter()
    mismatch_counter: Counter[str] = Counter()
    for r in final:
        omission_counter.update(_key(p) for p in r["omissions"])
        invention_counter.update(_key(p) for p in r["inventions"])
        mismatch_counter.update(_key(p) for p in r["mismatches"])

    # Expected-instance counts from manual truth (denominators for recall).
    expected_instances: Counter[str] = Counter()
    ambiguity_expected_cases = 0
    final_ids = {r["case_id"] for r in final}
    for c in golden:
        if c["case_id"] not in final_ids:
            continue
        exp = c["expected"]
        if exp.get("max_amount_minor") is not None:
            expected_instances["max_amount_minor"] += 1
            expected_instances["currency"] += 1
        if exp.get("quantity_max") is not None:
            expected_instances["quantity_max"] += 1
        expected_instances["brands"] += len(exp.get("brands", []))
        expected_instances["merchants"] += len(exp.get("merchant_allowlist", []))
        if exp.get("recurring_forbidden") is not None:
            expected_instances["recurring_forbidden"] += 1
        expected_instances["semantic"] += len(exp.get("semantic_must_contain", []))
        expected_instances["unspecified"] += len(exp.get("unspecified_contains", []))
        if exp.get("min_ambiguities", 0) > 0:
            ambiguity_expected_cases += 1

    def _recall(key: str) -> float | None:
        denom = expected_instances.get(key, 0)
        if denom == 0:
            return None
        return round(1.0 - omission_counter.get(key, 0) / denom, 4)

    # Precision: correct extractions / (correct + invented). Correct instances
    # = expected instances minus omissions (per field family).
    invented_money = invention_counter.get("money_unstated", 0)
    correct_money = max(
        0,
        expected_instances.get("max_amount_minor", 0)
        - omission_counter.get("max_amount_minor", 0),
    )
    money_precision = (
        round(correct_money / (correct_money + invented_money), 4)
        if correct_money + invented_money
        else None
    )

    ambiguity_ok = [
        r
        for r in final
        if golden_by_id.get(r["case_id"], {})
        .get("expected", {})
        .get("min_ambiguities", 0)
        > 0
        and not any(m.startswith("ambiguities<") for m in r["mismatches"])
        and r["status"] == "OK"
    ]

    by_difficulty: dict[str, dict] = {}
    for diff in ("easy", "medium", "hard"):
        sub = [r for r in final if r["difficulty"] == diff]
        if sub:
            by_difficulty[diff] = {
                "n": len(sub),
                "passed": sum(1 for r in sub if r["passed"]),
                "pass_rate": round(sum(1 for r in sub if r["passed"]) / len(sub), 4),
                "schema_ok": sum(1 for r in sub if r["status"] == "OK"),
            }

    by_category: dict[str, dict] = {}
    for cat in sorted({r["category"] for r in final}):
        sub = [r for r in final if r["category"] == cat]
        by_category[cat] = {
            "n": len(sub),
            "passed": sum(1 for r in sub if r["passed"]),
            "pass_rate": round(sum(1 for r in sub if r["passed"]) / len(sub), 4),
        }

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "golden_set": {
            "cases": manifest["cases"],
            "sha256": manifest["sha256"],
            "truth_source": manifest["truth_source"],
        },
        "coverage": {
            "final_rows": n,
            "of_golden": manifest["cases"],
            "sample": sample_n,
            "complete": sample_n is None and n >= manifest["cases"],
            "provider_noise_rows_excluded": len(noise),
        },
        "schema_validity": {
            "ok": len(ok),
            "failed": len(failed),
            "schema_valid_rate": round(len(ok) / n, 4) if n else None,
            "failure_codes": dict(Counter(r.get("error_code") for r in failed)),
        },
        "repair": {
            "cases_needing_repair": len(repaired),
            "repair_rate": round(len(repaired) / len(ok), 4) if ok else None,
            "repaired_to_valid": len(repaired),
        },
        "case_pass": {
            "passed": len(passed),
            "pass_rate": round(len(passed) / n, 4) if n else None,
            "by_difficulty": by_difficulty,
            "by_category": by_category,
        },
        "field_recall": {k: _recall(k) for k in sorted(expected_instances)},
        "numeric_correctness": {
            "expected_money_cases": expected_instances.get("max_amount_minor", 0),
            "amount_omissions": omission_counter.get("max_amount_minor", 0),
            "currency_omissions": omission_counter.get("currency", 0),
            "money_precision": money_precision,
        },
        "unsafe_omissions": dict(omission_counter),
        "hallucinated_constraints": dict(invention_counter),
        "mismatches": dict(mismatch_counter),
        "ambiguity_handling": {
            "cases_requiring_ambiguity": ambiguity_expected_cases,
            "satisfied": len(ambiguity_ok),
        },
        "latency_ms": {
            "p50": round(_percentile(latencies, 50), 1),
            "p95": round(_percentile(latencies, 95), 1),
            "max": round(max(latencies), 1) if latencies else None,
            "mean": round(statistics.fmean(latencies), 1) if latencies else None,
        },
    }
    OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary["coverage"], indent=2))
    print(f"wrote {OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
