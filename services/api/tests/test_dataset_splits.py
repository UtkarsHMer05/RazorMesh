"""P3-M23: leakage-safe splitting — group integrity + determinism."""

from datetime import UTC, datetime

import pytest

from razormesh_api.agentpay_ir import AgentPayIRRecord, make_record
from razormesh_api.dataset_splits import assert_no_leakage, assign_splits, leakage_report

PROV_BASE = {
    "generator": "seed-template-v1",
    "created_at_utc": datetime(2026, 8, 26, tzinfo=UTC),
}

COUNTER = {"n": 0}


def _rec(source_case: str, label="entailment") -> AgentPayIRRecord:
    COUNTER["n"] += 1
    return make_record(
        record_id=f"air_{str(COUNTER['n']).zfill(26)}",
        premise=f"Premise evidence text for {source_case} with price ₹1,000.",
        hypothesis=f"Authorization statement for {source_case}.",
        label=label,  # type: ignore[arg-type]
        label_source="template_truth",
        family="budget_ceiling",
        difficulty="easy",
        provenance={
            "generator": PROV_BASE["generator"],
            "source_case_id": source_case,
            "created_at_utc": PROV_BASE["created_at_utc"],
        },
    )


def test_groups_stay_whole_across_splits() -> None:
    records = [
        _rec("case-A", "entailment"),
        _rec("case-A", "contradiction"),
        _rec("case-A", "neutral"),
        *[_rec(f"case-{chr(66 + i)}", "entailment") for i in range(30)],
    ]
    split_rows = assign_splits(records)
    report = leakage_report(split_rows)
    assert report.passed
    a_split = {r.split for r in split_rows if r.provenance.source_case_id == "case-A"}
    assert len(a_split) == 1  # all three siblings share ONE split


def test_deterministic_assignment() -> None:
    records = [_rec(f"case-{i}", "entailment") for i in range(40)]
    s1 = [r.split for r in assign_splits(records)]
    s2 = [r.split for r in assign_splits(records)]
    assert s1 == s2


@pytest.mark.parametrize("target_ratio", [(0.70, 0.15, 0.15)])
def test_approximate_ratio(target_ratio) -> None:  # type: ignore[no-untyped-def]
    records = [
        _rec(f"case-{i:03d}", ["entailment", "neutral", "contradiction"][i % 3]) for i in range(300)
    ]
    split_rows = assign_splits(records)
    counts = leakage_report(split_rows).counts
    total = sum(counts.values())
    train_share = counts.get("train", 0) / total
    assert 0.55 <= train_share <= 0.85  # whole-group granularity tolerance


def test_leakage_report_detects_contaminated_fixture() -> None:
    """A group spanning two splits MUST be caught (the release-blocker)."""
    rows = []
    for i in range(6):
        r = _rec("shared-case", "entailment")
        rows.append(r.model_copy(update={"split": "train" if i < 3 else "test"}))
    report = leakage_report(rows)
    assert not report.passed
    assert "shared-case" in report.leaked_groups

    with pytest.raises(AssertionError, match="leakage detected"):
        assert_no_leakage(rows)


def test_unassigned_rows_flagged_in_counts() -> None:
    r = _rec("case-Z").model_copy(update={"split": None})
    report = leakage_report([r])
    assert report.counts.get("UNASSIGNED") == 1
