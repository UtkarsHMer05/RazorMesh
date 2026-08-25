"""P3-M21: candidate validation gates."""

from datetime import UTC, datetime

from razormesh_api.agentpay_ir import make_record
from razormesh_api.dataset_quality import validate_candidate


def _record(
    premise: str,
    hypothesis: str,
    *,
    family="trial_renewal_trap",
    label="contradiction",
    source="qwen_provisional",
    request_id="req-1",
) -> object:  # type: ignore[no-untyped-def]
    return make_record(
        record_id="air_" + "3" * 26,
        premise=premise,
        hypothesis=hypothesis,
        label=label,  # type: ignore[arg-type]
        label_source=source,  # type: ignore[arg-type]
        family=family,  # type: ignore[arg-type]
        difficulty="medium",
        provenance={
            "generator": "qwen3.8-max-free@tokenrouter",
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


def test_premise_equals_hypothesis_is_fatal() -> None:
    same = "The band renews monthly after a trial period ends."
    r = _record(premise=same, hypothesis=same)
    res = validate_candidate(r)
    assert "premise_equals_hypothesis" in res.fatal


def test_renewal_contradiction_without_evidence_warns() -> None:
    r = _record(
        premise="Product page describes a plain one-time gadget purchase.",
        hypothesis="The human forbade any recurring charges.",
    )
    res = validate_candidate(r)
    assert res.passed  # warnings are non-fatal
    assert any("renewal" in w for w in res.warnings)


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
