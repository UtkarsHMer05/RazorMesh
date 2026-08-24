"""P2-M41: provider-unknown / timeout reconciliation proofs.

Fault injection is LOCAL ONLY (httpx transports) — Razorpay is never attacked.

Proven here:
- dropped-response/timeout during order create -> PROVIDER_UNKNOWN,
  reconcile_state=REQUIRED, reservation HELD, no correlated order id (P2-S18);
- re-entry with the same ticket never re-sends the order create (P2-S19);
- receipt DISCOVERY recovers the provider order read-only and claims the
  correlation ONLY after authority validation; a claimed order makes later
  webhooks correlate normally again;
- fetch-proven capture evidence settles exactly-once through the ONE reducer
  and terminal settlements mark reconcile_state=RESOLVED;
- authority mismatches raise loudly and mutate nothing (P2-S06);
- ops surface exposes REQUIRED attempts read-only and runs one safe pass.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from razormesh_api.api.main import app
from razormesh_api.api.routes import ops as ops_route
from razormesh_api.executor import AttemptState, TrustedPaymentExecutor
from razormesh_api.persistence.models import (
    AuthorizationSpend,
    Checkout,
    Decision,
    ExecutionAttempt,
    ExecutionTicket,
)
from razormesh_api.providers.razorpay import (
    RazorpayClient,
    RazorpayPaymentProvider,
    RazorpayProviderStateConflict,
)
from razormesh_api.reconciliation import ReconciliationOutcome, ReconciliationService
from razormesh_api.reducer import ProviderStateReducer, VerifiedProviderEvent
from razormesh_api.settings import get_settings
from razormesh_api.spend import SpendManager
from test_executor import _make_ticket, _redis


class _CountingTransport(httpx.BaseTransport):
    def __init__(self, responder) -> None:  # type: ignore[no-untyped-def]
        self._responder = responder
        self.calls = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        return self._responder(request)


def _client_for(transport: _CountingTransport) -> RazorpayPaymentProvider:
    client = RazorpayClient(
        key_id="rzp_test_k",
        key_secret="s",
        base_url=get_settings().razorpay_api_base_url,
        timeout_seconds=5,
        transport=transport,
    )
    return RazorpayPaymentProvider(client)


@pytest.fixture()
def rec_env(tmp_path):  # type: ignore[no-untyped-def]
    from sqlalchemy import create_engine

    from razormesh_api.keys import DevSigningKeys
    from razormesh_api.persistence.db import create_session_factory
    from razormesh_api.persistence.models import IntentContract as RowIntent
    from razormesh_api.persistence.models import Merchant
    from razormesh_api.persistence.repositories import Repositories

    engine = create_engine(get_settings().database_url, future=True)
    repos = Repositories(create_session_factory(engine))
    keys = DevSigningKeys(
        private_path=str(tmp_path / "p.pem"), public_path=str(tmp_path / "pub.pem")
    ).ensure()
    spend = SpendManager(repos)
    yield repos, keys, spend
    with repos.transaction() as s:
        s.query(ExecutionAttempt).delete()
        s.query(ExecutionTicket).delete()
        s.query(Decision).delete()
        s.query(Checkout).delete()
        s.query(AuthorizationSpend).delete()
        s.query(Merchant).delete()
        s.query(RowIntent).delete()


def _unknown_attempt(repos, keys, spend):  # type: ignore[no-untyped-def]
    """Drive a REAL executor through a local timeout fault -> PROVIDER_UNKNOWN."""

    def dropped(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated dropped response", request=request)

    executor = TrustedPaymentExecutor(
        repos=repos,
        keys=keys,
        nonces=_redis(),
        provider=_client_for(_CountingTransport(dropped)),
        spend=spend,
    )
    signed, binding, contract = _make_ticket(keys, repos)
    spend.ensure_authorization(contract.intent_id, authorized_minor=5_000_000)
    attempt = executor.execute(signed_ticket=signed, binding=binding, intent_id=contract.intent_id)
    assert attempt.state == AttemptState.PROVIDER_UNKNOWN.value
    assert attempt.reconcile_state == "REQUIRED"
    assert attempt.razorpay_order_id is None  # response lost before parse
    return attempt, signed, binding, contract


def _spend_row(repos, intent_id):  # type: ignore[no-untyped-def]
    with repos.transaction() as s:
        row = s.get(AuthorizationSpend, str(intent_id))
        assert row is not None
        return row


def _keys():  # type: ignore[no-untyped-def]
    import tempfile

    from razormesh_api.keys import DevSigningKeys

    d = tempfile.mkdtemp(prefix="rzp_m41_")
    return DevSigningKeys(private_path=f"{d}/p.pem", public_path=f"{d}/pub.pem").ensure()


def _service(repos, provider) -> ReconciliationService:  # type: ignore[no-untyped-def]
    reducer = ProviderStateReducer(
        repos=repos, keys=_keys(), nonces=_redis(), provider=provider, spend=SpendManager(repos)
    )
    return ReconciliationService(repos=repos, provider=provider, reducer=reducer)


def _reducer(repos):  # type: ignore[no-untyped-def]
    return ProviderStateReducer(
        repos=repos, keys=_keys(), nonces=_redis(), provider=None, spend=SpendManager(repos)
    )


def _order_entity(attempt, status: str, *, amount=None, currency=None, receipt=None):  # type: ignore[no-untyped-def]
    entity = {
        "id": "order_disc_1",
        "status": status,
        "amount": attempt.amount_minor if amount is None else amount,
        "currency": attempt.currency if currency is None else currency,
        "receipt": f"r_{attempt.execution_attempt_id}" if receipt is None else receipt,
    }
    return entity


def _orders_transport(
    attempt, status: str, *, amount=None, currency=None, receipt=None, extra_items=None
):
    """Routes GET /orders (discovery listing) and GET /orders/{id} (fetch)."""

    def responder(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/orders"):
            item = _order_entity(attempt, status, amount=amount, currency=currency, receipt=receipt)
            items = [item] + (extra_items or [])
            return httpx.Response(200, json={"count": len(items), "items": items})
        assert "/orders/" in request.url.path
        entity = _order_entity(attempt, status, amount=amount, currency=currency, receipt=receipt)
        return httpx.Response(200, json=entity)

    return responder


def test_timeout_discovery_claims_created_and_keeps_waiting(rec_env) -> None:  # type: ignore[no-untyped-def]
    repos, keys, spend = rec_env
    attempt, _signed, _binding, _contract = _unknown_attempt(repos, keys, spend)

    recon = _CountingTransport(_orders_transport(attempt, "created"))
    outcome = _service(repos, _client_for(recon)).reconcile(attempt.execution_attempt_id)

    assert recon.calls == 2  # one listing (discovery) + one exact fetch
    assert outcome.order_discovered_and_claimed is True
    assert outcome.attempt_state_before == AttemptState.PROVIDER_UNKNOWN.value
    assert outcome.attempt_state_after == AttemptState.PROVIDER_UNKNOWN.value
    assert outcome.provider_order_status == "created"
    assert outcome.settled_by_reconciliation is False
    assert outcome.reconcile_state_after == "REQUIRED"

    with repos.transaction() as s:
        refreshed = s.get(ExecutionAttempt, attempt.execution_attempt_id)
        assert refreshed is not None
        assert refreshed.razorpay_order_id == "order_disc_1"  # correlation CLAIMED
        assert refreshed.razorpay_order_status == "created"
    row = _spend_row(repos, attempt.intent_id)
    assert row.reserved_minor == attempt.amount_minor  # reservation still held
    assert row.committed_minor == 0


def test_discovery_miss_keeps_identity_and_reservation(rec_env) -> None:  # type: ignore[no-untyped-def]
    repos, keys, spend = rec_env
    attempt, _signed, _binding, _contract = _unknown_attempt(repos, keys, spend)

    def empty_listing(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/orders")
        return httpx.Response(200, json={"count": 0, "items": []})

    outcome = _service(repos, _client_for(_CountingTransport(empty_listing))).reconcile(
        attempt.execution_attempt_id
    )

    assert outcome.order_discovered_and_claimed is False
    assert outcome.settled_by_reconciliation is False
    assert outcome.reconcile_state_after == "REQUIRED"
    with repos.transaction() as s:
        refreshed = s.get(ExecutionAttempt, attempt.execution_attempt_id)
        assert refreshed is not None
        assert refreshed.state == AttemptState.PROVIDER_UNKNOWN.value
        assert refreshed.razorpay_order_id is None  # nothing invented
    row = _spend_row(repos, attempt.intent_id)
    assert row.reserved_minor == attempt.amount_minor


def test_fetch_paid_resolves_unknown_exactly_once(rec_env) -> None:  # type: ignore[no-untyped-def]
    repos, keys, spend = rec_env
    attempt, _signed, _binding, _contract = _unknown_attempt(repos, keys, spend)

    service = _service(repos, _client_for(_CountingTransport(_orders_transport(attempt, "paid"))))
    outcome = service.reconcile(attempt.execution_attempt_id)

    assert outcome.settled_by_reconciliation is True
    assert outcome.attempt_state_after == AttemptState.SUCCEEDED.value
    assert outcome.reconcile_state_after == "RESOLVED"
    row = _spend_row(repos, attempt.intent_id)
    assert row.reserved_minor == 0
    assert row.committed_minor == attempt.amount_minor  # committed EXACTLY once

    second = service.reconcile(attempt.execution_attempt_id)
    assert second.attempt_state_after == AttemptState.SUCCEEDED.value
    assert second.settled_by_reconciliation is False  # idempotent no-op
    row2 = _spend_row(repos, attempt.intent_id)
    assert row2.committed_minor == attempt.amount_minor  # never double-committed

    with repos.transaction() as s:
        refreshed = s.get(ExecutionAttempt, attempt.execution_attempt_id)
        assert refreshed is not None
        assert refreshed.fulfilment_state == "ELIGIBLE"


def test_webhook_correlates_after_claim_and_settles_once(rec_env) -> None:  # type: ignore[no-untyped-def]
    """The regression that motivates discovery: BEFORE claiming, a webhook for
    the never-learned order cannot correlate. AFTER claiming, the SAME event
    settles exactly-once."""
    repos, keys, spend = rec_env
    attempt, _signed, _binding, _contract = _unknown_attempt(repos, keys, spend)

    reducer = _reducer(repos)
    with pytest.raises(Exception, match="no execution context claims"):
        reducer.apply_event(
            VerifiedProviderEvent(kind="payment.captured", razorpay_order_id="order_never_learned")
        )  # pre-claim: cannot correlate (safe)

    _service(
        repos, _client_for(_CountingTransport(_orders_transport(attempt, "created")))
    ).reconcile(attempt.execution_attempt_id)

    settled = reducer.apply_event(
        VerifiedProviderEvent(
            kind="payment.captured",
            razorpay_order_id="order_disc_1",
            razorpay_payment_id="pay_rec_1",
        )
    )
    assert settled.state == AttemptState.SUCCEEDED.value
    row = _spend_row(repos, attempt.intent_id)
    assert row.reserved_minor == 0
    assert row.committed_minor == attempt.amount_minor
    with repos.transaction() as s:
        refreshed = s.get(ExecutionAttempt, attempt.execution_attempt_id)
        assert refreshed is not None
        assert refreshed.reconcile_state == "RESOLVED"
        assert refreshed.fulfilment_state == "ELIGIBLE"


def test_authority_mismatch_mutates_nothing(rec_env) -> None:  # type: ignore[no-untyped-def]
    repos, keys, spend = rec_env
    attempt, _signed, _binding, _contract = _unknown_attempt(repos, keys, spend)

    with pytest.raises(RazorpayProviderStateConflict) as excinfo:
        _service(
            repos,
            _client_for(
                _CountingTransport(
                    _orders_transport(attempt, "paid", amount=attempt.amount_minor - 1)
                )
            ),
        ).reconcile(attempt.execution_attempt_id)
    assert excinfo.value.code == "RAZORPAY_AMOUNT_MISMATCH"

    with repos.transaction() as s:
        refreshed = s.get(ExecutionAttempt, attempt.execution_attempt_id)
        assert refreshed is not None
        assert refreshed.state == AttemptState.PROVIDER_UNKNOWN.value
        assert refreshed.reconcile_state == "REQUIRED"
        assert refreshed.razorpay_order_id is None  # conflicting order NEVER claimed
    row = _spend_row(repos, attempt.intent_id)
    assert row.reserved_minor == attempt.amount_minor
    assert row.committed_minor == 0

    with pytest.raises(RazorpayProviderStateConflict) as cur_exc:
        _service(
            repos,
            _client_for(_CountingTransport(_orders_transport(attempt, "paid", currency="USD"))),
        ).reconcile(
            attempt.execution_attempt_id
        )
    assert cur_exc.value.code == "RAZORPAY_CURRENCY_MISMATCH"


def test_duplicate_receipt_is_a_loud_conflict(rec_env) -> None:  # type: ignore[no-untyped-def]
    repos, keys, spend = rec_env
    attempt, _signed, _binding, _contract = _unknown_attempt(repos, keys, spend)

    duplicate = _order_entity(attempt, "created")
    second = dict(duplicate)
    second["id"] = "order_disc_2"

    with pytest.raises(RazorpayProviderStateConflict) as excinfo:
        _service(
            repos,
            _client_for(
                _CountingTransport(_orders_transport(attempt, "created", extra_items=[second]))
            ),
        ).reconcile(attempt.execution_attempt_id)
    assert excinfo.value.code == "RAZORPAY_ORDER_CONTEXT_MISMATCH"
    with repos.transaction() as s:
        refreshed = s.get(ExecutionAttempt, attempt.execution_attempt_id)
        assert refreshed is not None
        assert refreshed.razorpay_order_id is None


def test_unknown_attempt_raises_valueerror(rec_env) -> None:  # type: ignore[no-untyped-def]
    repos, _keys, _spend = rec_env
    with pytest.raises(ValueError):
        _service(repos, _client_for(_CountingTransport(lambda r: httpx.Response(200)))).reconcile(
            "exa_does_not_exist"
        )


def test_webhook_failure_resolution_marks_resolved(rec_env) -> None:  # type: ignore[no-untyped-def]
    repos, keys, spend = rec_env
    attempt, _signed, _binding, _contract = _unknown_attempt(repos, keys, spend)

    # Claim correlation first (discovery path); THEN the failure webhook correlates.
    _service(
        repos, _client_for(_CountingTransport(_orders_transport(attempt, "created")))
    ).reconcile(attempt.execution_attempt_id)

    settled = _reducer(repos).apply_event(
        VerifiedProviderEvent(
            kind="payment.failed",
            razorpay_order_id="order_disc_1",
            razorpay_payment_id="pay_failed_1",
        )
    )
    assert settled.state == AttemptState.FAILED.value
    with repos.transaction() as s:
        refreshed = s.get(ExecutionAttempt, attempt.execution_attempt_id)
        assert refreshed is not None
        assert refreshed.reconcile_state == "RESOLVED"  # M41 fix: never stranded REQUIRED
    row = _spend_row(repos, attempt.intent_id)
    assert row.reserved_minor == 0
    assert row.committed_minor == 0


# ---------------------------------------------------------------------------
# Ops surface (read-only listing + single safe pass wiring)
# ---------------------------------------------------------------------------


def test_ops_required_listing_and_pass_wiring(rec_env, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    repos, keys, spend = rec_env
    attempt, _signed, _binding, _contract = _unknown_attempt(repos, keys, spend)

    client = TestClient(app)
    listing = client.get("/ops/reconciliation/required")
    assert listing.status_code == 200
    body = listing.json()
    assert body["count"] >= 1
    match = [
        row
        for row in body["attempts"]
        if row["execution_attempt_id"] == attempt.execution_attempt_id
    ]
    assert match, "UNKNOWN attempt must be exposed on the reconciliation view"
    assert match[0]["state"] == AttemptState.PROVIDER_UNKNOWN.value
    assert match[0]["error_code"]
    assert "secret" not in {key.lower() for key in match[0]}  # safe fields only

    ok_outcome = ReconciliationOutcome(
        attempt_id=attempt.execution_attempt_id,
        intent_id=attempt.intent_id,
        order_id="order_stub_1",
        attempt_state_before=attempt.state,
        attempt_state_after=AttemptState.SUCCEEDED.value,
        reconcile_state_after="RESOLVED",
        provider_order_status="paid",
        order_discovered_and_claimed=True,
        settled_by_reconciliation=True,
        detail="capture evidence reduced through provider-state reducer",
    )

    class _StubService:
        def __init__(self, behavior) -> None:  # type: ignore[no-untyped-def]
            self._behavior = behavior

        def reconcile(self, attempt_id: str, *, now=None):  # type: ignore[no-untyped-def]
            return self._behavior(attempt_id)

    monkeypatch.setattr(
        ops_route, "_service", lambda settings: _StubService(lambda aid: ok_outcome)
    )
    ran = client.post(f"/ops/reconciliation/{attempt.execution_attempt_id}")
    assert ran.status_code == 200
    assert ran.json()["settled_by_reconciliation"] is True

    monkeypatch.setattr(
        ops_route,
        "_service",
        lambda settings: _StubService(
            lambda aid: (_ for _ in ()).throw(ValueError("not reconcilable"))
        ),
    )
    missing = client.post("/ops/reconciliation/exa_missing")
    assert missing.status_code == 404

    monkeypatch.setattr(
        ops_route,
        "_service",
        lambda settings: _StubService(
            lambda aid: (_ for _ in ()).throw(
                RazorpayProviderStateConflict("RAZORPAY_AMOUNT_MISMATCH", "conflict")
            )
        ),
    )
    conflict = client.post(f"/ops/reconciliation/{attempt.execution_attempt_id}")
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "RAZORPAY_AMOUNT_MISMATCH"


def test_settled_attempt_leaves_required_view(rec_env) -> None:  # type: ignore[no-untyped-def]
    repos, keys, spend = rec_env
    attempt, _signed, _binding, _contract = _unknown_attempt(repos, keys, spend)

    client = TestClient(app)
    before = client.get("/ops/reconciliation/required").json()
    assert attempt.execution_attempt_id in [
        row["execution_attempt_id"] for row in before["attempts"]
    ]

    _service(repos, _client_for(_CountingTransport(_orders_transport(attempt, "paid")))).reconcile(
        attempt.execution_attempt_id
    )

    after = client.get("/ops/reconciliation/required").json()
    assert attempt.execution_attempt_id not in [
        row["execution_attempt_id"] for row in after["attempts"]
    ]
