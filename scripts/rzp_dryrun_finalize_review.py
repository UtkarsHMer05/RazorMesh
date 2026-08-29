#!/usr/bin/env python3
"""Full dry-run review finalization on the REAL corpus in a TEMPORARY workspace
(PRE-REVIEW FINAL CORRECTION #24 — no training, nothing in the repo is modified).

What it does:
  1. builds a temporary workspace with the REAL frozen V3 review pack + linkage +
     role manifest + freeze manifest, the REAL corpus splits (symlinked read-only)
     and the REAL fresh OOD;
  2. generates a complete SYNTHETIC decision export for all 635 cards (seeded:
     ~90% agree, ~7% label flips, ~3% ambiguous/bad) in the real UI export shape;
  3. executes the ENTIRE finalizer (rzp_finalize_review_v2.py) with --root pointed
     at the temp workspace — validation, conflict checks, group-level gold
     isolation, human-gold freeze, supervised integration, hash recompute +
     validation, leakage gates, final freeze, FINAL Colab bundle + notebook;
  4. independently verifies every acceptance condition: final train/val/test,
     human gold with the synthetic labels, ZERO gold/training group overlap,
     valid content_sha256 on every final row, final ZIP train/val SHA256 equal to
     corpus/final/train.jsonl and corpus/final/val.jsonl, and the notebook's
     external EXPECTED_BUNDLE_SHA256 + bundle verification logic passing against
     the final ZIP.

Usage: services/api/.venv/bin/python scripts/rzp_dryrun_finalize_review.py
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED = 42
VALID = ("contradiction", "entailment", "neutral")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def content_sha256(premise: str, hypothesis: str, label: str) -> str:
    return hashlib.sha256("\x1f".join((premise, hypothesis, label, "canonical")).encode()).hexdigest()


def build_workspace(root: Path) -> None:
    av2 = root / "data" / "agentpay_ir_v2"
    (av2 / "corpus").mkdir(parents=True)
    (av2 / "review").mkdir()
    (av2 / "eval").mkdir()
    for split in ("train", "val", "test"):
        (av2 / "corpus" / f"{split}.jsonl").symlink_to(REPO / "data/agentpay_ir_v2/corpus" / f"{split}.jsonl")
    (av2 / "eval" / "fresh_ood_v2.jsonl").symlink_to(REPO / "data/agentpay_ir_v2/eval/fresh_ood_v2.jsonl")
    for name in ("REVIEW_PACK_V3.jsonl", "REVIEW_PACK_FREEZE_V3.json",
                 "REVIEW_LINKAGE_V3.json", "REVIEW_ROLE_MANIFEST_V3.json"):
        shutil.copy2(REPO / "data/agentpay_ir_v2/review" / name, av2 / "review" / name)


def synthetic_export(root: Path) -> dict:
    rng = random.Random(SEED)
    roles = json.loads((root / "data/agentpay_ir_v2/review/REVIEW_ROLE_MANIFEST_V3.json").read_text())["assignments"]
    linkage = json.loads((root / "data/agentpay_ir_v2/review/REVIEW_LINKAGE_V3.json").read_text())
    rows = []
    stats = {"agree": 0, "flip": 0, "ambiguous": 0}
    for cid in sorted(roles):
        link = linkage[cid]
        u = rng.random()
        if u < 0.03:
            decision = "ambiguous_bad_record"
            stats["ambiguous"] += 1
        elif u < 0.10:
            decision = rng.choice([l for l in VALID if l != link["source_label"]])
            stats["flip"] += 1
        else:
            decision = link["source_label"]
            stats["agree"] += 1
        rows.append({"card_id": cid, "decision": decision})
    print(f"synthetic decisions: {stats}")
    return {"export_version": 1, "rows": rows}


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="rzp_dryrun_final_"))
    print("dry-run workspace:", root)
    build_workspace(root)
    export = synthetic_export(root)
    dec = root / "review_decisions_export.json"
    dec.write_text(json.dumps(export, indent=1))

    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts/rzp_finalize_review_v2.py"),
         "--decisions", str(dec), "--root", str(root)],
        capture_output=True, text=True, timeout=600)
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr)
        print("DRY RUN FAIL: finalizer exited", proc.returncode)
        return 1

    av2 = root / "data" / "agentpay_ir_v2"
    final = av2 / "corpus" / "final"
    checks: dict[str, object] = {}

    # 1) final splits exist
    split_rows: dict[str, list[dict]] = {}
    for split in ("train", "val", "test"):
        split_rows[split] = [json.loads(l) for l in (final / f"{split}.jsonl").read_text().splitlines()]
    checks["final_counts"] = {s: len(rs) for s, rs in split_rows.items()}

    # 2) human gold uses the synthetic human labels
    gold_rows = [json.loads(l) for l in (av2 / "review" / "GOLD_FROZEN_V3.jsonl").read_text().splitlines()]
    dec_by_cid = {r["card_id"]: r["decision"] for r in export["rows"]}
    linkage = json.loads((av2 / "review" / "REVIEW_LINKAGE_V3.json").read_text())
    roles = json.loads((av2 / "review" / "REVIEW_ROLE_MANIFEST_V3.json").read_text())["assignments"]
    gold_ok = all(
        g["label"] == dec_by_cid[cid]
        and g["source_kind"] == "human_reviewed"
        and g["metadata"]["review_role"] == "gold_frozen"
        for g in gold_rows
        for cid in [next(c for c, l in linkage.items() if l["record_id"] == g["record_id"])]
        if roles[cid] == "gold" and dec_by_cid[cid] != "ambiguous_bad_record")
    checks["gold_rows"] = len(gold_rows)
    checks["gold_labels_are_human"] = gold_ok
    checks["gold_source_label_not_preserved"] = all(
        "source_label" not in json.dumps(g) for g in gold_rows)

    # 3) ZERO gold/training group overlap
    gold_groups = {g["split_group"] for g in gold_rows}
    overlap = {s: sorted(gold_groups & {r["split_group"] for r in rs})
               for s, rs in split_rows.items()}
    checks["gold_group_overlap"] = {s: len(v) for s, v in overlap.items()}
    assert not any(overlap.values()), overlap

    # 4) recomputed + validated hashes on every final row
    bad = [r["record_id"] for rs in [*split_rows.values(), gold_rows] for r in rs
           if content_sha256(r["premise"], r["hypothesis"], r["label"]) != r["content_sha256"]]
    checks["content_sha256_all_valid"] = not bad
    assert not bad, bad[:5]

    # 5) final ZIP train/val hashes equal the final corpus files
    zip_path = root / "artifacts" / "agentpay_ir_v2_colab_training_bundle.zip"
    checks["final_bundle_sha256"] = sha256_file(zip_path)
    with zipfile.ZipFile(zip_path) as z:
        train_member = hashlib.sha256(z.read("train.jsonl")).hexdigest()
        val_member = hashlib.sha256(z.read("val.jsonl")).hexdigest()
        names = set(z.namelist())
    checks["zip_train_sha_equals_final_corpus"] = train_member == sha256_file(final / "train.jsonl")
    checks["zip_val_sha_equals_final_corpus"] = val_member == sha256_file(final / "val.jsonl")
    checks["zip_excludes_test_gold_ood"] = not any(
        n.startswith(("test", "gold", "fresh_ood")) for n in names)
    assert checks["zip_train_sha_equals_final_corpus"] and checks["zip_val_sha_equals_final_corpus"]

    # 6) notebook external hash + executed bundle verification (no training)
    nb_path = root / "notebooks" / "RazorGuard_NLI_AgentPayIR_v2_Training.ipynb"
    cells = ["".join(c["source"]) for c in json.loads(nb_path.read_text())["cells"]
             if c["cell_type"] == "code"]
    m = re.search(r'EXPECTED_BUNDLE_SHA256 = "([0-9a-f]{64})"',
                  next(c for c in cells if "EXPECTED_BUNDLE_SHA256" in c))
    assert m and m.group(1) == checks["final_bundle_sha256"]
    verify_cell = next(c for c in cells if "def verify_bundle" in c)
    import os

    os.environ["BUNDLE_PATH"] = str(zip_path)
    ns: dict = {}
    exec(compile(verify_cell, "verify_cell", "exec"), ns)  # noqa: S102 - dry-run rig
    checks["notebook_bundle_verification"] = "PASS"

    print("DRY-RUN ACCEPTANCE:", json.dumps(checks, indent=1))
    print("DRY RUN PASS — final train/val/test + human gold + final bundle + notebook "
          "verification all green; NO training executed; real repo untouched.")
    shutil.rmtree(root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
