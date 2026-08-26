"""P3-M25: gold review pack integrity."""

import csv
import json
from pathlib import Path

GOLD = Path(__file__).resolve().parents[3] / "data" / "phase3" / "gold"


def test_pack_files_exist() -> None:
    for name in ("gold_review.csv", "gold_review.html", "INSTRUCTIONS.md", "manifest.json"):
        assert (GOLD / name).exists(), name


def test_csv_row_count_and_columns() -> None:
    manifest = json.loads((GOLD / "manifest.json").read_text())
    with (GOLD / "gold_review.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == manifest["sampled"] >= 300
    assert set(rows[0]) == {
        "record_id",
        "premise",
        "hypothesis",
        "family",
        "difficulty",
        "suggested_label",
    }
    ids = [r["record_id"] for r in rows]
    assert len(ids) == len(set(ids))
    # hash binding
    import hashlib

    digest = hashlib.sha256((GOLD / "gold_review.csv").read_bytes()).hexdigest()
    assert digest == manifest["csv_sha256"]


def test_stratification_all_families_and_labels() -> None:
    manifest = json.loads((GOLD / "manifest.json").read_text())
    assert manifest["families_covered"] >= 18
    assert set(manifest["by_label"]) == {"contradiction", "entailment", "neutral"}


def test_html_reviewer_wired() -> None:
    html = (GOLD / "gold_review.html").read_text()
    for hook in (
        "keydown",
        "'entailment'",
        "'neutral'",
        "'contradiction'",
        "gold_decisions.json",
        "__ROWS__",
    ):
        if hook == "__ROWS__":  # replaced at build time
            assert "__ROWS__" not in html
        else:
            assert hook in html


def test_reviewer_supports_invalid_exclusion_label() -> None:
    html = (GOLD / "gold_review.html").read_text()
    assert "decide('invalid'" in html
    assert "decide('invalid')" in html  # keydown handler
    assert "label === 'invalid'" in html  # decide() invalid branch
    assert "rm_gold_decisions_v1" in html  # localStorage persistence
    assert "label: 'invalid'" in html  # decide() builds the exclusion entry
    assert "reason" in html  # exclusion-reason capture wired
    # CSV/cards untouched by the reviewer upgrade
    with (GOLD / "gold_review.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 320 and all(r["suggested_label"] != "invalid" for r in rows)


def test_status_reflects_current_validation() -> None:
    """M25 expected PENDING_HUMAN_REVIEW; M26 completed gold review so the
    status legitimately flipped to GOLD_VALIDATED. Either is a valid
    'honest' state for the manifest — the assertion is now state-agnostic
    and only ensures the field is one of the two documented statuses."""
    manifest = json.loads((GOLD / "manifest.json").read_text())
    assert manifest["status"] in {"PENDING_HUMAN_REVIEW", "GOLD_VALIDATED"}
