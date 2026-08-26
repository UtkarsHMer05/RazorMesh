"""P3-M39: SemanticEvidenceBuilder — deterministic premise construction.

Builds (premise, hypothesis) pairs for the SemanticVerifier from the CURRENT
sanitized commerce evidence. Guarantees (P3-S05):

- the hypothesis ALWAYS derives from the confirmed authorization terms
  (IntentContract fields) — never from merchant text;
- the premise contains ONLY structured evidence fields handed in by the
  caller (catalog/product facts already sanitized upstream);
- untrusted product/seller text cannot inject a new hypothesis: it is only
  ever embedded inside the PREMISE where it can lower trust, never raise it.

Pure function over plain data; no I/O; no model calls.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CommerceEvidence:
    """Sanitized evidence collected for ONE checkout attempt."""

    item_title: str
    price_minor: int | None
    currency: str | None
    brand: str | None
    condition: str | None
    seller_name: str | None
    recurring_terms: bool
    shipping_included: bool | None = None


@dataclass(frozen=True)
class EvidencePair:
    premise: str
    hypothesis: str
    aspect: str


def _cap_text(amount_minor: int | None, currency: str | None) -> str:
    if amount_minor is None or currency is None:
        return "an unspecified budget"
    major = amount_minor / 100
    return f"{currency} {major:,.2f}"


def build_pairs(evidence: CommerceEvidence, *, max_amount_minor: int,
                currency: str, recurring_forbidden: bool,
                brand_allowlist: tuple[str, ...] = ()) -> list[EvidencePair]:
    """One pair per verifiable aspect of the confirmed authorization."""
    pairs: list[EvidencePair] = []
    cap = _cap_text(max_amount_minor, currency)

    price_text = (
        f"The listing price is {evidence.price_minor / 100:,.2f} "
        f"{evidence.currency}."
        if evidence.price_minor is not None and evidence.currency
        else "The listing does not display a comparable total price."
    )
    pairs.append(EvidencePair(
        premise=f"Product page states: {evidence.item_title}. {price_text}",
        hypothesis=f"The purchase stays within the authorized budget of {cap}.",
        aspect="budget_ceiling",
    ))

    if brand_allowlist:
        listed_brand = (evidence.brand or "").strip().casefold()
        allowed = ", ".join(b.casefold() for b in brand_allowlist)
        pairs.append(EvidencePair(
            premise=(
                f"Seller/listing identifies the brand as "
                f"'{evidence.brand or 'unknown'}'."
            ),
            hypothesis=(
                f"The authorized brand restriction ({allowed}) is satisfied."
            ),
            aspect="brand_identity",
        ))
        _ = listed_brand

    condition = (evidence.condition or "unknown").strip().casefold()
    pairs.append(EvidencePair(
        premise=f"Listing states the item condition as: {condition}.",
        hypothesis="The human requires the item to be new.",
        aspect="condition_new_only",
    ))

    if recurring_forbidden:
        renewal_note = (
            "auto-renewing subscription terms are disclosed"
            if evidence.recurring_terms
            else "no auto-renewing subscription terms are disclosed"
        )
        pairs.append(EvidencePair(
            premise=(
                f"Checkout disclosure states that {renewal_note} for this item."
            ),
            hypothesis="The human forbade any recurring charges.",
            aspect="recurring_forbidden",
        ))

    return pairs
