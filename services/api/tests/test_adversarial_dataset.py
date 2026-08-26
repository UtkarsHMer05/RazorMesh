"""P3-M24: adversarial expansion integrity."""

import hashlib
import json
from pathlib import Path

from razormesh_api.agentpay_ir import AgentPayIRRecord

ADV = Path(__file__).resolve().parents[3] / "data" / "phase3" / "dataset" / "adversarial"


def _rows() -> list[AgentPayIRRecord]:
    return [
        AgentPayIRRecord.model_validate_json(line)
        for line in (ADV / "adversarial_dataset.jsonl").read_text().splitlines()
        if line.strip()
    ]


def test_adversarial_file_valid_and_manifest_bound() -> None:
    manifest = json.loads((ADV / "manifest.json").read_text())
    rows = _rows()
    assert len(rows) >= 30
    assert manifest["records"] == len(rows)
    assert (
        manifest["sha256"]
        == hashlib.sha256((ADV / "adversarial_dataset.jsonl").read_bytes()).hexdigest()
    )


def test_injection_family_present_with_contradictions() -> None:
    inj = [r for r in _rows() if r.family == "injection_resistance"]
    assert len(inj) >= 10
    assert any(r.label == "contradiction" for r in inj)
    assert any(r.label == "entailment" for r in inj)


def test_safe_lookalikes_cover_both_directions() -> None:
    safe = [r for r in _rows() if r.family == "safe_lookalike"]
    assert len(safe) >= 2
    # The family deliberately mixes: benign-looking-but-fine cases AND
    # scary-sounding cases whose truth is a violation.
    assert {r.label for r in safe} <= {"entailment", "neutral", "contradiction"}


def test_all_hard_difficulty_template_truth() -> None:
    for r in _rows():
        assert r.difficulty == "hard"
        assert r.label_source == "template_truth"
