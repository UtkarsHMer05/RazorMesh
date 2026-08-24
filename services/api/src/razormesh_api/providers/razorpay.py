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
from datetime import datetime
from typing import TYPE_CHECKING, Any

import httpx

from razormesh_api.settings import Settings

if TYPE_CHECKING:
    from razormesh_api.persistence.repositories import Repositories
    from razormesh_api.providers.mock import MockPaymentProvider


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


@dataclass(frozen=True)
class RazorpayPaymentEntity:
    """Minimal validated projection of a Razorpay payment entity (read-only)."""

    payment_id: str
    status: str
    amount_minor: int
    currency: str
    order_id: str | None = None


@dataclass(frozen=True)
class RazorpayEventEntity:
    """Minimal validated projection of a Razorpay event entity (read-only)."""

    event_id: str
    event_type: str


def _validate_payment_payload(payload: Any, *, operation: str) -> RazorpayPaymentEntity:
    if not isinstance(payload, dict):
        raise RazorpayUnknownOutcomeError("malformed provider response", operation=operation)
    payment_id = payload.get("id")
    amount = payload.get("amount")
    currency = payload.get("currency")
    status = payload.get("status")
    if not isinstance(payment_id, str) or not payment_id:
        raise RazorpayUnknownOutcomeError(
            "provider response missing payment id", operation=operation
        )
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
    order_id = payload.get("order_id")
    return RazorpayPaymentEntity(
        payment_id=payment_id,
        status=status,
        amount_minor=amount,
        currency=currency,
        order_id=order_id if isinstance(order_id, str) and order_id else None,
    )


def _validate_event_payload(payload: Any, *, operation: str) -> RazorpayEventEntity:
    if not isinstance(payload, dict):
        raise RazorpayUnknownOutcomeError("malformed provider response", operation=operation)
    event_id = payload.get("id")
    event_type = payload.get("event")
    if not isinstance(event_id, str) or not event_id:
        raise RazorpayUnknownOutcomeError("provider response missing event id", operation=operation)
    if not isinstance(event_type, str) or not event_type:
        raise RazorpayUnknownOutcomeError(
            "provider response missing event type", operation=operation
        )
    return RazorpayEventEntity(event_id=event_id, event_type=event_type)


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

    def fetch_payment(self, payment_id: str) -> RazorpayPaymentEntity:
        """READ-ONLY reconciliation/evidence fetch (GET /payments/{id})."""
        payload = self._request_payload("GET", f"/payments/{payment_id}")
        return _validate_payment_payload(payload, operation="PAYMENT_FETCH_INVALID")

    def fetch_event(self, event_id: str) -> RazorpayEventEntity:
        """READ-ONLY reconciliation/evidence fetch (GET /events/{id})."""
        payload = self._request_payload("GET", f"/events/{event_id}")
        return _validate_event_payload(payload, operation="EVENT_FETCH_INVALID")

    # ------------------------------------------------------------------
    def _request(
        self, method: str, path: str, *, json_body: dict[str, Any] | None = None
    ) -> RazorpayOrder:
        payload = self._request_payload(method, path, json_body=json_body)
        operation = "ORDER_FETCH_INVALID" if method == "GET" else "ORDER_CREATE_UNKNOWN"
        return _validate_order_payload(payload, operation=operation)

    def _request_payload(
        self, method: str, path: str, *, json_body: dict[str, Any] | None = None
    ) -> Any:
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

        if response.status_code == 429:
            # Rate limiting refuses processing BEFORE any resource is created:
            # definitive no-effect. We still never auto-retry (P2-S19); a later
            # attempt requires a fresh execution authority.
            raise RazorpayRejectionError("provider rate limit refused processing (HTTP 429)")

        if response.status_code in (400, 404, 422):
            # 404 on fetch is definitive (entity does not exist); on create it is
            # also definitive validation rejection. Never retried.
            raise RazorpayRejectionError(f"provider rejected request ({response.status_code})")

        if (300 <= response.status_code < 400) or (405 <= response.status_code < 500):
            raise RazorpayRejectionError(
                f"provider definitively refused request ({response.status_code})"
            )

        if response.status_code != 200 and response.status_code != 201:
            raise RazorpayUnknownOutcomeError(f"unexpected provider status {response.status_code}")

        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise RazorpayUnknownOutcomeError("malformed JSON in provider response") from exc
        return payload


