#!/usr/bin/env python3
"""P2-M47: Phase-2 performance & network baseline (Test Mode, bounded).

Separates LOCAL COMPUTE from PROVIDER/NETWORK time:
- local: full trusted execution path (mock charge), callback HMAC verify,
  and webhook HMAC + durable-inbox claim + reducer settle against dev PostgreSQL;
- provider: REAL Razorpay TEST MODE order-create/fetch latency (bounded N;
  order entities only — no checkout/payment; disposable synthetic receipts).

Secrets are never printed. Output: docs/PHASE2_PERFORMANCE.json.
Run from the repository root.
"""

from __future__ import annotations

import json
import platform
import statistics
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

import hashlib as hl
import hmac as hm

import httpx
from razormesh_api.catalog import seed_catalog
from razormesh_api.checkout_service import CheckoutService, ProposedItem
from razormesh_api.decider import DecisionEngine
from razormesh_api.domain.ids import IntentId, new_ulid
from razormesh_api.executor import TrustedPaymentExecutor
from razormesh_api.keys import DevSigningKeys
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.nonce import NonceRegistry
from razormesh_api.persistence.db import (
    create_db_engine,
    create_session_factory,
)
from razormesh_api.persistence.models import IntentContract as RowIntent
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.providers.mock import MockMode, MockPaymentProvider
from razormesh_api.providers.razorpay import (
    RazorpayClient,
    RazorpayPaymentProvider,
)
from razormesh_api.reducer import (
    ProviderStateReducer,
    VerifiedProviderEvent,
)
from razormesh_api.rules.catalog_rules import CATALOG_RULES
from razormesh_api.rules.money_rules import MONEY_RULES
from razormesh_api.rules.policy_rules import POLICY_RULES
from razormesh_api.settings import get_settings
from razormesh_api.spend import SpendManager
from razormesh_api.webhook_inbox import ingest_verified_event

N_LOCAL_EXECUTOR = 50
N_HMAC = 3000
N_WEBHOOK = 50
N_PROVIDER = 5


def _stats(samples_ms: list[float]) -> dict[str, float | int]:
    return {
        "n": len(samples_ms),
        "mean_ms": round(statistics.mean(samples_ms), 4),
        "p50_ms": round(statistics.median(samples_ms), 4),
        "p95_ms": round(
            max(sorted(samples_ms)[: max(1, int(len(samples_ms) * 0.95) or 1)]), 4
        )
        if len(samples_ms) < 20
        else round(statistics.quantiles(samples_ms, n=20)[18], 4),
        "min_ms": round(min(samples_ms), 4),
        "max_ms": round(max(samples_ms), 4),
    }


def _time(fn, n: int) -> list[float]:
    out: list[float] = []
    for _ in range(n):
        t0 = datetime.now(UTC)
        fn()
        out.append((datetime.now(UTC) - t0).total_seconds() * 1000.0)
    return out


