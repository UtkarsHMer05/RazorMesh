#!/usr/bin/env python3
"""P3-M10: REAL TokenRouter authentication + capability probe (safe output).

Probes, in order:
1. GET /v1/models with the real key -> credential validity + catalog;
2. whether PLANNER_MODEL id is visible;
3. one small chat completion (latency, finish reason);
4. JSON-instruction compliance (model returns parseable JSON when asked);
5. response_format={"type":"json_object"} support shape.

Prints ONLY safe facts: booleans, model IDs, statuses, latencies, short content
snippets of OUR OWN prompts' outputs. Never prints the API key or headers.
Run from the repository root.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

from razormesh_api.intent_compiler import (
    TokenRouterAuthError,
    TokenRouterClient,
    TokenRouterError,
    TokenRouterRejectedError,
    TokenRouterUnknownOutcomeError,
)
from razormesh_api.settings import get_settings


def _lat_ms(t0: float) -> float:
    return round((time.time() - t0) * 1000.0, 1)


def _with_backoff(fn, *, attempts: int = 8, sleep_s: float = 20.0):
    """Free-tier windows return transient 503 hard_concurrency_limit.

    The PROBE may retry read-only diagnostics with bounded backoff; production
    compiler calls will NOT auto-retry (D-030 discipline) and instead fail
    closed per the master prompt failure policy.
    """
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except TokenRouterUnknownOutcomeError as exc:
            last_exc = exc
            if attempt < attempts - 1:
                print(f"  transient unknown outcome; backing off {sleep_s}s "
                      f"(attempt {attempt + 1}/{attempts})")
                time.sleep(sleep_s)
    raise last_exc if last_exc else RuntimeError("unreachable")


def main() -> int:
    s = get_settings()
    if not s.tokenrouter_credentials_present:
        print("TOKENROUTER_API_KEY absent; cannot probe.")
        return 2

    print("base_url_host:", s.tokenrouter_base_url.split("/")[2])
    print("planner_model configured:", s.planner_model)
    print("timeout bound:", s.tokenrouter_timeout_seconds, "s")

    client = TokenRouterClient(
        api_key=s.tokenrouter_api_key.get_secret_value(),
        base_url=s.tokenrouter_base_url,
        timeout_seconds=s.tokenrouter_timeout_seconds,
    )

    # 1. Auth via models listing
    try:
        t0 = time.time()
        ids = client.list_models()
        print(f"AUTH: ok | models_listed={len(ids)} | latency_ms={_lat_ms(t0)}")
    except TokenRouterAuthError as exc:
        print(f"AUTH: FAILED (auth error) request_id={exc.request_id}")
        return 3
    except TokenRouterError as exc:
        print(f"AUTH: INCONCLUSIVE ({exc.code}) request_id={exc.request_id}")
        return 4

    qwen_ids = [i for i in ids if i.lower().startswith("qwen/")]
    free_ids = [i for i in ids if "free" in i.lower()]
    print("qwen models visible:", qwen_ids[:10])
    print("free-suffix models visible:", free_ids[:10])
    planner_visible = s.planner_model in ids
    print("planner_model_visible:", planner_visible)

    # 2. Basic completion — generous budget: Qwen3.8 spends hidden reasoning
    # tokens BEFORE content; a tiny max_tokens ends finish=length content=''.
    try:
        t0 = time.time()
        r = _with_backoff(
            lambda: client.chat_completion(
                model=s.planner_model,
                messages=[
                    {"role": "system", "content": "Answer with a single word."},
                    {"role": "user", "content": "Reply with exactly: PONG"},
                ],
                max_tokens=512,
                temperature=0.0,
            )
        )
        print(
            f"BASIC COMPLETION: ok latency_ms={_lat_ms(t0)} "
            f"finish={r.finish_reason} reported_model={r.model_reported} "
            f"reasoning_tokens={r.reasoning_tokens} "
            f"says={r.content.strip()[:24]!r}"
        )
    except TokenRouterRejectedError as exc:
        print(f"BASIC COMPLETION: REJECTED ({exc.detail}) id={exc.request_id}")
    except TokenRouterError as exc:
        print(f"BASIC COMPLETION: {exc.code} id={exc.request_id}")

    # 3. JSON instruction compliance (no response_format)
    instruction = (
        'Return ONLY a JSON object with keys "max_price_minor" (integer) and '
        '"currency" ("INR"). No prose, no code fence. Context: budget under '
        "five thousand rupees."
    )
    try:
        t0 = time.time()
        r = _with_backoff(
            lambda: client.chat_completion(
                model=s.planner_model,
                messages=[
                    {"role": "system", "content": "You emit only strict JSON."},
                    {"role": "user", "content": instruction},
                ],
                max_tokens=1500,
                temperature=0.0,
            )
        )
        snippet = r.content.strip()
        try:
            parsed = json.loads(snippet)
            json_ok = isinstance(parsed, dict)
        except ValueError:
            json_ok = False
        print(
            f"JSON_INSTRUCTION: parseable={json_ok} latency_ms={_lat_ms(t0)} "
            f"finish={r.finish_reason} raw_len={len(r.content)}"
        )
    except TokenRouterError as exc:
        print(f"JSON_INSTRUCTION: {exc.code} id={exc.request_id}")

    # 4. response_format={"type":"json_object"} support shape
    try:
        t0 = time.time()
        r = _with_backoff(
            lambda: client.chat_completion(
                model=s.planner_model,
                messages=[
                    {"role": "system", "content": "You emit only strict JSON."},
                    {"role": "user", "content": instruction},
                ],
                max_tokens=1500,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
        )
        try:
            parsed = json.loads(r.content.strip())
            rf_ok = isinstance(parsed, dict)
        except ValueError:
            rf_ok = False
        print(
            f"RESPONSE_FORMAT_JSON_OBJECT: accepted=True parseable={rf_ok} "
            f"latency_ms={_lat_ms(t0)}"
        )
    except TokenRouterRejectedError as exc:
        print(
            "RESPONSE_FORMAT_JSON_OBJECT: rejected by gateway/model "
            f"({exc.detail}) id={exc.request_id}"
        )
    except TokenRouterError as exc:
        print(f"RESPONSE_FORMAT_JSON_OBJECT: {exc.code} id={exc.request_id}")

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
