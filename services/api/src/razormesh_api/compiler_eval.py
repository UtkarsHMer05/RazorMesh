"""P3-M14/M15: compiler golden-set schema + deterministic evaluation.

The golden set is authored TRUTH: every case carries its expected extraction
computed by the human-authored template itself — never by Qwen. The evaluator
compares a CompilerIntentPayload against that truth field-by-field and reports
omissions (unsafe under-extraction), inventions (hallucinated constraints),
and mismatches. It contains no model calls and no authority.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from razormesh_api.domain.intent_draft import CompilerIntentPayload

GOLDEN_FORMAT_VERSION = "compiler-golden-v1"


class Expectation(BaseModel):
    """Manual truth for one case. ``None`` means 'must be absent'."""

    model_config = ConfigDict(frozen=True)

    max_amount_minor: int | None = None
    currency: str | None = None
    quantity_max: int | None = None
    brands: tuple[str, ...] = ()
    merchant_allowlist: tuple[str, ...] = ()
    recurring_forbidden: bool | None = None
    semantic_must_contain: tuple[str, ...] = Field(default=(), max_length=8)
    semantic_must_not_contain: tuple[str, ...] = Field(default=(), max_length=8)
    min_ambiguities: int = 0
    unspecified_contains: tuple[str, ...] = ()
    forbidden_inventions: tuple[str, ...] = ()  # e.g. ("condition", "brand")


class GoldenCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    category: str
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    input_text: str = Field(min_length=5, max_length=2000)
    expected: Expectation


@dataclass(frozen=True)
class CaseVerdict:
    case_id: str
    passed: bool
    mismatches: tuple[str, ...]
    omissions: tuple[str, ...]
    inventions: tuple[str, ...]


def _norm(text: str) -> str:
    return text.strip().lower()


def evaluate_case(payload: CompilerIntentPayload | None, expected: Expectation) -> CaseVerdict:
    """Field-level verdict. Omission = stated-by-human but missing in draft;
    invention = constraint present that the human never authorized."""
    if payload is None:
        return CaseVerdict(
            case_id="",
            passed=False,
            mismatches=("payload_missing",),
            omissions=tuple(),
            inventions=tuple(),
        )
    hard = payload.hard
    mismatches: list[str] = []
    omissions: list[str] = []
    inventions: list[str] = []

    # --- money -----------------------------------------------------------
    got_amount = hard.max_amount.amount_minor if hard.max_amount else None
    got_currency = hard.max_amount.currency if hard.max_amount else None
    if expected.max_amount_minor is not None:
        if got_amount != expected.max_amount_minor:
            omissions.append(f"max_amount_minor:{expected.max_amount_minor}")
        if expected.currency and got_currency != expected.currency:
            omissions.append(f"currency:{expected.currency}")
    elif expected.currency == "UNSPECIFIED":
        if got_amount is not None or got_currency is not None:
            inventions.append("money_without_human_statement")

    # --- quantity ----------------------------------------------------------
    if expected.quantity_max is not None and hard.quantity_max != expected.quantity_max:
        omissions.append(f"quantity_max:{expected.quantity_max}")

    # --- brands / merchants ----------------------------------------------
    got_brands = {_norm(b) for b in hard.brand_allowlist}
    want_brands = {_norm(b) for b in expected.brands}
    if want_brands - got_brands:
        omissions.append("brands:" + ",".join(sorted(want_brands - got_brands)))
    if got_brands - want_brands:
        inventions.append("brands:" + ",".join(sorted(got_brands - want_brands)))
    got_merchants = {_norm(m) for m in hard.merchant_allowlist}
    want_merchants = {_norm(m) for m in expected.merchant_allowlist}
    if want_merchants - got_merchants:
        omissions.append("merchants:" + ",".join(sorted(want_merchants - got_merchants)))
    if got_merchants - want_merchants:
        inventions.append("merchants:" + ",".join(sorted(got_merchants - want_merchants)))

    # --- recurring ---------------------------------------------------------
    if expected.recurring_forbidden is not None and (
        hard.recurring_forbidden != expected.recurring_forbidden
    ):
        if expected.recurring_forbidden:
            omissions.append("recurring_forbidden:true")
        else:
            inventions.append("recurring_forbidden:true-not-stated")

    # --- semantic coverage --------------------------------------------------
    blob = " ".join(_norm(sc.text) for sc in payload.semantic_constraints)
    for needle in expected.semantic_must_contain:
        if _norm(needle) not in blob:
            omissions.append(f"semantic~{needle}")
    for banned in expected.semantic_must_not_contain:
        if _norm(banned) in blob:
            inventions.append(f"semantic~{banned}")

    # --- ambiguities / unspecified ----------------------------------------
    if len(payload.ambiguities) < expected.min_ambiguities:
        mismatches.append(f"ambiguities<{expected.min_ambiguities}")
    got_unspecified = {u.field for u in payload.unspecified}
    for field_name in expected.unspecified_contains:
        if field_name not in got_unspecified:
            mismatches.append(f"unspecified~{field_name}")

    # --- declared invention bans -------------------------------------------
    for ban in expected.forbidden_inventions:
        if ban == "condition" and any(
            sc.family_hint == "condition" for sc in payload.semantic_constraints
        ):
            inventions.append("invented:condition")
        if ban == "brand" and got_brands:
            inventions.append("invented:brand")
        if ban == "merchant" and got_merchants:
            inventions.append("invented:merchant")
        if ban == "warranty" and any(
            sc.family_hint == "warranty" for sc in payload.semantic_constraints
        ):
            inventions.append("invented:warranty")

    problems = tuple(mismatches) + tuple(omissions) + tuple(inventions)
    return CaseVerdict(
        case_id="",
        passed=not problems,
        mismatches=tuple(mismatches),
        omissions=tuple(omissions),
        inventions=tuple(inventions),
    )


def load_golden(path: Path) -> list[GoldenCase]:
    cases: list[GoldenCase] = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row: dict[str, Any] = json.loads(line)
            fmt = row.pop("format_version", GOLDEN_FORMAT_VERSION)
            assert fmt == GOLDEN_FORMAT_VERSION, f"bad golden format {fmt}"
            cases.append(GoldenCase.model_validate(row))
    return cases


def golden_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
