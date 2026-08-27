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
EVALUATOR_VERSION = "compiler-evaluator-v2"


class Expectation(BaseModel):
    """Partial truth: None is unchecked unless an explicit invention ban applies."""

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


@dataclass(frozen=True)
class FieldCounts:
    """Counts within explicitly annotated truth, not unstated semantic truth."""

    expected: int
    present: int | None
    correct: int


def payload_field_counts(
    payload: CompilerIntentPayload | None, expected: Expectation
) -> dict[str, FieldCounts]:
    """Exact scalar/set counts; partial substring truth has no precision denominator."""
    hard = payload.hard if payload else None
    amount = hard.max_amount if hard else None
    counts: dict[str, FieldCounts] = {}
    scalars: tuple[tuple[str, int | str | bool | None, int | str | bool | None, bool], ...] = (
        (
            "max_amount_minor",
            expected.max_amount_minor,
            amount.amount_minor if amount else None,
            expected.max_amount_minor is not None or expected.currency == "UNSPECIFIED",
        ),
        (
            "currency",
            expected.currency if expected.currency != "UNSPECIFIED" else None,
            amount.currency if amount else None,
            expected.currency is not None,
        ),
        (
            "quantity_max",
            expected.quantity_max,
            hard.quantity_max if hard else None,
            expected.quantity_max is not None,
        ),
        (
            "recurring_forbidden",
            expected.recurring_forbidden,
            hard.recurring_forbidden if hard else None,
            expected.recurring_forbidden is not None,
        ),
    )
    for field, want, got, checked in scalars:
        counts[field] = FieldCounts(
            int(checked and want is not None),
            int(checked and got is not None),
            int(checked and want is not None and got == want),
        )
    sets = (
        ("brands", expected.brands, hard.brand_allowlist if hard else ()),
        ("merchants", expected.merchant_allowlist, hard.merchant_allowlist if hard else ()),
    )
    for field, wanted, actual in sets:
        want_set, got_set = {_norm(x) for x in wanted}, {_norm(x) for x in actual}
        counts[field] = FieldCounts(len(want_set), len(got_set), len(want_set & got_set))
    blob = " ".join(_norm(sc.text) for sc in payload.semantic_constraints) if payload else ""
    counts["semantic"] = FieldCounts(
        len(expected.semantic_must_contain),
        None,
        sum(_norm(needle) in blob for needle in expected.semantic_must_contain),
    )
    actual_unspecified = {u.field for u in payload.unspecified} if payload else set()
    counts["unspecified"] = FieldCounts(
        len(expected.unspecified_contains),
        None,
        sum(field in actual_unspecified for field in expected.unspecified_contains),
    )
    return counts


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
        if got_amount is None:
            omissions.append(f"max_amount_minor:{expected.max_amount_minor}")
        elif got_amount != expected.max_amount_minor:
            mismatches.append(f"max_amount_minor:{got_amount}!={expected.max_amount_minor}")
        if expected.currency:
            if got_currency is None:
                omissions.append(f"currency:{expected.currency}")
            elif got_currency != expected.currency:
                mismatches.append(f"currency:{got_currency}!={expected.currency}")
    elif expected.currency == "UNSPECIFIED":
        if got_amount is not None or got_currency is not None:
            inventions.append("money_without_human_statement")

    # --- quantity ----------------------------------------------------------
    if expected.quantity_max is not None and hard.quantity_max != expected.quantity_max:
        if hard.quantity_max is None:
            omissions.append(f"quantity_max:{expected.quantity_max}")
        else:
            mismatches.append(f"quantity_max:{hard.quantity_max}!={expected.quantity_max}")

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
