"""AgentCommerceIR (Phase-4 §6) + commerce-commitment-v1 (§7).

`AgentCommerceIR` is the canonical authorization-relevant commerce
model. One IR per RazorMesh authorization flow. Integer minor units only.

`commerce-commitment-v1` is RazorMesh's INTERNAL cross-protocol
comparison hash. It is distinct from:
- an AP2 `checkout_hash`,
- an RFC 9421 Content-Digest,
- a UCP signature,
- an ExecutionTicket signature.

Presentation-only fields are excluded from the commitment; identity
fields bind.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

IR_VERSION = "agent-commerce-ir-v1"
COMMERCE_COMMITMENT_VERSION = "commerce-commitment-v1"


class _IRBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Money(_IRBase):
    """Integer minor units. Never float. Always a non-negative integer."""

    value_minor: int
    currency: str

    @field_validator("value_minor")
    @classmethod
    def _nonneg(cls, v: int) -> int:
        if v < 0:
            raise ValueError("value_minor must be >= 0 (use signed_amount_minor for refunds)")
        return v


class _Quantity(_IRBase):
    value: int
    unit: str
    scale: int

    @field_validator("value")
    @classmethod
    def _qpos(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity.value must be > 0")
        return v

    @field_validator("scale")
    @classmethod
    def _scaleok(cls, v: int) -> int:
        if v < 0:
            raise ValueError("quantity.scale must be >= 0")
        return v


class _IRItem(_IRBase):
    product_id: str
    variant_id: str | None = None
    merchant_item_id: str | None = None
    title: str | None = None  # presentation only
    brand: str | None = None
    condition: str | None = None
    quantity: _Quantity
    unit_price: _Money
    semantic_attributes: Mapping[str, Any] = Field(default_factory=dict)


class _IRTotals(_IRBase):
    subtotal_minor: int | None = None
    discount_minor: int | None = None
    tax_minor: int | None = None
    fulfillment_minor: int | None = None
    fee_minor: int | None = None
    total_minor: int  # REQUIRED, business-authoritative

    @field_validator("total_minor")
    @classmethod
    def _total_nonneg(cls, v: int) -> int:
        if v < 0:
            raise ValueError("total_minor must be >= 0 (use signed_amount_minor for refunds)")
        return v


class _IRRecurring(_IRBase):
    mode: str  # "none" | "allowed" | "unknown"
    interval: str | None = None
    amount_minor: int | None = None
    starts_at: str | None = None
    terms_hash: str | None = None


class _IRFulfillment(_IRBase):
    method_id: str | None = None
    type: str | None = None
    destination_fingerprint: str | None = None  # never raw address


class _IRMerchant(_IRBase):
    merchant_id: str
    seller_id: str | None = None
    origin: str | None = None
    merchant_profile_ref: str | None = None


class _IRCheckout(_IRBase):
    external_checkout_id: str | None = None
    revision: str
    expires_at: str | None = None


class _IRAuthorization(_IRBase):
    intent_contract_id: str
    authorization_generation: int
    ap2_mandate_refs: list[str] = Field(default_factory=list)
    protocol_authorization_refs: list[str] = Field(default_factory=list)


class _IRProvenance(_IRBase):
    source_protocols: list[str]
    evidence_refs: list[str] = Field(default_factory=list)


class AgentCommerceIR(_IRBase):
    """Canonical authorization-relevant commerce model (Phase-4 §6)."""

    schema_version: str = Field(default=IR_VERSION, frozen=True)

    principal_ref: str
    agent_ref: str

    merchant: _IRMerchant
    checkout: _IRCheckout

    items: list[_IRItem]
    totals: _IRTotals
    currency: str

    fulfillment: _IRFulfillment | None = None
    recurring: _IRRecurring | None = None

    authorization: _IRAuthorization
    provenance: _IRProvenance


# ======================================================================
# commerce-commitment-v1 — INTERNAL cross-protocol comparison hash
# ======================================================================


class CommitmentPayload(BaseModel):
    """The deterministic, authorization-relevant projection of an IR.

    Presentation-only fields (title, image URLs, display ordering) are
    excluded. Identity fields (product_id, merchant_id) bind. Material
    totals, currency, recurring, fulfillment, and authorization all
    bind.
    """

    model_config = ConfigDict(extra="forbid")

    commitment_version: str = Field(default=COMMERCE_COMMITMENT_VERSION, frozen=True)
    principal_ref: str
    agent_ref: str
    merchant_id: str
    seller_id: str | None = None
    checkout_revision: str
    external_checkout_id: str | None = None
    items: list[dict[str, Any]]
    currency: str
    subtotal_minor: int | None = None
    discount_minor: int | None = None
    tax_minor: int | None = None
    fulfillment_minor: int | None = None
    fee_minor: int | None = None
    total_minor: int
    recurring: dict[str, Any] | None = None
    fulfillment: dict[str, Any] | None = None
    authorization_generation: int
    intent_contract_id: str

    @staticmethod
    def from_ir(ir: AgentCommerceIR) -> CommitmentPayload:
        items: list[dict[str, Any]] = []
        for it in ir.items:
            item: dict[str, Any] = {
                "product_id": it.product_id,
                "variant_id": it.variant_id,
                "merchant_item_id": it.merchant_item_id,
                "brand": it.brand,
                "condition": it.condition,
                "quantity": {
                    "value": it.quantity.value,
                    "unit": it.quantity.unit,
                    "scale": it.quantity.scale,
                },
                "unit_price_minor": it.unit_price.value_minor,
                "currency": it.unit_price.currency,
            }
            # Sort the keys of semantic_attributes so commitment is
            # stable across adapters that emit attribute keys in
            # different orders.
            if it.semantic_attributes:
                item["semantic_attributes"] = _sort_nested(it.semantic_attributes)
            items.append(item)
        # Sort items by (product_id, variant_id, merchant_item_id) so
        # equivalent IRs that arrive in different item orders produce
        # the same commitment. Identity-preserving sort.
        items.sort(
            key=lambda i: (
                i.get("product_id") or "",
                i.get("variant_id") or "",
                i.get("merchant_item_id") or "",
            )
        )
        return CommitmentPayload(
            principal_ref=ir.principal_ref,
            agent_ref=ir.agent_ref,
            merchant_id=ir.merchant.merchant_id,
            seller_id=ir.merchant.seller_id,
            checkout_revision=ir.checkout.revision,
            external_checkout_id=ir.checkout.external_checkout_id,
            items=items,
            currency=ir.currency,
            subtotal_minor=ir.totals.subtotal_minor,
            discount_minor=ir.totals.discount_minor,
            tax_minor=ir.totals.tax_minor,
            fulfillment_minor=ir.totals.fulfillment_minor,
            fee_minor=ir.totals.fee_minor,
            total_minor=ir.totals.total_minor,
            recurring=(
                {
                    "mode": ir.recurring.mode,
                    "interval": ir.recurring.interval,
                    "amount_minor": ir.recurring.amount_minor,
                    "starts_at": ir.recurring.starts_at,
                    "terms_hash": ir.recurring.terms_hash,
                }
                if ir.recurring is not None
                else None
            ),
            fulfillment=(
                {
                    "method_id": ir.fulfillment.method_id,
                    "type": ir.fulfillment.type,
                    "destination_fingerprint": ir.fulfillment.destination_fingerprint,
                }
                if ir.fulfillment is not None
                else None
            ),
            authorization_generation=ir.authorization.authorization_generation,
            intent_contract_id=ir.authorization.intent_contract_id,
        )


def _sort_nested(obj: Any) -> Any:
    """Sort a mapping's keys recursively so equivalent payloads hash the same."""
    if isinstance(obj, Mapping):
        return {k: _sort_nested(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        return [_sort_nested(x) for x in obj]
    return obj


def _canonical_json(obj: Any) -> str:
    """JCS-friendly canonical JSON for hashing.

    Sort keys recursively. No whitespace. UTF-8. Stable for dict, list,
    primitive, and Pydantic-style objects that have been through
    model_dump.
    """
    return json.dumps(
        _sort_nested(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    )


def compute_commitment(ir: AgentCommerceIR) -> str:
    """Return the canonical JSON of the commitment projection.

    For a *hash*, call :func:`commitment_hash` instead. This returns
    the JSON so callers (UI, audit) can render the exact projection
    the system committed to.
    """
    payload = CommitmentPayload.from_ir(ir)
    return _canonical_json(payload.model_dump(mode="json"))


def commitment_hash(ir: AgentCommerceIR) -> str:
    """Return the SHA-256 hex digest of :func:`compute_commitment`."""
    payload = CommitmentPayload.from_ir(ir)
    blob = _canonical_json(payload.model_dump(mode="json")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def equal_under_commitment(ir_a: AgentCommerceIR, ir_b: AgentCommerceIR) -> bool:
    """True iff two IRs have identical authorization-relevant projections.

    The IR commitment projection is the single source of truth for
    cross-protocol commerce comparison. A signature can be valid and
    still fail this check (master prompt §10).
    """
    return compute_commitment(ir_a) == compute_commitment(ir_b)


__all__ = [
    "COMMERCE_COMMITMENT_VERSION",
    "IR_VERSION",
    "AgentCommerceIR",
    "CommitmentPayload",
    "commitment_hash",
    "compute_commitment",
    "equal_under_commitment",
]
