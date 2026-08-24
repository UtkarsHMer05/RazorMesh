"""M43: adversarial evaluation runner — executes scenarios through the REAL pipeline.

For every M42 scenario the runner:

1. wipes + seeds clean state (fresh authorization, catalog, empty ledger);
2. builds a REAL RazorGuard path: CheckoutService -> DecisionEngine ->
   evidence ledger -> TicketIssuer -> nonce registry -> TrustedPaymentExecutor
   -> MockPaymentProvider;
3. applies ONLY the structured mutation from the spec;
4. records the ACTUAL outcome.

Expected labels are used exclusively for pass/fail scoring AFTER execution —
they are never visible to any decision component.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from razormesh_api.catalog import seed_catalog
from razormesh_api.checkout_service import AuthorizationResult, CheckoutService, ProposedItem
from razormesh_api.decider import Decision, DecisionEngine
from razormesh_api.domain.ids import IntentId, new_ulid
from razormesh_api.executor import AttemptState, TrustedPaymentExecutor
from razormesh_api.keys import DevKeyPair, DevSigningKeys
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.nonce import NonceAlreadyClaimed, NonceRegistry
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.models import ExecutionAttempt
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.providers.mock import MockMode, MockPaymentProvider
from razormesh_api.revalidation import Revalidator
from razormesh_api.rules.catalog_rules import CATALOG_RULES
from razormesh_api.rules.money_rules import MONEY_RULES
from razormesh_api.rules.policy_rules import POLICY_RULES
from razormesh_api.scenarios import (
    SCENARIOS,
    ExpectedOutcome,
    ScenarioFamily,
    ScenarioSpec,
)
from razormesh_api.spend import SpendManager
from razormesh_api.tickets import CurrentBinding, TicketRejected


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    family: ScenarioFamily
    expected: ExpectedOutcome
    actual: str
    passed: bool
    detail: str


def _now() -> datetime:
    return datetime.now(UTC)


class AdversarialRunner:
    def __init__(self, engine: Engine | None = None, keys: DevKeyPair | None = None) -> None:
        if engine is None:
            from razormesh_api.settings import get_settings

            engine = create_engine(get_settings().database_url, future=True)
        self._engine = engine
        self._repos = Repositories(create_session_factory(engine))
        self._keys = (
            keys
            or DevSigningKeys(
                private_path="infra/keys/dev_ticket_ed25519_private.pem",
                public_path="infra/keys/dev_ticket_ed25519_public.pem",
            ).ensure()
        )

    # ------------------------------------------------------------------
    def wipe(self) -> None:
        statements = (
            "DELETE FROM execution_attempts",
            "DELETE FROM execution_tickets",
            "DELETE FROM decisions",
            "DELETE FROM authorization_spend",
            "DELETE FROM checkouts",
            "DELETE FROM intent_contracts",
            "DELETE FROM products",
            "DELETE FROM merchants",
        )
        with self._engine.begin() as conn:
            for stmt in statements:
                conn.execute(text(stmt))

    def _make_intent(self, family: ScenarioFamily) -> tuple[IntentId, str]:
        seed_catalog(self._repos)
        iid = IntentId.generate()
        product = min(self._repos.products.list(limit=100), key=lambda p: p.price_minor)
        now = _now()
        expired = family is ScenarioFamily.EXPIRED_AUTHORIZATION
        split = family is ScenarioFamily.APPROVAL_SPLIT
        payable_total = product.price_minor + product.shipping_minor
        cap = payable_total if split else 10_000_000
        from razormesh_api.persistence.models import IntentContract as RowIntent

        with self._repos.transaction() as s:
            s.merge(
                RowIntent(
                    intent_id=str(iid),
                    principal_id=f"usr_{new_ulid()}",
                    agent_id=f"agt_{new_ulid()}",
                    authorization_generation=1,
                    status="AUTHORIZED",
                    currency="INR",
                    recurring_allowed=False,
                    max_total_minor=cap,
                    aggregate_budget_minor=payable_total if split else 50_000_000,
                    max_quantity=1,
                    approval_threshold_minor=payable_total,
                    issued_at=now,
                    authorized_at=now,
                    expires_at=now + self._minutes(30),
                    created_at=now,
                    updated_at=now,
                )
            )
        if expired:
            # simulate the passage of time after contract creation
            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE intent_contracts SET "
                        "issued_at = NOW() - INTERVAL '20 minutes', "
                        "authorized_at = NOW() - INTERVAL '15 minutes', "
                        "expires_at = NOW() - INTERVAL '5 minutes' "
                        "WHERE intent_id = :i"
                    ).bindparams(i=str(iid))
                )
        return iid, product.id

    @staticmethod
    def _minutes(m: int) -> timedelta:
        return timedelta(minutes=m)

    def _service(self) -> CheckoutService:
        ledger = EvidenceLedger(self._repos)
        rules = DecisionEngine([*MONEY_RULES, *CATALOG_RULES, *POLICY_RULES])
        return CheckoutService(repos=self._repos, ledger=ledger, engine=rules, keys=self._keys)

    def _executor(self, provider: MockPaymentProvider) -> TrustedPaymentExecutor:
        spend = SpendManager(self._repos)
        return TrustedPaymentExecutor(
            repos=self._repos,
            keys=self._keys,
            nonces=self._nonces(),
            provider=provider,
            spend=spend,
        )

    def _nonces(self) -> NonceRegistry:
        import os

        from redis import Redis

        url = os.environ.get("RAZORMESH_TEST_REDIS_URL", "redis://127.0.0.1:16379/0")
        return NonceRegistry(Redis.from_url(url, decode_responses=True), ttl_seconds=120)

    # ------------------------------------------------------------------
    def run_all(self) -> list[ScenarioResult]:
        return [self.run_one(spec) for spec in SCENARIOS]

    def run_one(self, spec: ScenarioSpec) -> ScenarioResult:
        try:
            self.wipe()
            iid, product_id = self._make_intent(spec.family)
            svc = self._service()

            proposal = svc.propose(intent_id=iid, items=[ProposedItem(product_id)])
            authz = svc.authorize(intent_id=iid, proposal=proposal)
        except Exception as exc:  # noqa: BLE001 - recorded as actual outcome
            return self._finish(spec, f"PIPELINE_ERROR:{type(exc).__name__}", str(exc)[:280])

        handler = {
            ScenarioFamily.SAFE_BASELINE: self._safe_baseline,
            ScenarioFamily.CONTEXT_SWAP: self._context_swap,
            ScenarioFamily.REPLAY: self._replay,
            ScenarioFamily.CHECKOUT_DRIFT: self._drift,
            ScenarioFamily.APPROVAL_SPLIT: self._split,
            ScenarioFamily.PROVIDER_UNKNOWN: self._provider_unknown,
            ScenarioFamily.EXPIRED_AUTHORIZATION: self._expired,
        }[spec.family]
        return handler(iid, product_id, proposal, authz, spec)

    # -- family handlers -------------------------------------------------
    def _finish(self, spec: ScenarioSpec, actual: str, detail: str) -> ScenarioResult:
        return ScenarioResult(
            scenario_id=spec.scenario_id,
            family=spec.family,
            expected=spec.expected_outcome,
            actual=actual,
            passed=actual == spec.expected_outcome.value,
            detail=detail[:300],
        )

    def _safe_baseline(
        self, iid: IntentId, product_id: str, proposal, authz, spec
    ) -> ScenarioResult:  # type: ignore[no-untyped-def]
        attempt = self._exec(iid, authz)
        ok = attempt.state == AttemptState.SUCCEEDED.value
        return self._finish(spec, "ALLOW_EXECUTE_ONCE" if ok else "EXECUTION_FAILED", attempt.state)

    def _context_swap(
        self, iid: IntentId, product_id: str, proposal, authz, spec
    ) -> ScenarioResult:  # type: ignore[no-untyped-def]
        assert spec.swap_principal_to
        assert authz.signed_ticket is not None and authz.binding is not None
        self._ensure_spend(iid, authz.binding.amount_minor)
        swapped = CurrentBinding(
            **{**authz.binding.__dict__, "principal_id": spec.swap_principal_to}
        )
        executor = self._executor(MockPaymentProvider(mode=MockMode.SUCCESS))
        try:
            executor.execute(
                signed_ticket=authz.signed_ticket,
                binding=swapped,
                intent_id=iid,
                idempotency_key=f"idx-{new_ulid()}",
                now_utc=_now(),
            )
            return self._finish(spec, "EXECUTION_SUCCEEDED", "swap was NOT rejected")
        except TicketRejected as exc:
            return self._finish(spec, "EXECUTION_REJECTED", exc.code)

    def _replay(self, iid: IntentId, product_id: str, proposal, authz, spec) -> ScenarioResult:  # type: ignore[no-untyped-def]
        assert authz.signed_ticket is not None and authz.binding is not None
        self._ensure_spend(iid, authz.binding.amount_minor)
        executor = self._executor(MockPaymentProvider(mode=MockMode.SUCCESS))
        outcomes: list[str] = []
        for i in range(spec.replay_count):
            try:
                attempt = executor.execute(
                    signed_ticket=authz.signed_ticket,
                    binding=authz.binding,
                    intent_id=iid,
                    idempotency_key=f"idx-replay-{i}",
                    now_utc=_now(),
                )
                outcomes.append(attempt.state)
            except NonceAlreadyClaimed:
                outcomes.append("NONCE_REPLAY_REJECTED")
        attempts = self._attempt_count()
        detail = f"{outcomes}; durable attempts={attempts}"
        if attempts == 1 and outcomes.count("NONCE_REPLAY_REJECTED") == spec.replay_count - 1:
            return self._finish(spec, "SINGLE_EFFECT_ONLY", detail)
        return self._finish(spec, "MULTIPLE_EFFECTS", detail)

    def _drift(self, iid: IntentId, product_id: str, proposal, authz, spec) -> ScenarioResult:  # type: ignore[no-untyped-def]
        cid = str(proposal.envelope.checkout_id)
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE checkouts SET line_items = CAST(:li AS jsonb), "
                    "computed_total_minor = 999999 WHERE checkout_id = :cid"
                ).bindparams(li="[]", cid=cid)
            )
        verdict = Revalidator(self._repos).revalidate(
            intent_id=str(iid),
            checkout_id=cid,
            expected_checkout_hash=proposal.checkout_hash,
            expected_revision=1,
            expected_intent_hash=proposal.intent_hash,
            expected_generation=1,
        )
        if verdict.code == "STALE_CHECKOUT":
            return self._finish(spec, "STALE_DETECTED", verdict.detail or "")
        return self._finish(spec, "DRIFT_MISSED", verdict.code or "ok")

    def _split(self, iid: IntentId, product_id: str, proposal, authz, spec) -> ScenarioResult:  # type: ignore[no-untyped-def]
        # Part 1 executes and COMMITS its spend against aggregate capacity.
        attempt = self._exec(iid, authz)
        if attempt.state != AttemptState.SUCCEEDED.value:
            return self._finish(spec, "PART1_FAILED", attempt.state)
        svc = self._service()
        denied = 0
        parts = spec.split_parts
        for _ in range(parts - 1):
            later_proposal = svc.propose(intent_id=iid, items=[ProposedItem(product_id)])
            later = svc.authorize(intent_id=iid, proposal=later_proposal)
            if later.outcome.decision in (Decision.BLOCK, Decision.CHALLENGE):
                denied += 1
        if denied >= parts - 1:
            return self._finish(spec, "SPLIT_PREVENTED", f"{denied} later parts denied")
        return self._finish(spec, "SPLIT_ALLOWED", f"only {denied} denied")

    def _provider_unknown(
        self, iid: IntentId, product_id: str, proposal, authz, spec
    ) -> ScenarioResult:  # type: ignore[no-untyped-def]
        provider = MockPaymentProvider(mode=MockMode.TIMEOUT_AFTER_SUCCESS)
        executor = self._executor(provider)
        self._ensure_spend(iid, authz.binding.amount_minor)
        key = f"idx-{new_ulid()}"
        first = executor.execute(
            signed_ticket=authz.signed_ticket,
            binding=authz.binding,
            intent_id=iid,
            idempotency_key=key,
            now_utc=_now(),
        )
        second = executor.execute(
            signed_ticket=authz.signed_ticket,
            binding=authz.binding,
            intent_id=iid,
            idempotency_key=key,
            now_utc=_now(),
        )
        assert authz.signed_ticket is not None and authz.binding is not None
        if first.state != AttemptState.PROVIDER_UNKNOWN.value:
            return self._finish(spec, "WRONG_STATE", first.state)
        if second.execution_attempt_id == first.execution_attempt_id and provider.calls == 1:
            return self._finish(spec, "NO_FRESH_OP_AFTER_UNKNOWN", "same attempt reused; 1 call")
        return self._finish(spec, "FRESH_OP_CREATED", "retry created new work")

    def _expired(self, iid: IntentId, product_id: str, proposal, authz, spec) -> ScenarioResult:  # type: ignore[no-untyped-def]
        if authz.outcome.decision == Decision.BLOCK:
            return self._finish(spec, "EXECUTION_REJECTED", "expired authorization blocked")
        return self._finish(spec, "EXECUTION_ALLOWED", "expiry not enforced")

    # -- shared -----------------------------------------------------------
    def _ensure_spend(self, iid: IntentId, amount_minor: int) -> None:
        spend = SpendManager(self._repos)
        spend.ensure_authorization(iid, authorized_minor=200_000)
        spend.reserve(iid, amount_minor)

    def _exec(self, iid: IntentId, authz: AuthorizationResult) -> ExecutionAttempt:
        executor = self._executor(MockPaymentProvider(mode=MockMode.SUCCESS))
        assert authz.signed_ticket is not None and authz.binding is not None
        self._ensure_spend(iid, authz.binding.amount_minor)
        return executor.execute(
            signed_ticket=authz.signed_ticket,
            binding=authz.binding,
            intent_id=iid,
            idempotency_key=f"idx-{new_ulid()}",
            now_utc=_now(),
        )

    def _attempt_count(self) -> int:
        with self._repos.transaction() as s:
            return int(s.query(ExecutionAttempt).count())
