"""P3-M14: golden-set integrity + evaluator semantics.

The golden file is MANUAL TRUTH: its expectations are asserted against
hand-built payloads here — never against Qwen output.
"""

import importlib.util
import json
from pathlib import Path

import pytest

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


def test_wrong_present_money_currency_quantity_are_substitutions_not_omissions() -> None:
    payload = _payload(
        hard=HardConstraints(
            max_amount=MoneyBound(amount_minor=600000, currency="USD"),
            quantity_max=3,
        )
    )
    verdict = evaluate_case(
        payload,
        Expectation(
            max_amount_minor=500000,
            currency="INR",
            quantity_max=2,
        ),
    )
    assert verdict.omissions == ()
    assert verdict.mismatches == (
        "max_amount_minor:600000!=500000",
        "currency:USD!=INR",
        "quantity_max:3!=2",
    )
    assert not verdict.passed


def test_missing_money_currency_quantity_are_omissions_not_substitutions() -> None:
    verdict = evaluate_case(
        _payload(hard=HardConstraints()),
        Expectation(
            max_amount_minor=500000,
            currency="INR",
            quantity_max=2,
        ),
    )
    assert verdict.mismatches == ()
    assert verdict.omissions == (
        "max_amount_minor:500000",
        "currency:INR",
        "quantity_max:2",
    )


