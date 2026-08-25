"""P3-M19: seed dataset integrity — schema-valid, deterministic, balanced."""

import hashlib
import json
import subprocess
from pathlib import Path

from razormesh_api.agentpay_ir import AgentPayIRRecord

SEED = Path(__file__).resolve().parents[3] / "data" / "phase3" / "dataset" / "seed"
JSONL = SEED / "seed_dataset.jsonl"
MANIFEST = SEED / "manifest.json"


def _rows() -> list[AgentPayIRRecord]:
    return [
        AgentPayIRRecord.model_validate_json(line)
        for line in JSONL.read_text().splitlines()
        if line.strip()
    ]


def test_seed_exists_and_matches_manifest() -> None:
    assert JSONL.exists() and MANIFEST.exists()
    manifest = json.loads(MANIFEST.read_text())
    rows_raw = [
        line for line in JSONL.read_text().splitlines() if line.strip()
    ]
    assert manifest["records"] == len(rows_raw) >= 600  # master-prompt floor
    assert manifest["sha256"] == hashlib.sha256(JSONL.read_bytes()).hexdigest()


def test_every_row_schema_valid_and_unique() -> None:
    rows = _rows()
    ids = {r.record_id for r in rows}
    hashes = {r.content_sha256 for r in rows}
    assert len(ids) == len(rows)
    assert len(hashes) == len(rows)  # no duplicate content


def test_label_balance_is_reasonably_even() -> None:
    rows = _rows()
    labels = {r.label for r in rows}
    assert labels == {"entailment", "neutral", "contradiction"}
    counts = {label: sum(1 for r in rows if r.label == label) for label in labels}
    # Content-dedup may trim a few; each class must stay within 5% of a third.
    total = len(rows)
    for label, n in counts.items():
        assert abs(n - total / 3) <= total * 0.05, (label, n, total)


def test_family_coverage_complete() -> None:
    from razormesh_api.agentpay_ir import FAMILIES

    families = {r.family for r in _rows()}
    assert families == set(FAMILIES)


def test_all_template_truth_not_qwen() -> None:
    for r in _rows():
        assert r.label_source == "template_truth"
        assert r.review.reviewed_by_human is False
        assert r.provenance.generator.startswith("seed-template")


def test_determinism_regenerate_identical_bytes(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Re-running the builder yields byte-identical output (idempotent)."""
    before = JSONL.read_bytes()
    result = subprocess.run(  # noqa: S603 - fixed absolute tool path
        [
            "/Users/utkarshkhajuria/.local/bin/uv",
            "run",
            "--project",
            str(Path(__file__).resolve().parents[2]),
            "python",
            str(Path(__file__).resolve().parents[3] / "scripts" / "rzp_build_seed_dataset.py"),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[3],
    )
    assert result.returncode == 0, result.stderr[-500:]
    assert JSONL.read_bytes() == before  # byte-identical regeneration
