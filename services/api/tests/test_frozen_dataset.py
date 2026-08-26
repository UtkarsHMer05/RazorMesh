"""P3-M27: frozen dataset v1 — integrity, leakage-free, honest markers."""

import hashlib
import json
from pathlib import Path

from razormesh_api.agentpay_ir import AgentPayIRRecord

FROZEN = Path(__file__).resolve().parents[3] / "data" / "phase3" / "dataset" / "frozen_v1"


def _rows(split: str) -> list[AgentPayIRRecord]:
    return [
        AgentPayIRRecord.model_validate_json(line)
        for line in (FROZEN / f"{split}.jsonl").read_text().splitlines()
        if line.strip()
    ]


def test_all_splits_present_and_hash_bound() -> None:
    manifest = json.loads((FROZEN / "frozen_manifest.json").read_text())
    for split in ("train", "val", "test"):
        path = FROZEN / f"{split}.jsonl"
        assert path.exists()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == manifest["file_sha256"][split]
        assert manifest["counts_by_split"][split] == len(_rows(split))


def test_no_record_in_two_splits() -> None:
    seen: dict[str, str] = {}
    for split in ("train", "val", "test"):
        for r in _rows(split):
            assert r.record_id not in seen, r.record_id
            seen[r.record_id] = split


def test_leakage_gate_passes_on_frozen_rows() -> None:
    from razormesh_api.dataset_splits import assert_no_leakage

    all_rows = _rows("train") + _rows("val") + _rows("test")
    report = assert_no_leakage(all_rows)
    assert report.leaked_groups == ()


def test_gold_validation_marker_honest() -> None:
    manifest = json.loads((FROZEN / "frozen_manifest.json").read_text())
    assert manifest["gold_validation_status"] == "PENDING_GOLD_VALIDATION"
    provisional = sum(
        1
        for split in ("train", "val", "test")
        for r in _rows(split)
        if r.label_source == "qwen_provisional"
    )
    # provisional rows exist only if candidates were frozen; either way the
    # marker must be present whenever any qwen_provisional row is included
    if provisional:
        assert "await human gold review" in manifest["note"]


def test_every_frozen_row_schema_valid() -> None:
    total = len(_rows("train")) + len(_rows("val")) + len(_rows("test"))
    assert total >= 1000