class RazorpayPaymentProvider:
    """Real Test Mode provider beside MockPaymentProvider.

    Standard Checkout is an asynchronous confirmation model: the server-side
    money-relevant operations are order creation (pre-browser) and state
    reconciliation (post-browser via fetch/webhook/callback). This class
    therefore exposes the order lifecycle instead of a synchronous charge();
    the trusted executor keeps sole authority over attempt/reservation state.
    """

    name: str = "razorpay"

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

    def fetch_payment(self, payment_id: str) -> RazorpayPaymentEntity:
        """READ-ONLY reconciliation/evidence fetch; no business mutation."""
        return self._client.fetch_payment(payment_id)

    def fetch_event(self, event_id: str) -> RazorpayEventEntity:
        """READ-ONLY reconciliation/evidence fetch; no business mutation."""
        return self._client.fetch_event(event_id)


def build_payment_provider(
    settings: Settings,
) -> "tuple[MockPaymentProvider | RazorpayPaymentProvider, str]":
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


class RazorpayAuthDiagnostic:
    """Read-only credential verification (P2-M12).

    Performs a bounded, read-only GET /orders?count=1 against the configured
    account. Authentication failures surface as RAZORPAY_AUTH_FAILED; success
    proves ONLY that the credentials are valid Test Mode credentials. The
    result never contains secret material.
    """

    def __init__(self, client: RazorpayClient) -> None:
        self._client = client

    def run(self) -> dict[str, object]:
        import time as _time

        started = _time.perf_counter_ns()
        try:
            response = self._client._client.get("/orders", params={"count": 1})
        except httpx.TimeoutException:
            return {
                "ok": False,
                "code": "RAZORPAY_PROVIDER_OUTCOME_UNKNOWN",
                "detail": "timeout during read-only diagnostic",
            }
        except httpx.TransportError:
            return {
                "ok": False,
                "code": "RAZORPAY_PROVIDER_OUTCOME_UNKNOWN",
                "detail": "network failure during read-only diagnostic",
            }

        elapsed_ms = round((_time.perf_counter_ns() - started) / 1e6, 2)

        if response.status_code in (401, 403):
            return {
                "ok": False,
                "code": "RAZORPAY_AUTH_FAILED",
                "detail": f"provider rejected credentials (HTTP {response.status_code})",
            }
        if response.status_code != 200:
            return {
                "ok": False,
                "code": "RAZORPAY_PROVIDER_STATE_CONFLICT",
                "detail": f"unexpected diagnostic status {response.status_code}",
            }
        try:
            payload: Any = response.json()
            count = payload.get("count") if isinstance(payload, dict) else None
            items = payload.get("items") if isinstance(payload, dict) else None
        except ValueError:
            return {
                "ok": False,
                "code": "RAZORPAY_PROVIDER_STATE_CONFLICT",
                "detail": "malformed JSON in diagnostic response",
            }

        return {
            "ok": True,
            "code": "OK",
            "detail": "credentials accepted by provider (read-only)",
            "mode": "test (guard passed)",
            "listed_orders": len(items) if isinstance(items, list) else None,
            "response_count_field": count,
            "latency_ms": elapsed_ms,
        }


def razorpay_auth_diagnostic_from_settings(settings: Settings) -> dict[str, object]:
    """Fail-safe entry point used by scripts and admin tooling."""
    provider = RazorpayPaymentProvider.from_settings(settings)
    return RazorpayAuthDiagnostic(provider.client).run()