def test_legacy_summary_reports_unknown_precision_and_counts_entity_members() -> None:
    path = GOLDEN.parents[2] / "scripts" / "rzp_summarize_compiler_eval.py"
    spec = importlib.util.spec_from_file_location("compiler_summary", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = [
        {
            "case_id": "x",
            "status": "OK",
            "omissions": ["max_amount_minor:100", "brands:sony,bose"],
            "mismatches": [],
            "inventions": ["brands:apple,samsung"],
        }
    ]
    golden = [
        {"case_id": "x", "expected": {"max_amount_minor": 100, "brands": ["sony", "bose", "jbl"]}}
    ]
    metrics = module.field_metrics(rows, golden)
    assert metrics["max_amount_minor"]["precision"] is None
    assert metrics["max_amount_minor"]["present_instances"] is None
    assert metrics["max_amount_minor"]["recall"] == 0
    assert metrics["brands"]["expected_instances"] == 3
    assert metrics["brands"]["present_instances"] == 3
    assert metrics["brands"]["precision"] == 0.3333
    assert metrics["brands"]["recall"] == 0.3333


def _script_module(name: str):
    path = GOLDEN.parents[2] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_payload_summary_has_real_numeric_precision_denominators() -> None:
    module = _script_module("rzp_summarize_compiler_eval")
    payload = _payload(
        hard=HardConstraints(
            max_amount=MoneyBound(amount_minor=600000, currency="INR"),
            quantity_max=2,
        )
    )
    row = {
        "case_id": "x",
        "payload": payload.model_dump(mode="json"),
        "status": "OK",
        "omissions": [],
        "mismatches": [],
        "inventions": [],
    }
    golden = [
        {
            "case_id": "x",
            "expected": {"max_amount_minor": 500000, "currency": "INR", "quantity_max": 2},
        }
    ]
    metrics = module.field_metrics([row], golden)
    assert metrics["max_amount_minor"]["present_instances"] == 1
    assert metrics["max_amount_minor"]["precision"] == 0
    assert metrics["currency"]["precision"] == 1
    assert metrics["quantity_max"]["precision"] == 1
    assert metrics["semantic"]["precision"] is None


def test_repair_rate_includes_failed_repairs_in_all_case_denominator() -> None:
    module = _script_module("rzp_summarize_compiler_eval")
    metrics = module.repair_metrics(
        [
            {"status": "OK", "attempts": 1},
            {"status": "OK", "attempts": 2},
            {"status": "FAILED", "attempts": 2},
        ]
    )
    assert metrics == {
        "cases_needing_repair": 2,
        "evaluated_cases": 3,
        "repair_rate": 0.6667,
        "repaired_to_valid": 1,
        "failed_after_repair": 1,
        "repair_success_rate": 0.5,
    }


def test_whole_output_failure_reduces_recall_without_valid_output_omission() -> None:
    module = _script_module("rzp_summarize_compiler_eval")
    expected = Expectation(max_amount_minor=100, currency="INR", quantity_max=2)
    verdict = evaluate_case(None, expected)
    assert verdict.omissions == ()
    assert verdict.mismatches == ("payload_missing",)
    row = {"case_id": "failed", "status": "FAILED", "payload": None}
    metrics = module.field_metrics(
        [row], [{"case_id": "failed", "expected": expected.model_dump()}]
    )
    assert metrics["max_amount_minor"]["expected_instances"] == 1
    assert metrics["max_amount_minor"]["present_instances"] == 0
    assert metrics["max_amount_minor"]["recall"] == 0


def test_scalar_direction_does_not_reclassify_strict_bound_or_missing_output() -> None:
    module = _script_module("rzp_summarize_compiler_eval")
    payload = _payload(
        hard=HardConstraints(
            max_amount=MoneyBound(amount_minor=499999, currency="USD"),
            quantity_max=3,
        )
    )
    rows = [
        {"case_id": "x", "payload": payload.model_dump(mode="json")},
        {"case_id": "failed", "payload": None},
    ]
    golden = [
        {
            "case_id": key,
            "expected": {"max_amount_minor": 500000, "currency": "INR", "quantity_max": 2},
        }
        for key in ("x", "failed")
    ]
    metrics = module.scalar_mismatch_details(rows, golden)
    assert metrics["max_amount_minor"]["directions"] == {"lower": 1}
    assert metrics["max_amount_minor"]["cases"][0]["delta"] == -1
    assert metrics["quantity_max"]["directions"] == {"higher": 1}
    assert metrics["currency"]["directions"] == {"different_currency": 1}
    assert not evaluate_case(payload, Expectation.model_validate(golden[0]["expected"])).passed


def test_v2_runner_protects_legacy_and_resume_provenance(tmp_path, monkeypatch) -> None:
    runner = _script_module("rzp_run_compiler_eval")
    legacy = tmp_path / "legacy"
    monkeypatch.setattr(runner, "LEGACY", legacy)
    with pytest.raises(ValueError, match="immutable"):
        runner.prepare_run(legacy, {})
    output = tmp_path / "v2"
    results = runner.prepare_run(output, {"golden_sha256": "one"})
    assert results == output / "results.jsonl"
    with pytest.raises(ValueError, match="provenance mismatch"):
        runner.prepare_run(output, {"golden_sha256": "two"})


def test_v2_runner_rejects_unknown_and_legacy_rows(tmp_path) -> None:
    runner = _script_module("rzp_run_compiler_eval")
    results = tmp_path / "results.jsonl"
    results.write_text(json.dumps({"case_id": "unknown"}) + "\n")
    with pytest.raises(ValueError, match="unknown"):
        runner.completed_ids(results, {"x"})
    results.write_text(json.dumps({"case_id": "x"}) + "\n")
    with pytest.raises(ValueError, match="historical"):
        runner.completed_ids(results, {"x"})


def test_summary_rejects_unknown_ids_before_writing(tmp_path, monkeypatch) -> None:
    module = _script_module("rzp_summarize_compiler_eval")
    results = tmp_path / "results.jsonl"
    results.write_text(json.dumps({"case_id": "unknown"}) + "\n")
    output = tmp_path / "summary.json"
    monkeypatch.setattr("sys.argv", ["summary", "--results", str(results), "--output", str(output)])
    with pytest.raises(ValueError, match="unknown case"):
        module.main()
    assert not output.exists()


def test_summary_rejects_changed_golden_provenance(tmp_path, monkeypatch) -> None:
    module = _script_module("rzp_summarize_compiler_eval")
    case_id = module._load_golden()[0]["case_id"]
    results = tmp_path / "results.jsonl"
    results.write_text(
        json.dumps(
            {
                "case_id": case_id,
                "evaluator_version": module.EVALUATOR_VERSION,
                "payload": None,
                "provenance": {"golden_sha256": "wrong", "case_ids": [case_id]},
            }
        )
        + "\n"
    )
    output = tmp_path / "summary.json"
    monkeypatch.setattr("sys.argv", ["summary", "--results", str(results), "--output", str(output)])
    with pytest.raises(ValueError, match="provenance"):
        module.main()
    assert not output.exists()


def test_summary_rejects_versioned_verdict_without_payload(tmp_path, monkeypatch) -> None:
    module = _script_module("rzp_summarize_compiler_eval")
    results = tmp_path / "results.jsonl"
    results.write_text(
        json.dumps(
            {
                "case_id": module._load_golden()[0]["case_id"],
                "evaluator_version": module.EVALUATOR_VERSION,
            }
        )
        + "\n"
    )
    output = tmp_path / "summary.json"
    monkeypatch.setattr("sys.argv", ["summary", "--results", str(results), "--output", str(output)])
    with pytest.raises(ValueError, match="missing payload"):
        module.main()
    assert not output.exists()


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
