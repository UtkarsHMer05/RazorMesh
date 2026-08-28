"""M38: checkout proposal + authorization service.

Security properties implemented here:

- The server recomputes ALL amounts from TRUSTED catalog rows. Clients name
  products and quantities only (SEC-014). A client-supplied total that
  disagrees with the server-recomputed total is rejected loudly.
- Proposals against non-executable authorizations are refused up front
  (BLOCKED/CHALLENGED/EXPIRED never reach rule evaluation).
- The decision comes from the deterministic engine (M32) over trusted inputs,
  is persisted with both authorization hashes, and is appended to the
  tamper-evident ledger (M25). ONLY an ALLOW yields a signed execution ticket.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from razormesh_api.decider import Decision, DecisionEngine, DecisionOutcome
from razormesh_api.domain.authz_hash import (
    checkout_authorization_hash,
    intent_authorization_hash,
)
from razormesh_api.domain.checkout import (
    BoundedText,
    CheckoutEnvelope,
    LineItem,
    SubscriptionTerms,
)
from razormesh_api.domain.ids import (
    CheckoutId,
    DecisionId,
    ExecutionTicketId,
    IntentId,
    MerchantId,
    ProductId,
)
from razormesh_api.domain.money import Money
from razormesh_api.domain.provenance import Provenanced
from razormesh_api.domain.state_machine import (
    AuthorizationStatus,
    assert_executable,
)
from razormesh_api.keys import DevKeyPair
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.persistence.models import (
    Checkout as RowCheckout,
)
from razormesh_api.persistence.models import (
    Decision as RowDecision,
)
from razormesh_api.persistence.models import (
    ExecutionTicket as RowTicket,
)
from razormesh_api.persistence.models import (
    Product,
)
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.revalidation import domain_intent_from_row
from razormesh_api.rules.engine import EvaluationContext, ProductFacts
from razormesh_api.spend import SpendManager
from razormesh_api.tickets import (
    CurrentBinding,
    ExecutionTicketClaims,
    SignedTicket,
    TicketIssuer,
)


class CheckoutError(Exception):
    """Base class for checkout-service errors."""


class UnknownProduct(CheckoutError):
    def __init__(self, product_id: str) -> None:
        super().__init__(f"product not found in trusted catalog: {product_id}")


class MixedMerchants(CheckoutError):
    pass


class QuantityExceedsAuthorization(CheckoutError):
    pass


class ClientTotalMismatch(CheckoutError):
    def __init__(self, claimed: int, computed: int) -> None:
        super().__init__(
            f"client-provided total {claimed} disagrees with server-recomputed "
            f"total {computed}; amount manipulation is forbidden"
        )


class CatalogCurrencyMismatch(CheckoutError):
    pass


class IncompatibleRecurringTerms(CheckoutError):
    pass


@dataclass(frozen=True)
class ProposedItem:
    product_id: str
    quantity: int = 1


@dataclass(frozen=True)
class Proposal:
    envelope: CheckoutEnvelope
    intent_hash: str
    checkout_hash: str


@dataclass(frozen=True)
class AuthorizationResult:
    outcome: DecisionOutcome
    decision_id: DecisionId
    ticket_json: str | None = None  # canonical signed claims (ALLOW only)
    signed_ticket: SignedTicket | None = None  # ALLOW only
    binding: CurrentBinding | None = None  # ALLOW only


def _untrusted_name(text: str) -> Provenanced[BoundedText]:
    return Provenanced[BoundedText].model_construct(
        value=BoundedText(text=text[:500]),
        trust_class="UNTRUSTED_CONTENT",
        source_type="MERCHANT_FREE_TEXT",
        source_id="catalog",
        observed_at=datetime.now(UTC),
    )


class CheckoutService:
    def __init__(
        self,
        repos: Repositories,
        ledger: EvidenceLedger,
        engine: DecisionEngine,
        keys: DevKeyPair,
    ) -> None:
        self._repos = repos
        self._ledger = ledger
        self._engine = engine
        self._keys = keys

    # read-only service wiring: the Phase-4 acceptance orchestrator needs the
    # same durable repositories + deterministic engine this service uses.
    # Signing keys are deliberately NOT exposed.
    @property
    def repos(self) -> Repositories:
        return self._repos

    @property
    def engine(self) -> DecisionEngine:
        return self._engine

    @property
    def ledger(self) -> EvidenceLedger:
        """Read-only access for dependent trust stages (semantic audit)."""
        return self._ledger

    # ------------------------------------------------------------------
    # proposal (server-authoritative amounts)
    # ------------------------------------------------------------------
    def propose(
        self,
        *,
        intent_id: IntentId,
        items: list[ProposedItem],
        client_total_minor: int | None = None,
    ) -> Proposal:
        now = datetime.now(UTC)

        row_intent = self._repos.intents.get(intent_id)
        if row_intent is None:
            raise CheckoutError(f"unknown intent {intent_id}")
        assert_executable(AuthorizationStatus(row_intent.status))

        if not items:
            raise CheckoutError("proposal requires at least one item")
        max_qty = row_intent.max_quantity

        products: dict[str, Product] = {}
        merchant_ids: set[str] = set()
        for item in items:
            product = self._repos.products.get(ProductId(item.product_id))
            if product is None:
                raise UnknownProduct(item.product_id)
            if item.quantity > max_qty:
                raise QuantityExceedsAuthorization(
                    f"quantity {item.quantity} exceeds authorized maximum {max_qty}"
                )
            products[item.product_id] = product
            merchant_ids.add(product.merchant_id)

        if len(merchant_ids) != 1:
            raise MixedMerchants(f"proposal spans multiple merchants: {sorted(merchant_ids)}")
        merchant_id = merchant_ids.pop()

        currencies = {product.currency for product in products.values()}
        if currencies != {row_intent.currency}:
            raise CatalogCurrencyMismatch(
                f"catalog currencies {sorted(currencies)} do not match authorized "
                f"currency {row_intent.currency}; Phase 1 performs no FX conversion"
            )

        recurring_frequencies = {
            product.recurring_frequency for product in products.values() if product.recurring
        }
        if None in recurring_frequencies:
            raise IncompatibleRecurringTerms(
                "recurring catalog products require a trusted billing frequency"
            )
        if len(recurring_frequencies) > 1:
            raise IncompatibleRecurringTerms(
                f"checkout mixes recurring frequencies: {sorted(recurring_frequencies, key=str)}"
            )
        subscription_terms = (
            SubscriptionTerms(
                recurring=True,
                frequency=cast(
                    "Literal['monthly', 'quarterly', 'yearly'] | None",
                    next(iter(recurring_frequencies)),
                ),
            )
            if recurring_frequencies
            else None
        )

        line_items = tuple(
            LineItem(
                product_id=ProductId(pid),
                display_name=_untrusted_name(products[pid].title),
                quantity=item.quantity,
                unit_price=Money(
                    products[pid].price_minor, products[pid].currency
                ),  # TRUSTED price only
                condition=cast(
                    "Literal['new', 'refurbished', 'used'] | None",
                    products[pid].condition or "new",
                ),
            )
            for pid, item in ((i.product_id, i) for i in items)
        )
        shipping = Money(
            sum(products[i.product_id].shipping_minor for i in items), row_intent.currency
        )
        tax = Money(
            sum(products[i.product_id].tax_minor * i.quantity for i in items),
            row_intent.currency,
        )
        fees = Money(
            sum(products[i.product_id].fees_minor * i.quantity for i in items),
            row_intent.currency,
        )
        currency = row_intent.currency
        zero = Money.zero(currency)
        computed = zero
        for item in items:
            computed = computed.add(
                Money(
                    products[item.product_id].price_minor,
                    products[item.product_id].currency,
                ).multiply_positive_int(item.quantity)
            )
        computed = computed.add(tax).add(shipping).add(fees)

        env = CheckoutEnvelope(
            checkout_id=CheckoutId.generate(),
            revision=1,
            merchant_id=MerchantId(merchant_id),
            line_items=line_items,
            tax=tax,
            shipping=shipping,
            fees=fees,
            subscription_terms=subscription_terms,
            provided_total=computed,
            observed_at=now,
        )
        if client_total_minor is not None and client_total_minor != computed.amount_minor:
            raise ClientTotalMismatch(client_total_minor, computed.amount_minor)

        # Persist the durable checkout projection.
        with self._repos.transaction() as session:
            session.merge(
                RowCheckout(
                    checkout_id=str(env.checkout_id),
                    revision=env.revision,
                    merchant_id=str(env.merchant_id),
                    line_items=[
                        {
                            # Full authorization-relevant projection persisted
                            # so live revalidation can rebuild the exact hash.
                            "product_id": str(i.product_id),
                            "quantity": i.quantity,
                            "unit_price_minor": i.unit_price.amount_minor,
                            "currency": i.unit_price.currency,
                            "condition": i.condition,
                        }
                        for i in env.line_items
                    ],
                    tax_minor=env.tax.amount_minor,
                    shipping_minor=env.shipping.amount_minor,
                    fees_minor=env.fees.amount_minor,
                    provided_total_minor=computed.amount_minor,
                    computed_total_minor=computed.amount_minor,
                    currency=row_intent.currency,
                    subscription_terms=(
                        None
                        if subscription_terms is None
                        else subscription_terms.model_dump(mode="json")
                    ),
                    observed_at=now,
                    created_at=now,
                )
            )

        self._ledger.append(
            event_type="CHECKOUT_PROPOSED",
            actor="checkout-service",
            intent_id=str(intent_id),
            checkout_id=str(env.checkout_id),
            payload={"total_minor": computed.amount_minor},
        )

        return Proposal(
            envelope=env,
            intent_hash=intent_authorization_hash(domain_intent_from_row(row_intent)),
            checkout_hash=checkout_authorization_hash(env),
        )

    # ------------------------------------------------------------------
    # authorization (RazorGuard path)
    # ------------------------------------------------------------------
    def authorize(self, *, intent_id: IntentId, proposal: Proposal) -> AuthorizationResult:
        now = datetime.now(UTC)
        row_intent = self._repos.intents.get(intent_id)
        if row_intent is None:
            raise CheckoutError(f"unknown intent {intent_id}")
        contract = domain_intent_from_row(row_intent)
        env = proposal.envelope

        # Trusted product facts for catalog rules.
        facts: dict[str, ProductFacts] = {}
        for item in env.line_items:
            row = self._repos.products.get(item.product_id)
            if row is not None:
                facts[item.product_id.value] = ProductFacts(brand=row.brand, category=row.category)

        # Durable aggregate usage binds authorization decisions across checkouts.
        spend_row = None
        from sqlalchemy import select

        from razormesh_api.persistence.models import AuthorizationSpend

        with self._repos.factory() as session:
            spend_row = (
                session.execute(
                    select(AuthorizationSpend).where(AuthorizationSpend.intent_id == str(intent_id))
                )
                .scalars()
                .first()
            )

        outcome = self._engine.decide(
            intent=contract,
            checkout=env,
            ctx=EvaluationContext(
                intent=contract,
                checkout=env,
                committed_minor=spend_row.committed_minor if spend_row else 0,
                reserved_minor=spend_row.reserved_minor if spend_row else 0,
                now_utc=now,
                product_facts=facts,
            ),
        )

        decision_id = DecisionId.generate()
        with self._repos.transaction() as session:
            session.merge(
                RowDecision(
                    decision_id=str(decision_id),
                    intent_id=str(contract.intent_id),
                    checkout_id=str(env.checkout_id),
                    intent_generation=contract.authorization_generation,
                    checkout_hash=proposal.checkout_hash,
                    policy_version=outcome.policy_version,
                    decision=outcome.decision.value,
                    reason_codes=list(outcome.reason_codes),
                    rule_results={r.rule_id: r.outcome for r in outcome.rule_results},
                    created_at=now,
                )
            )

        self._ledger.append(
            event_type="DECISION_RECORDED",
            actor="razorguard",
            intent_id=str(contract.intent_id),
            checkout_id=str(env.checkout_id),
            decision_id=str(decision_id),
            intent_hash=proposal.intent_hash,
            checkout_hash=proposal.checkout_hash,
            reason_codes=list(outcome.reason_codes) or None,
            payload={"decision": outcome.decision.value},
        )

        if outcome.decision is not Decision.ALLOW:
            return AuthorizationResult(outcome, decision_id)

        # ALLOW only: mint the context-bound single-use ticket (M34).
        SpendManager(self._repos).ensure_authorization(
            contract.intent_id, authorized_minor=contract.aggregate_budget.amount_minor
        )
        claims = ExecutionTicketClaims(
            ticket_id=ExecutionTicketId.generate(),
            decision_id=decision_id,
            checkout_id=env.checkout_id,
            intent_id=contract.intent_id,
            principal_id=str(contract.principal_id),
            agent_id=str(contract.agent_id),
            authorization_generation=contract.authorization_generation,
            intent_hash=proposal.intent_hash,
            checkout_hash=proposal.checkout_hash,
            checkout_revision=env.revision,
            merchant_id=str(env.merchant_id),
            amount_minor=env.compute_total().amount_minor,
            currency=contract.currency,
            policy_version=outcome.policy_version,
            nonce=f"nonce-{uuid.uuid4().hex}{uuid.uuid4().hex}",
            issued_at=now,
            expires_at=now + timedelta(seconds=120),
        )
        signed = TicketIssuer(self._keys).issue(claims)
        with self._repos.transaction() as session:
            session.merge(
                RowTicket(
                    ticket_id=str(claims.ticket_id),
                    principal_id=str(claims.principal_id),
                    agent_id=str(claims.agent_id),
                    intent_id=str(claims.intent_id),
                    intent_hash=claims.intent_hash,
                    authorization_generation=claims.authorization_generation,
                    checkout_hash=claims.checkout_hash,
                    checkout_revision=claims.checkout_revision,
                    merchant_id=str(claims.merchant_id),
                    amount_minor=claims.amount_minor,
                    currency=str(claims.currency),
                    decision_id=str(decision_id),
                    policy_version=str(claims.policy_version),
                    nonce=str(claims.nonce),
                    issued_at=claims.issued_at,
                    expires_at=claims.expires_at,
                    used_at=None,
                    created_at=now,
                )
            )
        self._ledger.append(
            event_type="TICKET_ISSUED",
            actor="checkout-service",
            intent_id=str(contract.intent_id),
            checkout_id=str(env.checkout_id),
            decision_id=str(decision_id),
            ticket_id=str(claims.ticket_id),
            payload={"amount_minor": claims.amount_minor},
        )
        binding = CurrentBinding(
            principal_id=str(claims.principal_id),
            agent_id=str(claims.agent_id),
            intent_id=str(claims.intent_id),
            intent_hash=claims.intent_hash,
            authorization_generation=claims.authorization_generation,
            checkout_id=str(claims.checkout_id),
            checkout_hash=claims.checkout_hash,
            checkout_revision=claims.checkout_revision,
            merchant_id=str(claims.merchant_id),
            amount_minor=claims.amount_minor,
            currency=str(claims.currency),
        )
        return AuthorizationResult(
            outcome,
            decision_id,
            ticket_json=signed.claims_json,
            signed_ticket=signed,
            binding=binding,
        )
