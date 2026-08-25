"""P3-M18 (D-040): AgentPay-IR v0.1 — the NLI dataset record contract.

ORIENTATION RULE (fixed for all of Phase 3):
    premise    = TRUSTED EVIDENCE about the current commerce context
                 (product page facts, seller identity, price/fee breakdown);
    hypothesis = a STATEMENT OF CONFIRMED AUTHORIZATION derived only from what
                 the human confirmed.
Label semantics follow standard NLI:
    entailment     evidence supports that this authorization holds;
    neutral        evidence insufficient to decide;
    contradiction  evidence proves the authorization does NOT hold.

Every record carries machine-verifiable provenance; ``content_sha256`` is
computed over the canonical pair+label so any mutation is detectable.
``label_source`` distinguishes template truth, provisional Qwen labels, and
true human gold — P3-S09/S12 depend on this being honest.
"""

import hashlib
import json
from datetime import datetime
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

IR_FORMAT_VERSION: Final = "agentpay-ir-v0.1"

NliLabel = Literal["entailment", "neutral", "contradiction"]
LabelSource = Literal["template_truth", "human_gold", "qwen_provisional"]
Difficulty = Literal["easy", "medium", "hard"]

FAMILIES = (
    "budget_ceiling",
    "currency_binding",
    "quantity_limit",
    "brand_identity",
    "condition_new_only",
    "merchant_restriction",
    "recurring_forbidden",
    "trial_renewal_trap",
    "membership_insertion",
    "bundle_obligation",
    "shipping_fee",
    "delivery_timing",
    "return_refund",
    "warranty_claim",
    "variant_mismatch",
    "seller_alias",
    "safe_lookalike",
    "injection_resistance",
)

_TEXT_MAX_PREMISE = 1200
_TEXT_MAX_HYPOTHESIS = 400


class Provenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    generator: str = Field(min_length=3, max_length=64)
    template_id: str | None = None
    source_case_id: str | None = None
    created_at_utc: datetime
    generator_request_id: str | None = None


class Review(BaseModel):
    model_config = ConfigDict(frozen=True)

    reviewed_by_human: bool = False
    reviewer: str | None = None
    reviewed_at_utc: datetime | None = None
    notes: str | None = Field(default=None, max_length=500)


def compute_content_sha256(premise: str, hypothesis: str, label: NliLabel) -> str:
    """Deterministic content hash over the canonical JSON triple."""
    canonical = json.dumps(
        {"premise": premise, "hypothesis": hypothesis, "label": label},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AgentPayIRRecord(BaseModel):
    model_config = ConfigDict(frozen=True, validate_assignment=True)

    format_version: Literal["agentpay-ir-v0.1"] = IR_FORMAT_VERSION
    record_id: str = Field(pattern=r"^air_[0-9A-Z]{26}$")
    split: Literal["train", "val", "test"] | None = None
    premise: str = Field(min_length=10, max_length=_TEXT_MAX_PREMISE)
    hypothesis: str = Field(min_length=8, max_length=_TEXT_MAX_HYPOTHESIS)
    label: NliLabel
    label_source: LabelSource
    family: str
    difficulty: Difficulty
    provenance: Provenance
    review: Review = Field(default_factory=Review)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("family")
    @classmethod
    def _known_family(cls, v: str) -> str:
        if v not in FAMILIES:
            raise ValueError(f"unknown family {v!r}; must be one of FAMILIES")
        return v

    @field_validator("content_sha256")
    @classmethod
    def _hash_matches_content(cls, v: str, info):  # type: ignore[no-untyped-def]
        data = info.data
        if all(k in data for k in ("premise", "hypothesis", "label")):
            expected = compute_content_sha256(data["premise"], data["hypothesis"], data["label"])
            if v != expected:
                raise ValueError("content_sha256 does not match premise+hypothesis+label")
        return v


def make_record(
    *,
    record_id: str,
    premise: str,
    hypothesis: str,
    label: NliLabel,
    label_source: LabelSource,
    family: str,
    difficulty: Difficulty,
    provenance: Provenance,
    review: Review | None = None,
) -> AgentPayIRRecord:
    """Factory computing the integrity hash so callers cannot forget it."""
    return AgentPayIRRecord(
        record_id=record_id,
        premise=premise,
        hypothesis=hypothesis,
        label=label,
        label_source=label_source,
        family=family,
        difficulty=difficulty,
        provenance=provenance,
        review=review or Review(),
        content_sha256=compute_content_sha256(premise, hypothesis, label),
    )


def dump_jsonl(records: list[AgentPayIRRecord]) -> str:
    return "\n".join(r.model_dump_json() for r in records) + "\n"
