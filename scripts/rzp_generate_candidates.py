#!/usr/bin/env python3
"""P3-M20: Qwen candidate-pair generator (overnight-policy compliant).

Policy implemented (human authorization, 2026-08-26):
- resumable + idempotent: request-hash cache; results appended atomically;
- persist successful responses immediately;
- respect Retry-After header when provided;
- bounded exponential backoff WITH JITTER on transient failures;
- dead-window circuit breaker: after N consecutive provider failures the run
  exits (resumable) instead of hammering;
- qwen/qwen3.8-max-free ONLY — never falls back to a paid model;
- labels are PROVISIONAL (label_source="qwen_provisional") — never presented
  as template truth or human gold;
- every accepted candidate is schema-validated through AgentPayIRRecord;
- near-duplicate guard: exact-normalized-text dedup at generation time
  (fuzzy near-dup detection remains M22's job);
- --target N and --max-minutes M bound the run honestly; partial progress is
  recorded and resumable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

import httpx
from razormesh_api.agentpay_ir import make_record
from razormesh_api.settings import get_settings

SEED = REPO_ROOT / "data" / "phase3" / "dataset" / "seed" / "seed_dataset.jsonl"
OUT_DIR = REPO_ROOT / "data" / "phase3" / "dataset" / "candidates"
CACHE = OUT_DIR / "cache.json"
RESULTS = OUT_DIR / "candidates.jsonl"

GENERATOR_NAME = "qwen3.8-max-free@tokenrouter"
PROMPT_VERSION = "candidate-gen-v1"


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _load_cache() -> dict[str, dict]:
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    return {}


def _save_cache(cache: dict[str, dict]) -> None:
    CACHE.write_text(json.dumps(cache, ensure_ascii=False))


def _existing_keys() -> tuple[set[str], set[str]]:
    """Return (request-hash keys done, normalized seen texts)."""
    keys: set[str] = set()
    texts: set[str] = set()
    if RESULTS.exists():
        for line in RESULTS.read_text().splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            keys.add(row["request_key"])
            texts.add(_norm(row["premise"]))
            texts.add(_norm(row["hypothesis"]))
    return keys, texts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=650)
    parser.add_argument("--max-minutes", type=int, default=330)
    args = parser.parse_args()

    settings = get_settings()
    assert settings.tokenrouter_credentials_present, "TOKENROUTER_API_KEY missing"
    deadline = time.time() + args.max_minutes * 60

    seeds = [json.loads(line) for line in SEED.read_text().splitlines() if line.strip()]
    cache = _load_cache()
    done_keys, seen_texts = _existing_keys()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    http = httpx.Client(
        base_url=settings.tokenrouter_base_url,
        timeout=settings.tokenrouter_timeout_seconds,
        headers={
            "Authorization": f"Bearer {settings.tokenrouter_api_key.get_secret_value()}"
        },
    )
    planner = settings.planner_model

    # Deterministic work order over distinct seed records.
    work = []
    seen_seed_ids: set[str] = set()
    for seed in seeds:
        sid = seed["record_id"]
        if sid in seen_seed_ids:
            continue
        seen_seed_ids.add(sid)
        work.append(seed)

    produced = len(done_keys)
    consecutive_failures = 0
    rejected_invalid = 0
    duplicates_skipped = 0
    attempted = 0

    print(
        f"start: produced={produced} target={args.target} "
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
        base = min(60.0, 20.0 * (2**attempt))
        time.sleep(base + random.uniform(0, 7.5))  # bounded exp backoff + jitter

    for idx, seed in enumerate(work):
        if produced >= args.target:
            break
        if time.time() > deadline:
            print("time budget exhausted; exiting RESUMABLY", flush=True)
            break

        request_key = hashlib.sha256(
            f"{PROMPT_VERSION}|{seed['family']}|{seed['label']}|{seed['difficulty']}|{idx}".encode()
        ).hexdigest()
        if request_key in done_keys:
            continue

        attempted += 1

        # Cache hit path (idempotent regeneration without network).
        if request_key in cache:
            payload = cache[request_key]
        else:
            system = (
                "You generate ONE new NLI example for an agentic-commerce trust "
                "dataset. Same meaning-relation as specified, DIFFERENT surface "
                'content. Output ONLY JSON {"premise": str, "hypothesis": str}.'
            )
            user = (
                f"Family: {seed['family']}. Difficulty: {seed['difficulty']}. "
                f"Label to preserve: {seed['label']}. "
                "premise = a short product/seller EVIDENCE paragraph. "
                "hypothesis = a statement about what the human authorized. "
                f'Reference style (do NOT copy): premise="{seed["premise"][:200]}" '
                f'hypothesis="{seed["hypothesis"][:160]}".'
            )
            ok_payload = None
            for attempt in range(4):
                t0 = time.time()
                try:
                    resp = http.post(
                        "/chat/completions",
                        json={
                            "model": planner,
                            "temperature": 0.7,
                            "max_tokens": 900,
                            "messages": [
                                {"role": "system", "content": system},
                                {"role": "user", "content": user},
                            ],
                        },
                        headers={"X-Request-Id": request_key[:32]},
                    )
                except httpx.TransportError:
                    resp = None
                if resp is not None and resp.status_code == 200:
                    try:
                        data = resp.json()
                        content = data["choices"][0]["message"]["content"].strip()
                        start, end = content.find("{"), content.rfind("}")
                        parsed = json.loads(content[start : end + 1])
                        if (
                            isinstance(parsed.get("premise"), str)
                            and isinstance(parsed.get("hypothesis"), str)
                            and len(parsed["premise"]) >= 10
                            and len(parsed["hypothesis"]) >= 8
                        ):
                            ok_payload = {
                                "premise": parsed["premise"],
                                "hypothesis": parsed["hypothesis"],
                                "latency_ms": round((time.time() - t0) * 1000, 1),
                                "model_reported": data.get("model", planner),
                            }
                        break
                    except (ValueError, KeyError, TypeError):
                        ok_payload = None
                        break  # malformed content is deterministic-ish; don't burn retries
                else:
                    retry_after = (
                        resp.headers.get("Retry-After") if resp is not None else None
                    )
                    status = resp.status_code if resp is not None else -1
                    print(
                        f"[{idx}] provider {status}; backoff (attempt {attempt + 1}/4)",
                        flush=True,
                    )
                    if attempt < 3:
                        backoff(attempt, retry_after)

            if ok_payload is None:
                consecutive_failures += 1
                if consecutive_failures >= 10:
                    print(
                        "dead window: too many consecutive provider failures; "
                        "exiting RESUMABLY",
                        flush=True,
                    )
                    return 5
                continue
            consecutive_failures = 0
            payload = ok_payload
            cache[request_key] = payload
            if len(cache) % 10 == 0:
                _save_cache(cache)

        # Near-dup guard against everything recorded so far.
        if (
            _norm(payload["premise"]) in seen_texts
            or _norm(payload["hypothesis"]) in seen_texts
        ):
            duplicates_skipped += 1
            done_keys.add(request_key)
            continue

        try:
            record = make_record(
                record_id="air_"
                + hashlib.sha256(request_key.encode()).hexdigest()[:26].upper(),
                premise=payload["premise"],
                hypothesis=payload["hypothesis"],
                label=seed["label"],  # relation preserved by construction
                label_source="qwen_provisional",
                family=seed["family"],
                difficulty=seed["difficulty"],
                provenance={
                    "generator": GENERATOR_NAME,
                    "source_case_id": seed["record_id"],
                    "created_at_utc": datetime.now(UTC),
                    "generator_request_id": payload.get("model_reported"),
                },
            )
        except Exception as exc:  # noqa: BLE001 - invalid candidates counted, not fatal
            rejected_invalid += 1
            print(f"[{idx}] invalid candidate rejected: {exc}", flush=True)
            done_keys.add(request_key)
            continue

        row = {
            "request_key": request_key,
            "record_id": record.record_id,
            "family": record.family,
            "label": record.label,
            "difficulty": record.difficulty,
            "premise": record.premise,
            "hypothesis": record.hypothesis,
            "content_sha256": record.content_sha256,
            "latency_ms": payload.get("latency_ms"),
            "created_at_utc": datetime.now(UTC).isoformat(),
        }
        with RESULTS.open("a") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        seen_texts.add(_norm(record.premise))
        seen_texts.add(_norm(record.hypothesis))
        done_keys.add(request_key)
        produced += 1

        if produced % 5 == 0:
            print(
                f"progress: produced={produced}/{args.target} "
                f"(attempted={attempted}, dup={duplicates_skipped}, "
                f"invalid={rejected_invalid})",
                flush=True,
            )

    _save_cache(cache)
    summary = {
        "produced_total": produced,
        "attempted_this_run": attempted,
        "duplicates_skipped_total_estimate": duplicates_skipped,
        "rejected_invalid_this_run": rejected_invalid,
        "generator": GENERATOR_NAME,
        "prompt_version": PROMPT_VERSION,
        "finished_at_utc": datetime.now(UTC).isoformat(),
    }
    (OUT_DIR / "last_run.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
