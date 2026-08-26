#!/usr/bin/env python3
"""P3-M21: validate the full Qwen candidate pool and emit auditable outputs."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

from razormesh_api.dataset_quality import validate_candidate_jsonl

SOURCE = REPO_ROOT / "data" / "phase3" / "dataset" / "candidates" / "candidates.jsonl"
OUT_DIR = SOURCE.parent / "validation"
ACCEPTED = OUT_DIR / "validated_candidates.jsonl"
REJECTED = OUT_DIR / "rejected_candidates.jsonl"
WARNINGS = OUT_DIR / "validation_warnings.jsonl"
REPORT = OUT_DIR / "quality_report.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(body, encoding="utf-8")
    os.replace(temporary, path)


def _jsonl(rows: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)


def main() -> int:
    if not SOURCE.exists():
        print(f"candidate source missing: {SOURCE}", file=sys.stderr)
        return 2

    result = validate_candidate_jsonl(SOURCE.read_text(encoding="utf-8").splitlines())
    accepted_rows = [record.model_dump(mode="json") for record in result.accepted]
    rejected_rows = [
        {
            "line_number": item.line_number,
            "record_id": item.record_id,
            "reason_codes": list(item.reasons),
            "warning_codes": list(item.warnings),
        }
        for item in result.rejected
    ]
    warning_rows = [
        {"record_id": record_id, "warning_codes": list(warnings)}
        for record_id, warnings in sorted(result.warnings_by_record.items())
    ]

    _atomic_write(ACCEPTED, _jsonl(accepted_rows))
    _atomic_write(REJECTED, _jsonl(rejected_rows))
    _atomic_write(WARNINGS, _jsonl(warning_rows))

    accepted = result.accepted
    report = {
        "milestone": "P3-M21",
        "validator_version": "candidate-quality-v2",
        "validated_at_utc": datetime.now(UTC).isoformat(),
        "source": str(SOURCE.relative_to(REPO_ROOT)),
        "source_sha256": _sha256(SOURCE),
        "input_rows": result.input_rows,
        "accepted_rows": len(accepted),
        "rejected_rows": len(result.rejected),
        "acceptance_rate": (
            round(len(accepted) / result.input_rows, 6) if result.input_rows else 0.0
        ),
        "quality_gate_status": "PASS" if not result.rejected else "PASS_FILTERED",
        "rejection_reason_counts": result.reason_counts,
        "warning_record_count": len(result.warnings_by_record),
        "warning_reason_counts": result.warning_counts,
        "accepted_by_family": dict(sorted(Counter(r.family for r in accepted).items())),
        "accepted_by_label": dict(sorted(Counter(r.label for r in accepted).items())),
        "accepted_by_difficulty": dict(
            sorted(Counter(r.difficulty for r in accepted).items())
        ),
        "accepted_label_sources": dict(
            sorted(Counter(r.label_source for r in accepted).items())
        ),
        "accepted_sha256": _sha256(ACCEPTED),
        "rejected_sha256": _sha256(REJECTED),
        "warnings_sha256": _sha256(WARNINGS),
        "checks": [
            "json_and_agentpay_schema",
            "text_limits_and_control_characters",
            "complete_generation_provenance",
            "label_consistency_heuristics",
            "malformed_money",
            "payment_authority_misinformation",
            "duplicated_record_ids_and_content",
            "secret_like_values",
            "generation_artifacts",
        ],
    }
    _atomic_write(REPORT, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
