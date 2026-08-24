"""P2-M16: exhaustive Razorpay error-taxonomy classification matrix.

Every provider interaction class maps to exactly one internal error/state class:
- 401/403                     -> RAZORPAY_AUTH_FAILED            (definitive)
- 400/404/422                 -> RAZORPAY_ORDER_CREATE_REJECTED   (definitive)
- 429                         -> RAZORPAY_ORDER_CREATE_REJECTED   (no effect; never auto-retried)
- other definitive 3xx/4xx    -> RAZORPAY_ORDER_CREATE_REJECTED
- 500/502/503/504             -> UNKNOWN                          (truth not disproven)
- timeout / connection errors -> UNKNOWN
- malformed JSON / bad entity -> UNKNOWN
"""

from datetime import UTC, datetime

import httpx
import pytest

from razormesh_api.providers.razorpay import (
    RazorpayAuthError,
    RazorpayClient,
    RazorpayRejectionError,
    RazorpayUnknownOutcomeError,
)

NOW = datetime.now(UTC)


def _client(responder) -> RazorpayClient:  # type: ignore[no-untyped-def]
    return RazorpayClient(
        key_id="rzp_test_k",
        key_secret="s",
        base_url="https://api.razorpay.com/v1",
        timeout_seconds=5,
        transport=httpx.MockTransport(responder),
    )


def _create(client: RazorpayClient):  # type: ignore[no-untyped-def]
    return client.create_order(amount_minor=100, currency="INR", receipt="r", notes={"a": "b"})


@pytest.mark.parametrize("status", [401, 403])
def test_auth_failures(status: int) -> None:
    with pytest.raises(RazorpayAuthError):
        _create(_client(lambda r: httpx.Response(status)))


@pytest.mark.parametrize("status", [400, 404, 422, 429, 405, 410])
def test_definitive_rejections(status: int) -> None:
    with pytest.raises(RazorpayRejectionError):
        _create(_client(lambda r: httpx.Response(status)))


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_server_errors_are_unknown(status: int) -> None:
    calls = 0

    def responder(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status)

    with pytest.raises(RazorpayUnknownOutcomeError):
        _create(_client(responder))
    assert calls == 1


def test_timeout_is_unknown() -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("t", request=request)

    with pytest.raises(RazorpayUnknownOutcomeError):
        _create(_client(responder))


def test_connect_error_is_unknown() -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns failure", request=request)

    with pytest.raises(RazorpayUnknownOutcomeError):
        _create(_client(responder))


def test_malformed_json_is_unknown() -> None:
    with pytest.raises(RazorpayUnknownOutcomeError):
        _create(_client(lambda r: httpx.Response(200, content=b"not-json")))


def test_non_dict_json_is_unknown() -> None:
    with pytest.raises(RazorpayUnknownOutcomeError):
        _create(_client(lambda r: httpx.Response(200, json=[1, 2, 3])))


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "created", "amount": 100, "currency": "INR"},  # no id
        {"id": "order_x", "status": "created", "currency": "INR"},  # no amount
        {"id": "order_x", "amount": -5, "currency": "INR"},  # invalid amount
        {"id": "order_x", "status": "created", "amount": 100},  # no currency
    ],
)
def test_invalid_entities_are_unknown(payload: dict) -> None:
    with pytest.raises(RazorpayUnknownOutcomeError):
        _create(_client(lambda r: httpx.Response(200, json=payload)))


def test_valid_entity_parses() -> None:
    order = _create(
        _client(
            lambda r: httpx.Response(
                201,
                json={
                    "id": "order_ok",
                    "status": "created",
                    "amount": 100,
                    "currency": "INR",
                },
            )
        )
    )
    assert order.order_id == "order_ok"
    assert order.amount_minor == 100
