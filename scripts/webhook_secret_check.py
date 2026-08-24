#!/usr/bin/env python3
"""P2-M38 safe diagnostic: webhook-secret hygiene report.

Reports ONLY non-secret facts about RAZORPAY_WEBHOOK_SECRET:
presence, length, whitespace/quoting traits, and whether the runtime
Settings view (what the API process loads from the root .env) matches the
raw .env file line — compared via an HMAC probe, booleans only.

NEVER prints the secret, any signature, or any HMAC digest.

Run:  uv run --project services/api python scripts/webhook_secret_check.py
"""

from __future__ import annotations

import hashlib
import hmac
import os

PROBE = b"razormesh-webhook-diagnostic-probe"


def traits(value: str) -> dict[str, object]:
    return {
        "present": bool(value),
        "length": len(value),
        "has_leading_whitespace": value != value.lstrip(),
        "has_trailing_whitespace": value != value.rstrip(),
        "has_cr": "\r" in value,
        "has_newline": "\n" in value,
        "has_quote_char": ('"' in value) or ("'" in value),
        "has_internal_space": " " in value.strip(),
        "printable_ascii": value.isascii() and value.isprintable(),
    }


def main() -> int:
    from razormesh_api.settings import Settings

    runtime = Settings().razorpay_webhook_secret.get_secret_value()

    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    file_raw = ""
    with open(env_path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("RAZORPAY_WEBHOOK_SECRET="):
                file_raw = line.split("=", 1)[1].rstrip("\r\n")
                break

    # Mirror pydantic-settings: surrounding quotes are stripped when present.
    file_value = file_raw.strip()
    if (
        len(file_value) >= 2
        and file_value[0] == file_value[-1]
        and file_value[0] in ("'", '"')
    ):
        file_value = file_value[1:-1]

    runtime_digest = hmac.new(runtime.encode(), PROBE, hashlib.sha256).digest()
    file_digest = hmac.new(file_value.encode(), PROBE, hashlib.sha256).digest()

    print("runtime_settings:   ", traits(runtime))
    print(
        "env_file_line:      ", traits(file_value), {"raw_line_length": len(file_raw)}
    )
    print("runtime_matches_env_file:", hmac.compare_digest(runtime_digest, file_digest))
    print("process_env_override_present:", "RAZORPAY_WEBHOOK_SECRET" in os.environ)
    print(
        "note: identical Dashboard + runtime secrets are REQUIRED (R-014); "
        "the Dashboard value is human-entered and cannot be inspected from here."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
