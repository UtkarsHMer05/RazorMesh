#!/usr/bin/env python3
"""Post-review ingestion + final AgentPay-IR v2 freeze (PVB correction #6 +
PRE-REVIEW FINAL CORRECTION #6-12).

Runs ONLY after the human completes the V3 review pack. Pipeline:
  1. verify the FROZEN role manifest under the ONE canonical hash definition
     (assignments-only sha256, stored exclusively in the freeze manifest);
  2. validate the exported decisions JSON (values, unknown/duplicate/missing
     card ids, rc2_* namespace);
  3. detect and REJECT conflicting human decisions (PRE-REVIEW FINAL
     CORRECTION #11): the same card_id, the same underlying record_id, or the
     same identical normalized (premise, hypothesis) pair decided two different
     ways. The V3 pack already eliminated duplicate records/pairs before
     review; these checks are the release-blocking failsafe. NOTE: different
     decisions on DIFFERENT records sharing a split_group are NOT conflicts —
     in this corpus one generator group legitimately carries records with
     different labels (same scenario family, different hypothesis constraints);
  3b. gold-adequacy guard (pre-label correction): STOP if the usable human-gold
     set falls below min(--min-gold-rows [default 250], 85% of the frozen gold
     allocation) because too many GOLD cards were marked ambiguous/bad — never
     silently continue with a tiny gold set; warn below 95%.
  4. route ambiguous/bad rows OUT (excluded entirely);
  5. GOLD isolation at GROUP level (#8): every corpus row whose split_group is
     a gold card's split_group is removed from train/val/test entirely; ONLY
     the independently human-labeled review card's own record becomes a gold
     evaluation row; gold-adequacy guard stops the run when the usable gold
     set is materially smaller than intended;
  5b. OPTIONAL (explicit --integrate-prompt-injection-augmentation): merge the
     PREPARED 96-row prompt-injection staging set into the FINAL TRAIN split
     only — never val/test/gold/OOD — and re-run all gates over the merged set;
  6. gold rows use the HUMAN decision as label (#9), provenance
     source_kind=human_reviewed, and never preserve the original source label
     as gold truth (only a boolean agreement flag);
  7. supervised rows: human labels override corpus labels in the grouped
     train/val flow (group identity preserved);
  8. every relabeled row gets content_sha256 RECOMPUTED per the canonical
     AgentPay-IR-v2 contract sha256(premise␟hypothesis␟label␟"canonical"), and
     EVERY final row's hash is re-validated (#10);
  9. rerun ALL leakage checks (release-blocking) incl. gold group/hash
     separation and OOD deconfliction;
 10. freeze final hashes;
 11. rebuild the FINAL Colab bundle via rzp_build_colab_bundle_v2.py with an
     explicit --corpus-dir (corpus/final) so the FINAL train/val land in the
     ZIP (#12), and regenerate the notebook with the FINAL zip's external
     EXPECTED_BUNDLE_SHA256 (#13).

Usage:
  services/api/.venv/bin/python scripts/rzp_finalize_review_v2.py \
      --decisions data/agentpay_ir_v2/review/review_decisions_export.json

Test/dry-run: pass --root to redirect the whole workspace (corpus, review,
artifacts, notebooks) at a temporary directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

VALID = {"contradiction", "entailment", "neutral", "ambiguous_bad_record"}
CARD_ID_RE = re.compile(r"^rc2_\d{4}$")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def norm(t: str) -> str:
    return re.sub(r"\W+", " ", t.lower()).strip()


def content_sha256(premise: str, hypothesis: str, label: str) -> str:
    """Canonical AgentPay-IR-v2 hashing contract (SCHEMA.md)."""
    return hashlib.sha256("\x1f".join((premise, hypothesis, label, "canonical")).encode()).hexdigest()


def fail(msg: str) -> None:
    print(f"FINALIZE FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decisions", required=True)
    ap.add_argument("--root", default=None,
                    help="workspace root (default: repo root; tests/dry-runs redirect this)")
    ap.add_argument("--min-gold-rows", type=int, default=250,
                    help="absolute floor for usable human-gold rows (never applied below "
                         "85%% of the frozen gold allocation, so small test workspaces pass)")
    ap.add_argument("--integrate-prompt-injection-augmentation", action="store_true",
                    help="training-only integration of the PREPARED 96-row prompt-injection "
                         "staging set into the FINAL TRAIN split (never val/test/gold/OOD); "
                         "all gates re-run over the merged set")
    ap.add_argument("--max-synthetic-fraction", type=float, default=0.10,
                    help="synthetic_adversarial share cap for the final train split "
                         "(the real corpus sits at <1%%; tiny test workspaces may raise it)")
    ap.add_argument("--skip-bundle", action="store_true")
    args = ap.parse_args()

    repo = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[1]
    corpus = repo / "data" / "agentpay_ir_v2" / "corpus"
    review = repo / "data" / "agentpay_ir_v2" / "review"
    artifacts = repo / "artifacts"

    # ---- 0. role manifest hash under the ONE canonical definition (#6) ----
    freeze = json.loads((review / "REVIEW_PACK_FREEZE_V3.json").read_text())
    role_manifest = json.loads((review / "REVIEW_ROLE_MANIFEST_V3.json").read_text())
    if "role_manifest_sha256" in role_manifest:
        fail("role manifest contains a self-referential hash field; canonical definition "
             "stores the assignments-only sha256 exclusively in the freeze manifest")
    assignments = role_manifest["assignments"]
    recomputed = hashlib.sha256(
        json.dumps(assignments, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if recomputed != freeze["role_manifest_sha256"]:
        fail("role manifest hash changed since freeze")
    print("role manifest hash verified:", recomputed[:16], "…")

    # ---- 1. validate exported decisions ----
    exported = json.loads(Path(args.decisions).read_text())
    rows = exported.get("rows") if isinstance(exported, dict) else exported
    cards = [json.loads(line) for line in (review / "REVIEW_PACK_V3.jsonl").read_text().splitlines() if line.strip()]
    card_ids = {c["card_id"] for c in cards}
    seen: dict[str, str] = {}
    decisions: dict[str, str] = {}
    errors: list[str] = []
    for r in rows:
        cid = r.get("card_id", "")
        if not CARD_ID_RE.match(cid):
            errors.append(f"malformed card_id {cid!r}")
            continue
        if cid in seen:
            errors.append(f"duplicate card_id {cid}")
            continue
        if cid not in card_ids:
            errors.append(f"unknown card_id {cid} (not in frozen pack)")
            continue
        if r.get("decision") not in VALID:
            errors.append(f"invalid decision {r.get('decision')!r} for {cid}")
            continue
        seen[cid] = r["decision"]
        decisions[cid] = r["decision"]
    if errors:
        fail("decision validation errors:\n  " + "\n  ".join(errors[:20]))
    missing = sorted(card_ids - set(decisions))
    if missing:
        fail(f"missing decisions for {len(missing)} cards, e.g. {missing[:5]} (all cards must be labeled)")
    linkage = json.loads((review / "REVIEW_LINKAGE_V3.json").read_text())
    print(f"validated {len(decisions)} decisions (complete pack)")

    # ---- 2. conflicting human decisions (#11, release-blocking) ----
    by_record: dict[str, dict[str, str]] = {}
    by_pair: dict[tuple[str, str], dict[str, str]] = {}
    corpus_text: dict[str, tuple[str, str]] = {}
    for split in ("train", "val", "test"):
        for line in (corpus / f"{split}.jsonl").read_text().splitlines():
            row = json.loads(line)
            corpus_text[row["record_id"]] = (row["premise"], row["hypothesis"])
    for cid, dec in decisions.items():
        rid = linkage[cid]["record_id"]
        by_record.setdefault(rid, {})[cid] = dec
        pair = tuple(norm(t)[:160] for t in corpus_text[rid])
        by_pair.setdefault(pair, {})[cid] = dec
    conflicts = []
    for rid, ds in by_record.items():
        if len(set(ds.values())) > 1:
            conflicts.append(f"record {rid}: {ds}")
    for pair, ds in by_pair.items():
        if len(set(ds.values())) > 1:
            conflicts.append(f"identical pair {pair[0][:60]!r}…: {ds}")
    if conflicts:
        fail("conflicting human decisions for the same underlying record/pair:\n  "
             + "\n  ".join(conflicts[:10]))
    print("conflict check: PASS (no record/pair decided two different ways)")

    # ---- 3-5. route by role; ambiguous out; GROUP-LEVEL gold isolation (#8) ----
    roles = assignments
    ambiguous, gold_ids, supervised = [], [], {}
    for cid, dec in decisions.items():
        if dec == "ambiguous_bad_record":
            ambiguous.append(cid)
        elif roles[cid] == "gold":
            gold_ids.append(cid)
        else:
            supervised[cid] = dec
    print(f"routing: ambiguous/bad={len(ambiguous)} gold={len(gold_ids)} supervised={len(supervised)}")

    label_updates: dict[str, str] = {}
    bad_record_ids: set[str] = set()
    for cid in supervised:
        label_updates[linkage[cid]["record_id"]] = supervised[cid]
    for cid in ambiguous:
        bad_record_ids.add(linkage[cid]["record_id"])
    gold_by_record = {linkage[c]["record_id"]: decisions[c] for c in gold_ids}
    gold_groups = {linkage[c]["split_group"] for c in gold_ids}

    final: dict[str, list[dict]] = {"train": [], "val": [], "test": []}
    stats = Counter()
    gold_rows: list[dict] = []
    for split in ("train", "val", "test"):
        for line in (corpus / f"{split}.jsonl").read_text().splitlines():
            r = json.loads(line)
            rid = r["record_id"]
            if rid in bad_record_ids:
                stats["bad_removed"] += 1
                continue
            if r["split_group"] in gold_groups:
                if rid in gold_by_record:
                    # the ONLY row kept from a gold group: the human-reviewed card itself
                    human = gold_by_record[rid]
                    g = dict(r)
                    g["label"] = human  # HUMAN decision is the gold truth (#9)
                    g["source_kind"] = "human_reviewed"
                    g["content_sha256"] = content_sha256(g["premise"], g["hypothesis"], human)
                    g["metadata"] = {**r.get("metadata", {}), "review_role": "gold_frozen",
                                     "human_label_override": True,
                                     "label_agrees_with_source": r["label"] == human}
                    gold_rows.append(g)
                    stats["gold_rows_kept"] += 1
                else:
                    stats["gold_group_excluded"] += 1  # same group, not itself reviewed
                continue
            if rid in label_updates:
                human = label_updates[rid]
                stats["label_confirmed" if r["label"] == human else "relabeled"] += 1
                r = {**r, "label": human, "source_kind": "human_reviewed",
                     "content_sha256": content_sha256(r["premise"], r["hypothesis"], human),
                     "metadata": {**r.get("metadata", {}), "human_label_override": True}}
            final[split].append(r)
    print("supervised integration:", dict(stats))

    # ---- gold-adequacy guard: never silently continue with a tiny usable
    # human-gold set (post-review). usable = gold-role cards the human labeled
    # non-ambiguous; the floor never exceeds 85% of the frozen gold allocation
    # so legitimately small test workspaces still pass.
    intended_gold = sum(1 for v in roles.values() if v == "gold")
    usable_gold = len(gold_rows)
    gold_floor = min(args.min_gold_rows, math.ceil(0.85 * intended_gold))
    if usable_gold < gold_floor:
        fail(f"human-gold set too small: {usable_gold} usable gold rows (floor "
             f"{gold_floor} = min(--min-gold-rows {args.min_gold_rows}, 85% of the "
             f"{intended_gold} frozen gold allocations)). Too many GOLD cards were "
             f"marked ambiguous/bad; re-review the flagged gold cards or lower "
             f"--min-gold-rows explicitly before finalizing.")
    if usable_gold < 0.95 * intended_gold:
        print(f"WARNING: usable human gold {usable_gold}/{intended_gold} "
              f"({intended_gold - usable_gold} gold cards marked ambiguous/bad) — "
              f"gold evaluation power is reduced; continuing.")
    print(f"gold adequacy: {usable_gold}/{intended_gold} usable (floor {gold_floor})")

    # ---- 5b. OPTIONAL prompt-injection augmentation (training-only, pre-label
    # correction #7): merges the PREPARED staging set into the FINAL TRAIN split
    # ONLY — never val/test/gold/OOD — and re-runs all gates over the merged set
    # (hash validation below + leakage section). Requires the explicit flag; the
    # default run is byte-identical to no integration.
    augmentation_info = None
    if args.integrate_prompt_injection_augmentation:
        aug_dir = repo / "data" / "agentpay_ir_v2" / "augmentation"
        aug_path = aug_dir / "prompt_injection_aug_v2.jsonl"
        manifest_path = aug_dir / "PROMPT_INJECTION_AUG_V2_MANIFEST.json"
        if not aug_path.exists() or not manifest_path.exists():
            fail("augmentation requested but staging files missing under " + str(aug_dir))
        aug_manifest = json.loads(manifest_path.read_text())
        aug_sha = sha256_file(aug_path)
        if aug_manifest.get("sha256") != aug_sha or aug_manifest.get("rows") != sum(
            1 for _ in aug_path.open()
        ):
            fail("augmentation staging manifest does not match its data (sha/rows)")
        aug_rows = [json.loads(line) for line in aug_path.read_text().splitlines() if line.strip()]
        existing_hashes = {r["content_sha256"] for rs in [*final.values(), gold_rows] for r in rs}
        existing_groups = {r["split_group"] for rs in [*final.values(), gold_rows] for r in rs}
        for r in aug_rows:
            for field in ("record_id", "schema_version", "source_dataset", "source_kind",
                          "source_license", "split_group", "generator_parent_id",
                          "template_family_id", "entity_family_id", "content_sha256"):
                if not r.get(field):
                    fail(f"augmentation row {r.get('record_id')} missing {field}")
            if r["schema_version"] != "agentpay-ir-v2":
                fail(f"augmentation row {r['record_id']} not v2-normalized")
            if r["content_sha256"] in existing_hashes or r["split_group"] in existing_groups:
                fail(f"augmentation row {r['record_id']} collides with final data")
            if content_sha256(r["premise"], r["hypothesis"], r["label"]) != r["content_sha256"]:
                fail(f"augmentation row {r['record_id']} fails the canonical hash contract")
        train_synth = sum(1 for r in [*final["train"], *aug_rows]
                          if r["source_kind"] == "synthetic_adversarial")
        train_total = len(final["train"]) + len(aug_rows)
        synth_fraction = train_synth / train_total
        if synth_fraction > args.max_synthetic_fraction:
            fail(f"prompt-injection augmentation would breach the synthetic-security "
                 f"cap: {synth_fraction:.4f} > {args.max_synthetic_fraction}")
        # provenance note stamped per merged row (metadata only; hash untouched)
        merged = []
        for r in aug_rows:
            merged.append({**r, "metadata": {**r.get("metadata", {}),
                             "integration": "integrated into TRAIN by finalizer "
                                            "(explicit human decision)"}})
        final["train"].extend(merged)
        augmentation_info = {"rows": len(merged), "sha256": aug_sha,
                             "train_synthetic_adversarial_fraction": round(synth_fraction, 6)}
        print(f"prompt-injection augmentation INTEGRATED into train only: {len(merged)} rows "
              f"| train synthetic fraction {synth_fraction:.4f}")

    # ---- 6. canonical hash validation for EVERY final row (#10) ----
    bad_hash = 0
    for rows_ in [*final.values(), gold_rows]:
        for r in rows_:
            if content_sha256(r["premise"], r["hypothesis"], r["label"]) != r["content_sha256"]:
                bad_hash += 1
    if bad_hash:
        fail(f"{bad_hash} final rows fail the canonical content_sha256 contract")
    print(f"content_sha256 validated: {sum(len(v) for v in final.values()) + len(gold_rows)} rows")

    # ---- 7. leakage checks (release-blocking) ----
    groups = {s: {r["split_group"] for r in rows_} for s, rows_ in final.items()}
    hashes = {s: {r["content_sha256"] for r in rows_} for s, rows_ in final.items()}
    pairs = {s: {(norm(r["premise"]), norm(r["hypothesis"])) for r in rows_} for s, rows_ in final.items()}
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
    for s in names:
        if gold_hashes & hashes[s]:
            leaks.append(f"gold hash in {s}")
        if gold_groups & groups[s]:
            leaks.append(f"gold group in {s}")
    gold_pair_set = {(norm(r["premise"]), norm(r["hypothesis"])) for r in gold_rows}
    for s in names:
        if gold_pair_set & pairs[s]:
            leaks.append(f"gold pair in {s}")
    ood_path = repo / "data/agentpay_ir_v2/eval/fresh_ood_v2.jsonl"
    if ood_path.exists():
        ood_hashes = {json.loads(line)["content_sha256"] for line in ood_path.read_text().splitlines()}
        for s in names:
            if ood_hashes & hashes[s]:
                leaks.append(f"ood hash in {s}")
    if leaks:
        fail("leakage: " + ", ".join(leaks))
    print("LEAKAGE GATE: PASS (incl. group-level gold separation and OOD deconfliction)")

    # ---- 8. freeze final hashes ----
    out_dir = corpus / "final"
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for s in names:
        (out_dir / f"{s}.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in final[s]))
        counts[s] = len(final[s])
    gold_path = review / "GOLD_FROZEN_V3.jsonl"
    gold_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in gold_rows))
    frozen = {
        "counts": counts,
        "stats": dict(stats),
        "gold_cards": len(gold_rows),
        "gold_human_label_agreement": sum(1 for g in gold_rows
                                          if g["metadata"]["label_agrees_with_source"]),
        "files": {f: sha256_file(out_dir / f) for f in ("train.jsonl", "val.jsonl", "test.jsonl")},
        "gold_frozen_sha256": sha256_file(gold_path),
        "ambiguous_excluded": len(ambiguous),
        "augmentation_integrated": augmentation_info,
    }
    (out_dir / "FINAL_FREEZE_MANIFEST.json").write_text(json.dumps(frozen, indent=2))
    print("final freeze:", json.dumps(counts), "| gold rows:", len(gold_rows))

    # ---- 9. rebuild the FINAL Colab bundle from corpus/final (#12/#13) ----
    if not args.skip_bundle:
        script = Path(__file__).resolve().parent / "rzp_build_colab_bundle_v2.py"
        cmd = [sys.executable, str(script), "--corpus-dir", str(out_dir),
               "--out-zip", str(artifacts / "agentpay_ir_v2_colab_training_bundle.zip"),
               "--notebook-out", str(repo / "notebooks" / "RazorGuard_NLI_AgentPayIR_v2_Training.ipynb")]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("FINAL bundle rebuilt from", out_dir)

    print("PRE-TRAINING FREEZE COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
