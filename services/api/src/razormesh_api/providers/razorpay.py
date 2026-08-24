"""P2-M11/M16: Razorpay Test Mode provider behind the project trust boundary.

Decision D-030: ONE thin httpx wrapper; no SDK; NO transport-level automatic
retries (a mutating call must never be silently re-sent — P2-S17..S19).

Security properties:
- Only trusted execution components may import this module; buyer/agent layers
  never receive the client or credentials (SEC-001, P2-S23).
- Amount/currency sent to Razorpay come exclusively from durable internal state
  (P2-S05/S06); this module never accepts browser-derived values.
- Errors carry reason codes, never secret material or raw provider payloads.

Timeout semantics (master prompt §27): a timeout or connection failure AFTER the
request may have reached Razorpay maps to UNKNOWN — the order may or may not
exist; reconciliation (fetch by known correlation) resolves it later.
"""

from dataclasses import dataclass
from typing import Any

import httpx

from razormesh_api.settings import Settings


class RazorpayError(Exception):
    """Base class. ``code`` uses the documented Phase-2 reason codes."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"[{code}] {detail}")
        self.code = code
        self.detail = detail


class RazorpayAuthError(RazorpayError):
    def __init__(self, detail: str) -> None:
        super().__init__("RAZORPAY_AUTH_FAILED", detail)


class RazorpayConfigError(RazorpayError):
    def __init__(self, detail: str) -> None:
        super().__init__("RAZORPAY_TEST_MODE_REQUIRED", detail)


class RazorpayRejectionError(RazorpayError):
    """Definitive provider-side rejection (4xx validation semantics)."""

    def __init__(self, detail: str) -> None:
        super().__init__("RAZORPAY_ORDER_CREATE_REJECTED", detail)


class RazorpayUnknownOutcomeError(RazorpayError):
    """The request MAY have reached the provider; truth must be reconciled."""

    def __init__(self, detail: str, *, operation: str = "ORDER_CREATE_UNKNOWN") -> None:
        self.operation_code = f"RAZORPAY_{operation}"
        super().__init__(self.operation_code, detail)


@dataclass(frozen=True)
class RazorpayOrder:
    """Minimal validated projection of a Razorpay order entity."""

    order_id: str
    status: str
    amount_minor: int
    currency: str
    receipt: str | None = None


def _validate_order_payload(payload: Any, *, operation: str) -> RazorpayOrder:
    if not isinstance(payload, dict):
        raise RazorpayUnknownOutcomeError("malformed provider response", operation=operation)
    order_id = payload.get("id")
    amount = payload.get("amount")
    currency = payload.get("currency")
    status = payload.get("status")
    if not isinstance(order_id, str) or not order_id:
        raise RazorpayUnknownOutcomeError("provider response missing order id", operation=operation)
    if not isinstance(amount, int) or amount <= 0:
        raise RazorpayUnknownOutcomeError(
            "provider response has invalid amount", operation=operation
        )
    if not isinstance(currency, str) or len(currency) != 3:
        raise RazorpayUnknownOutcomeError(
            "provider response has invalid currency", operation=operation
        )
    if not isinstance(status, str):
        raise RazorpayUnknownOutcomeError(
            "provider response has invalid status", operation=operation
        )
    receipt = payload.get("receipt")
    return RazorpayOrder(
        order_id=order_id,
        status=status,
        amount_minor=amount,
        currency=currency,
        receipt=receipt if isinstance(receipt, str) else None,
    )


class RazorpayClient:
    """Single project-standard HTTP client for Razorpay (D-030).

    ``transport`` exists purely as a test seam (httpx.MockTransport).
    """

    def __init__(
        self,
        *,
        key_id: str,
        key_secret: str,
        base_url: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._auth = (key_id, key_secret)
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._client = httpx.Client(
            auth=self._auth,
            base_url=self._base_url,
            timeout=self._timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------------
    def create_order(
        self, *, amount_minor: int, currency: str, receipt: str, notes: dict[str, str]
    ) -> RazorpayOrder:
        body = {
            "amount": amount_minor,
            "currency": currency,
            "receipt": receipt,
            "notes": notes,
        }
        return self._request("POST", "/orders", json_body=body)

    def fetch_order(self, order_id: str) -> RazorpayOrder:
        return self._request("GET", f"/orders/{order_id}")

    # ------------------------------------------------------------------
    def _request(
        self, method: str, path: str, *, json_body: dict[str, Any] | None = None
    ) -> RazorpayOrder:
        try:
            response = self._client.request(method, path, json=json_body)
        except httpx.TimeoutException as exc:
            raise RazorpayUnknownOutcomeError(
                f"provider timeout during {method} {path}: request outcome unknown"
            ) from exc
        except httpx.TransportError as exc:
            raise RazorpayUnknownOutcomeError(
                f"connection failure during {method} {path}: request outcome unknown"
            ) from exc

        if response.status_code == 401 or response.status_code == 403:
            raise RazorpayAuthError("credential rejected by provider")

        if response.status_code >= 500:
            # A 5xx after transmission leaves creation/fetch truth unknown.
            raise RazorpayUnknownOutcomeError(f"provider server error {response.status_code}")

        if response.status_code in (400, 404, 422):
            # 404 on fetch is definitive (order does not exist); on create it is
            # also definitive validation rejection. Never retried.
            raise RazorpayRejectionError(f"provider rejected request ({response.status_code})")

        if response.status_code != 200 and response.status_code != 201:
            raise RazorpayUnknownOutcomeError(f"unexpected provider status {response.status_code}")

        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise RazorpayUnknownOutcomeError("malformed JSON in provider response") from exc

        operation = "ORDER_FETCH_INVALID" if method == "GET" else "ORDER_CREATE_UNKNOWN"
        return _validate_order_payload(payload, operation=operation)


class RazorpayPaymentProvider:
    """Real Test Mode provider beside MockPaymentProvider.

    Standard Checkout is an asynchronous confirmation model: the server-side
    money-relevant operations are order creation (pre-browser) and state
    reconciliation (post-browser via fetch/webhook/callback). This class
    therefore exposes the order lifecycle instead of a synchronous charge();
    the trusted executor keeps sole authority over attempt/reservation state.
    """

    def __init__(self, client: RazorpayClient) -> None:
        self._client = client

    @classmethod
    def from_settings(cls, settings: Settings) -> "RazorpayPaymentProvider":
        from razormesh_api.settings import validate_payment_provider_config

        validate_payment_provider_config(settings)
        if settings.payment_provider != "razorpay":
            raise RazorpayConfigError(
                "RAZORPAY_TEST_MODE_REQUIRED: PAYMENT_PROVIDER must be 'razorpay' "
                "to construct the real provider"
            )
        if settings.razorpay_mode != "test":
            raise RazorpayConfigError("RAZORPAY_TEST_MODE_REQUIRED: mode != test")
        client = RazorpayClient(
            key_id=settings.razorpay_key_id,
            key_secret=settings.razorpay_key_secret.get_secret_value(),
            base_url=settings.razorpay_api_base_url,
            timeout_seconds=settings.razorpay_request_timeout_seconds,
        )
        return cls(client)

    @property
    def client(self) -> RazorpayClient:
        return self._client

    def create_order(
        self, *, amount_minor: int, currency: str, receipt: str, notes: dict[str, str]
    ) -> RazorpayOrder:
        return self._client.create_order(
            amount_minor=amount_minor,
            currency=currency,
            receipt=receipt,
            notes=notes,
        )

    def fetch_order(self, order_id: str) -> RazorpayOrder:
        return self._client.fetch_order(order_id)


def build_payment_provider(settings: Settings) -> tuple[object, object]:
    """Dependency-injection seam for trusted execution components.

    Returns ``(provider, kind)`` where kind is ``"mock"`` or ``"razorpay"``.
    Real-provider construction runs the fail-safe config guard (P2-S01..S03);
    mock construction requires no credentials (P2-S20). Never falls back from
    razorpay to mock on failure (P2-S21): configuration errors propagate loudly.
    """
    if settings.payment_provider == "razorpay":
        return RazorpayPaymentProvider.from_settings(settings), "razorpay"
    from razormesh_api.providers.mock import MockMode, MockPaymentProvider

    return MockPaymentProvider(mode=MockMode.SUCCESS), "mock"
