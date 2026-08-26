#!/usr/bin/env python3
"""P3-M27: freeze AgentPay-IR v1 — combined pools + splits + manifests.

Snapshot semantics: whatever exists in seed/adversarial/candidates at freeze
time becomes frozen_v1. The candidate generator keeps running independently;
a LATER refresh produces frozen_v2 via the same script with --out frozen_v2.

Outputs data/phase3/dataset/frozen_v1/:
  train.jsonl / val.jsonl / test.jsonl   (split-assigned records)
  frozen_manifest.json                   (counts/hashes/leakage/PENDING marker)
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

from razormesh_api.agentpay_ir import AgentPayIRRecord, make_record
from razormesh_api.dataset_splits import (
    assign_splits,
    leakage_report,
)

DATA = REPO_ROOT / "data" / "phase3"
SPLITS = ("train", "val", "test")


def _load_full(path: Path) -> list[AgentPayIRRecord]:
    if not path.exists():
        return []
    out: list[AgentPayIRRecord] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        if "label_source" in raw:
            out.append(AgentPayIRRecord.model_validate(raw))
            continue
        prov = {
            "generator": "qwen3.8-max-free@tokenrouter",
            "created_at_utc": raw.get("created_at_utc")
            or datetime.now(UTC).isoformat(),
            "generator_request_id": raw.get("request_key", "")[:64],
            "source_case_id": raw.get("source_case_id")
            or ("cand_" + raw.get("request_key", "")[:20]),
        }
        out.append(make_record_from_parts(raw, prov))
    return out


def make_record_from_parts(raw: dict, prov: dict) -> AgentPayIRRecord:

    return make_record(
        record_id=raw["record_id"],
        premise=raw["premise"],
        hypothesis=raw["hypothesis"],
        label=raw["label"],  # type: ignore[arg-type]
        label_source="qwen_provisional",  # compact rows are always provisional
        family=raw["family"],  # type: ignore[arg-type]
        difficulty=raw["difficulty"],  # type: ignore[arg-type]
        provenance=prov,  # type: ignore[arg-type]
    )


def main() -> int:
    out_dir = DATA / "dataset" / "frozen_v1"
    out_dir.mkdir(parents=True, exist_ok=True)

    pool: list[AgentPayIRRecord] = []
    sources: dict[str, int] = {}
    for name, rel in (
        ("seed", "dataset/seed/seed_dataset.jsonl"),
        ("adversarial", "dataset/adversarial/adversarial_dataset.jsonl"),
        (
            "candidates",
            "dataset/candidates/validation/validated_candidates.jsonl",
        ),
    ):
        rows = _load_full(DATA / rel)
        sources[name] = len(rows)
        pool.extend(rows)

    split_rows = assign_splits(pool)
    report = leakage_report(split_rows)
    if not report.passed:
        print("LEAKAGE DETECTED — refusing to freeze:", report.leaked_groups)
        return 4

    files: dict[str, str] = {}
    for split in SPLITS:
        rows = [r for r in split_rows if r.split == split]
        body = (
            "\n".join(
                r.model_dump_json() for r in sorted(rows, key=lambda x: x.record_id)
            )
            + "\n"
        )
        p = out_dir / f"{split}.jsonl"
        p.write_text(body, encoding="utf-8")
        files[split] = hashlib.sha256(p.read_bytes()).hexdigest()

    manifest = {
        "format_version": "agentpay-ir-v0.1",
        "frozen_version": "v1",
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "sources": sources,
        "total_records": len(split_rows),
        "counts_by_split": dict(report.counts),
        "labels_by_split": report.labels_by_split,
        "leakage_passed": report.passed,
        "leaked_groups": list(report.leaked_groups),
        "file_sha256": files,
        "gold_validation_status": "PENDING_GOLD_VALIDATION",
        "note": "splits are whole-group; qwen_provisional rows await human gold review",
    }
    (out_dir / "frozen_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
