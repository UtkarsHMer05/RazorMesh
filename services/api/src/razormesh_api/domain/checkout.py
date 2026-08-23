"""Canonical CheckoutEnvelope with server-side total recomputation.

The client never supplies authoritative totals (SEC-014 / PRD-CHK-001): the
envelope recomputes the payable total from line items, tax, shipping and fees,
and construction fails loudly if a provided total disagrees.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from razormesh_api.domain.ids import CheckoutId, MerchantId, ProductId
from razormesh_api.domain.money import Money
from razormesh_api.domain.provenance import Provenanced

MAX_LINE_ITEMS = 50
MAX_TEXT_LEN = 500


class BoundedText(BaseModel):
    """Free text carried as untrusted data with hard size bounds."""

    model_config = ConfigDict(frozen=True)

    text: Annotated[str, Field(max_length=MAX_TEXT_LEN)]
    origin: str = Field(default="untrusted", max_length=100)


class SubscriptionTerms(BaseModel):
    model_config = ConfigDict(frozen=True)

    recurring: bool
    frequency: Literal["monthly", "quarterly", "yearly"] | None = None
    description: str | None = Field(default=None, max_length=MAX_TEXT_LEN)


class LineItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: ProductId
    display_name: Provenanced[BoundedText]  # untrusted merchant content
    quantity: int = Field(ge=1, le=1000)
    unit_price: Money
    condition: Literal["new", "refurbished", "used"] | None = None


class CheckoutEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    checkout_id: CheckoutId
    revision: int = Field(ge=1)
    merchant_id: MerchantId

    line_items: tuple[LineItem, ...] = Field(min_length=1, max_length=MAX_LINE_ITEMS)

    tax: Money
    shipping: Money
    fees: Money

    subscription_terms: SubscriptionTerms | None = None

    # What the proposing side *claimed* the total is; verified below.
    provided_total: Money

    observed_at: datetime  # when the trusted system captured this checkout state

    @model_validator(mode="after")
    def _check_consistency(self) -> "CheckoutEnvelope":
        currencies = {
            self.tax.currency,
            self.shipping.currency,
            self.fees.currency,
            self.provided_total.currency,
            *(item.unit_price.currency for item in self.line_items),
        }
        if len(currencies) != 1:
            raise ValueError(f"checkout mixes currencies: {sorted(currencies)}")

        computed = self.compute_total()
        if computed != self.provided_total:
            raise ValueError(
                f"provided total {self.provided_total} disagrees with server-recomputed "
                f"total {computed}; silent disagreement is forbidden"
            )
        return self

    def compute_total(self) -> Money:
        """Authoritative payable amount: sum(quantity x unit_price) + tax + shipping + fees."""
        currency = self.line_items[0].unit_price.currency if self.line_items else "INR"
        subtotal = Money.zero(currency)
        for item in self.line_items:
            subtotal = subtotal.add(item.unit_price.multiply_positive_int(item.quantity))
        return subtotal.add(self.tax).add(self.shipping).add(self.fees)

    @property
    def subtotal(self) -> Money:
        currency = self.line_items[0].unit_price.currency
        result = Money.zero(currency)
        for item in self.line_items:
            result = result.add(item.unit_price.multiply_positive_int(item.quantity))
        return result

    def has_recurring_terms(self) -> bool:
        return bool(self.subscription_terms and self.subscription_terms.recurring)
