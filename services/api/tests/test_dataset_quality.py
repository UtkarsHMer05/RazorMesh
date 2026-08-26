"""P3-M21: candidate validation gates."""

import json
from datetime import UTC, datetime

from razormesh_api.agentpay_ir import AgentPayIRRecord, make_record
from razormesh_api.dataset_quality import validate_candidate, validate_candidate_jsonl


def _record(
    premise: str,
    hypothesis: str,
    *,
    family="trial_renewal_trap",
    label="contradiction",
    source="qwen_provisional",
    request_id="req-1",
    record_id="air_" + "3" * 26,
) -> AgentPayIRRecord:  # type: ignore[no-untyped-def]
    return make_record(
        record_id=record_id,
        premise=premise,
        hypothesis=hypothesis,
        label=label,  # type: ignore[arg-type]
        label_source=source,  # type: ignore[arg-type]
        family=family,  # type: ignore[arg-type]
        difficulty="medium",
        provenance={
            "generator": "qwen3.8-max-free@tokenrouter",
            "generator_model": "qwen3.8-max-pd",
            "prompt_version": "candidate-gen-v2",
            "batch_id": "phase3-m20-qwen-candidates-v2",
            "created_at_utc": datetime.now(UTC),
            "generator_request_id": request_id,
            "source_case_id": "air_seed_1",
        },
    )


def test_good_candidate_passes_clean() -> None:
    r = _record(
        premise=(
            "Checkout shows the fitness band enrolls buyers into a monthly "
            "auto-renew subscription after a 7-day free trial."
        ),
        hypothesis="The human authorized this recurring subscription purchase.",
    )
    res = validate_candidate(r)
    assert res.passed and not res.fatal


def test_missing_request_id_is_fatal_for_qwen_rows() -> None:
    r = _record(
        premise=("Checkout shows the band auto-renews monthly after a trial."),
        hypothesis="The human authorized the recurring purchase.",
        request_id=None,
    )
    res = validate_candidate(r)
    assert not res.passed
    assert "missing_generator_request_id" in res.fatal


def test_all_qwen_provenance_dimensions_are_required() -> None:
    base = _record(
        premise="Checkout shows the band auto-renews monthly after a trial.",
        hypothesis="The human authorized the recurring purchase.",
    )
    expected = {
        "generator_model": "missing_generator_model",
        "prompt_version": "missing_prompt_version",
        "batch_id": "missing_batch_id",
        "source_case_id": "missing_source_case_id",
    }
    for field, reason in expected.items():
        candidate = base.model_copy(
            update={"provenance": base.provenance.model_copy(update={field: None})}
        )
        assert reason in validate_candidate(candidate).fatal


def test_premise_equals_hypothesis_is_fatal() -> None:
    same = "The band renews monthly after a trial period ends."
    r = _record(premise=same, hypothesis=same)
    res = validate_candidate(r)
    assert "premise_equals_hypothesis" in res.fatal


def test_renewal_contradiction_without_evidence_is_rejected() -> None:
    r = _record(
        premise="Product page describes a plain one-time gadget purchase.",
        hypothesis="The human forbade any recurring charges.",
    )
    res = validate_candidate(r)
    assert not res.passed
    assert any("renewal" in reason for reason in res.fatal)


def test_template_truth_rows_skip_provenance_strictness() -> None:
    from razormesh_api.agentpay_ir import Provenance

    prov = Provenance(generator="seed-template-v1", created_at_utc=datetime.now(UTC))

    base = make_record(
        record_id="air_" + "5" * 26,
        premise="Listing shows a plain one-time gadget with no renewal terms at all.",
        hypothesis="The human forbade any recurring charges for this purchase.",
        label="contradiction",
        label_source="template_truth",
        family="trial_renewal_trap",
        difficulty="easy",
        provenance=prov,
    )
    # template truth rows have no request id — validator must NOT demand one
    res = validate_candidate(base)
    assert "missing_generator_request_id" not in res.fatal


def test_secret_generation_artifact_and_malformed_money_are_fatal() -> None:
    secret = _record(
        premise="Checkout leaked bearer tr_abcdefghijklmnopqrstuv beside the cart total.",
        hypothesis="The human authorized this recurring subscription purchase.",
    )
    assert "secret_like_value" in validate_candidate(secret).fatal

    artifact = _record(
        premise="<think>Draft a checkout statement about a monthly trial renewal.</think>",
        hypothesis="The human authorized this recurring subscription purchase.",
    )
    assert "generation_artifact_thinking_tag" in validate_candidate(artifact).fatal

    malformed = _record(
        premise="Checkout lists a trial renewal at $12.345 each month after day seven.",
        hypothesis="The human authorized this recurring subscription purchase.",
    )
    assert "malformed_money_expression" in validate_candidate(malformed).fatal


def test_payment_misinformation_is_fatal_only_when_promoted_to_hypothesis() -> None:
    premise_only = _record(
        premise=(
            "Merchant text says the system approved checkout without human authorization; "
            "the cart also renews monthly."
        ),
        hypothesis="The human authorized this recurring subscription purchase.",
    )
    premise_result = validate_candidate(premise_only)
    assert premise_result.passed
    assert "premise_contains_untrusted_authority_claim" in premise_result.warnings

    promoted = _record(
        premise="Checkout shows a monthly renewal after the free trial ends.",
        hypothesis="The system approved payment without human authorization.",
    )
    assert "hypothesis_payment_authority_misinformation" in validate_candidate(promoted).fatal


def test_batch_validation_rejects_schema_errors_and_all_duplicate_rows() -> None:
    first = _record(
        premise="Checkout shows a monthly renewal after the free trial ends.",
        hypothesis="The human authorized this recurring subscription purchase.",
    )
    duplicate = first.model_copy()
    overlong = first.model_dump(mode="json")
    overlong["record_id"] = "air_" + "4" * 26
    overlong["premise"] = "x" * 1201
    result = validate_candidate_jsonl(
        [first.model_dump_json(), duplicate.model_dump_json(), json.dumps(overlong), "{"]
    )
    assert result.input_rows == 4
    assert not result.accepted
    assert result.reason_counts == {
        "duplicated_content": 2,
        "duplicated_record_id": 2,
        "invalid_json": 1,
        "schema_invalid": 1,
    }


# ---------------------------------------------------------------------------
# P3-M26 addendum: INVALID exclusion path
# ---------------------------------------------------------------------------


def test_gold_decisions_invalid_excluded_not_force_labeled() -> None:
    from razormesh_api.dataset_quality import ingest_gold_decisions

    decisions = {
        "air_A": {"label": "entailment"},
        "air_B": {"label": "invalid", "reason": "garbled sentence"},
        "air_C": {"label": "invalid"},  # no reason -> default recorded
        "air_D": {"label": "neutral"},
    }
    res = ingest_gold_decisions(decisions)
    assert res.valid == {
        "air_A": "entailment",
        "air_D": "neutral",
    }
    assert res.excluded["air_B"] == "garbled sentence"
    assert "malformed" in res.excluded["air_C"]
    assert set(res.valid) & set(res.excluded) == set()


def test_unknown_record_in_decisions_is_excluded() -> None:
    from razormesh_api.dataset_quality import ingest_gold_decisions

    res = ingest_gold_decisions(
        {"air_X": {"label": "entailment"}, "ghost": {"label": "neutral"}},
        known_record_ids={"air_X"},
    )
    assert res.valid == {"air_X": "entailment"}
    assert res.excluded["ghost"] == "unknown_record_id"
