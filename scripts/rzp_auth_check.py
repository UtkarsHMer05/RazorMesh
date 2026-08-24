"""P2-M12: run the safe Razorpay Test Mode authentication diagnostic.

Prints a non-secret summary only. Never prints key/secret values.
Requires PAYMENT_PROVIDER=razorpay and valid Test credentials in .env.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

from razormesh_api.providers.razorpay import (
    RazorpayError,
    razorpay_auth_diagnostic_from_settings,
)
from razormesh_api.settings import (
    ProviderConfigError,
    Settings,
    validate_payment_provider_config,
)


def main() -> int:
    settings = Settings()
    try:
        validate_payment_provider_config(settings)
    except ProviderConfigError as exc:
        print("CONFIG GUARD FAILED:")
        for problem in exc.problems:
            print(f"  - {problem}")
        return 2

    if settings.payment_provider != "razorpay":
        print("PAYMENT_PROVIDER is not 'razorpay'; nothing to diagnose.")
        return 2

    print("Razorpay auth diagnostic (read-only GET /orders?count=1)")
    print("  RAZORPAY_MODE: test")
    print(
        f"  RAZORPAY_KEY_ID: PRESENT ({'test prefix OK' if settings.razorpay_key_id.startswith('rzp_test_') else 'UNEXPECTED PREFIX'})"
    )
    print("  RAZORPAY_KEY_SECRET: PRESENT")
    print("  RAZORPAY_WEBHOOK_SECRET: PRESENT")

    try:
        result = razorpay_auth_diagnostic_from_settings(settings)
    except RazorpayError as exc:
        print(f"DIAGNOSTIC ERROR: [{exc.code}] {exc.detail}")
        return 1

    for key, value in result.items():
        print(f"  {key}: {value}")
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
