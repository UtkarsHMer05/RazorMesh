"""P3-M11 (D-038): versioned IntentDraft — the compiler's ONLY output shape.

An IntentDraft is a PROPOSAL (P3-S03). It separates what the human's words
pin down into four explicit buckets:

- hard constraints      -> machine-checkable, feed RazorGuard later;
- semantic constraints  -> NLI-verifiable statements of intent;
- ambiguities           -> questions the human must resolve;
- unspecified fields    -> named slots the human did not mention.

Anti-invention rules encoded HERE, at the type level:
- money is StrictInt minor units + explicit ISO currency; floats/bools are
  rejected even when integral;
- every field is Optional WITHOUT a default value: absence means "unspecified",
  never an invented constant (no implicit currency="INR", no implicit
  condition="new");
- extra keys are forbidden so hallucinated fields fail validation;
- all free text and lists are size-bounded;
- ``schema_version`` is part of the contract and pinned by Literal.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

DRAFT_SCHEMA_VERSION = Literal["agentpay-intent-draft-v1"]
SCHEMA_VERSION_VALUE = "agentpay-intent-draft-v1"

_CURRENCY_PATTERN = r"^[A-Z]{3}$"
_TEXT_MAX = 280
_LIST_MAX = 8
_ITEM_MAX = 120


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class MoneyBound(_Strict):
    """A hard monetary ceiling in integer minor units + explicit currency."""

    amount_minor: StrictInt = Field(ge=1, le=10_000_000_000)
    currency: str = Field(pattern=_CURRENCY_PATTERN)


class HardConstraints(_Strict):
    """Machine-checkable constraints. None == unspecified (never defaulted)."""

    max_amount: MoneyBound | None = None
    quantity_max: StrictInt | None = Field(default=None, ge=1, le=999)
    brand_allowlist: tuple[str, ...] = Field(default=(), max_length=_LIST_MAX)
    condition_allowlist: tuple[
        Literal["new"], ...
    ] = ()  # only 'new' is hard-checkable today; refurb/used stay semantic
    merchant_allowlist: tuple[str, ...] = Field(default=(), max_length=_LIST_MAX)
    recurring_forbidden: bool | None = None

    @field_validator("brand_allowlist", "merchant_allowlist")
    @classmethod
    def _items_bounded(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        for item in v:
            if not item or len(item) > _ITEM_MAX:
                raise ValueError("allowlist items must be 1..120 chars")
        return v


class SemanticConstraint(_Strict):
    """A natural-language statement of intent, verifiable via NLI."""

    text: str = Field(min_length=3, max_length=_TEXT_MAX)
    family_hint: (
        Literal[
            "condition",
            "brand_identity",
            "seller_identity",
            "seller_authorization",
            "bundle",
            "recurring",
            "trial_renewal",
            "membership",
            "shipping_fee",
            "delivery_timing",
            "return_refund",
            "warranty",
            "variant_mismatch",
            "other",
        ]
        | None
    ) = None


class Ambiguity(_Strict):
    question: str = Field(min_length=5, max_length=_TEXT_MAX)
    options: tuple[str, ...] = Field(default=(), max_length=6)

    @field_validator("options")
    @classmethod
    def _options_bounded(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        for item in v:
            if not item or len(item) > _ITEM_MAX:
                raise ValueError("option items must be 1..120 chars")
        return v


class UnspecifiedField(_Strict):
    field: Literal[
        "currency",
        "budget",
        "quantity",
        "brand",
        "condition",
        "merchant",
        "recurring",
        "shipping",
        "deadline",
        "variant",
    ]


class CompilerIntentPayload(_Strict):
    """Exactly what the LLM is allowed to emit (pre-identity, pre-status)."""

    schema_version: DRAFT_SCHEMA_VERSION
    product_summary: str = Field(min_length=3, max_length=_ITEM_MAX)
    hard: HardConstraints = Field(default_factory=HardConstraints)
    semantic_constraints: tuple[SemanticConstraint, ...] = Field(default=(), max_length=12)
    ambiguities: tuple[Ambiguity, ...] = Field(default=(), max_length=6)
    unspecified: tuple[UnspecifiedField, ...] = Field(default=(), max_length=10)

    @field_validator("semantic_constraints")
    @classmethod
    def _semantics_bounded(
        cls, v: tuple[SemanticConstraint, ...]
    ) -> tuple[SemanticConstraint, ...]:
        return v


class IntentDraft(CompilerIntentPayload):
    """Durable wrapper adding identity/time. Never constructible from raw LLM
    output alone: identity is generated server-side (P3-S03)."""

    draft_id: str = Field(pattern=r"^drf_[0-9A-Z]{26}$")
    source_text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime


def empty_hard() -> HardConstraints:
    return HardConstraints()
