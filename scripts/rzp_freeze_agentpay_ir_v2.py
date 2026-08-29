#!/usr/bin/env python3
"""Freeze AgentPay-IR v2 artifacts (gates: leakage, review roles, OOD freeze).

- Leakage gate: zero shared split_group / identical / normalized-pair overlap
  across train/val/test (release-blocking).
- Review pack: 700 frozen candidates get HIDDEN review_role (supervised/gold)
  assigned deterministically BEFORE any human label exists. gold rows are never
  usable for training/selection/calibration.
- Fresh OOD v2: frozen IDs + hashes; inaccessible to training/selection.

Usage: services/api/.venv/bin/python scripts/rzp_freeze_agentpay_ir_v2.py
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "data" / "agentpay_ir_v2" / "corpus"
EVAL = REPO / "data" / "agentpay_ir_v2" / "eval"
DOCS = REPO / "docs" / "agentpay_ir_v2"
SEED = 42


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def norm_text(t: str) -> str:
    return re.sub(r"\W+", " ", t.lower()).strip()


def load(split: str) -> list[dict]:
    return [json.loads(l) for l in open(CORPUS / f"{split}.jsonl")]


def main() -> int:
    splits = {s: load(s) for s in ("train", "val", "test")}

    # ---- leakage gate (release-blocking) ----
    groups: dict[str, set[str]] = {s: {r["split_group"] for r in rows} for s, rows in splits.items()}
    group_overlaps = {
        f"{a}x{b}": len(groups[a] & groups[b])
        for i, a in enumerate(("train", "val", "test"))
        for b in ("train", "val", "test")[i + 1:]
    }
    pairs: dict[str, set[tuple[str, str, str]]] = {}
    norm_pairs: dict[str, set[tuple[str, str]]] = {}
    hashes: dict[str, set[str]] = {}
    for s, rows in splits.items():
        pairs[s] = {(r["premise"], r["hypothesis"], r["label"]) for r in rows}
        norm_pairs[s] = {(norm_text(r["premise"]), norm_text(r["hypothesis"])) for r in rows}
        hashes[s] = {r["content_sha256"] for r in rows}
    names = ("train", "val", "test")
    leaks = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if group_overlaps[f"{a}x{b}"]:
                leaks.append(f"group overlap {a}x{b}")
            if hashes[a] & hashes[b]:
                leaks.append(f"content_sha256 overlap {a}x{b}")
            if pairs[a] & pairs[b]:
                leaks.append(f"exact pair overlap {a}x{b}")
            if norm_pairs[a] & norm_pairs[b]:
                leaks.append(f"normalized pair overlap {a}x{b}")
    # OOD must not intersect any corpus split
    ood = [json.loads(l) for l in open(EVAL / "fresh_ood_v2.jsonl")]
    ood_hashes = {r["content_sha256"] for r in ood}
    ood_groups = {r["split_group"] for r in ood}
    if ood_hashes & (hashes["train"] | hashes["val"] | hashes["test"]):
        leaks.append("OOD content_sha256 overlap with corpus")
    if ood_groups & (groups["train"] | groups["val"] | groups["test"]):
        leaks.append("OOD split_group overlap with corpus")
    leakage_ok = not leaks
    print("LEAKAGE GATE:", "PASS" if leakage_ok else "FAIL", "| overlaps:", group_overlaps, "| leaks:", leaks)

    # ---- review roles (hidden; assigned before any human label) ----
    cands = [json.loads(l) for l in open(CORPUS / "review_candidates.jsonl")]
    rng = random.Random(SEED)
    roles = ["gold"] * 300 + ["supervised"] * (len(cands) - 300)
    rng.shuffle(roles)
    role_manifest = {
        "frozen_at": "2026-08-29T02:20:00+00:00",
        "seed": SEED,
        "n_candidates": len(cands),
        "n_gold": roles.count("gold"),
        "n_supervised": roles.count("supervised"),
        "assignments": {c["candidate_id"]: role for c, role in zip(cands, roles)},
    }
    # role manifest hash frozen; roles hidden from review UI payload
    (CORPUS / "review_role_manifest.json").write_text(json.dumps(role_manifest, indent=2))
    for c, role in zip(cands, roles):
        c["review_role"] = role  # present in the frozen pack but hidden by the review UI
    (CORPUS / "review_candidates_with_roles.jsonl").write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cands))
    print("review roles frozen: gold", roles.count("gold"), "/ supervised", roles.count("supervised"))

    # ---- freeze hashes ----
    files = ["train.jsonl", "val.jsonl", "test.jsonl", "review_candidates.jsonl",
             "review_candidates_with_roles.jsonl", "review_role_manifest.json"]
    frozen = {f: sha256_file(CORPUS / f) for f in files}
    frozen["fresh_ood_v2.jsonl"] = sha256_file(EVAL / "fresh_ood_v2.jsonl")
    (EVAL / "fresh_ood_v2_FROZEN.json").write_text(json.dumps({
        "frozen_at": "2026-08-29T02:20:00+00:00",
        "rows": len(ood),
        "sha256": frozen["fresh_ood_v2.jsonl"],
        "rule": "never used for training/validation/selection/calibration; historical 129-row OOD remains comparator-only",
    }, indent=2))
    (CORPUS / "FREEZE_MANIFEST.json").write_text(json.dumps(frozen, indent=2))
    print("freeze manifest written:", json.dumps(frozen, indent=1)[:400])

    # ---- label/family/class reports ----
    report = {}
    for s, rows in splits.items():
        report[s] = {
            "rows": len(rows),
            "labels": dict(Counter(r["label"] for r in rows)),
            "source_kinds": dict(Counter(r["source_kind"] for r in rows)),
            "families": len({r["family"] for r in rows}),
            "split_groups": len(groups[s]),
        }
    (CORPUS / "distribution_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=1))
    return 0 if leakage_ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
