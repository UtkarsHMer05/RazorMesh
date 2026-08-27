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

import argparse
import json
import statistics
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

from razormesh_api.compiler_eval import (
    EVALUATOR_VERSION,
    Expectation,
    evaluate_case,
    golden_sha256,
    payload_field_counts,
)
from razormesh_api.domain.intent_draft import CompilerIntentPayload

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


def _load_rows(path: Path = RESULTS) -> list[dict]:
    rows: dict[str, dict] = {}
    for line in path.read_text().splitlines():
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


def field_metrics(final: list[dict], golden: list[dict]) -> dict[str, dict]:
    """Recover only measures identifiable from preserved verdicts, not missing payloads.

    Scalar v1 'omissions' mean absent OR wrong-present. Set differences preserve
    brand/merchant cardinality; semantic truth contains only substring probes.
    """
    by_id = {c["case_id"]: c["expected"] for c in golden}
    result = {}
    for field in OMISSION_KEYS:
        expected = correct = invented = 0
        payload_present = 0
        present_known = True
        for row in final:
            exp = by_id[row["case_id"]]
            if "payload" in row:
                payload = (
                    CompilerIntentPayload.model_validate(row["payload"])
                    if row["payload"]
                    else None
                )
                counts = payload_field_counts(payload, Expectation.model_validate(exp))[
                    field
                ]
                expected += counts.expected
                correct += counts.correct
                if counts.present is None:
                    present_known = False
                else:
                    payload_present += counts.present
                continue
            if field in {"brands", "merchants"}:
                key = "brands" if field == "brands" else "merchant_allowlist"
                count = len({v.strip().lower() for v in exp.get(key, [])})
            elif field == "semantic":
                count = len(exp.get("semantic_must_contain", []))
            elif field == "unspecified":
                count = len(exp.get("unspecified_contains", []))
            elif field == "currency":
                count = int(
                    exp.get("max_amount_minor") is not None and bool(exp.get(field))
                )
            else:
                count = int(exp.get(field) is not None)
            expected += count
            problems = row["omissions"] + row["mismatches"]
            if field in {"brands", "merchants"}:
                missing = sum(
                    len(p.split(":", 1)[1].split(","))
                    for p in problems
                    if p.startswith(field + ":")
                )
                invented += sum(
                    len(p.split(":", 1)[1].split(","))
                    for p in row["inventions"]
                    if p.startswith(field + ":")
                )
            else:
                missing = sum(_key(p) == field for p in problems)
                present_known = False
            correct += max(0, count - missing) if row["status"] == "OK" else 0
        legacy_correct = 0
        if field in {"brands", "merchants"}:
            legacy_correct = correct - sum(
                payload_field_counts(
                    CompilerIntentPayload.model_validate(r["payload"])
                    if r["payload"]
                    else None,
                    Expectation.model_validate(by_id[r["case_id"]]),
                )[field].correct
                for r in final
                if "payload" in r
            )
        present = payload_present + legacy_correct + invented if present_known else None
        result[field] = {
            "expected_instances": expected,
            "correct_expected_instances": correct,
            "present_instances": present,
            "precision": round(correct / present, 4) if present else None,
            "recall": round(correct / expected, 4) if expected else None,
            "scope": (
                "explicitly annotated scalar expectations / normalized entity-set members"
                if present is not None
                else "expected field/probe exact-match recall only; present denominator unavailable"
            ),
        }
    return result


def repair_metrics(final: list[dict]) -> dict:
    repaired = [r for r in final if r["attempts"] > 1]
    valid = [r for r in repaired if r["status"] == "OK"]
    return {
        "cases_needing_repair": len(repaired),
        "evaluated_cases": len(final),
        "repair_rate": round(len(repaired) / len(final), 4) if final else None,
        "repaired_to_valid": len(valid),
        "failed_after_repair": len(repaired) - len(valid),
        "repair_success_rate": round(len(valid) / len(repaired), 4)
        if repaired
        else None,
    }