# ---------------------------------------------------------------------------
# P2-M14: internal -> Razorpay order correlation (receipt/notes contract)
# Official limits (R-013): receipt <= 40 chars; notes <= 15 pairs, values <= 256.
# Only OPAQUE internal identifiers travel to the provider — never secrets,
# user identifiers beyond opaque tokens, or free text (P2-S22).
# ---------------------------------------------------------------------------

_RECEIPT_MAX = 40
_NOTES_MAX_PAIRS = 15
_NOTE_VALUE_MAX = 256

_NOTE_KEYS = ("intent_id", "checkout_id", "decision_id", "ticket_id")


def build_order_correlation(
    *,
    execution_attempt_id: str,
    intent_id: str,
    checkout_id: str,
    decision_id: str,
    ticket_id: str,
    authorization_generation: int,
) -> tuple[str, dict[str, str]]:
    """Return ``(receipt, notes)`` binding a Razorpay order to ONE execution context.

    The receipt embeds the durable execution-attempt id so any provider-side row
    can be traced back without storing provider state internally first.
    """
    receipt = f"r_{execution_attempt_id}"
    if len(execution_attempt_id) > _RECEIPT_MAX - 2:
        raise ValueError("execution attempt id exceeds receipt budget")
    if len(receipt) > _RECEIPT_MAX:
        raise ValueError("receipt exceeds Razorpay limit")

    notes = {
        "intent_id": intent_id,
        "checkout_id": checkout_id,
        "decision_id": decision_id,
        "ticket_id": ticket_id,
        "authorization_generation": str(authorization_generation),
    }
    if len(notes) > _NOTES_MAX_PAIRS:
        raise ValueError("too many note pairs")
    for key, value in notes.items():
        if len(key) > _NOTE_VALUE_MAX or len(value) > _NOTE_VALUE_MAX:
            raise ValueError(f"note pair exceeds limit: {key}")
    return receipt, notes


def parse_order_correlation(notes: dict[str, str]) -> dict[str, str]:
    """Extract the internal references from provider order notes."""
    return {key: notes[key] for key in _NOTE_KEYS if key in notes}


# ---------------------------------------------------------------------------
# P2-M18: fetch-based reconciliation against internal authority
# ---------------------------------------------------------------------------


