"""P2-M17: first REAL Razorpay Test Mode order via the trusted execution path.

Runs the full local trust pipeline (fixture authorization -> RazorGuard ALLOW ->
reservation -> ticket -> nonce -> durable ExecutionAttempt) and lets the trusted
executor create ONE real Test Mode order. No checkout/payment is performed.

Prints safe identifiers only. Requires: Docker infra up, migrations applied,
dev keys generated, PAYMENT_PROVIDER=razorpay in .env.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

from razormesh_api.catalog import seed_catalog
from razormesh_api.checkout_service import CheckoutService, ProposedItem
from razormesh_api.decider import DecisionEngine
from razormesh_api.domain.ids import IntentId, new_ulid
from razormesh_api.executor import AttemptState, TrustedPaymentExecutor
from razormesh_api.keys import DevSigningKeys
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.nonce import NonceRegistry
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.models import IntentContract as RowIntent
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.providers.razorpay import RazorpayPaymentProvider
from razormesh_api.rules.catalog_rules import CATALOG_RULES
from razormesh_api.rules.money_rules import MONEY_RULES
from razormesh_api.rules.policy_rules import POLICY_RULES
from razormesh_api.settings import Settings
from razormesh_api.spend import SpendManager


def main() -> int:
    settings = Settings()
    if settings.payment_provider != "razorpay":
        print("PAYMENT_PROVIDER != razorpay; refusing to run.")
        return 2

    engine_url = settings.database_url
    repos = Repositories(create_session_factory(create_engine(engine_url)))
    keys = DevSigningKeys(
        private_path=settings.dev_ticket_private_key_path,
        public_path=settings.dev_ticket_public_key_path,
    ).ensure()

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

    ledger = EvidenceLedger(repos)
    engine_rules = DecisionEngine([*MONEY_RULES, *CATALOG_RULES, *POLICY_RULES])
    svc = CheckoutService(repos=repos, ledger=ledger, engine=engine_rules, keys=keys)

    proposal = svc.propose(intent_id=iid, items=[ProposedItem(product.id)])
    authz = svc.authorize(intent_id=iid, proposal=proposal)
    if (
        authz.outcome.decision.value != "ALLOW"
        or authz.signed_ticket is None
        or authz.binding is None
    ):
        print(
            f"RazorGuard did not ALLOW: {authz.outcome.decision} {authz.outcome.reason_codes}"
        )
        return 1

    spend = SpendManager(repos)
    # P2-M49 clean-room fix: the executor owns reservation (D-028) — a manual
    # reserve here double-held capacity and leaked a ghost reservation after
    # settlement. Only durable authorization capacity is prepared here.
    spend.ensure_authorization(iid, authorized_minor=10_000_000)

    nonces = NonceRegistry(
        __import__("redis").Redis.from_url(settings.redis_url, decode_responses=True),
        ttl_seconds=120,
    )
    provider = RazorpayPaymentProvider.from_settings(settings)
    executor = TrustedPaymentExecutor(
        repos=repos, keys=keys, nonces=nonces, provider=provider, spend=spend
    )

    attempt = executor.execute(
        signed_ticket=authz.signed_ticket,
        binding=authz.binding,
        intent_id=iid,
        now_utc=datetime.now(UTC),
    )

    print("== trusted-path result ==")
    print(
        json.dumps(
            {
                "intent_id": str(iid),
                "checkout_id": attempt.checkout_id,
                "execution_attempt_id": attempt.execution_attempt_id,
                "state": attempt.state,
                "amount_minor": attempt.amount_minor,
                "currency": attempt.currency,
                "razorpay_order_id": attempt.razorpay_order_id,
                "razorpay_order_status": attempt.razorpay_order_status,
                "reconcile_state": attempt.reconcile_state,
                "fulfilment_state": attempt.fulfilment_state,
            },
            indent=2,
        )
    )

    if attempt.state == AttemptState.EXECUTING.value and attempt.razorpay_order_id:
        fetched = provider.fetch_order(attempt.razorpay_order_id)
        print("== provider fetch (read-only reconciliation) ==")
        print(
            json.dumps(
                {
                    "fetched_order_id": fetched.order_id,
                    "status": fetched.status,
                    "amount_minor": fetched.amount_minor,
                    "currency": fetched.currency,
                    "receipt": fetched.receipt,
                    "amount_matches_internal": fetched.amount_minor
                    == attempt.amount_minor,
                    "currency_matches_internal": fetched.currency == attempt.currency,
                    "receipt_matches_internal": fetched.receipt
                    == f"r_{attempt.execution_attempt_id}",
                },
                indent=2,
            )
        )
        return 0

    print(f"UNEXPECTED terminal state: {attempt.state} code={attempt.error_code}")
    return 1


def create_engine(url: str):  # type: ignore[no-untyped-def]
    from razormesh_api.persistence.db import create_db_engine

    return create_db_engine(url)


if __name__ == "__main__":
    raise SystemExit(main())
