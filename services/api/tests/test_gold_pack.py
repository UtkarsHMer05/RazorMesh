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


def test_status_marked_pending_human() -> None:
    manifest = json.loads((GOLD / "manifest.json").read_text())
    assert manifest["status"] == "PENDING_HUMAN_REVIEW"
