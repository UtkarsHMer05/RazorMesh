#!/usr/bin/env python3
"""Phase-3 dataset / model / runtime semantic audit (read-only).

Produces:
  docs/PHASE3_DATASET_RUNTIME_AUDIT.md   human-readable audit
  docs/PHASE3_DATASET_RUNTIME_AUDIT.json machine-readable evidence

This script NEVER mutates a dataset, a checkpoint or a policy manifest. It
recomputes every reported number from bytes on disk so that documentation
truth and runtime truth cannot drift again.

Usage:
  services/api/.venv/bin/python scripts/rzp_audit_phase3_dataset.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

DOCS = REPO_ROOT / "docs"
FROZEN = REPO_ROOT / "data" / "phase3" / "dataset" / "frozen_v1"
TRAINING = REPO_ROOT / "training" / "phase3"
OOD_PATH = REPO_ROOT / "data" / "phase3" / "eval" / "untouched_ood" / "ood_adversarial_129.jsonl"
GOLD_DECISIONS = REPO_ROOT / "data" / "phase3" / "gold" / "gold_decisions.json"
GOLD_FROZEN = REPO_ROOT / "data" / "phase3" / "gold" / "gold_frozen.json"
GOLD_MANIFEST = REPO_ROOT / "data" / "phase3" / "gold" / "manifest.json"
ARTIFACT = REPO_ROOT / "artifacts" / "models" / "incoming" / "phase3-finetuned"
POLICY = REPO_ROOT / "data" / "phase3" / "policy" / "semantic_thresholds.json"

VALID_LABELS = ("contradiction", "entailment", "neutral")

# The canonical AgentPay-IR contract (see the Phase-3 correction brief, S2/S3).
REQUIRED_FIELDS = (
    "record_id",
    "premise",
    "hypothesis",
    "label",
    "family",
    "content_sha256",
)
CONTRACT_FIELDS_V02 = (
    "schema_version",
    "subfamily",
    "authorization_field",
    "evidence_field",
    "generator_parent_id",
    "template_family_id",
    "source",
    "safe_or_attack",
    "split_group",
)

# Markers that prove the human authorization prose was folded INTO the premise.
AUTH_IN_PREMISE_MARKERS = (
    "session context — human request:",
    "session context - human request:",
    "human request:",
    "human instruction:",
    "buyer stated:",
    "authorized at checkout:",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def norm_text(text: str) -> str:
    """Whitespace/punctuation-insensitive comparison key for near-duplicate work."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def classify_orientation(row: dict[str, Any]) -> str:
    """Return canonical | authorization_in_premise | unclassified.

    CANONICAL: premise carries ONLY current sanitized commerce evidence and the
    hypothesis carries the normalized human authorization constraint.

    AUTHORIZATION_IN_PREMISE: the human authorization prose is embedded inside
    the premise, so the pair no longer has the runtime's evidence-vs-constraint
    shape. This is the train/serve skew this audit exists to find.
    """
    premise = str(row.get("premise", ""))
    lowered = premise.lower()
    if any(marker in lowered for marker in AUTH_IN_PREMISE_MARKERS):
        return "authorization_in_premise"
    if premise.strip():
        return "canonical"
    return "unclassified"


def dist(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(r.get(key)) for r in rows).items()))