class RazorpayProviderStateConflict(RazorpayError):
    """Provider state contradicts durable internal authority — never silently rewritten."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(code, detail)


@dataclass(frozen=True)
class ReconcileResult:
    attempt_id: str
    order_id: str
    provider_status: str
    payment_status: str | None
    consistent: bool


def reconcile_attempt(
    *,
    repos: "Repositories",
    provider: RazorpayPaymentProvider,
    attempt_id: str,
    now: datetime,
) -> ReconcileResult:
    """Fetch a KNOWN razorpay order and validate it against the durable attempt.

    Amount/currency mismatches raise RAZORPAY_AMOUNT_MISMATCH /
    RAZORPAY_CURRENCY_MISMATCH (P2-S06: provider never rewrites authority).
    Provider status is snapshotted onto the attempt; business settlement remains
    the reducer's job (M26+), so this call performs NO terminal transitions.
    """
    from razormesh_api.persistence.models import ExecutionAttempt

    with repos.transaction() as session:
        attempt = session.get(ExecutionAttempt, attempt_id, with_for_update=True)
        if attempt is None:
            raise ValueError(f"unknown attempt {attempt_id}")
        if not attempt.razorpay_order_id:
            raise ValueError(f"attempt {attempt_id} has no correlated razorpay order to reconcile")
        order_id = attempt.razorpay_order_id

    fetched = provider.fetch_order(order_id)

    if fetched.amount_minor != attempt.amount_minor:
        raise RazorpayProviderStateConflict(
            "RAZORPAY_AMOUNT_MISMATCH",
            f"provider {fetched.amount_minor} != internal {attempt.amount_minor}",
        )
    if fetched.currency != attempt.currency:
        raise RazorpayProviderStateConflict(
            "RAZORPAY_CURRENCY_MISMATCH",
            f"provider {fetched.currency} != internal {attempt.currency}",
        )
    if fetched.receipt is not None and fetched.receipt != f"r_{attempt.execution_attempt_id}":
        raise RazorpayProviderStateConflict(
            "RAZORPAY_ORDER_CONTEXT_MISMATCH",
            f"provider receipt {fetched.receipt!r} does not reference this attempt",
        )

    payment_status = None
    if fetched.status in ("paid", "attempted"):
        # orders entity exposes attempts/payments separately; capture evidence
        # arrives through payments/webhooks and is settled by the reducer.
        payment_status = "captured" if fetched.status == "paid" else None

    with repos.transaction() as session:
        row = session.get(ExecutionAttempt, attempt_id, with_for_update=True)
        if row is None:
            raise ValueError(f"attempt vanished: {attempt_id}")
        row.razorpay_order_status = fetched.status
        row.updated_at = now

    return ReconcileResult(
        attempt_id=attempt_id,
        order_id=order_id,
        provider_status=fetched.status,
        payment_status=payment_status,
        consistent=True,
    )


# ---------------------------------------------------------------------------
# P2-M19: Checkout launch contract (browser receives PUBLIC data ONLY)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckoutLaunchPayload:
    """Everything Standard Checkout needs — and NOTHING secret."""

    public_key_id: str
    razorpay_order_id: str
    amount_minor: int
    currency: str
    execution_attempt_id: str
    intent_id: str
    checkout_id: str


def build_launch_payload(
    *,
    attempt_state: str,
    attempt_amount_minor: int,
    attempt_currency: str,
    attempt_execution_attempt_id: str,
    attempt_intent_id: str,
    attempt_checkout_id: str,
    attempt_razorpay_order_id: str | None,
    settings: Settings,
) -> CheckoutLaunchPayload:
    """Issue a launch payload ONLY for an EXECUTING attempt holding an order claim."""
    if attempt_state != "EXECUTING":
        raise RazorpayError(
            "RAZORPAY_PAYMENT_NOT_CAPTURED",
            f"launch requires an in-progress order (attempt state {attempt_state})",
        )
    if not attempt_razorpay_order_id:
        raise RazorpayError(
            "RAZORPAY_ORDER_CONTEXT_MISMATCH",
            "launch requires a correlated razorpay order",
        )
    return CheckoutLaunchPayload(
        public_key_id=settings.razorpay_key_id,
        razorpay_order_id=attempt_razorpay_order_id,
        amount_minor=attempt_amount_minor,
        currency=attempt_currency,
        execution_attempt_id=attempt_execution_attempt_id,
        intent_id=attempt_intent_id,
        checkout_id=attempt_checkout_id,
    )


# ---------------------------------------------------------------------------
# P2-M23: mandatory server-side checkout signature verification
# Official formula: expected = HMAC_SHA256(order_id|payment_id, key_secret) hex
# CRITICAL: uses the SERVER-stored order id, never the browser's value (P2-S08).
# ---------------------------------------------------------------------------


def verify_checkout_signature(
    *, order_id: str, payment_id: str, signature_hex: str, key_secret: str
) -> bool:
    import hashlib
    import hmac as _hmac

    expected = _hmac.new(
        key_secret.encode("utf-8"),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return _hmac.compare_digest(expected, signature_hex.lower())


def verify_webhook_signature(*, raw_body: bytes, signature: str, webhook_secret: str) -> bool:
    """Official formula (R-014): HMAC_SHA256(raw_body, webhook_secret) hex compare."""
    import hashlib
    import hmac as _hmac

    expected = _hmac.new(webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return _hmac.compare_digest(expected, signature.strip().lower())
