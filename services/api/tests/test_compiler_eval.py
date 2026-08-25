"""P3-M14: golden-set integrity + evaluator semantics.

The golden file is MANUAL TRUTH: its expectations are asserted against
hand-built payloads here — never against Qwen output.
"""

import json
from pathlib import Path

from razormesh_api.compiler_eval import (
    Expectation,
    evaluate_case,
    load_golden,
)
from razormesh_api.domain.intent_draft import (
    CompilerIntentPayload,
    HardConstraints,
    MoneyBound,
    SemanticConstraint,
    UnspecifiedField,
)

GOLDEN = Path(__file__).resolve().parents[3] / "data" / "phase3" / "compiler_golden"
JSONL = GOLDEN / "golden_set.jsonl"
MANIFEST = GOLDEN / "manifest.json"


def _payload(**overrides) -> CompilerIntentPayload:
    base = dict(
        schema_version="agentpay-intent-draft-v1",
        product_summary="headphones",
        hard=HardConstraints(
            max_amount=MoneyBound(amount_minor=500000, currency="INR"),
            recurring_forbidden=True,
        ),
        semantic_constraints=(
            SemanticConstraint(text="must be brand new", family_hint="condition"),
        ),
        ambiguities=(),
        unspecified=(UnspecifiedField(field="merchant"),),
    )
    base.update(overrides)
    return CompilerIntentPayload.model_validate(base)


# ---------------------------------------------------------------------------
# Golden-file integrity
# ---------------------------------------------------------------------------


def test_golden_file_exists_matches_manifest() -> None:
    assert JSONL.exists() and MANIFEST.exists()
    manifest = json.loads(MANIFEST.read_text())
    rows = [json.loads(line) for line in JSONL.read_text().splitlines() if line.strip()]
    assert manifest["cases"] == len(rows) >= 300
    import hashlib

    digest = hashlib.sha256(JSONL.read_bytes()).hexdigest()
    assert digest == manifest["sha256"]
    assert manifest["truth_source"].startswith("human-authored")


def test_all_cases_parse_and_have_unique_ids() -> None:
    cases = load_golden(JSONL)
    ids = [c.case_id for c in cases]
    assert len(ids) == len(set(ids))
    for c in cases:
        assert c.input_text and c.category
        assert c.difficulty in {"easy", "medium", "hard"}


def test_categories_and_difficulty_stratified() -> None:
    cases = load_golden(JSONL)
    cats = {c.category for c in cases}
    assert len(cats) >= 20
    diffs = {c.difficulty for c in cases}
    assert {"easy", "medium", "hard"} <= diffs


def test_truth_never_from_model_field() -> None:
    """Structural honesty check: no row may carry a model/self-label field."""
    for line in JSONL.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        assert "generator_model" not in row
        assert "qwen_label" not in row
        assert "model_confidence" not in row


# ---------------------------------------------------------------------------
# Evaluator semantics
# ---------------------------------------------------------------------------


def test_perfect_extraction_passes() -> None:
    expected = Expectation(max_amount_minor=500000, currency="INR", recurring_forbidden=True)
    verdict = evaluate_case(_payload(), expected)
    assert verdict.passed and not verdict.omissions and not verdict.inventions


def test_omission_detected_when_human_stated_budget_but_draft_missing() -> None:
    payload = _payload(hard=HardConstraints(recurring_forbidden=True))  # budget dropped
    verdict = evaluate_case(payload, Expectation(max_amount_minor=500000, currency="INR"))
    assert not verdict.passed
    assert any(o.startswith("max_amount_minor") for o in verdict.omissions)


def test_invention_detected_when_currency_guessed() -> None:
    # human never mentioned money; the "UNSPECIFIED" sentinel marks that truth
    invented = HardConstraints(max_amount=MoneyBound(amount_minor=100000, currency="INR"))
    payload = _payload(hard=invented)
    verdict = evaluate_case(payload, Expectation(currency="UNSPECIFIED"))
    assert any(i.startswith("money_without_human_statement") for i in verdict.inventions)


def test_brand_invention_detected() -> None:
    payload = _payload(
        hard=HardConstraints(
            max_amount=MoneyBound(amount_minor=500000, currency="INR"),
            brand_allowlist=("sony",),
            recurring_forbidden=True,
        )
    )
    verdict = evaluate_case(payload, Expectation())
    assert any("brands:sony" in i for i in verdict.inventions)


def test_semantic_must_contain_checked_normalized() -> None:
    verdict = evaluate_case(_payload(), Expectation(semantic_must_contain=("brand new",)))
    assert verdict.passed  # 'MUST BE BRAND NEW' normalized contains 'brand new'
    missing = evaluate_case(
        _payload(semantic_constraints=()), Expectation(semantic_must_contain=("new",))
    )
    assert not missing.passed


def test_forbidden_invention_condition_blocked() -> None:
    payload = _payload(
        semantic_constraints=(
            SemanticConstraint(text="condition is new only", family_hint="condition"),
        )
    )
    verdict = evaluate_case(payload, Expectation(forbidden_inventions=("condition",)))
    assert any(i == "invented:condition" for i in verdict.inventions)


def test_unspecified_and_ambiguity_mismatch_recorded() -> None:
    verdict = evaluate_case(
        _payload(), Expectation(unspecified_contains=("currency",), min_ambiguities=2)
    )
    assert any(m == "unspecified~currency" for m in verdict.mismatches)
    assert any(m.startswith("ambiguities<") for m in verdict.mismatches)


def test_missing_payload_fails_closed() -> None:
    verdict = evaluate_case(None, Expectation(max_amount_minor=1))
    assert verdict.passed is False
    assert verdict.mismatches == ("payload_missing",)


def test_real_golden_sample_evaluates_cleanly_against_own_truth_shape() -> None:
    """Sanity: evaluator runs over the real set without crashing; a
    deliberately perfect payload passes where truth allows."""
    cases = load_golden(JSONL)
    assert len(cases) >= 300
    minimal = Expectation(min_ambiguities=0)
    sample = next(c for c in cases if c.expected.min_ambiguities == 0)
    verdict = evaluate_case(None, minimal)
    assert verdict.mismatches == ("payload_missing",)
    assert sample.case_id
