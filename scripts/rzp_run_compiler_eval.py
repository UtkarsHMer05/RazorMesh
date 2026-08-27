#!/usr/bin/env python3
"""P3-M15: append-only, versioned real compiler evaluation (network opt-in CLI).

Historical compiler_eval/results.jsonl is immutable. New measurements default
to compiler_eval/v2; resume requires matching golden/prompt/model/schema settings.
Each service call is retained, including provider errors, without compaction.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

from razormesh_api.compiler_eval import (
    EVALUATOR_VERSION,
    GoldenCase,
    evaluate_case,
    golden_sha256,
    load_golden,
)
from razormesh_api.domain.intent_draft import SCHEMA_VERSION_VALUE
from razormesh_api.intent_compilation_service import IntentCompilationService
from razormesh_api.intent_compiler import TokenRouterClient
from razormesh_api.intent_compiler_prompt import (
    COMPILER_PROMPT_VERSION,
    TrustedHumanAuthorization,
    prompt_sha256,
)
from razormesh_api.settings import get_settings

GOLDEN = REPO_ROOT / "data" / "phase3" / "compiler_golden" / "golden_set.jsonl"
LEGACY = REPO_ROOT / "data" / "phase3" / "compiler_eval"
DEFAULT_OUTPUT = LEGACY / "v2"
BACKOFF_SECONDS = 30.0
MAX_CONSECUTIVE_PROVIDER_FAILS = 12


def stratified(cases: list[dict], n: int) -> list[dict]:
    by_cat: dict[str, list[dict]] = {}
    for case in cases:
        by_cat.setdefault(case["category"], []).append(case)
    picked = []
    index = 0
    while len(picked) < n:
        progressed = False
        for category in sorted(by_cat):
            bucket = by_cat[category]
            if index < len(bucket):
                picked.append(bucket[index])
                progressed = True
                if len(picked) == n:
                    break
        if not progressed:
            break
        index += 1
    return picked


def prepare_run(output: Path, provenance: dict) -> Path:
    output = output.resolve()
    if output == LEGACY.resolve():
        raise ValueError(
            "historical output directory is immutable; use a versioned directory"
        )
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / "run_manifest.json"
    results = output / "results.jsonl"
    if results.resolve() == (LEGACY / "results.jsonl").resolve():
        raise ValueError("historical result file is immutable")
    if manifest.exists():
        if json.loads(manifest.read_text()) != provenance:
            raise ValueError(
                "resume provenance mismatch; choose a new output directory"
            )
    elif results.exists():
        raise ValueError("refusing results without provenance")
    else:
        with manifest.open("x") as handle:
            handle.write(json.dumps(provenance, indent=2) + "\n")
    return results


def completed_ids(results: Path, known: set[str]) -> set[str]:
    done = set()
    if results.exists():
        for line in results.read_text().splitlines():
            row = json.loads(line)
            if row["case_id"] not in known:
                raise ValueError("result contains unknown case ID")
            if (
                row.get("evaluator_version") != EVALUATOR_VERSION
                or "payload" not in row
            ):
                raise ValueError("cannot mix historical verdict-only rows into v2")
            if row.get("error_code") != "COMPILER_UNAVAILABLE":
                done.add(row["case_id"])
    return done


def run_cases(
    service: IntentCompilationService,
    cases: list[GoldenCase],
    results: Path,
    provenance: dict,
) -> int:
    done = completed_ids(results, {case.case_id for case in cases})
    todo = [case for case in cases if case.case_id not in done]
    consecutive_failures = 0
    for index, case in enumerate(todo):
        for call_attempt in range(1, 5):
            start = time.monotonic()
            outcome = service.compile(TrustedHumanAuthorization(text=case.input_text))
            verdict = evaluate_case(outcome.payload, case.expected)
            row = {
                "case_id": case.case_id,
                "category": case.category,
                "difficulty": case.difficulty,
                "evaluator_version": EVALUATOR_VERSION,
                "provenance": provenance,
                "payload": outcome.payload.model_dump(mode="json")
                if outcome.payload
                else None,
                "status": outcome.status,
                "error_code": outcome.error_code,
                "attempts": outcome.attempts,
                "runner_call_attempt": call_attempt,
                "latency_ms": round((time.monotonic() - start) * 1000, 1),
                "passed": verdict.passed,
                "mismatches": list(verdict.mismatches),
                "omissions": list(verdict.omissions),
                "inventions": list(verdict.inventions),
                "request_ids": list(outcome.request_ids),
            }
            with results.open("a") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(
                f"[{index + 1}/{len(todo)}] {case.case_id} {outcome.status}", flush=True
            )
            if outcome.error_code != "COMPILER_UNAVAILABLE":
                consecutive_failures = 0
                done.add(case.case_id)
                break
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_PROVIDER_FAILS:
                return 5
            if call_attempt < 4:
                time.sleep(BACKOFF_SECONDS)
    return 0 if done == {case.case_id for case in cases} else 5


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sample", nargs="?", type=int)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.sample is not None and args.sample < 1:
        parser.error("sample must be positive")
    all_cases = load_golden(GOLDEN)
    cases = (
        [
            GoldenCase.model_validate(c)
            for c in stratified(
                [case.model_dump() for case in all_cases],
                args.sample,
            )
        ]
        if args.sample
        else all_cases
    )
    settings = get_settings()
    provenance = {
        "evaluator_version": EVALUATOR_VERSION,
        "golden_sha256": golden_sha256(GOLDEN),
        "prompt_version": COMPILER_PROMPT_VERSION,
        "prompt_sha256": prompt_sha256(),
        "schema_version": SCHEMA_VERSION_VALUE,
        "model": settings.planner_model,
        "max_output_tokens": 4000,
        "temperature": 0.0,
        "case_ids": sorted(case.case_id for case in cases),
    }
    results = prepare_run(args.output_dir, provenance)
    completed_ids(results, set(provenance["case_ids"]))
    if not settings.tokenrouter_credentials_present:
        raise ValueError("TOKENROUTER_API_KEY missing")
    client = TokenRouterClient(
        api_key=settings.tokenrouter_api_key.get_secret_value(),
        base_url=settings.tokenrouter_base_url,
        timeout_seconds=min(settings.tokenrouter_timeout_seconds, 120),
    )
    try:
        service = IntentCompilationService(
            client,
            model=settings.planner_model,
            max_output_tokens=4000,
            temperature=0.0,
        )
        return run_cases(service, cases, results, provenance)
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
