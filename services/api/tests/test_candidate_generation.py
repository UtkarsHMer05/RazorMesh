"""P3-M20 generator acceptance semantics without external API calls."""

from datetime import UTC, datetime

from razormesh_api.candidate_generation import (
    BATCH_ID,
    GENERATOR_NAME,
    PROMPT_VERSION,
    build_record,
    diversity_first,
    request_key,
)


def _seed(record_id: str, family: str, label: str, difficulty: str) -> dict:
    return {
        "record_id": record_id,
        "family": family,
        "label": label,
        "difficulty": difficulty,
    }


def test_request_key_is_order_independent_and_prompt_version_bound() -> None:
    seed = _seed("air_" + "A" * 26, "seller_alias", "neutral", "hard")
    assert request_key(seed) == request_key(dict(reversed(list(seed.items()))))
    assert len(request_key(seed)) == 64


def test_diversity_first_prefix_spans_buckets_and_is_deterministic() -> None:
    rows = [
        _seed("air_" + str(i).zfill(26), "budget_ceiling", "entailment", "easy") for i in range(6)
    ] + [
        _seed("air_" + "B" * 25 + "1", "seller_alias", "neutral", "hard"),
        _seed("air_" + "C" * 25 + "1", "injection_resistance", "contradiction", "hard"),
    ]
    first = diversity_first(rows)
    second = diversity_first(reversed(rows))
    assert [r["record_id"] for r in first] == [r["record_id"] for r in second]
    assert [r["family"] for r in first[:3]] == [
        "injection_resistance",
        "seller_alias",
        "budget_ceiling",
    ]


def test_generated_row_is_provisional_and_provenance_complete() -> None:
    seed = _seed("air_" + "D" * 26, "trial_renewal_trap", "contradiction", "hard")
    key = request_key(seed)
    record = build_record(
        seed=seed,
        premise="Checkout says no charge today, then renews for INR 499 monthly.",
        hypothesis="The human authorized no recurring commitment for this purchase.",
        key=key,
        model_reported="qwen3.8-max-pd",
        created_at_utc=datetime(2026, 8, 27, tzinfo=UTC),
    )
    assert record.label_source == "qwen_provisional"
    assert record.review.reviewed_by_human is False
    assert record.provenance.generator == GENERATOR_NAME
    assert record.provenance.generator_model == "qwen3.8-max-pd"
    assert record.provenance.prompt_version == PROMPT_VERSION
    assert record.provenance.batch_id == BATCH_ID
    assert record.provenance.source_case_id == seed["record_id"]
    assert record.provenance.generator_request_id == key
    assert "secret" not in record.model_dump_json().lower()
