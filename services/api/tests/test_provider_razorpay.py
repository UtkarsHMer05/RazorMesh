"""P2-M11: Razorpay provider skeleton — typed errors, no-retry, DI seams."""

import httpx
import pytest

from razormesh_api.providers.razorpay import (
    RazorpayAuthError,
    RazorpayConfigError,
    RazorpayPaymentProvider,
    RazorpayRejectionError,
    RazorpayUnknownOutcomeError,
)
from razormesh_api.settings import Settings


def _settings(**kw: object) -> Settings:
    base = dict(
        payment_provider="razorpay",
        razorpay_key_id="rzp_test_key",
        razorpay_key_secret="secret-value",
        razorpay_webhook_secret="hook-value",
        razorpay_request_timeout_seconds=0.2,
    )
    base.update(kw)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


def _provider(handler) -> RazorpayPaymentProvider:  # type: ignore[no-untyped-def]
    transport = httpx.MockTransport(handler)
    client = RazorpayClientForTest(transport)
    return RazorpayPaymentProvider(client)


class RazorpayClientForTest:
    """Constructs the real client with a MockTransport and test settings."""

    def __init__(self, transport: httpx.BaseTransport) -> None:
        from razormesh_api.providers.razorpay import RazorpayClient

        self._inner = RazorpayClient(
            key_id="rzp_test_k",
            key_secret="s",
            base_url="https://api.razorpay.com/v1",
            timeout_seconds=5,
            transport=transport,
        )

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
        return getattr(self._inner, name)


ORDER_BODY = {
    "id": "order_test123",
    "entity": "order",
    "amount": 64890,
    "currency": "INR",
    "status": "created",
    "receipt": "rcpt-1",
}


def test_create_order_success_parses_projection() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.read()
        seen["auth"] = request.headers.get("Authorization", "")
        return httpx.Response(201, json=ORDER_BODY)

    provider = _provider(handler)
    order = provider.create_order(
        amount_minor=64890, currency="INR", receipt="rcpt-1", notes={"k": "v"}
    )
    assert order.order_id == "order_test123"
    assert order.amount_minor == 64890
    assert order.currency == "INR"
    assert order.status == "created"
    assert b"64890" in seen["body"]
    # Basic auth is used; the secret travels only in the Authorization header
    assert seen["auth"].startswith("Basic ")


def test_create_order_auth_failure_maps_to_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"description": "bad"}})

    provider = _provider(handler)
    with pytest.raises(RazorpayAuthError) as exc:
        provider.create_order(amount_minor=100, currency="INR", receipt="r", notes={})
    assert exc.value.code == "RAZORPAY_AUTH_FAILED"


def test_create_order_validation_rejection_is_definitive() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"code": "BAD_REQUEST_ERROR"}})

    provider = _provider(handler)
    with pytest.raises(RazorpayRejectionError):
        provider.create_order(amount_minor=0, currency="INR", receipt="r", notes={})


def _assert_unknown(exc: pytest.ExceptionInfo[RazorpayUnknownOutcomeError]) -> None:
    assert exc.value.code.startswith("RAZORPAY_")
    assert "UNKNOWN" in exc.value.code


def test_timeout_maps_to_unknown() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectTimeout("simulated timeout", request=request)

    provider = _provider(handler)
    with pytest.raises(RazorpayUnknownOutcomeError) as exc:
        provider.create_order(amount_minor=100, currency="INR", receipt="r", notes={})
    _assert_unknown(exc)
    # NO transport-level retry: exactly one attempt (P2-S19 / D-030)
    assert calls == 1


def test_server_error_maps_to_unknown_and_never_retries() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    provider = _provider(handler)
    with pytest.raises(RazorpayUnknownOutcomeError):
        provider.fetch_order("order_x")
    assert calls == 1


def test_malformed_json_maps_to_unknown() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>not json</html>")

    provider = _provider(handler)
    with pytest.raises(RazorpayUnknownOutcomeError):
        provider.fetch_order("order_x")


def test_fetch_order_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/orders/order_abc")
        return httpx.Response(200, json={**ORDER_BODY, "id": "order_abc", "status": "paid"})

    provider = _provider(handler)
    order = provider.fetch_order("order_abc")
    assert order.status == "paid"


def test_from_settings_requires_razorpay_selection() -> None:
    with pytest.raises(RazorpayConfigError):
        RazorpayPaymentProvider.from_settings(_settings(payment_provider="mock"))


def test_build_factory_returns_mock_without_credentials() -> None:
    from razormesh_api.providers.mock import MockPaymentProvider

    provider, kind = build_payment_provider_for_test(Settings(_env_file=None))
    assert kind == "mock"
    assert isinstance(provider, MockPaymentProvider)


def build_payment_provider_for_test(settings: Settings) -> tuple[object, str]:
    from razormesh_api.providers.razorpay import build_payment_provider

    provider, kind = build_payment_provider(settings)
    assert isinstance(kind, str)
    return provider, kind
