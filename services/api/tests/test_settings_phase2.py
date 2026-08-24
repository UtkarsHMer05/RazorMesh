"""P2-M08/M09: typed Razorpay configuration — test-mode guards and secret hygiene."""

import pytest
from pydantic import ValidationError

from razormesh_api.settings import Settings


def test_mock_default_is_credential_free() -> None:
    s = Settings(_env_file=None)
    assert s.payment_provider == "mock"
    assert s.mock_payment_provider is True
    assert s.razorpay_credentials_present is False


def test_secrets_are_secretstr_and_never_leak_via_repr() -> None:
    s = Settings(
        razorpay_key_id="rzp_test_abc",
        razorpay_key_secret="supersecret",
        razorpay_webhook_secret="hooksecret",
        _env_file=None,
    )
    rendered = repr(s) + str(s.model_dump())
    assert "supersecret" not in rendered
    assert "hooksecret" not in rendered
    assert s.razorpay_key_secret.get_secret_value() == "supersecret"


def test_mode_literal_rejects_live_value() -> None:
    with pytest.raises(ValidationError):
        Settings(razorpay_mode="live", _env_file=None)  # type: ignore[arg-type]


def test_provider_literal_rejects_unknown_provider() -> None:
    with pytest.raises(ValidationError):
        Settings(payment_provider="stripe", _env_file=None)  # type: ignore[arg-type]


def test_timeout_bounds_enforced() -> None:
    assert (
        Settings(
            razorpay_request_timeout_seconds=0.5, _env_file=None
        ).razorpay_request_timeout_seconds
        == 0.5
    )
    with pytest.raises(ValidationError):
        Settings(razorpay_request_timeout_seconds=0, _env_file=None)
    with pytest.raises(ValidationError):
        Settings(razorpay_request_timeout_seconds=61, _env_file=None)


def test_credentials_present_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_x")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "s")
    s = Settings(_env_file=None)
    assert s.razorpay_credentials_present is True


def _cfg(**kw: object) -> Settings:
    return Settings(_env_file=None, **kw)  # type: ignore[arg-type]


def test_mock_mode_needs_no_razorpay_credentials() -> None:
    from razormesh_api.settings import validate_payment_provider_config

    validate_payment_provider_config(_cfg())  # must not raise


def test_real_provider_without_credentials_names_missing_vars_only() -> None:
    from razormesh_api.settings import ProviderConfigError, validate_payment_provider_config

    with pytest.raises(ProviderConfigError) as exc:
        validate_payment_provider_config(_cfg(payment_provider="razorpay"))
    joined = "; ".join(exc.value.problems)
    assert "RAZORPAY_KEY_ID" in joined
    assert "RAZORPAY_KEY_SECRET" in joined
    assert "RAZORPAY_WEBHOOK_SECRET" in joined
    # no values are ever echoed
    assert "=" not in joined.replace("PAYMENT_PROVIDER=razorpay", "")


def test_live_key_prefix_rejected_even_in_mock_mode() -> None:
    from razormesh_api.settings import ProviderConfigError, validate_payment_provider_config

    with pytest.raises(ProviderConfigError) as exc:
        validate_payment_provider_config(
            _cfg(
                razorpay_key_id="rzp_live_CkYzExample",
                razorpay_key_secret="whatever",
            )
        )
    assert any("RAZORPAY_LIVE_KEY_REJECTED" in p for p in exc.value.problems)


def test_test_prefix_with_all_credentials_passes_guard() -> None:
    from razormesh_api.settings import validate_payment_provider_config

    validate_payment_provider_config(
        _cfg(
            payment_provider="razorpay",
            razorpay_key_id="rzp_test_ok",
            razorpay_key_secret="s3cret-value",
            razorpay_webhook_secret="hook-value",
        )
    )


def test_error_message_never_contains_secret_values() -> None:
    from razormesh_api.settings import ProviderConfigError, validate_payment_provider_config

    secret_value = "super-secret-do-not-leak"
    with pytest.raises(ProviderConfigError) as exc:
        validate_payment_provider_config(
            _cfg(payment_provider="razorpay", razorpay_webhook_secret=secret_value)
        )
    assert secret_value not in str(exc.value)