def audit_dataset(path: Path, *, purpose: str, role: str) -> dict[str, Any]:
    rows = load_jsonl(path)
    orientations = Counter(classify_orientation(r) for r in rows)
    missing_required = sorted(
        {
            f
            for row in rows
            for f in REQUIRED_FIELDS
            if row.get(f) in (None, "")
        }
    )
    present_contract = [f for f in CONTRACT_FIELDS_V02 if any(f in r for r in rows)]
    absent_contract = [f for f in CONTRACT_FIELDS_V02 if not any(f in r for r in rows)]
    bad_labels = sorted({str(r.get("label")) for r in rows} - set(VALID_LABELS))
    split_mismatch = sorted({str(r.get("split")) for r in rows} - {role}) if role != "mixed" else []
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "exists": path.exists(),
        "purpose": purpose,
        "rows": len(rows),
        "sha256": sha256_file(path) if path.exists() else None,
        "label_distribution": dist(rows, "label"),
        "family_distribution": dist(rows, "family"),
        "difficulty_distribution": dist(rows, "difficulty"),
        "label_source_distribution": dist(rows, "label_source"),
        "orientation_distribution": dict(sorted(orientations.items())),
        "canonical_orientation_fraction": (
            round(orientations.get("canonical", 0) / len(rows), 4) if rows else None
        ),
        "missing_required_fields": missing_required,
        "contract_v02_fields_present": present_contract,
        "contract_v02_fields_absent": absent_contract,
        "invalid_labels": bad_labels,
        "split_field_mismatches": split_mismatch,
    }


