"""P3-M18: AgentPay-IR v0.1 schema — orientation, provenance, integrity."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from razormesh_api.agentpay_ir import (
    IR_FORMAT_VERSION,
    AgentPayIRRecord,
    Provenance,
    Review,
    compute_content_sha256,
    dump_jsonl,
    make_record,
)


def _prov(**over) -> Provenance:  # type: ignore[no-untyped-def]
    base = {
        "generator": "template-v1",
        "template_id": "T-cond-01",
        "created_at_utc": datetime.now(UTC),
    }
    base.update(over)
    return Provenance(**base)


def _record(**over) -> AgentPayIRRecord:  # type: ignore[no-untyped-def]
    kwargs = dict(
        record_id="air_" + "0" * 26,
        premise=(
            "Product page states: refurbished unit, 6-month seller warranty only, "
            "priced at ₹4,999 with free shipping."
        ),
        hypothesis="The human authorized buying a brand-new unit with full warranty.",
        label="contradiction",
        label_source="template_truth",
        family="condition_new_only",
        difficulty="medium",
        provenance=_prov(),
    )
    kwargs.update(over)
    return make_record(**kwargs)


def test_valid_record_round_trips() -> None:
    r = _record()
    again = AgentPayIRRecord.model_validate_json(r.model_dump_json())
    assert again == r
    assert again.format_version == IR_FORMAT_VERSION


def test_hash_binds_content_any_mutation_detected() -> None:
    r = _record()
    tampered = r.model_dump()
    tampered["premise"] = tampered["premise"].replace("refurbished", "brand new")
    with pytest.raises(ValidationError, match="content_sha256"):
        AgentPayIRRecord.model_validate(tampered)


def test_unknown_family_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown family"):
        _record(family="vibes")


def test_label_vocabulary_enforced() -> None:
    with pytest.raises(ValidationError):
        _record(label="maybe")  # type: ignore[arg-type]


def test_label_source_vocabulary_enforced() -> None:
    with pytest.raises(ValidationError):
        _record(label_source="qwen_gold")  # type: ignore[arg-type]


def test_split_only_known_values_or_none() -> None:
    from razormesh_api.agentpay_ir import AgentPayIRRecord

    base = _record()
    none_row = AgentPayIRRecord(**{**base.model_dump(), "split": None})
    train_row = AgentPayIRRecord(**{**base.model_dump(), "split": "train"})
    assert none_row.split is None and train_row.split == "train"
    with pytest.raises(ValidationError):
        AgentPayIRRecord(**{**base.model_dump(), "split": "holdout"})


def test_text_bounds_enforced() -> None:
    with pytest.raises(ValidationError):
        _record(premise="short")
    with pytest.raises(ValidationError):
        _record(hypothesis="tiny")
    with pytest.raises(ValidationError):
        _record(premise="x" * 1201)


def test_review_defaults_unreviewed() -> None:
    r = _record()
    assert r.review.reviewed_by_human is False
    assert r.review.reviewer is None


def test_factory_computes_hash() -> None:
    r = make_record(
        record_id="air_" + "1" * 26,
        premise="Seller listing: genuine Sony WH-1000XM5, brand new, ₹24,990.",
        hypothesis="Authorization covers a genuine Sony WH-1000XM5 at about ₹25k.",
        label="entailment",
        label_source="human_gold",
        family="brand_identity",
        difficulty="easy",
        provenance=_prov(generator="human-gold-entry"),
        review=Review(reviewed_by_human=True, reviewer="owner"),
    )
    assert (
        r.content_sha256 == compute_content_sha256(r.premise, r.hypothesis, r.label)  # type: ignore[arg-type]
    )


def test_dump_jsonl_round_trip() -> None:
    second = make_record(
        record_id="air_" + "2" * 26,
        premise=_record().premise,
        hypothesis=_record().hypothesis,
        label="contradiction",
        label_source="template_truth",
        family="condition_new_only",
        difficulty="easy",
        provenance=_prov(),
    )
    lines = dump_jsonl([_record(), second]).strip().splitlines()
    parsed = [AgentPayIRRecord.model_validate_json(line) for line in lines]
    assert len(parsed) == 2
