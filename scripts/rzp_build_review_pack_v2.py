#!/usr/bin/env python3
"""Build the STRATIFIED AgentPay-IR v2 human review pack (PVB correction #2-#4).

Requirements enforced here:
- 600-1000 cards, stratified across the required RazorMesh semantic/security
  families, spanning contradiction/entailment/neutral.
- Reviewer-facing artifact contains NO review_role, NO label_hint, NO suggested
  label, and no metadata that reveals the expected answer.
- Hidden roles (300 gold / rest supervised) preassigned BEFORE any human label
  and frozen with a role-manifest sha256.
- The previous 700-card pack (all esci_ambiguous_color_missing with neutral
  hints) is marked INVALID and not reused.

Outputs:
  data/agentpay_ir_v2/review/REVIEW_PACK_V2.jsonl      (reviewer-facing cards)
  data/agentpay_ir_v2/review/REVIEW_ROLE_MANIFEST_V2.json (hidden; frozen hash)
  data/agentpay_ir_v2/review/REVIEW_PACK_FREEZE_V2.json
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "data" / "agentpay_ir_v2" / "corpus"
REVIEW = REPO / "data" / "agentpay_ir_v2" / "review"
SEED = 42

# user-required families -> internal frozen_v2 family names (where drawn)
INTERNAL_STRATA = {
    "product_identity": ["product_identity", "product_equivalence", "variant", "aliases"],
    "brand": ["brand_identity", "product_identity"],
    "condition": ["product_condition", "warranty_condition"],
    "merchant_seller": ["merchant_identity", "seller_identity", "seller_authorization", "merchant_description_manipulation", "product_title_manipulation"],
    "quantity": ["quantity", "quantity_units"],
    "price": ["price_constraint"],
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
PER_STRATUM = 38  # 19 strata x 38 = 722 internal-sourced cards
CONTRACTNLI_CARDS = 60
ESCI_CARDS = 60
TOTAL_TARGET = 800


def norm(t: str) -> str:
    return re.sub(r"\W+", " ", t.lower()).strip()


def main() -> int:
    REVIEW.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    # ---- internal security/commerce strata from the corpus (provenance kept internal) ----
    by_family: dict[str, list[dict]] = defaultdict(list)
    seen_pairs: set[tuple[str, str]] = set()
    for split in ("train", "val", "test"):
        for line in open(CORPUS / f"{split}.jsonl"):
            r = json.loads(line)
            if r["source_dataset"] != "razormesh_frozen_v2":
                continue
            key = (norm(r["premise"])[:120], norm(r["hypothesis"])[:120])
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            by_family[r["family"]].append(r)

    cards: list[dict] = []
    card_index = 0
    for stratum, fams in INTERNAL_STRATA.items():
        pool: list[dict] = []
        for f in fams:
            pool.extend(by_family.get(f, []))
        # dedupe within stratum
        uniq: dict[tuple[str, str], dict] = {}
        for r in pool:
            uniq.setdefault((norm(r["premise"])[:120], norm(r["hypothesis"])[:120]), r)
        pool = list(uniq.values())
        # balance labels: round-robin C/E/N
        by_label: dict[str, list[dict]] = defaultdict(list)
        for r in pool:
            by_label[r["label"]].append(r)
        for lab in by_label:
            rng.shuffle(by_label[lab])
        picked: list[dict] = []
        while len(picked) < PER_STRATUM and any(by_label.values()):
            for lab in ("contradiction", "entailment", "neutral"):
                if by_label[lab] and len(picked) < PER_STRATUM:
                    picked.append(by_label[lab].pop())
        for r in picked:
            card_index += 1
            cards.append({
                "card_id": f"rc_{card_index:04d}",
                "stratum": stratum,
                "source_class": "razormesh_security_corpus",
                "premise": r["premise"],
                "hypothesis": r["hypothesis"],
                "_link": {"source_dataset": r["source_dataset"], "source_record_id": r["source_record_id"],
                           "record_id": r["record_id"], "split_group": r["split_group"], "label": r["label"]},
            })

    # ---- real human NLI (ContractNLI) sample ----
    cn = [json.loads(l) for l in open(CORPUS / "train.jsonl") if '"contractnli"' in l]
    rng.shuffle(cn)
    for r in cn[:CONTRACTNLI_CARDS]:
        card_index += 1
        cards.append({
            "card_id": f"rc_{card_index:04d}",
            "stratum": "contract_obligation",
            "source_class": "contractnli_real_human_nli",
            "premise": r["premise"][:900],
            "hypothesis": r["hypothesis"],
            "_link": {"source_dataset": r["source_dataset"], "source_record_id": r["source_record_id"],
                       "record_id": r["record_id"], "split_group": r["split_group"], "label": r["label"]},
        })

    # ---- real commerce (ESCI-derived corpus rows) sample ----
    esci = [json.loads(l) for l in open(CORPUS / "train.jsonl") if '"esci"' in l]
    # stratify esci by subfamily for spread
    by_sub: dict[str, list[dict]] = defaultdict(list)
    for r in esci:
        by_sub[r["subfamily"]].append(r)
    per_sub = max(1, ESCI_CARDS // max(1, len(by_sub)))
    for sub in sorted(by_sub):
        rng.shuffle(by_sub[sub])
        for r in by_sub[sub][:per_sub]:
            card_index += 1
            cards.append({
                "card_id": f"rc_{card_index:04d}",
                "stratum": f"esci_{sub}",
                "source_class": "esci_real_commerce",
                "premise": r["premise"][:600],
                "hypothesis": r["hypothesis"],
                "_link": {"source_dataset": r["source_dataset"], "source_record_id": r["source_record_id"],
                           "record_id": r["record_id"], "split_group": r["split_group"], "label": r["label"]},
            })

    assert 600 <= len(cards) <= 1000, f"pack size {len(cards)} outside 600-1000"
    rng.shuffle(cards)
    # re-key card ids after shuffle so ids do not encode stratum order
    for i, c in enumerate(cards, 1):
        c["card_id"] = f"rc_{i:04d}"

    # ---- hidden roles: 300 gold / rest supervised, frozen BEFORE any label ----
    roles = ["gold"] * 300 + ["supervised"] * (len(cards) - 300)
    rng2 = random.Random(SEED + 1)
    rng2.shuffle(roles)
    role_manifest = {
        "frozen_at": "2026-08-29T12:00:00+00:00",
        "seed": SEED + 1,
        "pack": "REVIEW_PACK_V2",
        "n_cards": len(cards),
        "n_gold": roles.count("gold"),
        "n_supervised": roles.count("supervised"),
        "assignments": {c["card_id"]: role for c, role in zip(cards, roles)},
    }
    role_bytes = json.dumps(role_manifest, sort_keys=True).encode()
    role_hash = hashlib.sha256(role_bytes).hexdigest()
    role_manifest["role_manifest_sha256"] = role_hash

    # reviewer-facing artifact: NO roles, NO hints, NO labels, NO metadata
    reviewer_pack = [
        {"card_id": c["card_id"], "stratum": c["stratum"],
         "source_class": c["source_class"], "premise": c["premise"], "hypothesis": c["hypothesis"]}
        for c in cards
    ]
    # PRIVATE (never reviewer-facing): card -> corpus record linkage for ingestion
    linkage = {c["card_id"]: c["_link"] for c in cards}
    (REVIEW / "REVIEW_LINKAGE_V2.json").write_text(json.dumps(linkage, indent=1, sort_keys=True))
    (REVIEW / "REVIEW_PACK_V2.jsonl").write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in reviewer_pack))
    (REVIEW / "REVIEW_ROLE_MANIFEST_V2.json").write_text(json.dumps(role_manifest, indent=2))

    # leak check: reviewer artifact must not contain role/hint markers
    # structural leak check: forbidden JSON keys must not appear as keys
    for c in reviewer_pack:
        assert set(c.keys()) == {"card_id", "stratum", "source_class", "premise", "hypothesis"}, c.keys()
    for line in open(REVIEW / "REVIEW_PACK_V2.jsonl"):
        obj = json.loads(line)
        assert "review_role" not in obj and "label_hint" not in obj and "label" not in obj \
            and "esci_label" not in obj and "expected" not in obj and "metadata" not in obj, obj.keys()

    freeze = {
        "pack": "REVIEW_PACK_V2",
        "cards": len(reviewer_pack),
        "strata": len({c["stratum"] for c in reviewer_pack}),
        "label_span_required": ["contradiction", "entailment", "neutral", "ambiguous"],
        "reviewer_artifact_sha256": hashlib.sha256((REVIEW / "REVIEW_PACK_V2.jsonl").read_bytes()).hexdigest(),
        "role_manifest_sha256": role_hash,
        "gold": role_manifest["n_gold"],
        "supervised": role_manifest["n_supervised"],
        "invalidates": "previous 700-card pack (all esci_ambiguous_color_missing, neutral hint) — marked INVALID, not for review",
        "frozen_at": role_manifest["frozen_at"],
    }
    (REVIEW / "REVIEW_PACK_FREEZE_V2.json").write_text(json.dumps(freeze, indent=2))
    print(json.dumps(freeze, indent=1))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