def main() -> int:
    settings = get_settings()
    repos = Repositories(
        create_session_factory(create_db_engine(settings.database_url))
    )
    keys = DevSigningKeys(
        private_path=settings.dev_ticket_private_key_path,
        public_path=settings.dev_ticket_public_key_path,
    ).ensure()
    spend = SpendManager(repos)

    def nonces() -> NonceRegistry:
        import redis

        return NonceRegistry(
            redis.Redis.from_url(settings.redis_url, decode_responses=True),
            ttl_seconds=120,
        )

    def checkout_service() -> CheckoutService:
        return CheckoutService(
            repos=repos,
            ledger=EvidenceLedger(repos),
            engine=DecisionEngine([*MONEY_RULES, *CATALOG_RULES, *POLICY_RULES]),
            keys=keys,
        )

    def make_authorized():
        """Fresh fixture authorization through the REAL RazorGuard path."""
        seed_catalog(repos)
        product = min(repos.products.list(limit=100), key=lambda p: p.price_minor)
        iid = IntentId.generate()
        now = datetime.now(UTC)
        payable = product.price_minor + product.shipping_minor
        with repos.transaction() as s:
            s.merge(
                RowIntent(
                    intent_id=str(iid),
                    principal_id=f"usr_{new_ulid()}",
                    agent_id=f"agt_{new_ulid()}",
                    authorization_generation=1,
                    status="AUTHORIZED",
                    currency="INR",
                    recurring_allowed=False,
                    max_total_minor=10_000_000,
                    aggregate_budget_minor=50_000_000,
                    max_quantity=1,
                    approval_threshold_minor=payable,
                    issued_at=now,
                    authorized_at=now,
                    expires_at=now + timedelta(minutes=30),
                    created_at=now,
                    updated_at=now,
                )
            )
        svc = checkout_service()
        proposal = svc.propose(intent_id=iid, items=[ProposedItem(product.id)])
        authz = svc.authorize(intent_id=iid, proposal=proposal)
        assert authz.signed_ticket is not None and authz.binding is not None
        spend.ensure_authorization(iid, authorized_minor=10_000_000)
        return iid, authz

    result: dict[str, object] = {
        "context": _context(settings),
        "local": {},
        "provider": {},
    }

    # ---------------- LOCAL: trusted execution path (mock charge) ----------
    def local_execute() -> None:
        iid, authz = make_authorized()
        executor = TrustedPaymentExecutor(
            repos=repos,
            keys=keys,
            nonces=nonces(),
            provider=MockPaymentProvider(mode=MockMode.SUCCESS),
            spend=spend,
        )
        assert authz.signed_ticket is not None and authz.binding is not None
        executor.execute(
            signed_ticket=authz.signed_ticket, binding=authz.binding, intent_id=iid
        )

    result["local"]["executor_trusted_path_mock"] = _stats(
        _time(local_execute, N_LOCAL_EXECUTOR)
    )  # type: ignore[assignment]

    # ---------------- LOCAL: callback HMAC verification (pure compute) -----
    cb_secret = "perf-local-only-secret"
    good_sig = hm.new(cb_secret.encode(), b"order_x|pay_y", hl.sha256).hexdigest()
    from razormesh_api.providers.razorpay import verify_checkout_signature

    samples = _time(
        lambda: verify_checkout_signature(
            order_id="order_x",
            payment_id="pay_y",
            signature_hex=good_sig,
            key_secret=cb_secret,
        ),
        N_HMAC,
    )
    result["local"]["callback_hmac_verify"] = _stats(samples)  # type: ignore[assignment]

    # ------------- LOCAL: webhook HMAC + inbox claim + reducer settle ------
    def scripted_provider() -> RazorpayPaymentProvider:
        counter = {"n": 0}

        def ok_order(request: httpx.Request) -> httpx.Response:
            counter["n"] += 1
            return httpx.Response(
                201,
                json={
                    "id": f"order_perf_local_{counter['n']}_{new_ulid().lower()}",
                    "status": "created",
                    "amount": 100,
                    "currency": "INR",
                },
            )

        client = RazorpayClient(
            key_id="rzp_test_perf",
            key_secret="perf-local-only",
            base_url=settings.razorpay_api_base_url,
            timeout_seconds=5,
            transport=httpx.MockTransport(ok_order),
        )
        return RazorpayPaymentProvider(client)

    rz_local = scripted_provider()
    reducer = ProviderStateReducer(
        repos=repos,
        keys=keys,
        nonces=nonces(),
        provider=None,
        spend=SpendManager(repos),
    )
    wh_counter = {"i": 0}

    def webhook_pass() -> None:
        iid, authz = make_authorized()
        executor = TrustedPaymentExecutor(
            repos=repos, keys=keys, nonces=nonces(), provider=rz_local, spend=spend
        )
        assert authz.signed_ticket is not None and authz.binding is not None
        att = executor.execute(
            signed_ticket=authz.signed_ticket, binding=authz.binding, intent_id=iid
        )
        assert att.razorpay_order_id is not None
        wh_counter["i"] += 1
        body = (
            '{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_p'
            + str(wh_counter["i"])
            + '","order_id":"'
            + att.razorpay_order_id
            + '"}}}}'
        ).encode()
        signature = hm.new(b"whsec-perf-local", body, hl.sha256).hexdigest()
        from razormesh_api.providers.razorpay import verify_webhook_signature

        assert verify_webhook_signature(
            raw_body=body, signature=signature, webhook_secret="whsec-perf-local"
        )

        def process() -> None:
            reducer.apply_event(
                VerifiedProviderEvent(
                    kind="payment.captured",
                    razorpay_order_id=str(att.razorpay_order_id),
                )
            )

        ingest_verified_event(
            repos,
            event_id=f"evt_perf_{new_ulid().lower()}",
            event_type="payment.captured",
            payload_sha256=hl.sha256(body).hexdigest(),
            razorpay_order_id=str(att.razorpay_order_id),
            razorpay_payment_id=None,
            process=process,
        )

    result["local"]["webhook_ingest_end_to_end_db"] = _stats(
        _time(webhook_pass, N_WEBHOOK)
    )  # type: ignore[assignment]

    # ------------- PROVIDER: real Test Mode create/fetch (bounded) ---------
    if settings.payment_provider == "razorpay":
        real = RazorpayClient(
            key_id=settings.razorpay_key_id,
            key_secret=settings.razorpay_key_secret.get_secret_value(),
            base_url=settings.razorpay_api_base_url,
            timeout_seconds=settings.razorpay_request_timeout_seconds,
        )
        provider = RazorpayPaymentProvider(real)
        create_ms: list[float] = []
        fetch_ms: list[float] = []
        for i in range(N_PROVIDER):
            receipt = f"r_perf_{int(datetime.now(UTC).timestamp())}_{i}"[:40]
            t0 = datetime.now(UTC)
            order = provider.create_order(
                amount_minor=100,
                currency="INR",
                receipt=receipt,
                notes={
                    "intent_id": "perf",
                    "checkout_id": "perf",
                    "decision_id": "perf",
                    "ticket_id": "perf",
                    "authorization_generation": "1",
                },
            )
            create_ms.append((datetime.now(UTC) - t0).total_seconds() * 1000.0)
            t0 = datetime.now(UTC)
            provider.fetch_order(order.order_id)
            fetch_ms.append((datetime.now(UTC) - t0).total_seconds() * 1000.0)
        result["provider"] = {  # type: ignore[assignment]
            "mode": "REAL_RAZORPAY_TEST_MODE",
            "note": "order entities only; no checkout/payment performed; ids are disposable",
            "create_order": _stats(create_ms),
            "fetch_order": _stats(fetch_ms),
            "sample_n": N_PROVIDER,
        }
    else:
        result["provider"] = {"mode": "SKIPPED_MOCK_SELECTOR"}  # type: ignore[assignment]

    artifact = {
        **result,
        "human_reference": {
            "source": "docs/PHASE2_STATUS.md M38/M40 evidence (recorded live sessions)",
            "caveat": "human-in-the-loop wall time dominates live flows and is NOT system performance",
        },
        "generated_at_utc": datetime.now(UTC).isoformat(),
    }
    out = REPO_ROOT / "docs" / "PHASE2_PERFORMANCE.json"
    out.write_text(json.dumps(artifact, indent=2))
    print(f"written: {out}")
    return 0


def _context(settings) -> dict[str, object]:  # type: ignore[no-untyped-def]
    uname = platform.uname()
    return {
        "label": "Phase-2 baseline: local compute vs provider/network separation; NOT production capacity",
        "platform": f"{uname.system}-{uname.release}-{uname.machine}",
        "machine": uname.machine,
        "cpu": platform.processor() or uname.machine,
        "python_version": platform.python_version(),
        "payment_provider_selector": settings.payment_provider,
        "test_mode_caveat": "Razorpay Test Mode latency is NOT representative of Live Mode production traffic",
    }


if __name__ == "__main__":
    raise SystemExit(main())