def scalar_mismatch_details(final: list[dict], golden: list[dict]) -> dict:
    """Observed direction, not a judgment that a different bound is safer or correct."""
    by_id = {c["case_id"]: c["expected"] for c in golden}
    details: dict[str, list[dict]] = {
        k: [] for k in ("max_amount_minor", "currency", "quantity_max")
    }
    for row in final:
        if not row.get("payload"):
            continue
        payload = CompilerIntentPayload.model_validate(row["payload"])
        expected = by_id[row["case_id"]]
        amount = payload.hard.max_amount
        actuals = {
            "max_amount_minor": amount.amount_minor if amount else None,
            "currency": amount.currency if amount else None,
            "quantity_max": payload.hard.quantity_max,
        }
        for field, actual in actuals.items():
            wanted = expected.get(field)
            if (
                wanted is None
                or wanted == "UNSPECIFIED"
                or actual is None
                or actual == wanted
            ):
                continue
            item = {"case_id": row["case_id"], "expected": wanted, "actual": actual}
            if field == "currency":
                item["direction"] = "different_currency"
            else:
                item["delta"] = actual - wanted
                item["direction"] = "lower" if actual < wanted else "higher"
            details[field].append(item)
    return {
        field: {
            "count": len(items),
            "directions": dict(Counter(i["direction"] for i in items)),
            "cases": items,
        }
        for field, items in details.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sample", nargs="?", type=int)
    parser.add_argument("--results", type=Path, default=RESULTS)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    if args.output.resolve() in {
        args.results.resolve(),
        RESULTS.resolve(),
        GOLDEN.resolve(),
        MANIFEST.resolve(),
    }:
        raise ValueError(
            "summary output must not overwrite raw results or golden truth"
        )
    sample_n = args.sample
    rows = _load_rows(args.results)
    golden = _load_golden()
    manifest = json.loads(MANIFEST.read_text())
    golden_by_id = {c["case_id"]: c for c in golden}
    unknown_ids = {r["case_id"] for r in rows} - set(golden_by_id)
    if unknown_ids:
        raise ValueError(f"unknown case IDs: {sorted(unknown_ids)}")
    if manifest["sha256"] != golden_sha256(GOLDEN) or manifest["cases"] != len(golden):
        raise ValueError("golden manifest does not match current truth")
    provenance_seen: set[str] = set()
    for row in rows:
        if "payload" not in row and not row.get("evaluator_version"):
            continue  # Preserved legacy evidence has explicitly limited metrics.
        if row.get("evaluator_version") != EVALUATOR_VERSION or "payload" not in row:
            raise ValueError("unsupported evaluator or missing payload evidence")
        provenance = row.get("provenance", {})
        if provenance.get("golden_sha256") != manifest["sha256"]:
            raise ValueError("result provenance does not match current golden truth")
        if row["case_id"] not in provenance.get("case_ids", []):
            raise ValueError("result case ID absent from run provenance")
        provenance_seen.add(json.dumps(provenance, sort_keys=True))
    if len(provenance_seen) > 1:
        raise ValueError("mixed run provenance; summarize runs separately")
    # Payload-backed rows can be rescored without another provider request.
    for row in rows:
        if "payload" in row:
            payload = (
                CompilerIntentPayload.model_validate(row["payload"])
                if row["payload"]
                else None
            )
            verdict = evaluate_case(
                payload,
                Expectation.model_validate(golden_by_id[row["case_id"]]["expected"]),
            )
            row.update(
                passed=verdict.passed,
                omissions=list(verdict.omissions),
                mismatches=list(verdict.mismatches),
                inventions=list(verdict.inventions),
            )
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

    recovered_fields = field_metrics(final, golden)
    legacy_rows = [r for r in final if not r.get("evaluator_version")]

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
            "complete": sample_n is None
            and {r["case_id"] for r in final} == set(golden_by_id),
            "provider_noise_rows_excluded": len(noise),
        },
        "schema_validity": {
            "ok": len(ok),
            "failed": len(failed),
            "schema_valid_rate": round(len(ok) / n, 4) if n else None,
            "failure_codes": dict(Counter(r.get("error_code") for r in failed)),
        },
        "repair": repair_metrics(final),
        "case_pass": {
            "passed": len(passed),
            "pass_rate": round(len(passed) / n, 4) if n else None,
            "by_difficulty": by_difficulty,
            "by_category": by_category,
        },
        "evidence_limits": {
            "legacy_verdict_only_rows": len(legacy_rows),
            "payload_rows": sum(r.get("payload") is not None for r in final),
            "rescored": not legacy_rows and bool(final),
            "payload_backed_rows_rescored": sum("payload" in r for r in final),
            "note": "Legacy rows conflate absent/wrong-present values: precision and exact omission split unknown. Payload-backed rows are rescored with v2 within explicitly annotated truth. Final-row counts do not measure provider failure rate.",
        },
        "field_metrics": recovered_fields,
        "field_recall": {k: v["recall"] for k, v in recovered_fields.items()},
        "field_precision": {k: v["precision"] for k, v in recovered_fields.items()},
        "numeric_correctness": {
            "count_scope": "Omissions/substitutions count valid payloads only; whole-output failures are separate.",
            "expected_money_cases": expected_instances.get("max_amount_minor", 0),
            "amount_omissions_or_substitutions": omission_counter.get(
                "max_amount_minor", 0
            )
            + mismatch_counter.get("max_amount_minor", 0),
            "currency_omissions_or_substitutions": omission_counter.get("currency", 0)
            + mismatch_counter.get("currency", 0),
            "amount_omissions": None
            if legacy_rows
            else omission_counter.get("max_amount_minor", 0),
            "currency_omissions": None
            if legacy_rows
            else omission_counter.get("currency", 0),
            "numeric_substitutions": None
            if legacy_rows
            else {
                k: mismatch_counter.get(k, 0)
                for k in ("max_amount_minor", "currency", "quantity_max")
            },
            "money_precision": recovered_fields["max_amount_minor"]["precision"],
        },
        "scalar_mismatch_details": scalar_mismatch_details(final, golden),
        "valid_output_omissions": None if legacy_rows else dict(omission_counter),
        "whole_output_failures": {
            "cases": len(failed),
            "case_ids": [r["case_id"] for r in failed],
            "expected_instances_without_output": {
                k: v["expected_instances"]
                for k, v in field_metrics(failed, golden).items()
            },
            "note": "Absent complete outputs reduce all-case recall; not classified as individual valid-output omissions.",
        },
        "valid_output_field_metrics": field_metrics(ok, golden),
        "legacy_omission_classifications": dict(omission_counter),
        "unsafe_omissions": None if legacy_rows else dict(omission_counter),
        "payload_backed_field_metrics": field_metrics(
            [r for r in final if "payload" in r], golden
        ),
        "hallucinated_constraints": dict(invention_counter),
        "hallucination_case_count": sum(bool(r["inventions"]) for r in final),
        "hallucination_case_rate": round(
            sum(bool(r["inventions"]) for r in final) / n, 4
        )
        if n
        else None,
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
    args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary["coverage"], indent=2))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
