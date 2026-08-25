#!/usr/bin/env python3
"""P3-M15: run the REAL Qwen compiler over the golden set (resumable).

Design constraints from reality (M10 probe):
- free tier throws transient 503 hard_concurrency_limit WINDOWS;
- thinking-model latency is seconds-to-minutes;
- production discipline: NO automatic transport retry inside the client —
  this RUNNER owns pacing/backoff and checkpoints every case to disk so any
  interrupted run resumes exactly where it stopped.

Outputs:
  data/phase3/compiler_eval/results.jsonl   (one row per case, resumable)
  data/phase3/compiler_eval/summary.json    (aggregate metrics)
Run from the repository root.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

from razormesh_api.compiler_eval import (
    GoldenCase,
    evaluate_case,
    load_golden,
)
from razormesh_api.intent_compilation_service import (
    IntentCompilationService,
)
from razormesh_api.intent_compiler import TokenRouterClient
from razormesh_api.intent_compiler_prompt import TrustedHumanAuthorization
from razormesh_api.settings import get_settings

GOLDEN = REPO_ROOT / "data" / "phase3" / "compiler_golden" / "golden_set.jsonl"

# Stratified sampling (P3-M15): free-tier throughput makes a full 307-case run
# a multi-hour grind; --sample N selects a deterministic round-robin across
# categories preserving difficulty mix. Full set remains resumable anytime.
SAMPLE_N: int | None = None
OUT_DIR = REPO_ROOT / "data" / "phase3" / "compiler_eval"
RESULTS = OUT_DIR / "results.jsonl"

PACE_SECONDS = 0.0
BACKOFF_SECONDS = 30.0
MAX_CONSECUTIVE_PROVIDER_FAILS = 12


def _rows() -> list[dict]:
    rows: dict[str, dict] = {}
    if RESULTS.exists():
        for line in RESULTS.read_text().splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            rows[row.get("case_id", "")] = row  # last row wins
    return list(rows.values())


def load_done() -> set[str]:
    """A case counts as done unless its ONLY outcome was provider noise —
    COMPILER_UNAVAILABLE rows are retried on the next resumable run."""
    done: set[str] = set()
    for row in _rows():
        if (
            row["status"] == "FAILED"
            and row.get("error_code") == "COMPILER_UNAVAILABLE"
        ):
            continue
        done.add(row["case_id"])
    return done


def compact_results() -> None:
    """Rewrite results.jsonl keeping the LAST row per case (noise-free view)."""
    rows = _rows()
    if rows:
        with RESULTS.open("w") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def stratified(cases: list[dict], n: int) -> list[dict]:
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
    return picked


def main() -> int:
    global SAMPLE_N
    if len(sys.argv) > 1:
        SAMPLE_N = int(sys.argv[1])
    settings = get_settings()
    assert settings.tokenrouter_credentials_present, "TOKENROUTER_API_KEY missing"
    all_cases = load_golden(GOLDEN)
    cases = (
        stratified([c.model_dump() for c in all_cases], SAMPLE_N)
        if SAMPLE_N
        else [c.model_dump() for c in all_cases]
    )
    cases = [GoldenCase.model_validate(c) for c in cases]
    done = load_done()
    todo = [c for c in cases if c.case_id not in done]
    print(f"golden={len(cases)} done={len(done)} todo={len(todo)}", flush=True)

    client = TokenRouterClient(
        api_key=settings.tokenrouter_api_key.get_secret_value(),
        base_url=settings.tokenrouter_base_url,
        timeout_seconds=min(settings.tokenrouter_timeout_seconds, 120),
    )
    # M10 evidence: Qwen3.8 is a THINKING model — reasoning tokens consume the
    # budget before content; hard multi-constraint cases exhausted a 2000 cap
    # (4 harness-induced failures remeasured at 4000, see eval doc).
    service = IntentCompilationService(
        client, model=settings.planner_model, max_output_tokens=4000, temperature=0.0
    )

    consecutive_provider_fails = 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for idx, case in enumerate(todo):
        trusted = TrustedHumanAuthorization(text=case.input_text)
        t0 = time.time()
        outcome = None

        # Runner-level pacing around transient provider windows: probe-style
        # backoff BEFORE giving up on this single case (max 4 attempts).
        for _attempt in range(4):
            outcome = service.compile(trusted)
            if outcome.error_code != "COMPILER_UNAVAILABLE":
                break
            consecutive_provider_fails += 1
            if consecutive_provider_fails >= MAX_CONSECUTIVE_PROVIDER_FAILS:
                print(
                    f"provider window closed ({consecutive_provider_fails} "
                    "consecutive unavailable); aborting RESUMABLY",
                    flush=True,
                )
                return 5
            time.sleep(BACKOFF_SECONDS)

        latency_ms = round((time.time() - t0) * 1000.0, 1)
        verdict = evaluate_case(outcome.payload, case.expected)
        verdict_row = {
            "case_id": case.case_id,
            "category": case.category,
            "difficulty": case.difficulty,
            "status": outcome.status,
            "error_code": outcome.error_code,
            "attempts": outcome.attempts,
            "latency_ms": latency_ms,
            "passed": verdict.passed,
            "mismatches": list(verdict.mismatches),
            "omissions": list(verdict.omissions),
            "inventions": list(verdict.inventions),
            "request_ids": list(outcome.request_ids),
        }
        with RESULTS.open("a") as fh:
            fh.write(json.dumps(verdict_row, ensure_ascii=False) + "\n")

        if outcome.error_code != "COMPILER_UNAVAILABLE":
            consecutive_provider_fails = 0

        print(
            f"[{idx + 1}/{len(todo)}] {case.case_id} {outcome.status} "
            f"attempts={outcome.attempts} passed={verdict.passed} "
            f"{latency_ms}ms",
            flush=True,
        )
        time.sleep(PACE_SECONDS)

    compact_results()
    pending_noise = len({c.case_id for c in cases} - load_done())
    if pending_noise:
        print(
            f"run finished but {pending_noise} case(s) still provider-noise; resumable",
            flush=True,
        )
        return 5
    print("run complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
