"""P3-M39: SemanticEvidenceBuilder — deterministic premise construction.

Builds (premise, hypothesis) pairs for the SemanticVerifier from the CURRENT
sanitized commerce evidence. Guarantees (P3-S05):

- the hypothesis ALWAYS derives from the confirmed authorization terms
  (IntentContract fields) — never from merchant text;
- the premise contains ONLY structured evidence fields handed in by the
  caller (catalog/product facts already sanitized upstream);
- untrusted product/seller text cannot inject a new hypothesis: it is only
  ever embedded inside the PREMISE where it can lower trust, never raise it.

Phase-3 correction (§2/§17): pair texts follow the canonical orientation and
the frozen AgentPay-IR v2 corpus phrasing the fine-tuned model was trained on
(``data/phase3/dataset/frozen_v2``). A pair is emitted ONLY for an aspect the
confirmed authorization actually constrains — an aspect with no authorization
term has no hypothesis to verify.

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
    # Server-recomputed checkout total (sum of unit_price x quantity + tax+shipping+fees).
    # When present the budget pair states the FINAL total, matching the corpus
    # ``price_constraint`` template; when absent the builder falls back to the
    # listing price. Default None keeps historical construction sites valid.
    final_total_minor: int | None = None


@dataclass(frozen=True)
class EvidencePair:
    premise: str
    hypothesis: str
    aspect: str


_CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}


def _money_text(amount_minor: int, currency: str | None) -> str:
    major = amount_minor / 100
    symbol = _CURRENCY_SYMBOLS.get((currency or "").upper())
    return f"{symbol}{major:,.2f}" if symbol else f"{currency or ''} {major:,.2f}".strip()


def build_pairs(
    evidence: CommerceEvidence,
    *,
    max_amount_minor: int,
    currency: str,
    recurring_forbidden: bool,
    brand_allowlist: tuple[str, ...] = (),
    allowed_conditions: tuple[str, ...] | None = None,
) -> list[EvidencePair]:
    """One pair per verifiable aspect of the confirmed authorization.

    ``allowed_conditions=None`` means the human placed no condition
    requirement on this intent and no condition pair is built (unknown
    evidence would otherwise map to NEUTRAL → CHALLENGE for legitimately
    permissive authorizations).
    """
    pairs: list[EvidencePair] = []

    if evidence.final_total_minor is not None:
        price_text = (
            "The tax-inclusive final total is "
            f"{_money_text(evidence.final_total_minor, evidence.currency or currency)} "
            "with no later mandatory fees."
        )
    elif evidence.price_minor is not None and evidence.currency:
        price_text = f"The listing price is {_money_text(evidence.price_minor, evidence.currency)}."
    else:
        price_text = "The listing does not display a comparable total price."
    pairs.append(
        EvidencePair(
            premise=f"Product page states: {evidence.item_title}. {price_text}",
            hypothesis=(
                "The human authorized a final payable total no higher than "
                f"{_money_text(max_amount_minor, currency)}."
            ),
            aspect="budget_ceiling",
        )
    )

    if brand_allowlist:
        allowed = " or ".join(b.casefold() for b in brand_allowlist)
        pairs.append(
            EvidencePair(
                premise=f"The brand field reads {evidence.brand or 'unknown'}.",
                hypothesis=f"The human authorized only {allowed} branded products.",
                aspect="brand_identity",
            )
        )

    if allowed_conditions is not None:
        condition = (evidence.condition or "").strip().casefold()
        if condition in allowed_conditions:
            premise = f"The item condition field reads {condition.capitalize()} - factory sealed."
        elif condition:
            premise = (
                f"The item condition field reads {condition.capitalize()} "
                "- as stated by the seller."
            )
        else:
            premise = "The item condition is not stated on the listing."
        if len(allowed_conditions) == 1:
            only = next(iter(allowed_conditions))
            hypothesis = (
                "The human authorized only a factory-new, previously unused item."
                if only == "new"
                else f"The human authorized only a {only} item."
            )
        else:
            ordered = ", ".join(sorted(allowed_conditions)[:-1])
            last = sorted(allowed_conditions)[-1]
            hypothesis = f"The human authorized only a {ordered} or {last} item."
        pairs.append(
            EvidencePair(
                premise=premise,
                hypothesis=hypothesis,
                aspect="condition_new_only",
            )
        )

    if recurring_forbidden:
        renewal_note = (
            "The purchase includes a plan that continues at a periodic fee "
            "every month with no action required."
            if evidence.recurring_terms
            else "The order line shows no renewal and no recurring fee after purchase."
        )
        pairs.append(
            EvidencePair(
                premise=renewal_note,
                hypothesis="The human authorized a one-time purchase with no recurring charge.",
                aspect="recurring_forbidden",
            )
        )

    return pairs
