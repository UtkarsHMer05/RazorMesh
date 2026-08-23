"""M39: live revalidation of the authoritative checkout before execution.

Between decision and execution the world can move: catalog prices change,
quantities are revised, authorizations get superseded. Immediately BEFORE any
financial side effect, ``Revalidator.revalidate``:

1. re-reads the durable checkout row (PostgreSQL = authority),
2. rebuilds the AuthorizationRelevantCheckout projection from stored fields,
3. recomputes its canonical hash and compares it to the ticket's binding,
4. re-checks the intent's status/generation/terms against the ticket.

Relevant drift -> STALE_CHECKOUT / AUTHORIZATION_STALE (execution refused).
Presentation-only changes (untrusted titles, images) are NOT part of the
projection and therefore never cause false invalidation.
"""

from datetime import UTC, datetime

from razormesh_api.domain.authz_hash import (
    checkout_authorization_hash,
    intent_authorization_hash,
)
from razormesh_api.domain.checkout import BoundedText, CheckoutEnvelope, LineItem
from razormesh_api.domain.ids import (
    AgentId,
    CheckoutId,
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
from razormesh_api.persistence.models import Checkout as RowCheckout
from razormesh_api.persistence.models import IntentContract as RowIntent
from razormesh_api.persistence.repositories import Repositories


class Verdict:
    __slots__ = ("code", "detail", "ok")

    def __init__(self, ok: bool, code: str | None = None, detail: str | None = None) -> None:
        self.ok = ok
        self.code = code
        self.detail = detail

    def __repr__(self) -> str:  # pragma: no cover - debug convenience
        return f"Verdict(ok={self.ok}, code={self.code!r})"


def _placeholder_name() -> Provenanced[BoundedText]:
    return Provenanced[BoundedText].model_construct(
        value=BoundedText(text="<untrusted; excluded from authorization>"),
        trust_class="UNTRUSTED_CONTENT",
        source_type="MERCHANT_FREE_TEXT",
        source_id="rebuild",
        observed_at=datetime.now(UTC),
    )


def domain_intent_from_row(row: RowIntent) -> IntentContract:
    """Rebuild the domain contract from its durable projection (public helper)."""
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


class Revalidator:
    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    def rebuild_envelope(self, row: RowCheckout) -> CheckoutEnvelope:
        """Rebuild the envelope EXACTLY from durable authorization-relevant fields."""

        def _line(d: dict) -> LineItem:
            return LineItem(
                product_id=ProductId(str(d["product_id"])),
                display_name=_placeholder_name(),
                quantity=int(d["quantity"]),
                unit_price=Money(int(d["unit_price_minor"]), str(d.get("currency", "INR"))),
                condition=d.get("condition") or None,
            )

        items = tuple(_line(d) for d in row.line_items)
        zero = Money.zero(row.currency)
        total = zero
        for i in items:
            total = total.add(i.unit_price.multiply_positive_int(i.quantity))
        total = (
            total.add(Money(row.tax_minor, row.currency))
            .add(Money(row.shipping_minor, row.currency))
            .add(Money(row.fees_minor, row.currency))
        )
        return CheckoutEnvelope(
            checkout_id=CheckoutId(row.checkout_id),
            revision=row.revision,
            merchant_id=MerchantId(row.merchant_id),
            line_items=items,
            tax=Money(row.tax_minor, row.currency),
            shipping=Money(row.shipping_minor, row.currency),
            fees=Money(row.fees_minor, row.currency),
            subscription_terms=None,
            provided_total=total,
            observed_at=row.observed_at or datetime.now(UTC),
        )

    def revalidate(
        self,
        *,
        intent_id: str,
        checkout_id: str,
        expected_checkout_hash: str,
        expected_revision: int,
        expected_intent_hash: str,
        expected_generation: int,
    ) -> Verdict:
        # 1. Authoritative intent state.
        intent_row = self._repos.intents.get(IntentId(intent_id))
        if intent_row is None:
            return Verdict(False, "AUTHORIZATION_MISSING", "intent not found")
        if intent_row.status != IntentStatus.AUTHORIZED.value:
            return Verdict(
                False,
                "AUTHORIZATION_STALE",
                f"intent status is {intent_row.status}, not executable",
            )
        if intent_row.authorization_generation != expected_generation:
            return Verdict(
                False,
                "AUTHORIZATION_SUPERSEDED",
                f"generation moved to {intent_row.authorization_generation}",
            )
        current_intent_hash = intent_authorization_hash(domain_intent_from_row(intent_row))
        if current_intent_hash != expected_intent_hash:
            return Verdict(False, "AUTHORIZATION_STALE", "intent terms changed since decision")

        # 2. Authoritative checkout state.
        from sqlalchemy import select

        with self._repos.factory() as session:
            row = (
                session.execute(select(RowCheckout).where(RowCheckout.checkout_id == checkout_id))
                .scalars()
                .first()
            )
        if row is None:
            return Verdict(False, "CHECKOUT_MISSING", "checkout no longer exists")
        if row.revision != expected_revision:
            return Verdict(
                False,
                "STALE_CHECKOUT",
                f"revision moved to {row.revision} (ticket bound to {expected_revision})",
            )

        # 3. Rebuild + recompute the canonical authorization hash.
        rebuilt = self.rebuild_envelope(row)
        fresh_hash = checkout_authorization_hash(rebuilt)
        if fresh_hash != expected_checkout_hash:
            return Verdict(
                False,
                "STALE_CHECKOUT",
                f"authorization-relevant drift: ticket bound to "
                f"{expected_checkout_hash[:16]}..., current {fresh_hash[:16]}...",
            )
        return Verdict(ok=True)
