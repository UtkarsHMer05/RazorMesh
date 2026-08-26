#!/usr/bin/env python3
"""P3-M20: restartable, diversity-first Qwen candidate generation.

The runner uses only the authorized free-tier model, persists every successful
response before processing the next seed, records sanitized failure evidence,
and writes schema-valid provisional AgentPay-IR rows with full provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

import httpx
from razormesh_api.agentpay_ir import AgentPayIRRecord
from razormesh_api.candidate_generation import (
    GENERATOR_NAME,
    PROMPT_VERSION,
    build_record,
    diversity_first,
    legacy_request_key,
    request_key,
)
from razormesh_api.settings import get_settings

SEED = REPO_ROOT / "data" / "phase3" / "dataset" / "seed" / "seed_dataset.jsonl"
OUT_DIR = REPO_ROOT / "data" / "phase3" / "dataset" / "candidates"
CACHE = OUT_DIR / "cache.json"
RESULTS = OUT_DIR / "candidates.jsonl"
FAILURES = OUT_DIR / "failures.jsonl"
MANIFEST = OUT_DIR / "manifest.json"
LAST_RUN = OUT_DIR / "last_run.json"


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _atomic_write_json(path: Path, payload: Any, *, indent: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=indent) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _atomic_write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    body = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    temporary.write_text(body, encoding="utf-8")
    os.replace(temporary, path)


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _load_cache() -> dict[str, dict[str, Any]]:
    if not CACHE.exists():
        return {}
    raw = json.loads(CACHE.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("candidate cache must be a JSON object")
    return raw


def _load_seeds() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in SEED.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _upgrade_legacy_results(
    seeds: list[dict[str, Any]], cache: dict[str, dict[str, Any]]
) -> int:
    """Upgrade compact v1 result rows to canonical AgentPay-IR in place."""
    if not RESULTS.exists():
        return 0

    distinct: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for seed in seeds:
        seed_id = str(seed["record_id"])
        if seed_id not in seen_ids:
            distinct.append(seed)
            seen_ids.add(seed_id)
    legacy = {
        legacy_request_key(seed, index): seed for index, seed in enumerate(distinct)
    }

    upgraded = 0
    canonical: list[dict[str, Any]] = []
    for line in RESULTS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        if "label_source" in raw:
            existing = AgentPayIRRecord.model_validate(raw)
            if (
                existing.provenance.prompt_version == "candidate-gen-v1"
                and existing.provenance.batch_id != "phase3-m20-qwen-candidates-v1"
            ):
                existing = existing.model_copy(
                    update={
                        "provenance": existing.provenance.model_copy(
                            update={"batch_id": "phase3-m20-qwen-candidates-v1"}
                        )
                    }
                )
                upgraded += 1
            canonical.append(existing.model_dump(mode="json"))
            continue
        key = str(raw.get("request_key", ""))
        legacy_seed = legacy.get(key)
        if legacy_seed is None:
            raise ValueError(f"cannot resolve legacy candidate request {key[:12]}")
        payload = cache.get(key, {})
        record = build_record(
            seed=legacy_seed,
            premise=str(raw["premise"]),
            hypothesis=str(raw["hypothesis"]),
            key=key,
            model_reported=str(payload.get("model_reported", "unreported")),
            created_at_utc=datetime.fromisoformat(str(raw["created_at_utc"])),
            prompt_version="candidate-gen-v1",
            batch_id="phase3-m20-qwen-candidates-v1",
        )
        canonical.append(record.model_dump(mode="json"))
        upgraded += 1

    if upgraded:
        _atomic_write_jsonl(RESULTS, canonical)
    return upgraded


def _existing_state() -> tuple[set[str], set[str], int]:
    keys: set[str] = set()
    texts: set[str] = set()
    record_count = 0
    if RESULTS.exists():
        for line in RESULTS.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = AgentPayIRRecord.model_validate_json(line)
            record_count += 1
            key = record.provenance.generator_request_id
            if key:
                keys.add(key)
            texts.update({_norm(record.premise), _norm(record.hypothesis)})
    if FAILURES.exists():
        for line in FAILURES.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            failure = json.loads(line)
            if str(failure.get("error_code", "")).startswith("TERMINAL_"):
                keys.add(str(failure["request_key"]))
    return keys, texts, record_count


def _write_manifest() -> dict[str, Any]:
    rows = (
        [
            AgentPayIRRecord.model_validate_json(line)
            for line in RESULTS.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if RESULTS.exists()
        else []
    )
    manifest = {
        "milestone": "P3-M20",
        "schema": "agentpay-ir-v0.1",
        "generator": GENERATOR_NAME,
        "current_prompt_version": PROMPT_VERSION,
        "prompt_versions": dict(
            sorted(Counter(str(row.provenance.prompt_version) for row in rows).items())
        ),
        "batch_ids": dict(
            sorted(Counter(str(row.provenance.batch_id) for row in rows).items())
        ),
        "records": len(rows),
        "label_source": dict(Counter(row.label_source for row in rows)),
        "by_family": dict(sorted(Counter(row.family for row in rows).items())),
        "by_label": dict(sorted(Counter(row.label for row in rows).items())),
        "by_difficulty": dict(sorted(Counter(row.difficulty for row in rows).items())),
        "results_sha256": (
            hashlib.sha256(RESULTS.read_bytes()).hexdigest()
            if RESULTS.exists()
            else None
        ),
        "failures_recorded": (
            sum(1 for line in FAILURES.read_text().splitlines() if line.strip())
            if FAILURES.exists()
            else 0
        ),
        "labels_are_provisional": True,
        "contains_credentials": False,
        "generated_at_utc": datetime.now(UTC).isoformat(),
    }
    _atomic_write_json(MANIFEST, manifest, indent=2)
    return manifest


def _failure(
    *,
    key: str,
    seed: dict[str, Any],
    attempt: int,
    status: int,
    code: str,
    retry_after: str | None,
) -> None:
    _append_jsonl(
        FAILURES,
        {
            "request_key": key,
            "source_case_id": seed["record_id"],
            "family": seed["family"],
            "attempt": attempt,
            "status": status,
            "error_code": code,
            "retry_after_seconds": retry_after,
            "generator": GENERATOR_NAME,
            "prompt_version": PROMPT_VERSION,
            "occurred_at_utc": datetime.now(UTC).isoformat(),
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=650)
    parser.add_argument("--max-minutes", type=int, default=330)
    parser.add_argument("--failure-threshold", type=int, default=10)
    parser.add_argument("--min-request-interval", type=float, default=1.0)
    args = parser.parse_args()
    if (
        args.target < 0
        or args.max_minutes < 0
        or args.failure_threshold < 1
        or args.min_request_interval < 0
    ):
        parser.error("numeric bounds invalid")

    settings = get_settings()
    if not settings.tokenrouter_credentials_present:
        raise RuntimeError("TOKENROUTER_API_KEY missing")
    deadline = time.time() + args.max_minutes * 60
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    seeds = _load_seeds()
    cache = _load_cache()
    upgraded = _upgrade_legacy_results(seeds, cache)
    done_keys, seen_texts, produced = _existing_state()
    work = diversity_first(seeds)
    start_count = produced
    consecutive_failures = 0
    rejected_invalid = 0
    duplicates_skipped = 0
    attempted = 0
    exit_code = 0
    exit_reason = "target_reached" if produced >= args.target else "work_exhausted"
    last_network_request_at = 0.0

    print(
        f"start: produced={produced} target={args.target} upgraded={upgraded} "
        f"max_minutes={args.max_minutes}",
        flush=True,
    )

    def backoff(attempt: int, retry_after: str | None) -> None:
        if retry_after:
            try:
                time.sleep(min(float(retry_after), 120.0))
                return
            except ValueError:
                pass
        time.sleep(min(60.0, 20.0 * (2**attempt)) + random.uniform(0, 7.5))

    http = httpx.Client(
        base_url=settings.tokenrouter_base_url,
        timeout=settings.tokenrouter_timeout_seconds,
        headers={
            "Authorization": f"Bearer {settings.tokenrouter_api_key.get_secret_value()}"
        },
    )
    planner = settings.planner_model
    try:
        for index, seed in enumerate(work):
            if produced >= args.target:
                exit_reason = "target_reached"
                break
            if time.time() > deadline:
                exit_reason = "time_budget_exhausted"
                break

            key = request_key(seed)
            if key in done_keys:
                continue
            attempted += 1

            payload: dict[str, Any]
            if key in cache:
                payload = cache[key]
                consecutive_failures = 0
            else:
                system = (
                    "Generate ONE novel NLI example for an agentic-commerce trust "
                    "dataset. Preserve the requested semantic relation but change the "
                    "scenario and wording. Output ONLY JSON with string fields "
                    '"premise" and "hypothesis".'
                )
                user = (
                    f"Family: {seed['family']}. Difficulty: {seed['difficulty']}. "
                    f"Relation: {seed['label']}. Premise is trusted current-commerce "
                    "evidence; hypothesis states confirmed human authorization. Include "
                    "realistic ambiguity, adversarial wording, or a safe lookalike when "
                    f"appropriate. Do not copy: premise={str(seed['premise'])[:200]!r}; "
                    f"hypothesis={str(seed['hypothesis'])[:160]!r}."
                )
                payload = {}
                for attempt in range(1, 5):
                    remaining_interval = args.min_request_interval - (
                        time.monotonic() - last_network_request_at
                    )
                    if remaining_interval > 0:
                        time.sleep(remaining_interval)
                    started = time.time()
                    last_network_request_at = time.monotonic()
                    response: httpx.Response | None
                    try:
                        response = http.post(
                            "/chat/completions",
                            json={
                                "model": planner,
                                "temperature": 0.7,
                                "max_tokens": 1800,
                                "response_format": {"type": "json_object"},
                                "messages": [
                                    {"role": "system", "content": system},
                                    {"role": "user", "content": user},
                                ],
                            },
                            headers={"X-Request-Id": key[:32]},
                        )
                    except httpx.TransportError:
                        response = None
                    if response is not None and response.status_code == 200:
                        try:
                            data = response.json()
                            content = data["choices"][0]["message"]["content"].strip()
                            start, end = content.find("{"), content.rfind("}")
                            parsed = json.loads(content[start : end + 1])
                            if (
                                isinstance(parsed.get("premise"), str)
                                and isinstance(parsed.get("hypothesis"), str)
                                and len(parsed["premise"]) >= 10
                                and len(parsed["hypothesis"]) >= 8
                            ):
                                payload = {
                                    "premise": parsed["premise"],
                                    "hypothesis": parsed["hypothesis"],
                                    "latency_ms": round(
                                        (time.time() - started) * 1000, 1
                                    ),
                                    "model_reported": data.get("model", planner),
                                }
                                cache[key] = payload
                                _atomic_write_json(CACHE, cache)
                            else:
                                _failure(
                                    key=key,
                                    seed=seed,
                                    attempt=attempt,
                                    status=200,
                                    code="INVALID_RESPONSE_SHAPE",
                                    retry_after=None,
                                )
                                if attempt < 4:
                                    backoff(attempt - 1, None)
                                    continue
                            break
                        except (ValueError, KeyError, TypeError):
                            _failure(
                                key=key,
                                seed=seed,
                                attempt=attempt,
                                status=200,
                                code="MALFORMED_RESPONSE",
                                retry_after=None,
                            )
                            if attempt < 4:
                                backoff(attempt - 1, None)
                                continue
                            break

                    retry_after = (
                        response.headers.get("Retry-After")
                        if response is not None
                        else None
                    )
                    status = response.status_code if response is not None else -1
                    _failure(
                        key=key,
                        seed=seed,
                        attempt=attempt,
                        status=status,
                        code="PROVIDER_HTTP"
                        if response is not None
                        else "TRANSPORT_ERROR",
                        retry_after=retry_after,
                    )
                    print(
                        f"[{index}] provider {status}; attempt {attempt}/4", flush=True
                    )
                    if attempt < 4:
                        backoff(attempt - 1, retry_after)

                if not payload:
                    consecutive_failures += 1
                    if consecutive_failures >= args.failure_threshold:
                        exit_reason = "provider_dead_window"
                        exit_code = 5
                        break
                    continue
                consecutive_failures = 0

            if (
                _norm(str(payload["premise"])) in seen_texts
                or _norm(str(payload["hypothesis"])) in seen_texts
            ):
                duplicates_skipped += 1
                _failure(
                    key=key,
                    seed=seed,
                    attempt=0,
                    status=0,
                    code="TERMINAL_DUPLICATE_CONTENT",
                    retry_after=None,
                )
                done_keys.add(key)
                continue

            try:
                record = build_record(
                    seed=seed,
                    premise=str(payload["premise"]),
                    hypothesis=str(payload["hypothesis"]),
                    key=key,
                    model_reported=str(payload.get("model_reported", planner)),
                    created_at_utc=datetime.now(UTC),
                )
            except Exception as exc:  # noqa: BLE001 - invalid row is evidence, not fatal
                rejected_invalid += 1
                _failure(
                    key=key,
                    seed=seed,
                    attempt=0,
                    status=0,
                    code=f"TERMINAL_SCHEMA_REJECTED_{type(exc).__name__}",
                    retry_after=None,
                )
                done_keys.add(key)
                continue

            _append_jsonl(RESULTS, record.model_dump(mode="json"))
            seen_texts.update({_norm(record.premise), _norm(record.hypothesis)})
            done_keys.add(key)
            produced += 1
            if produced % 5 == 0:
                print(f"progress: produced={produced}/{args.target}", flush=True)
    finally:
        http.close()

    _atomic_write_json(CACHE, cache)
    manifest = _write_manifest()
    summary = {
        "milestone": "P3-M20",
        "start_count": start_count,
        "produced_total": produced,
        "produced_this_run": produced - start_count,
        "attempted_this_run": attempted,
        "duplicates_skipped_this_run": duplicates_skipped,
        "rejected_invalid_this_run": rejected_invalid,
        "legacy_rows_upgraded": upgraded,
        "exit_reason": exit_reason,
        "exit_code": exit_code,
        "generator": GENERATOR_NAME,
        "prompt_version": PROMPT_VERSION,
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "family_count": len(manifest["by_family"]),
    }
    _atomic_write_json(LAST_RUN, summary, indent=2)
    print(json.dumps(summary, indent=2), flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
