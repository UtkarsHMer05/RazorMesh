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
from razormesh_api.domain.checkout import BoundedText, CheckoutEnvelope, LineItem
from razormesh_api.domain.ids import (
    AgentId,
    CheckoutId,
    DecisionId,
    ExecutionTicketId,
    IntentId,
    MerchantId,
    PrincipalId,
    ProductId,
)
from razormesh_api.domain.intent import (
    IntentContract,
    IntentStatus,
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
    IntentContract as RowIntent,
)
from razormesh_api.persistence.models import (
    Product,
)
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.rules.engine import EvaluationContext, ProductFacts
from razormesh_api.tickets import ExecutionTicketClaims, TicketIssuer


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


def _untrusted_name(text: str) -> Provenanced[BoundedText]:
    return Provenanced[BoundedText].model_construct(
        value=BoundedText(text=text[:500]),
        trust_class="UNTRUSTED_CONTENT",
        source_type="MERCHANT_FREE_TEXT",
        source_id="catalog",
        observed_at=datetime.now(UTC),
    )


def _domain_intent(row: RowIntent) -> IntentContract:
    """Rebuild the domain contract from its durable projection."""
    return IntentContract(
        intent_id=IntentId(row.intent_id),
        principal_id=PrincipalId(row.principal_id),
        agent_id=AgentId(row.agent_id),
        authorization_generation=row.authorization_generation,
        status=IntentStatus(row.status),
        currency=row.currency,
        max_total=Money(row.max_total_minor),
        aggregate_budget=Money(row.aggregate_budget_minor),
        max_quantity=row.max_quantity,
        recurring_allowed=row.recurring_allowed,
        approval_threshold=Money(row.approval_threshold_minor),
        issued_at=row.issued_at,
        authorized_at=row.authorized_at,
        expires_at=row.expires_at,
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

        line_items = tuple(
            LineItem(
                product_id=ProductId(pid),
                display_name=_untrusted_name(products[pid].title),
                quantity=item.quantity,
                unit_price=Money(products[pid].price_minor),  # TRUSTED price only
                condition=cast(
                    "Literal['new', 'refurbished', 'used'] | None",
                    products[pid].condition or "new",
                ),
            )
            for pid, item in ((i.product_id, i) for i in items)
        )
        shipping = Money(sum(products[i.product_id].shipping_minor for i in items))
        currency = row_intent.currency
        zero = Money.zero(currency)
        computed = zero
        for item in items:
            computed = computed.add(
                Money(products[item.product_id].price_minor).multiply_positive_int(item.quantity)
            )
        computed = computed.add(zero).add(shipping).add(zero)

        env = CheckoutEnvelope(
            checkout_id=CheckoutId.generate(),
            revision=1,
            merchant_id=MerchantId(merchant_id),
            line_items=line_items,
            tax=zero,
            shipping=shipping,
            fees=zero,
            subscription_terms=None,
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
            intent_hash=intent_authorization_hash(_domain_intent(row_intent)),
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
        contract = _domain_intent(row_intent)
        env = proposal.envelope

        # Trusted product facts for catalog rules.
        facts: dict[str, ProductFacts] = {}
        for item in env.line_items:
            row = self._repos.products.get(item.product_id)
            if row is not None:
                facts[item.product_id.value] = ProductFacts(brand=row.brand, category=row.category)

        outcome = self._engine.decide(
            intent=contract,
            checkout=env,
            ctx=EvaluationContext(
                intent=contract,
                checkout=env,
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
        return AuthorizationResult(outcome, decision_id, ticket_json=signed.claims_json)
