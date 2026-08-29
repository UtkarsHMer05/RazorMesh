#!/usr/bin/env python3
"""Build the FINAL pre-review pack V3 (PRE-REVIEW FINAL CORRECTION #1-6, #11).

Hard guarantees (each enforced by an assertion here AND by a committed test in
services/api/tests/agentpay_v2/test_review_pack_v3.py):
- zero duplicate normalized (premise, hypothesis) pairs;
- zero duplicate underlying record_ids (one card per corpus record);
- role assignment is GROUP-LEVEL (never card-random): every card of a
  split_group receives the same role. Because entity_family_id and
  generator_parent_id are 1:1 with split_group in this corpus, group-level
  assignment isolates record_id, split_group, generator parent AND entity
  family. Additionally, INTERNAL (razormesh_frozen_v2) template families are
  unioned into group components so no internal template family spans GOLD and
  SUPERVISED either. ContractNLI/ESCI fixed-hypothesis template families DO
  span roles by construction (e.g. nda-11 spans 557 document groups); that
  exception is recorded in the freeze manifest and documented in
  docs/agentpay_ir_v2/NEAR_DUP_CROSS_SPLIT_REPORT.md — human gold + OOD are
  the stronger generalization benchmarks for those families.
- reviewer-facing JSON contains ONLY card_id, premise, hypothesis;
- label-bearing linkage + roles + working decisions stay LOCAL (gitignored);
  only hashes/counts/provenance are committed;
- role-manifest hash has ONE canonical definition:
      sha256(json.dumps(assignments, sort_keys=True, separators=(",", ":")))
  over the {card_id: role} mapping ONLY. It is stored exclusively in the
  separate freeze manifest; the role manifest never contains a hash of
  itself.

New generation => new card ids (rc2_NNNN). The v2 pack is superseded and
removed from tracking (its label-bearing linkage/roles were previously
public; git history retains the reviewer-facing cards only).

Outputs
  data/agentpay_ir_v2/review/REVIEW_PACK_V3.jsonl        (committed: reviewer-facing)
  data/agentpay_ir_v2/review/REVIEW_PACK_FREEZE_V3.json  (committed: hashes/counts)
  data/agentpay_ir_v2/review/REVIEW_LINKAGE_V3.json      (LOCAL: card -> record + group)
  data/agentpay_ir_v2/review/REVIEW_ROLE_MANIFEST_V3.json (LOCAL: hidden roles)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import tempfile
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "data" / "agentpay_ir_v2" / "corpus"
REVIEW = REPO / "data" / "agentpay_ir_v2" / "review"
SEED = 42
GOLD_TARGET = 300
GOLD_HARD_CAP = 340

INTERNAL_STRATA = {
    "quantity": ["quantity", "quantity_units"],
    "price": ["price_constraint"],
    "condition": ["product_condition", "warranty_condition"],
    "variant_identity": ["variant", "aliases", "product_identity", "product_equivalence"],
    "brand": ["brand_identity"],
    "merchant_seller": ["merchant_identity", "seller_identity", "seller_authorization",
                        "merchant_description_manipulation", "product_title_manipulation"],
    "currency": ["currency"],
    "recurring_subscription": ["recurring_subscription", "euphemistic_subscription", "automatic_renewal"],
    "trial_to_paid": ["trial_to_paid_renewal"],
    "membership_insertion": ["membership_insertion"],
    "fees": ["semantic_fees"],
    "shipping": ["shipping_obligation"],
    "fulfillment": ["fulfillment_constraint", "delivery_constraint"],
    "safe_lookalikes": ["safe_lookalikes", "equivalent_benign_wording", "safe_paraphrases"],
    "ambiguity": ["ambiguous_evidence"],
    "negation": ["misleading_negation", "double_negation"],
    "prompt_injection": ["prompt_injection_like_merchant_text", "irrelevant_hostile_text"],
    "bundle": ["bundles"],
    "return_warranty": ["return_condition", "warranty_condition"],
}
PER_STRATUM = 34


def norm(t: str) -> str:
    return re.sub(r"\W+", " ", t.lower()).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--verify-only", action="store_true",
        help="fresh-clone reproduction check: regenerate everything into a temp dir "
             "and verify the pack bytes, role-assignment hash and freeze manifest "
             "match the tracked frozen artifacts; writes NOTHING")
    args = ap.parse_args()
    review = REVIEW
    if args.verify_only:
        review = Path(tempfile.mkdtemp(prefix="rzp_pack_verify_"))
    review.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    by_family: dict[str, list[dict]] = defaultdict(list)
    for split in ("train", "val", "test"):
        for line in open(CORPUS / f"{split}.jsonl"):
            r = json.loads(line)
            if r["source_dataset"] == "razormesh_frozen_v2":
                by_family[r["family"]].append(r)

    cards: list[dict] = []
    used_pairs: set[tuple[str, str]] = set()
    used_record_ids: set[str] = set()

    def add_card(stratum: str, source_class: str, r: dict) -> bool:
        pair = (norm(r["premise"])[:160], norm(r["hypothesis"])[:160])
        if pair in used_pairs or r["record_id"] in used_record_ids:
            return False
        used_pairs.add(pair)
        used_record_ids.add(r["record_id"])
        cards.append({
            "card_id": "",  # assigned after shuffle
            "stratum": stratum,  # private (linkage only)
            "source_class": source_class,  # private (linkage only)
            "premise": r["premise"][:900],
            "hypothesis": r["hypothesis"][:400],
            "_record_id": r["record_id"],
            "_split_group": r["split_group"],
            "_template_family": r.get("template_family_id", ""),
            "_label": r["label"],
        })
        return True

    for stratum, fams in INTERNAL_STRATA.items():
        pool: dict[str, dict] = {}
        for f in fams:
            for r in by_family.get(f, []):
                pool.setdefault(r["record_id"], r)
        by_label: dict[str, list[dict]] = defaultdict(list)
        for r in pool.values():
            by_label[r["label"]].append(r)
        for lab in by_label:
            rng.shuffle(by_label[lab])
        picked = 0
        while picked < PER_STRATUM and any(by_label.values()):
            for lab in ("contradiction", "entailment", "neutral"):
                if by_label[lab] and picked < PER_STRATUM:
                    if add_card(stratum, "razormesh_security_corpus", by_label[lab].pop()):
                        picked += 1

    # real human NLI + real commerce rounds (smaller, spread across strata)
    for line in open(CORPUS / "train.jsonl"):
        r = json.loads(line)
        if r["source_dataset"] == "contractnli" and sum(1 for c in cards if c["stratum"] == "contract_obligation") < 50:
            add_card("contract_obligation", "contractnli_real_human_nli", r)
        elif r["source_dataset"] == "esci" and sum(1 for c in cards if c["stratum"].startswith("esci_")) < 50:
            add_card(f"esci_{r['subfamily']}", "esci_real_commerce", r)

    rng.shuffle(cards)
    for i, c in enumerate(cards, 1):
        c["card_id"] = f"rc2_{i:04d}"

    # ---- hard guarantees (also pinned by tests) ----
    pairs = [(norm(c["premise"])[:160], norm(c["hypothesis"])[:160]) for c in cards]
    assert len(pairs) == len(set(pairs)), "duplicate normalized pair in pack"
    rids = [c["_record_id"] for c in cards]
    assert len(rids) == len(set(rids)), "duplicate record_id in pack"
    assert 600 <= len(cards) <= 1000, f"pack size {len(cards)}"

    # ---- GROUP-LEVEL role assignment: no required grouping unit spans roles ----
    by_group: dict[str, list[dict]] = defaultdict(list)
    for c in cards:
        by_group[c["_split_group"]].append(c)

    # Union groups that share an INTERNAL template family so no internal
    # template family can span GOLD and SUPERVISED (exception: contractnli/esci,
    # whose fixed hypotheses span all document groups by construction).
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    tf_groups: dict[str, set[str]] = defaultdict(set)
    for c in cards:
        if c["_template_family"] and c["source_class"] == "razormesh_security_corpus":
            tf_groups[c["_template_family"]].add(c["_split_group"])
    for groups in tf_groups.values():
        gs = sorted(groups)
        for g in gs[1:]:
            union(gs[0], g)

    components: dict[str, list[str]] = defaultdict(list)
    for g in by_group:
        components[find(g)].append(g)
    ordered = sorted(
        components.values(),
        key=lambda gs: hashlib.sha256(("goldsel_" + min(gs)).encode()).hexdigest(),
    )
    roles: dict[str, str] = {}
    gold_cards = 0
    for gs in ordered:
        role = "gold" if gold_cards < GOLD_TARGET else "supervised"
        n = sum(len(by_group[g]) for g in gs)
        if role == "gold" and gold_cards + n > GOLD_HARD_CAP:
            role = "supervised"  # group isolation outranks the exact count
        for g in gs:
            for c in by_group[g]:
                roles[c["card_id"]] = role
        if role == "gold":
            gold_cards += n
    role_values = set(roles.values())
    assert role_values == {"gold", "supervised"}, role_values
    assert 250 <= gold_cards <= GOLD_HARD_CAP, f"gold cards {gold_cards}"

    # ---- canonical role hash: hash the ASSIGNMENTS object only (no self-field) ----
    assignments = {cid: roles[cid] for cid in sorted(roles)}
    role_sha = hashlib.sha256(
        json.dumps(assignments, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    # ---- reviewer-facing artifact: ONLY card_id, premise, hypothesis ----
    reviewer = [{"card_id": c["card_id"], "premise": c["premise"], "hypothesis": c["hypothesis"]}
                for c in cards]
    for c in reviewer:
        assert set(c.keys()) == {"card_id", "premise", "hypothesis"}
        for forbidden in ("stratum", "source_class", "label", "role", "hint", "metadata"):
            assert forbidden not in c
    pack_path = review / "REVIEW_PACK_V3.jsonl"
    pack_path.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in reviewer))
    pack_sha = hashlib.sha256(pack_path.read_bytes()).hexdigest()

    # ---- PRIVATE files (gitignored) ----
    linkage = {c["card_id"]: {"record_id": c["_record_id"], "split_group": c["_split_group"],
                              "template_family_id": c["_template_family"],
                              "source_label": c["_label"], "stratum": c["stratum"],
                              "source_class": c["source_class"]} for c in cards}
    (review / "REVIEW_LINKAGE_V3.json").write_text(json.dumps(linkage, indent=1, sort_keys=True))
    role_manifest = {
        "pack": "REVIEW_PACK_V3",
        "frozen_at": "2026-08-29T15:00:00+00:00",
        "seed": SEED,
        "n_gold": sum(1 for v in roles.values() if v == "gold"),
        "n_supervised": sum(1 for v in roles.values() if v == "supervised"),
        "group_level": True,
        "assignments": assignments,
    }
    (review / "REVIEW_ROLE_MANIFEST_V3.json").write_text(json.dumps(role_manifest, indent=1))

    # ---- committed freeze manifest: counts + hashes + provenance ONLY ----
    gold_groups = sorted({linkage[cid]["split_group"] for cid, r in roles.items() if r == "gold"})
    sup_groups = sorted({linkage[cid]["split_group"] for cid, r in roles.items() if r == "supervised"})
    assert not (set(gold_groups) & set(sup_groups)), "group spans GOLD and SUPERVISED"

    def tf_span(source_class: str) -> int:
        tfr: dict[str, set[str]] = defaultdict(set)
        for cid, l in linkage.items():
            if l["source_class"] == source_class and l["template_family_id"]:
                tfr[l["template_family_id"]].add(roles[cid])
        return sum(1 for rs in tfr.values() if len(rs) > 1)

    internal_tf_span = tf_span("razormesh_security_corpus")
    assert internal_tf_span == 0, f"{internal_tf_span} internal template families span roles"
    contract_span = tf_span("contractnli_real_human_nli") + tf_span("esci_real_commerce")

    freeze = {
        "pack": "REVIEW_PACK_V3",
        "generation_note": "fresh generation; supersedes V2; new card-id namespace rc2_*",
        "cards": len(cards),
        "unique_record_ids": len(set(rids)),
        "unique_normalized_pairs": len(set(pairs)),
        "unique_split_groups": len(by_group),
        "gold_cards": role_manifest["n_gold"],
        "supervised_cards": role_manifest["n_supervised"],
        "gold_groups": len(gold_groups),
        "supervised_groups": len(sup_groups),
        "group_isolation": ("no split_group / record_id / generator_parent_id / entity_family_id "
                            "spans gold and supervised (asserted); internal template families "
                            "unioned into group components (asserted)"),
        "template_family_exception": {
            "contractnli_esci_families_spanning_roles": contract_span,
            "note": ("ContractNLI/ESCI fixed hypotheses span document groups by construction and "
                     "cannot be template-held-out; human gold + untouched OOD are the stronger "
                     "generalization benchmarks for those families"),
        },
        "reviewer_fields": ["card_id", "premise", "hypothesis"],
        "reviewer_pack_sha256": pack_sha,
        "role_manifest_sha256": role_sha,
        "role_sha_definition": "sha256(json.dumps(assignments, sort_keys=True, separators=(',',':'))) over {card_id: role} only; stored HERE, never inside the role manifest",
        "private_files_gitignored": ["REVIEW_LINKAGE_V3.json", "REVIEW_ROLE_MANIFEST_V3.json",
                                     "decisions_working.json", "GOLD_FROZEN_V3.jsonl"],
        "frozen_at": role_manifest["frozen_at"],
    }
    (review / "REVIEW_PACK_FREEZE_V3.json").write_text(json.dumps(freeze, indent=1))
    if args.verify_only:
        tracked_pack = (REVIEW / "REVIEW_PACK_V3.jsonl").read_bytes()
        tracked_freeze = json.loads((REVIEW / "REVIEW_PACK_FREEZE_V3.json").read_text())
        checks = {
            "pack_bytes_match_tracked": pack_path.read_bytes() == tracked_pack,
            "pack_sha_matches_freeze": freeze["reviewer_pack_sha256"]
                                       == tracked_freeze["reviewer_pack_sha256"],
            "role_sha_matches_freeze": freeze["role_manifest_sha256"]
                                       == tracked_freeze["role_manifest_sha256"],
            "freeze_manifest_byte_identical": (review / "REVIEW_PACK_FREEZE_V3.json").read_bytes()
                                              == (REVIEW / "REVIEW_PACK_FREEZE_V3.json").read_bytes(),
        }
        print(json.dumps(checks, indent=1))
        if not all(checks.values()):
            print("VERIFY-ONLY FAIL: tracked frozen pack does not reproduce from the tracked corpus")
            return 1
        print("VERIFY-ONLY PASS: fresh-clone reproduction matches the frozen artifacts")
        return 0
    print(json.dumps({k: freeze[k] for k in ("cards", "unique_record_ids", "gold_cards",
                                             "supervised_cards", "gold_groups", "supervised_groups",
                                             "reviewer_pack_sha256", "role_manifest_sha256")}, indent=1))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
