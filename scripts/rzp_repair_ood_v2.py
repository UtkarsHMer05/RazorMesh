#!/usr/bin/env python3
"""Repair + refreeze the fresh AgentPay-IR v2 OOD set (PVB correction #13).

Fixes:
- every row normalized to the FULL v2 provenance contract (source_dataset,
  source_kind, license, fields — the old mix had 51 legacy v0.2 rows missing
  source_dataset/source_kind);
- representative composition: ~50% real human NLI (ContractNLI withheld docs),
  ~25% real commerce (ESCI withheld products, deterministic rules), ~25%
  internal commerce/security (withheld families), all hash/group-disjoint from
  the corpus and from human gold;
- frozen BEFORE training; never tuned from afterward.

Usage: services/api/.venv/bin/python scripts/rzp_repair_ood_v2.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from rzp_build_agentpay_ir_v2_corpus import (  # noqa: E402
    BRAND_HINT, CORPUS, EVAL, RAW, canonical_guard, dedup, make_record, norm_text as norm,
)

SEED = 42


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main() -> int:
    corpus_hashes: set[str] = set()
    corpus_groups: set[str] = set()
    for split in ("train", "val", "test"):
        for line in open(CORPUS / f"{split}.jsonl"):
            r = json.loads(line)
            corpus_hashes.add(r["content_sha256"])
            corpus_groups.add(r["split_group"])
    gold_hashes: set[str] = set()
    gold = REVIEW = REPO / "data/agentpay_ir_v2/review/GOLD_FROZEN_V2.jsonl"
    if gold.exists():
        gold_hashes = {json.loads(l)["content_sha256"] for l in open(gold)}

    ood: list[dict] = []

    # ---- 1. internal withheld families, NORMALIZED to the v2 contract ----
    withheld = {"currency", "delivery_constraint"}
    for split in ("train", "val", "test"):
        p = REPO / "data" / "phase3" / "dataset" / "frozen_v2" / f"{split}.jsonl"
        for line in open(p):
            r = json.loads(line)
            if r["family"] not in withheld:
                continue
            if not canonical_guard(r["premise"], r["hypothesis"]):
                continue
            rec = make_record(
                premise=r["premise"], hypothesis=r["hypothesis"], label=r["label"],
                family=r["family"], subfamily=r.get("subfamily", r["family"]),
                authorization_field=r.get("authorization_field", "intent_constraint"),
                evidence_field=r.get("evidence_field", "synthetic_commerce_evidence"),
                source_dataset="razormesh_frozen_v2",
                source_record_id=r["record_id"],
                source_license="project-internal",
                source_kind="deterministic_derived",
                split_group="ood_" + r.get("split_group", r["record_id"]),
                difficulty=r.get("difficulty", "medium"),
                safe_or_attack=r.get("safe_or_attack", "safe"),
                metadata={"ood_role": "fresh_v2_untouched", "withheld": "family"},
            )
            rec["metadata"]["legacy_provenance_normalized"] = True
            ood.append(rec)

    n_internal = len(ood)

    # ---- 2. ContractNLI withheld docs (real human NLI), capped for composition ----
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "rzp_build_agentpay_ir_v2_corpus", REPO / "scripts/rzp_build_agentpay_ir_v2_corpus.py")
    B = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(B)

    cnli_all, cnli_ood = B.load_contractnli()
    ood.extend(cnli_ood[:200])
    n_cnli = len(ood) - n_internal

    # ---- 3. ESCI withheld products (real commerce), deterministic rules ----
    import pandas as pd  # noqa: PLC0415

    ex = pd.read_parquet(RAW / "esci-data/shopping_queries_dataset/shopping_queries_dataset_examples.parquet")
    pr = pd.read_parquet(RAW / "esci-data/shopping_queries_dataset/shopping_queries_dataset_products.parquet")
    ex = ex[ex.product_locale == "us"]
    pr_us = pr[pr.product_locale == "us"].set_index("product_id")
    corpus_pids = {g.split("esci_p_", 1)[1] for g in corpus_groups if g.startswith("esci_p_")}
    wanted = ex[~ex.product_id.isin(corpus_pids)]
    esci_ood = []
    cap = 180
    for r in wanted.itertuples(index=False):
        if len(esci_ood) >= cap:
            break
        pid = r.product_id
        if pid not in pr_us.index:
            continue
        p = pr_us.loc[pid]
        if isinstance(p, pd.DataFrame):
            p = p.iloc[0]
        title = "" if pd.isna(p.product_title) else str(p.product_title)[:300]
        brand = "" if pd.isna(p.product_brand) else str(p.product_brand).strip()
        m = BRAND_HINT.search(str(r.query).lower())
        if not m or not brand or not title:
            continue
        qb = norm(m.group(0))
        b = norm(brand)
        if qb in b or b in qb:
            label, diff = "entailment", "easy"
        elif qb not in b and b not in qb:
            label, diff = "contradiction", "medium"
        else:
            continue
        premise = f"Proposed product listing — title: {title} Seller-listed brand: {brand}."
        hypothesis = f"The authorized product brand must be {brand}." if label == "entailment" else f"The authorized product brand must be {qb.title()}."
        if not canonical_guard(premise, hypothesis):
            continue
        esci_ood.append(make_record(
            premise=premise, hypothesis=hypothesis, label=label,
            family="product_identity", subfamily="esci_brand_ood",
            authorization_field="brand_allowlist",
            evidence_field="product_listing_title_and_brand",
            source_dataset="esci", source_record_id=str(r.example_id),
            source_license="Apache-2.0", source_kind="real_commerce",
            split_group=f"ood_esci_p_{pid}", difficulty=diff, safe_or_attack="safe",
            entity_family_id=f"esci_p_{pid}", template_family_id="brand_rule",
            metadata={"ood_role": "fresh_v2_untouched", "withheld": "entity"}))
    ood.extend(esci_ood)

    # ---- deconflict + dedup ----
    ood, _ = dedup(ood)
    before = len(ood)
    ood = [r for r in ood if r["content_sha256"] not in corpus_hashes
           and r["split_group"] not in corpus_groups
           and r["content_sha256"] not in gold_hashes]
    print(f"deconfliction removed {before - len(ood)} rows")

    # ---- composition report + provenance completeness gate ----
    kinds = Counter(r["source_kind"] for r in ood)
    fams = Counter(r["family"] for r in ood)
    labels = Counter(r["label"] for r in ood)
    for r in ood:
        for field in ("source_dataset", "source_kind", "source_license", "split_group",
                      "content_sha256", "record_id", "schema_version"):
            assert r.get(field), f"OOD row {r.get('record_id')} missing {field}"
        assert r["schema_version"] == "agentpay-ir-v2"
    assert len(ood) >= 300, f"OOD too small: {len(ood)}"
    print("OOD composition:", dict(kinds), "| families:", len(fams), "| labels:", dict(labels))

    out = EVAL / "fresh_ood_v2.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ood))
    (EVAL / "fresh_ood_v2_FROZEN.json").write_text(json.dumps({
        "frozen_at": "2026-08-29T13:00:00+00:00",
        "rows": len(ood),
        "sha256": sha256_file(out),
        "composition": {"source_kinds": dict(kinds), "labels": dict(labels),
                        "internal_withheld_family": n_internal, "contractnli_withheld_docs": n_cnli,
                        "esci_withheld_products": len(ood) - n_internal - n_cnli},
        "provenance": "every row normalized to the agentpay-ir-v2 record contract",
        "rule": "never used for training/validation/selection/calibration; never tuned from afterward",
        "replaces": "400-row mixed-provenance OOD (349 CNLI + 51 legacy v0.2 rows)",
    }, indent=2))
    print("OOD refrozen:", len(ood), "rows |", sha256_file(out)[:16], "…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
