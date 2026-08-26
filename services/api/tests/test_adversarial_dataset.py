"""P3-M24: curated adversarial/OOD expansion acceptance gates."""

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from razormesh_api.agentpay_ir import FAMILIES, AgentPayIRRecord
from razormesh_api.dataset_dedup import analyze
from razormesh_api.dataset_splits import assign_splits, leakage_report

ADV = Path(__file__).resolve().parents[3] / "data" / "phase3" / "dataset" / "adversarial"
REQUIRED_SUBFAMILIES = {
    "euphemistic_recurring_care",
    "double_negative_renewal",
    "unicode_homoglyph_seller",
    "legal_entity_alias",
    "refurbished_grade_euphemism",
    "mandatory_accessory_bundle",
    "no_charge_today_conversion",
    "fake_system_approval",
    "embedded_budget_override",
    "benign_caps_marketing",
    "benign_security_warning",
    "compatible_product_language",
}
SECRET_PATTERN = re.compile(
    r"(?:\btr_[A-Za-z0-9_-]{16,}\b|\bsk-[A-Za-z0-9_-]{16,}\b|"
    r"\brzp_live_[A-Za-z0-9_-]{8,}\b|-----BEGIN PRIVATE KEY-----)",
    re.IGNORECASE,
)


def _rows() -> list[AgentPayIRRecord]:
    return [
        AgentPayIRRecord.model_validate_json(line)
        for line in (ADV / "adversarial_dataset.jsonl").read_text().splitlines()
        if line.strip()
    ]


def test_adversarial_file_valid_manifest_bound_and_broad() -> None:
    manifest = json.loads((ADV / "manifest.json").read_text())
    rows = _rows()
    assert len(rows) >= 120
    assert manifest["records"] == len(rows)
    assert manifest["independent_scenario_groups"] >= 40
    assert manifest["records_per_scenario_group"] == 3
    assert (
        manifest["sha256"]
        == hashlib.sha256((ADV / "adversarial_dataset.jsonl").read_bytes()).hexdigest()
    )
    assert manifest["generated_at_utc"] == "2026-08-27T00:00:00+00:00"
    assert REQUIRED_SUBFAMILIES <= set(manifest["subfamilies"])
    assert manifest["semantic_families"] == 18
    assert manifest["maximum_semantic_family_share"] <= 0.10
    assert manifest["fatal_quality_findings"] == 0
    assert manifest["warning_records"] == 3
    assert manifest["exact_or_near_duplicate_rejections"] == 0
    assert manifest["cross_class_near_collisions"] == 0
    assert manifest["leakage_preview_passed"] is True


def test_every_semantic_family_and_label_is_covered_without_dominance() -> None:
    rows = _rows()
    family_counts = Counter(row.family for row in rows)
    label_counts = Counter(row.label for row in rows)
    assert set(family_counts) == set(FAMILIES)
    assert label_counts == {"entailment": 43, "neutral": 43, "contradiction": 43}
    assert max(family_counts.values()) / len(rows) <= 0.10


def test_each_subfamily_is_one_group_with_three_relation_labels() -> None:
    groups: dict[str, list[AgentPayIRRecord]] = defaultdict(list)
    for row in _rows():
        assert row.provenance.source_case_id is not None
        groups[row.provenance.source_case_id].append(row)
    assert len(groups) == 43
    for group_id, siblings in groups.items():
        assert group_id.startswith("ood-v2:")
        assert len(siblings) == 3
        assert {row.label for row in siblings} == {
            "entailment",
            "neutral",
            "contradiction",
        }
        assert len({row.provenance.template_id for row in siblings}) == 3


def test_all_rows_are_hard_template_truth_with_no_secret_artifacts() -> None:
    body = (ADV / "adversarial_dataset.jsonl").read_text()
    assert not SECRET_PATTERN.search(body)
    for row in _rows():
        assert row.difficulty == "hard"
        assert row.label_source == "template_truth"
        assert row.provenance.generator == "adversarial-ood-curated-v2"
        assert row.review.reviewed_by_human is False


def test_no_exact_or_near_duplicate_contamination() -> None:
    report = analyze(_rows(), near_threshold=0.90)
    assert not report.duplicate_of
    assert not report.cross_class_collisions
    assert len(report.canonical_ids) == len(_rows())


def test_source_groups_stay_whole_in_leakage_safe_split() -> None:
    split_rows = assign_splits(_rows())
    report = leakage_report(split_rows)
    assert report.passed
    by_group: dict[str, set[str | None]] = defaultdict(set)
    for row in split_rows:
        assert row.provenance.source_case_id is not None
        by_group[row.provenance.source_case_id].add(row.split)
    assert all(len(splits) == 1 for splits in by_group.values())
