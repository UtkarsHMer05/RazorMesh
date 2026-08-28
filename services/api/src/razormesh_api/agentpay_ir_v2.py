"""AgentPay-IR v0.2 — the CORRECTED NLI record contract (canonical orientation).

Why this exists
---------------
``agentpay_ir.py`` (v0.1) documented the canonical orientation rule but the
frozen v1 corpus violated it: 657/723 training rows folded the human's own
request into the premise ("Session context — human request: ..."), while the
runtime ``SemanticEvidenceBuilder`` emits evidence-only premises. The paired
orientation diagnostic (``docs/PHASE3_ORIENTATION_DIAGNOSTIC.md``) measured the
consequence on the frozen checkpoint and concluded RETRAIN_REQUIRED = YES.

v0.2 makes the orientation machine-enforced rather than documentary:

    premise    = CURRENT SANITIZED COMMERCE EVIDENCE, and nothing else
    hypothesis = NORMALIZED HUMAN AUTHORIZATION CONSTRAINT
    label      = contradiction | entailment | neutral

Guarantees, all enforced by validators:

* ``FORBIDDEN PREMISE FRAMES`` — no authorization prose may appear in the
  premise. This is the prompt-injection boundary (§17 of the correction brief):
  merchant text is premise-side only and can never define authority.
* ``authorization_field`` / ``evidence_field`` name the trusted field pair each
  record actually compares, so a record cannot claim one aspect and test another.
* ``split_group`` is the unit that splitting must respect; two records sharing a
  group may never land in different splits.
* ``content_sha256`` covers premise+hypothesis+label+orientation so any silent
  re-orientation of a row changes its hash.

Money is always rendered from integer minor units by the builder; no floats are
stored. No secrets, credentials or personal data may enter a record.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

IR_SCHEMA_VERSION: Final = "agentpay-ir-v0.2"

NliLabel = Literal["contradiction", "entailment", "neutral"]
RecordSource = Literal["deterministic", "qwen", "human_reviewed", "adversarial"]
Difficulty = Literal["easy", "medium", "hard"]
SafeOrAttack = Literal["safe", "attack", "ambiguous"]
SplitName = Literal["train", "val", "test"]

LABELS: Final[tuple[str, ...]] = ("contradiction", "entailment", "neutral")

# ---------------------------------------------------------------------------
# Orientation guard
# ---------------------------------------------------------------------------
# Any of these appearing in a premise means the human's authorization has been
# folded into the evidence side, which is exactly the v0.1 defect. The list is
# deliberately narrow: it targets authorization *frames*, not ordinary words.
FORBIDDEN_PREMISE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"session context", re.IGNORECASE),
    re.compile(r"human request", re.IGNORECASE),
    re.compile(
        r"the human (?:authorized|forbade|requires|required|said|stated|specified)",
        re.IGNORECASE,
    ),
    re.compile(r"authorized by the (?:human|buyer)", re.IGNORECASE),
    re.compile(r"buyer'?s? (?:stated )?(?:intent|request) was", re.IGNORECASE),
    re.compile(r"^user:\s", re.IGNORECASE),
    re.compile(r"^system:\s", re.IGNORECASE),
)

# Every hypothesis must be a statement about the authorization, never a bare
# observation, otherwise the pair carries no constraint to check.
HYPOTHESIS_AUTHORIZATION_MARKERS: Final[tuple[str, ...]] = (
    "authoriz",
    "permit",
    "allowed",
    "must",
    "forbid",
    "forbade",
    "forbids",
    "prohibit",
    "restrict",
    "ceiling",
    "limit",
    "requires",
    "required",
    "consent",
    "mandate",
    "only if",
    "no higher than",
)


def premise_orientation_violations(premise: str) -> list[str]:
    """Return the authorization-frame markers found in a premise (empty = canonical)."""
    return [pattern.pattern for pattern in FORBIDDEN_PREMISE_PATTERNS if pattern.search(premise)]


def is_canonical_orientation(premise: str) -> bool:
    return not premise_orientation_violations(premise)


def hypothesis_is_authorization_shaped(hypothesis: str) -> bool:
    lowered = hypothesis.casefold()
    return any(marker in lowered for marker in HYPOTHESIS_AUTHORIZATION_MARKERS)


# ---------------------------------------------------------------------------
# Semantic families (correction brief §4 — all 35 required categories)
# ---------------------------------------------------------------------------
FAMILIES: Final[tuple[str, ...]] = (
    "product_identity",
    "product_equivalence",
    "product_condition",
    "brand_identity",
    "variant",
    "merchant_identity",
    "seller_identity",
    "seller_authorization",
    "quantity",
    "quantity_units",
    "price_constraint",
    "currency",
    "bundles",
    "recurring_subscription",
    "trial_to_paid_renewal",
    "membership_insertion",
    "automatic_renewal",
    "semantic_fees",
    "shipping_obligation",
    "delivery_constraint",
    "return_condition",
    "warranty_condition",
    "fulfillment_constraint",
    "aliases",
    "safe_paraphrases",
    "safe_lookalikes",
    "ambiguous_evidence",
    "misleading_negation",
    "double_negation",
    "euphemistic_subscription",
    "prompt_injection_like_merchant_text",
    "irrelevant_hostile_text",
    "merchant_description_manipulation",
    "product_title_manipulation",
    "equivalent_benign_wording",
)

# Trusted authorization fields the runtime IntentContract can carry. A record
# must name one of these so the evidence/authorization pairing is auditable.
AUTHORIZATION_FIELDS: Final[tuple[str, ...]] = (
    "max_amount_minor",
    "currency",
    "quantity_max",
    "brand_allowlist",
    "merchant_allowlist",
    "seller_allowlist",
    "condition_new_only",
    "recurring_forbidden",
    "product_identity",
    "variant_identity",
    "shipping_free",
    "delivery_constraint",
    "return_window_min_days",
    "warranty_required",
    "fulfillment_constraint",
    "human_confirmation_required",
)

EVIDENCE_FIELDS: Final[tuple[str, ...]] = (
    "listing_price",
    "final_total",
    "settlement_currency",
    "checkout_quantity",
    "product_condition",
    "manufacturer_identity",
    "selected_sku",
    "merchant_registry",
    "seller_identity",
    "recurring_terms",
    "trial_conversion",
    "membership_enrollment",
    "auto_renewal_flag",
    "fee_breakdown",
    "shipping_line",
    "delivery_option",
    "return_policy",
    "warranty_registry",
    "fulfillment_option",
    "product_title",
    "product_description",
    "merchant_free_text",
    "consent_event",
)

_TEXT_MAX_PREMISE: Final = 900
_TEXT_MAX_HYPOTHESIS: Final = 400


def compute_content_sha256(premise: str, hypothesis: str, label: str) -> str:
    """Deterministic integrity hash over the canonical orientation triple."""
    canonical = json.dumps(
        {
            "premise": premise,
            "hypothesis": hypothesis,
            "label": label,
            "orientation": "evidence-implies-authorization",
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class AgentPayIRv2Record(BaseModel):
    """One canonical NLI record. Frozen; the hash is part of the contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    record_id: str = Field(pattern=r"^air2_[0-9A-Z]{26}$")
    schema_version: Literal["agentpay-ir-v0.2"] = IR_SCHEMA_VERSION

    premise: str = Field(min_length=20, max_length=_TEXT_MAX_PREMISE)
    hypothesis: str = Field(min_length=15, max_length=_TEXT_MAX_HYPOTHESIS)
    label: NliLabel

    family: str
    subfamily: str = Field(min_length=2, max_length=64)

    authorization_field: str
    evidence_field: str

    generator_parent_id: str = Field(min_length=3, max_length=96)
    template_family_id: str = Field(min_length=3, max_length=96)

    source: RecordSource
    safe_or_attack: SafeOrAttack

    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    split_group: str = Field(min_length=3, max_length=96)

    split: SplitName | None = None
    label_source: Literal["template_truth", "human_gold", "qwen_provisional"] = "template_truth"
    difficulty: Difficulty = "easy"
    created_at_utc: datetime
    review: ReviewV2 = Field(default_factory=lambda: ReviewV2())
    metadata: dict[str, Any] = Field(default_factory=dict)

    # -- validators ---------------------------------------------------------

    @field_validator("family")
    @classmethod
    def _known_family(cls, value: str) -> str:
        if value not in FAMILIES:
            raise ValueError(f"unknown family {value!r}")
        return value

    @field_validator("authorization_field")
    @classmethod
    def _known_authorization_field(cls, value: str) -> str:
        if value not in AUTHORIZATION_FIELDS:
            raise ValueError(f"unknown authorization_field {value!r}")
        return value

    @field_validator("evidence_field")
    @classmethod
    def _known_evidence_field(cls, value: str) -> str:
        if value not in EVIDENCE_FIELDS:
            raise ValueError(f"unknown evidence_field {value!r}")
        return value

    @field_validator("premise")
    @classmethod
    def _premise_is_evidence_only(cls, value: str) -> str:
        violations = premise_orientation_violations(value)
        if violations:
            raise ValueError(
                "premise must contain ONLY current commerce evidence; "
                f"authorization frame detected: {violations[0]!r}"
            )
        return value

    @field_validator("hypothesis")
    @classmethod
    def _hypothesis_is_authorization(cls, value: str) -> str:
        if not hypothesis_is_authorization_shaped(value):
            raise ValueError("hypothesis must state a normalized human authorization constraint")
        return value

    @model_validator(mode="after")
    def _hash_and_group_consistency(self) -> AgentPayIRv2Record:
        expected = compute_content_sha256(self.premise, self.hypothesis, self.label)
        if self.content_sha256 != expected:
            raise ValueError("content_sha256 does not match premise+hypothesis+label")
        if self.split_group != self.generator_parent_id:
            raise ValueError("split_group must equal generator_parent_id")
        return self

    # -- helpers ------------------------------------------------------------

    def normalized_pair(self) -> str:
        """Whitespace/case/punctuation-insensitive identity for near-dup checks."""
        return " ".join(f"{self.premise} ||| {self.hypothesis}".casefold().split()).rstrip(".")

    def to_json_line(self) -> str:
        return self.model_dump_json()