def keys_for(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Build several independent identity views over one split."""
    out: dict[str, dict[str, str]] = {
        "record_id": {},
        "content_sha256": {},
        "pair_normalized": {},
        "template": {},
        "source_case": {},
    }
    for row in rows:
        rid = str(row.get("record_id", ""))
        out["record_id"][rid] = rid
        csum = str(row.get("content_sha256", ""))
        if csum:
            out["content_sha256"][csum] = rid
        pair = norm_text(str(row.get("premise", ""))) + "|" + norm_text(str(row.get("hypothesis", "")))
        out["pair_normalized"][hashlib.sha256(pair.encode()).hexdigest()] = rid
        prov = row.get("provenance") or {}
        if isinstance(prov, dict):
            tmpl = prov.get("template_id")
            case = prov.get("source_case_id")
            if tmpl:
                out["template"][str(tmpl)] = rid
            if case:
                out["source_case"][str(case)] = rid
    return out


def leakage_matrix(sets: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Pairwise overlap per identity view. Group views prove parent leakage."""
    views = {name: keys_for(rows) for name, rows in sets.items()}
    names = sorted(views)
    findings: dict[str, dict[str, Any]] = {}
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            per_view: dict[str, int] = {}
            sample: dict[str, list[str]] = {}
            for view in views[a]:
                shared = sorted(set(views[a][view]) & set(views[b][view]))
                per_view[view] = len(shared)
                if shared:
                    sample[view] = [views[a][view][k] for k in shared[:5]]
            findings[f"{a}::{b}"] = {"overlap_counts": per_view, "sample_record_ids": sample}
    return findings


def internal_duplicates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    id_counts = Counter(str(r.get("record_id")) for r in rows)
    pair_counts = Counter(
        norm_text(str(r.get("premise", ""))) + "|" + norm_text(str(r.get("hypothesis", "")))
        for r in rows
    )
    return {
        "duplicate_record_ids": sorted(k for k, v in id_counts.items() if v > 1),
        "duplicate_normalized_pairs": sum(1 for v in pair_counts.values() if v > 1),
    }


def gold_role_analysis() -> dict[str, Any]:
    """Where did each human-reviewed card actually land, and did it influence training?

    This is the section that fixes the "320 gold examples were held out" claim.
    """
    decisions_raw: dict[str, Any] = json.loads(GOLD_DECISIONS.read_text())
    frozen_rows = {
        split: load_jsonl(FROZEN / f"{split}.jsonl") for split in ("train", "val", "test")
    }
    index = {
        str(row["record_id"]): (split, row) for split, rows in frozen_rows.items() for row in rows
    }
    by_split: Counter[str] = Counter()
    agreement: Counter[str] = Counter()
    disagreements: list[dict[str, str]] = []
    excluded: Counter[str] = Counter()
    for rid, entry in decisions_raw.items():
        label = entry.get("label") if isinstance(entry, dict) else entry
        if str(label).upper() in {"INVALID", "UNLABELED", "EXCLUDE", "SKIP"}:
            excluded[str(label)] += 1
            continue
        where = index.get(rid)
        if where is None:
            by_split["not_in_frozen_dataset"] += 1
            continue
        split, row = where
        by_split[split] += 1
        if row.get("label") == label:
            agreement["matches_frozen_label"] += 1
        else:
            agreement["differs_from_frozen_label"] += 1
            disagreements.append(
                {"record_id": rid, "split": split, "frozen": str(row.get("label")), "human": str(label)}
            )
    return {
        "gold_decision_files": {
            "gold_decisions.json": sha256_file(GOLD_DECISIONS),
            "gold_frozen.json": sha256_file(GOLD_FROZEN),
            "manifest.json": sha256_file(GOLD_MANIFEST),
        },
        "total_reviewed_entries": len(decisions_raw),
        "excluded_entries": dict(excluded),
        "valid_by_frozen_split": dict(sorted(by_split.items())),
        "label_agreement_vs_frozen": dict(sorted(agreement.items())),
        "disagreements": disagreements,
        "honest_terminology": {
            "human_reviewed_supervised": by_split["train"],
            "human_reviewed_validation_influenced_selection": by_split["val"],
            "human_reviewed_test_previously_examined": by_split["test"],
            "human_reviewed_blind_heldout": 0,
            "note": (
                "No subset of the reviewed cards is a blind holdout: the val cards "
                "drove checkpoint selection and threshold calibration, and the test "
                "cards were already inspected in earlier milestones. Only a NEW "
                "human-reviewed set, collected after this correction freezes, may be "
                "called human-held-out."
            ),
        },
    }


def artifact_audit() -> dict[str, Any]:
    files: dict[str, Any] = {}
    if ARTIFACT.exists():
        for path in sorted(ARTIFACT.iterdir()):
            if path.is_file():
                files[path.name] = {
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
    config: dict[str, Any] = {}
    label_map: dict[str, Any] = {}
    base_model = None
    metrics: dict[str, Any] = {}
    if (ARTIFACT / "config.json").exists():
        config = json.loads((ARTIFACT / "config.json").read_text())
    if (ARTIFACT / "label_map.json").exists():
        label_map = json.loads((ARTIFACT / "label_map.json").read_text())
    if (ARTIFACT / "base_model.txt").exists():
        base_model = (ARTIFACT / "base_model.txt").read_text().strip()
    if (ARTIFACT / "metrics.json").exists():
        metrics = json.loads((ARTIFACT / "metrics.json").read_text())
    id2label = {str(k): v for k, v in (config.get("id2label") or {}).items()}
    consistency = {
        "label_map_matches_config_id2label": label_map == id2label,
        "config_architectures": config.get("architectures"),
        "config_model_type": config.get("model_type"),
        "config_num_labels": config.get("num_labels", len(id2label) if id2label else None),
        "transformers_version_in_config": config.get("transformers_version"),
        "declared_base_model": base_model,
    }
    return {
        "artifact_dir": str(ARTIFACT.relative_to(REPO_ROOT)),
        "exists": ARTIFACT.exists(),
        "files": files,
        "label_map": label_map,
        "config_id2label": id2label,
        "consistency": consistency,
        "reported_training_metrics": metrics,
        "model_manifest_present": (ARTIFACT / "model_manifest.json").exists(),
    }


def policy_audit() -> dict[str, Any]:
    manifest = json.loads(POLICY.read_text())
    selected = manifest.get("selected", {})
    return {
        "path": str(POLICY.relative_to(REPO_ROOT)),
        "sha256": sha256_file(POLICY),
        "policy_version": manifest.get("policy_version"),
        "model": manifest.get("model"),
        "base_model": manifest.get("base_model"),
        "label_map": manifest.get("label_map"),
        "tau_block": selected.get("tau_block"),
        "tau_entail": selected.get("tau_entail"),
        "calibrated_on": manifest.get("calibrated_on"),
        "rows_used": manifest.get("rows_used"),
        "gold_validation_status": manifest.get("gold_validation_status"),
        "heldout_claim": manifest.get("validation_on_human_gold_heldout"),
    }


def runtime_wiring_audit() -> dict[str, Any]:
    """Prove from source which verifier the running server actually instantiates."""
    src_root = REPO_ROOT / "services" / "api" / "src" / "razormesh_api"
    importers: dict[str, list[int]] = {}
    for path in sorted(src_root.rglob("*.py")):
        try:
            lines = path.read_text().splitlines()
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(lines, start=1):
            if "DeterministicKeywordVerifier(" in line or "DebertaNLISemanticVerifier(" in line:
                key = f"{path.relative_to(REPO_ROOT)}"
                importers.setdefault(key, [])
                if "DeterministicKeywordVerifier(" in line:
                    importers[key].append(n)
    settings = (src_root / "settings.py").read_text()
    return {
        "keyword_verifier_instantiations": importers,
        "deberta_instantiated_in_server_source": any(
            "DebertaNLISemanticVerifier(" in p for p in importers
        ),
        "semantic_backend_setting_declared": "semantic_verifier_backend" in settings.lower(),
        "semantic_model_path_setting_declared": "semantic_model_path" in settings.lower(),
    }


def build_report() -> dict[str, Any]:
    datasets = {
        "training_train": audit_dataset(
            TRAINING / "train.jsonl",
            purpose="bundle copy actually fed to the fine-tune job",
            role="train",
        ),
        "training_val": audit_dataset(
            TRAINING / "val.jsonl",
            purpose="bundle copy used for checkpoint selection",
            role="val",
        ),
        "frozen_train": audit_dataset(
            FROZEN / "train.jsonl", purpose="gradient updates", role="train"
        ),
        "frozen_val": audit_dataset(
            FROZEN / "val.jsonl",
            purpose="checkpoint selection + threshold calibration",
            role="val",
        ),
        "frozen_test": audit_dataset(
            FROZEN / "test.jsonl", purpose="previously examined evaluation", role="test"
        ),
        "ood": audit_dataset(
            OOD_PATH, purpose="out-of-distribution adversarial evaluation", role="mixed"
        ),
    }
    sets = {
        "frozen_train": load_jsonl(FROZEN / "train.jsonl"),
        "frozen_val": load_jsonl(FROZEN / "val.jsonl"),
        "frozen_test": load_jsonl(FROZEN / "test.jsonl"),
        "ood": load_jsonl(OOD_PATH),
    }
    bundle_identical = {
        "train": (TRAINING / "train.jsonl").read_bytes() == (FROZEN / "train.jsonl").read_bytes(),
        "val": (TRAINING / "val.jsonl").read_bytes() == (FROZEN / "val.jsonl").read_bytes(),
    }
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "repository": str(REPO_ROOT),
        "datasets": datasets,
        "training_bundle_identical_to_frozen": bundle_identical,
        "internal_duplicates": {
            name: internal_duplicates(rows) for name, rows in sets.items()
        },
        "leakage_matrix": leakage_matrix(sets),
        "gold": gold_role_analysis(),
        "artifact": artifact_audit(),
        "policy": policy_audit(),
        "runtime_wiring": runtime_wiring_audit(),
    }


def render_markdown(report: dict[str, Any]) -> str:
    d = report["datasets"]
    out: list[str] = []
    add = out.append
    add("# Phase-3 dataset / model / runtime semantic audit")
    add("")
    add(f"Generated: `{report['generated_at_utc']}` by `scripts/rzp_audit_phase3_dataset.py`.")
    add("")
    add("Read-only. Every number below is recomputed from bytes on disk.")
    add("")
    add("## 1. Datasets on disk")
    add("")
    add("| dataset | rows | SHA-256 | purpose |")
    add("|---|---:|---|---|")
    for key, info in d.items():
        add(
            f"| `{info['path']}` | {info['rows']} | `{(info['sha256'] or '')[:16]}…` | {info['purpose']} |"
        )
    add("")
    add("## 2. Label and family distribution")
    add("")
    for key, info in d.items():
        add(f"### `{info['path']}`")
        add("")
        add(f"- labels: `{json.dumps(info['label_distribution'])}`")
        add(f"- label source: `{json.dumps(info['label_source_distribution'])}`")
        add(f"- difficulty: `{json.dumps(info['difficulty_distribution'])}`")
        add(f"- families ({len(info['family_distribution'])}): `{json.dumps(info['family_distribution'])}`")
        add("")
    add("## 3. NLI orientation contract")
    add("")
    add(
        "CANONICAL: `premise` = current sanitized commerce evidence only; "
        "`hypothesis` = normalized human authorization constraint."
    )
    add("")
    add("| dataset | canonical | authorization folded into premise | canonical fraction |")
    add("|---|---:|---:|---:|")
    for info in d.values():
        o = info["orientation_distribution"]
        add(
            f"| `{info['path']}` | {o.get('canonical', 0)} | "
            f"{o.get('authorization_in_premise', 0)} | {info['canonical_orientation_fraction']} |"
        )
    add("")
    add("## 4. AgentPay-IR field contract")
    add("")
    for info in d.values():
        add(f"- `{info['path']}`: missing required `{info['missing_required_fields']}`; "
            f"v0.2 fields absent `{info['contract_v02_fields_absent']}`")
    add("")
    add("## 5. Split isolation / leakage")
    add("")
    add("Training bundle byte-identical to frozen: "
        f"`{json.dumps(report['training_bundle_identical_to_frozen'])}`")
    add("")
    add("| pair | record_id | content_sha256 | normalized pair | template_id | source_case_id |")
    add("|---|---:|---:|---:|---:|---:|")
    for pair, res in report["leakage_matrix"].items():
        c = res["overlap_counts"]
        add(
            f"| `{pair}` | {c.get('record_id', 0)} | {c.get('content_sha256', 0)} | "
            f"{c.get('pair_normalized', 0)} | {c.get('template', 0)} | {c.get('source_case', 0)} |"
        )
    add("")
    add("## 6. Human gold: honest split roles")
    add("")
    gold = report["gold"]
    add(f"- reviewed entries: {gold['total_reviewed_entries']}")
    add(f"- by frozen split: `{json.dumps(gold['valid_by_frozen_split'])}`")
    add(f"- human label vs frozen label: `{json.dumps(gold['label_agreement_vs_frozen'])}`")
    add(f"- disagreements: {len(gold['disagreements'])}")
    add("")
    add("```json")
    add(json.dumps(gold["honest_terminology"], indent=2))
    add("```")
    add("")
    add("## 7. Fine-tuned artifact")
    add("")
    art = report["artifact"]
    add(f"- directory: `{art['artifact_dir']}` (exists: {art['exists']})")
    add(f"- `model_manifest.json` present: {art['model_manifest_present']}")
    add("")
    add("| file | bytes | SHA-256 |")
    add("|---|---:|---|")
    for name, info in art["files"].items():
        add(f"| `{name}` | {info['bytes']} | `{info['sha256'][:16]}…` |")
    add("")
    add("```json")
    add(json.dumps(art["consistency"], indent=2))
    add("```")
    add("")
    add("## 8. Frozen threshold policy")
    add("")
    add("```json")
    add(json.dumps(report["policy"], indent=2))
    add("```")
    add("")
    add("## 9. Runtime wiring as found")
    add("")
    add("```json")
    add(json.dumps(report["runtime_wiring"], indent=2))
    add("```")
    add("")
    return "\n".join(out)


def main() -> int:
    report = build_report()
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "PHASE3_DATASET_RUNTIME_AUDIT.json").write_text(json.dumps(report, indent=2) + "\n")
    (DOCS / "PHASE3_DATASET_RUNTIME_AUDIT.md").write_text(render_markdown(report) + "\n")
    print(json.dumps({k: report[k] for k in ("datasets", "leakage_matrix", "runtime_wiring")}, indent=2)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
