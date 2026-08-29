#!/usr/bin/env python3
"""Post-review ingestion + final AgentPay-IR v2 freeze (PVB correction #6).

Runs ONLY after the human completes the V2 review pack. Pipeline:
  1. validate the exported decisions JSON (values, unknown/duplicate/missing IDs)
  2. join to the PRE-FROZEN role manifest (hash re-verified)
  3. route ambiguous/bad rows OUT (excluded entirely)
  4. GOLD rows -> held out completely (never train/val; future external eval only)
  5. SUPERVISED rows -> human labels override corpus labels in the grouped
     train/val flow (group identity preserved)
  6. rerun ALL leakage checks (release-blocking)
  7. freeze final hashes
  8. rebuild the FINAL Colab training bundle (train+val only)

Usage:
  services/api/.venv/bin/python scripts/rzp_finalize_review_v2.py \
      --decisions data/agentpay_ir_v2/review/review_decisions_export.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "data" / "agentpay_ir_v2" / "corpus"
REVIEW = REPO / "data" / "agentpay_ir_v2" / "review"
ARTIFACTS = REPO / "artifacts"
VALID = {"contradiction", "entailment", "neutral", "ambiguous_bad_record"}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def norm(t: str) -> str:
    return re.sub(r"\W+", " ", t.lower()).strip()


def fail(msg: str) -> None:
    print(f"FINALIZE FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decisions", required=True)
    args = ap.parse_args()

    # ---- 0. role manifest hash must still match the frozen value ----
    freeze = json.loads((REVIEW / "REVIEW_PACK_FREEZE_V2.json").read_text())
    role_manifest = json.loads((REVIEW / "REVIEW_ROLE_MANIFEST_V2.json").read_text())
    recomputed = hashlib.sha256(
        json.dumps(role_manifest, sort_keys=True).encode()
    ).hexdigest()
    if recomputed != freeze["role_manifest_sha256"]:
        fail("role manifest hash changed since freeze")
    print("role manifest hash verified:", recomputed[:16], "…")

    # ---- 1. validate exported decisions ----
    exported = json.loads(Path(args.decisions).read_text())
    rows = exported.get("rows") if isinstance(exported, dict) else exported
    cards = [json.loads(l) for l in open(REVIEW / "REVIEW_PACK_V2.jsonl")]
    card_ids = {c["card_id"] for c in cards}
    seen: set[str] = set()
    decisions: dict[str, str] = {}
    errors: list[str] = []
    for r in rows:
        cid = r.get("card_id", "")
        if not re.fullmatch(r"rc_\d{4}", cid):
            errors.append(f"malformed card_id {cid!r}")
            continue
        if cid in seen:
            errors.append(f"duplicate card_id {cid}")
            continue
        seen.add(cid)
        if cid not in card_ids:
            errors.append(f"unknown card_id {cid} (not in frozen pack)")
            continue
        if r.get("decision") not in VALID:
            errors.append(f"invalid decision {r.get('decision')!r} for {cid}")
            continue
        decisions[cid] = r["decision"]
    if errors:
        fail("decision validation errors:\n  " + "\n  ".join(errors[:20]))
    missing = sorted(card_ids - set(decisions))
    if missing:
        fail(f"missing decisions for {len(missing)} cards, e.g. {missing[:5]} (all cards must be labeled)")
    linkage = json.loads((REVIEW / "REVIEW_LINKAGE_V2.json").read_text())
    print(f"validated {len(decisions)} decisions (complete pack)")

    # ---- 2-4. route by role; ambiguous out; gold separate ----
    roles = role_manifest["assignments"]
    ambiguous, gold_ids, supervised = [], [], {}
    for cid, dec in decisions.items():
        if dec == "ambiguous_bad_record":
            ambiguous.append(cid)
        elif roles[cid] == "gold":
            gold_ids.append(cid)
        else:
            supervised[cid] = dec
    print(f"routing: ambiguous/bad={len(ambiguous)} gold={len(gold_ids)} supervised={len(supervised)}")

    # ---- 5. apply supervised labels to corpus rows (grouped flow preserved) ----
    label_updates: dict[str, str] = {}
    bad_record_ids: set[str] = set()
    for cid in supervised:
        link = linkage[cid]
        label_updates[link["record_id"]] = supervised[cid]
    for cid in ambiguous:
        bad_record_ids.add(linkage[cid]["record_id"])
    gold_record_ids = [linkage[c]["record_id"] for c in gold_ids]

    final: dict[str, list[dict]] = {"train": [], "val": [], "test": []}
    stats = {"relabeled": 0, "label_confirmed": 0, "bad_removed": 0, "gold_excluded": 0}
    gold_rows: list[dict] = []
    for split in ("train", "val", "test"):
        for line in open(CORPUS / f"{split}.jsonl"):
            r = json.loads(line)
            rid = r["record_id"]
            if rid in bad_record_ids:
                stats["bad_removed"] += 1
                continue
            if rid in gold_record_ids:
                stats["gold_excluded"] += 1
                g = dict(r)
                g["metadata"] = {**r.get("metadata", {}), "review_role": "gold_frozen"}
                gold_rows.append(g)
                continue
            if rid in label_updates:
                human = label_updates[rid]
                if r["label"] == human:
                    stats["label_confirmed"] += 1
                else:
                    stats["relabeled"] += 1
                r = {**r, "label": human,
                     "source_kind": "human_reviewed",
                     "metadata": {**r.get("metadata", {}), "human_label_override": True}}
            final[split].append(r)
    # corpus rows that a supervised card matched must exist in exactly one split
    print("supervised integration:", stats)

    # ---- 6. leakage checks (release-blocking) ----
    groups = {s: {r["split_group"] for r in rows} for s, rows in final.items()}
    hashes = {s: {r["content_sha256"] for r in rows} for s, rows in final.items()}
    pairs = {s: {(norm(r["premise"]), norm(r["hypothesis"])) for r in rows} for s, rows in final.items()}
    names = ("train", "val", "test")
    leaks = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if groups[a] & groups[b]:
                leaks.append(f"group {a}x{b}")
            if hashes[a] & hashes[b]:
                leaks.append(f"hash {a}x{b}")
            if pairs[a] & pairs[b]:
                leaks.append(f"pair {a}x{b}")
    gold_hashes = {r["content_sha256"] for r in gold_rows}
    gold_groups = {r["split_group"] for r in gold_rows}
    for s in names:
        if gold_hashes & hashes[s]:
            leaks.append(f"gold hash in {s}")
        if gold_groups & groups[s]:
            leaks.append(f"gold group in {s}")
    ood_hashes = {json.loads(l)["content_sha256"] for l in open(REPO / "data/agentpay_ir_v2/eval/fresh_ood_v2.jsonl")}
    for s in names:
        if ood_hashes & hashes[s]:
            leaks.append(f"ood hash in {s}")
    if leaks:
        fail("leakage: " + ", ".join(leaks))
    print("LEAKAGE GATE: PASS (incl. gold separation and OOD deconfliction)")

    # ---- 7. freeze final hashes ----
    out_dir = CORPUS / "final"
    out_dir.mkdir(exist_ok=True)
    counts = {}
    for s in names:
        (out_dir / f"{s}.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in final[s]))
        counts[s] = len(final[s])
    gold_path = REVIEW / "GOLD_FROZEN_V2.jsonl"
    gold_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in gold_rows))
    frozen = {
        "counts": counts,
        "stats": stats,
        "files": {f: sha256_file(out_dir / f) for f in ("train.jsonl", "val.jsonl", "test.jsonl")},
        "gold_frozen_sha256": sha256_file(gold_path),
        "ambiguous_excluded": len(ambiguous),
    }
    (out_dir / "FINAL_FREEZE_MANIFEST.json").write_text(json.dumps(frozen, indent=2))
    print("final freeze:", json.dumps(counts), "| gold rows:", len(gold_rows))

    # ---- 8. rebuild FINAL Colab bundle (train+val only) ----
    stage = ARTIFACTS / "_bundle_stage"
    stage.mkdir(exist_ok=True)
    files = {
        "train.jsonl": out_dir / "train.jsonl",
        "val.jsonl": out_dir / "val.jsonl",
        "label_map.json": None,
        "train_config.json": None,
        "requirements-frozen.txt": None,
        "SCHEMA.md": REPO / "docs/agentpay_ir_v2/SCHEMA.md",
    }
    import zipfile
    for n, p in files.items():
        if p:
            (stage / n).write_bytes(p.read_bytes())
    # reuse config/label map/requirements from the pre-review bundle stage builder
    import subprocess
    subprocess.run([sys.executable, str(REPO / "scripts/rzp_build_colab_bundle_v2.py")], check=True,
                   capture_output=True)  # regenerates stage files deterministically
    bundle_manifest = json.loads((stage / "bundle_manifest.json").read_text())
    hashes = {n: sha256_file(stage / n) for n in
              ("train.jsonl", "val.jsonl", "label_map.json", "train_config.json", "requirements-frozen.txt", "SCHEMA.md")}
    bundle_manifest["files"] = hashes
    bundle_manifest["final_freeze"] = frozen
    bundle_manifest["bundle_role"] = "FINAL post-review training bundle (supervised labels integrated; gold/test/OOD excluded)"
    (stage / "bundle_manifest.json").write_text(json.dumps(bundle_manifest, indent=2))
    final_zip = ARTIFACTS / "agentpay_ir_v2_colab_training_bundle.zip"
    if final_zip.exists():
        final_zip.unlink()
    with zipfile.ZipFile(final_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for n in ("train.jsonl", "val.jsonl", "bundle_manifest.json", "label_map.json", "train_config.json", "requirements-frozen.txt", "SCHEMA.md"):
            z.write(stage / n, n)
    print("FINAL bundle:", final_zip, "| sha256:", sha256_file(final_zip))
    print("PRE-TRAINING FREEZE COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
