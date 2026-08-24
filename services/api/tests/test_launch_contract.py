"""P2-M19: checkout launch contract — public data only, trust-gated issuance."""

import pytest

from razormesh_api.providers.razorpay import (
    RazorpayError,
    build_launch_payload,
)
from razormesh_api.settings import Settings


def _settings(**kw: object) -> Settings:
    base = dict(
        payment_provider="razorpay",
        razorpay_key_id="rzp_test_PUBLICKEY",
        razorpay_key_secret="SUPERSECRET",
        razorpay_webhook_secret="HOOKSECRET",
    )
    base.update(kw)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


def _build(settings: Settings):  # type: ignore[no-untyped-def]
    return build_launch_payload(
        attempt_state="EXECUTING",
        attempt_amount_minor=64890,
        attempt_currency="INR",
        attempt_execution_attempt_id="exa_01M0SQSH4NTZP0T5M1YJN4MBKW",
        attempt_intent_id="int_01M0SQSH0KPD76GNP48YA2ABQ4",
        attempt_checkout_id="chk_01M0SQSH0ZFA5608KGJTJMBCKQ",
        attempt_razorpay_order_id="order_TTaTD5sEvimzoD",
        settings=settings,
    )


def test_payload_contains_only_public_fields() -> None:
    payload = _build(_settings())
    data = payload.__dict__
    assert set(data) == {
        "public_key_id",
        "razorpay_order_id",
        "amount_minor",
        "currency",
        "execution_attempt_id",
        "intent_id",
        "checkout_id",
    }
    assert data["public_key_id"] == "rzp_test_PUBLICKEY"
    assert data["razorpay_order_id"] == "order_TTaTD5sEvimzoD"
    assert data["amount_minor"] == 64890


def test_no_secret_material_in_any_field() -> None:
    rendered = str(_build(_settings()).__dict__).lower()
    assert "supersecret" not in rendered
    assert "hooksecret" not in rendered


def test_launch_refused_for_terminal_attempt() -> None:
    with pytest.raises(RazorpayError):
        build_launch_payload(
            attempt_state="SUCCEEDED",
            attempt_amount_minor=1,
            attempt_currency="INR",
            attempt_execution_attempt_id="exa_x",
            attempt_intent_id="int_x",
            attempt_checkout_id="chk_x",
            attempt_razorpay_order_id="order_x",
            settings=_settings(),
        )


def test_launch_refused_without_order_correlation() -> None:
    with pytest.raises(RazorpayError):
        build_launch_payload(
            attempt_state="EXECUTING",
            attempt_amount_minor=1,
            attempt_currency="INR",
            attempt_execution_attempt_id="exa_x",
            attempt_intent_id="int_x",
            attempt_checkout_id="chk_x",
            attempt_razorpay_order_id=None,
            settings=_settings(),
        )


def test_launch_payload_is_immutable() -> None:
    from dataclasses import FrozenInstanceError

    payload = _build(_settings())
    with pytest.raises(FrozenInstanceError):
        payload.amount_minor = 1  # type: ignore[misc]