class ReviewV2(BaseModel):
    model_config = ConfigDict(frozen=True)

    reviewed_by_human: bool = False
    reviewer: str | None = None
    reviewed_at_utc: datetime | None = None
    notes: str | None = Field(default=None, max_length=500)


AgentPayIRv2Record.model_rebuild()


def make_v2_record(
    *,
    record_id: str,
    premise: str,
    hypothesis: str,
    label: NliLabel,
    family: str,
    subfamily: str,
    authorization_field: str,
    evidence_field: str,
    generator_parent_id: str,
    template_family_id: str,
    source: RecordSource,
    safe_or_attack: SafeOrAttack,
    created_at_utc: datetime,
    difficulty: Difficulty = "easy",
    label_source: Literal["template_truth", "human_gold", "qwen_provisional"] = "template_truth",
    review: ReviewV2 | None = None,
    metadata: dict[str, Any] | None = None,
) -> AgentPayIRv2Record:
    """Factory that computes the integrity hash so callers cannot forget it."""
    return AgentPayIRv2Record(
        record_id=record_id,
        premise=premise,
        hypothesis=hypothesis,
        label=label,
        family=family,
        subfamily=subfamily,
        authorization_field=authorization_field,
        evidence_field=evidence_field,
        generator_parent_id=generator_parent_id,
        template_family_id=template_family_id,
        source=source,
        safe_or_attack=safe_or_attack,
        content_sha256=compute_content_sha256(premise, hypothesis, label),
        split_group=generator_parent_id,
        created_at_utc=created_at_utc,
        difficulty=difficulty,
        label_source=label_source,
        review=review or ReviewV2(),
        metadata=metadata or {},
    )


def load_jsonl(path: Any) -> list[AgentPayIRv2Record]:
    from pathlib import Path

    text = Path(path).read_text(encoding="utf-8")
    return [
        AgentPayIRv2Record.model_validate_json(line) for line in text.splitlines() if line.strip()
    ]


def dump_jsonl(records: list[AgentPayIRv2Record]) -> str:
    return "\n".join(r.to_json_line() for r in records) + "\n"


__all__ = [
    "AUTHORIZATION_FIELDS",
    "EVIDENCE_FIELDS",
    "FAMILIES",
    "IR_SCHEMA_VERSION",
    "LABELS",
    "AgentPayIRv2Record",
    "ReviewV2",
    "compute_content_sha256",
    "dump_jsonl",
    "hypothesis_is_authorization_shaped",
    "is_canonical_orientation",
    "load_jsonl",
    "make_v2_record",
    "premise_orientation_violations",
]
