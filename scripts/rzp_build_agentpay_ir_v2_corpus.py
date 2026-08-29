#!/usr/bin/env python3
"""Build the AgentPay-IR v2 real-data-dominant corpus (gates G060-G093).

Orientation (non-negotiable, master prompt §3):
    premise    = CURRENT SANITIZED COMMERCE / MERCHANT / CHECKOUT EVIDENCE
    hypothesis = NORMALIZED HUMAN-CONFIRMED AUTHORIZATION CONSTRAINT
    label      = contradiction | entailment | neutral

Sources (frozen in docs/agentpay_ir_v2/DATA_SOURCE_MATRIX.md):
    contractnli  CC BY 4.0   real human NLI      -> contract clause semantics
    esci         Apache-2.0  real commerce       -> brand/color/condition/model identity
    razormesh_frozen_v2      internal supervised -> provenance-normalized seed
    internal adversarial     synthetic_adversarial (<=10% of train)

Deterministic label rules (G070): every automatic label is backed by an explicit,
deterministic semantic relationship; anything ambiguous is NOT auto-labeled
(ambiguous ESCI rows are candidates for the human review pack instead).

Outputs (never overwrites frozen_v2):
    data/agentpay_ir_v2/corpus/{train,val,test}.jsonl
    data/agentpay_ir_v2/corpus/review_candidates.jsonl
    data/agentpay_ir_v2/eval/fresh_ood_v2.jsonl   (frozen; never used for training)
    data/agentpay_ir_v2/corpus/manifest.json
    docs/agentpay_ir_v2/TRANSFORMATION_REPORT.md

Usage: services/api/.venv/bin/python scripts/rzp_build_agentpay_ir_v2_corpus.py
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "services" / "api" / "src"))

RAW = REPO / "data" / "agentpay_ir_v2" / "raw"
CORPUS = REPO / "data" / "agentpay_ir_v2" / "corpus"
EVAL = REPO / "data" / "agentpay_ir_v2" / "eval"
DOCS = REPO / "docs" / "agentpay_ir_v2"
SCHEMA_VERSION = "agentpay-ir-v2"
LABELS = ("contradiction", "entailment", "neutral")

SEED = 42


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def sha256_text(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def norm_text(t: str) -> str:
    return re.sub(r"\W+", " ", t.lower()).strip()


def span_texts(doc_text: str, spans: list[Any]) -> list[str]:
    out = []
    for s in spans[:3]:  # cap 3 spans per premise (bounded evidence)
        if not isinstance(s, (list, tuple)) or len(s) != 2:
            continue
        a, b = int(s[0]), int(s[1])
        frag = doc_text[a:b].strip()
        if 20 <= len(frag) <= 700:
            out.append(re.sub(r"\s+", " ", frag))
    return out


def ann_span_texts(doc: dict[str, Any], ann: dict[str, Any]) -> list[str]:
    """ContractNLI annotation spans are INDICES into doc['spans'] (char pairs)."""
    idxs = ann.get("spans") or []
    char_pairs = [doc["spans"][i] for i in idxs if isinstance(i, int) and 0 <= i < len(doc["spans"])]
    return span_texts(doc["text"], char_pairs)


def group_bucket(group_id: str) -> str:
    """Deterministic grouped split: 75/12.5/12.5 by sha256(group_id)."""
    h = int(hashlib.sha256(group_id.encode()).hexdigest(), 16) % 1000
    if h < 750:
        return "train"
    if h < 875:
        return "val"
    return "test"


def make_record(
    *,
    premise: str,
    hypothesis: str,
    label: str,
    family: str,
    subfamily: str,
    authorization_field: str,
    evidence_field: str,
    source_dataset: str,
    source_record_id: str,
    source_license: str,
    source_kind: str,
    split_group: str,
    difficulty: str,
    safe_or_attack: str,
    entity_family_id: str = "",
    template_family_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    content_sha256 = sha256_text(premise, hypothesis, label, "canonical")
    return {
        "record_id": "ap2_" + sha256_text(source_dataset, source_record_id, premise, hypothesis)[:26],
        "schema_version": SCHEMA_VERSION,
        "premise": premise,
        "hypothesis": hypothesis,
        "label": label,
        "family": family,
        "subfamily": subfamily,
        "authorization_field": authorization_field,
        "evidence_field": evidence_field,
        "source_dataset": source_dataset,
        "source_record_id": source_record_id,
        "source_license": source_license,
        "source_provenance": json.dumps(
            {"generator_parent_id": split_group, "template_family_id": template_family_id,
             "entity_family_id": entity_family_id}, sort_keys=True),
        "source_kind": source_kind,
        "generator_parent_id": split_group,
        "template_family_id": template_family_id,
        "entity_family_id": entity_family_id,
        "safe_lookalike_family_id": "",
        "split_group": split_group,
        "difficulty": difficulty,
        "safe_or_attack": safe_or_attack,
        "content_sha256": content_sha256,
        "metadata": metadata or {},
    }


def canonical_guard(premise: str, hypothesis: str) -> bool:
    """Reject authorization prose folded into the premise (the v0.1 defect)."""
    bad = ("authorized contract", "human request", "the authorized", "authorization:",
           "you authorize", "user authorize", "confirmed intent")
    p = premise.lower()
    return not any(b in p for b in bad)


# --------------------------------------------------------------------------
# ContractNLI transform (G065)
# --------------------------------------------------------------------------
def load_contractnli() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    zip_path = RAW / "contract-nli.zip"
    rows: list[dict[str, Any]] = []
    ood_rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(zip_path) as z:
        for split_file in ("train.json", "dev.json", "test.json"):
            data = json.loads(z.read(f"contract-nli/{split_file}"))
            hyp_templates = data["labels"]  # dict hyp_id -> {short_description, hypothesis}
            for doc in data["documents"]:
                doc_group = f"contractnli_doc_{doc['id']}"
                withheld_doc = int(hashlib.sha256(("oodsel_" + doc_group).encode()).hexdigest(), 16) % 1000 >= 950
                target = ood_rows if withheld_doc else rows
                anns = doc["annotation_sets"][0]["annotations"]
                span_texts_cache: dict[str, list[str]] = {}
                for hid, ann in anns.items():
                    span_texts_cache[hid] = ann_span_texts(doc, ann)
                # first non-empty evidence from a different hypothesis (for NM premises)
                other_evidence = next(
                    (st for hid, st in span_texts_cache.items()
                     if st and anns[hid]["choice"] != "NotMentioned"),
                    [],
                )
                nm_kept = 0
                for hid, ann in anns.items():
                    choice = ann["choice"]
                    template = hyp_templates[hid]
                    hypothesis = template["hypothesis"].strip()
                    subfamily = "contract_" + re.sub(r"\W+", "_", template["short_description"].lower())[:40]
                    if choice in ("Entailment", "Contradiction"):
                        st = span_texts_cache[hid]
                        if not st:
                            continue
                        premise = " ".join(st)
                        if len(premise) > 2000:
                            continue
                        if not canonical_guard(premise, hypothesis):
                            continue
                        label = "entailment" if choice == "Entailment" else "contradiction"
                        target.append(make_record(
                            premise=premise, hypothesis=hypothesis, label=label,
                            family="contract_obligation", subfamily=subfamily,
                            authorization_field="contract_clause_authorization",
                            evidence_field="contract_evidence_span",
                            source_dataset="contractnli",
                            source_record_id=f"{split_file}:{doc['id']}:{hid}",
                            source_license="CC BY 4.0",
                            source_kind="real_human_nli",
                            split_group=f"contractnli_doc_{doc['id']}",
                            difficulty="hard" if label == "contradiction" else "medium",
                            safe_or_attack="safe",
                            template_family_id=hid,
                            entity_family_id=f"cnli_doc_{doc['id']}",
                            metadata={"evidence_span_count": len(st), "upstream_split": split_file},
                        ))
                    else:  # NotMentioned -> neutral with cross-clause evidence
                        if not other_evidence or nm_kept >= 6:
                            continue
                        premise = " ".join(other_evidence)
                        if len(premise) > 2000:
                            continue
                        if not canonical_guard(premise, hypothesis):
                            continue
                        target.append(make_record(
                            premise=premise, hypothesis=hypothesis, label="neutral",
                            family="contract_obligation", subfamily=subfamily + "_not_mentioned",
                            authorization_field="contract_clause_authorization",
                            evidence_field="contract_other_clause_span",
                            source_dataset="contractnli",
                            source_record_id=f"{split_file}:{doc['id']}:{hid}:nm",
                            source_license="CC BY 4.0",
                            source_kind="real_human_nli",
                            split_group=f"contractnli_doc_{doc['id']}",
                            difficulty="hard",
                            safe_or_attack="safe",
                            template_family_id=hid,
                            entity_family_id=f"cnli_doc_{doc['id']}",
                            metadata={"neutral_premise": "cross_clause_span", "upstream_split": split_file},
                        ))
                        nm_kept += 1
    return rows, ood_rows


# --------------------------------------------------------------------------
# ESCI transform (G067/G068/G070) — deterministic explicit-semantics rules only
# --------------------------------------------------------------------------
BRAND_HINT = re.compile(
    r"\b(samsung|apple|sony|nike|adidas|puma|levis|levi's|under armour|ugg|crocs|keurig|ninja|"
    r"dyson|bose|jbl|beats|anker|logitech|razer|canon|nikon|gopro|dell|hp|lenovo|asus|acer|"
    r"lego|fisher[\s-]?price|cuisinart|kitchenaid|weber|stanley|hydro flask|yeti|new balance|"
    r"reebok|vans|converse|tommy hilfiger|calvin klein|ralph lauren|columbia|north face|patagonia|"
    r"l'or[eé]al|maybelline|neutrogena|cetaphil|olaplex|garnier|crest|oral[\s-]?b|philips|panasonic|"
    r"xiaomi|oneplus|google|motorola|t[\s-]?mobile|samsung galaxy|hp|epson|brother|shure|audio[\s-]?technica|"
    r"sennheiser|marshall|jawbone|fitbit|garmin|timex|casio|fossil|michael kors|kate spade)\b", re.I)
COLOR_WORDS = ("black", "white", "red", "blue", "green", "yellow", "pink", "purple", "gray", "grey",
               "silver", "gold", "orange", "brown", "beige")
CONDITION_NEW = re.compile(r"\b(new|brand new|sealed)\b", re.I)
CONDITION_USED = re.compile(r"\b(refurbished|renewed|used|pre[\s-]?owned|open[\s-]?box)\b", re.I)
MODEL_TOKEN = re.compile(r"\b[a-z]{0,4}[\s-]?\d{3,5}[a-z]{0,3}\b|\b[a-z]{1,4}\d{2,4}[a-z]{0,4}\b", re.I)


def brand_in_text(brand: str, text: str) -> bool:
    if not brand:
        return False
    b = norm_text(brand)
    t = norm_text(text)
    return b in t


def esci_rows(candidates_out: list[dict[str, Any]]) -> list[dict[str, Any]]:
    import pandas as pd  # provided by uv --with at build time

    ex = pd.read_parquet(RAW / "esci-data/shopping_queries_dataset/shopping_queries_dataset_examples.parquet")
    pr = pd.read_parquet(RAW / "esci-data/shopping_queries_dataset/shopping_queries_dataset_products.parquet")
    ex = ex[ex.product_locale == "us"]
    pr = pr[pr.product_locale == "us"]
    prod = pr.set_index("product_id")
    rows: list[dict[str, Any]] = []
    caps = {
        "esci_brand_entailment": 2600, "esci_brand_contradiction": 2600,
        "esci_brand_neutral": 1600, "esci_color": 1800, "esci_condition": 1800,
        "esci_model_identity": 1400,
    }
    counts: Counter[str] = Counter()
    review_seen = 0
    for r in ex.itertuples(index=False):
        if all(counts[k] >= v for k, v in caps.items()):
            break
        pid = r.product_id
        if pid not in prod.index:
            continue
        p = prod.loc[pid]
        if isinstance(p, pd.DataFrame):
            p = p.iloc[0]
        title = "" if pd.isna(p.product_title) else str(p.product_title)[:300]
        brand = "" if pd.isna(p.product_brand) else str(p.product_brand).strip()
        color = "" if pd.isna(p.product_color) else str(p.product_color).strip()
        query = str(r.query)
        ql = query.lower()
        gq = f"esci_p_{pid}"  # product is the shared conceptual parent

        m = BRAND_HINT.search(ql)
        # --- review candidates: ambiguous rows (independent of label caps) ---
        if m and review_seen < 700:
            qb0 = norm_text(m.group(0))
            if not brand and len(title) > 40:
                candidates_out.append({
                    "candidate_id": f"rev_esci_{r.example_id}",
                    "provenance": "esci_ambiguous_brand_missing",
                    "premise": f"Proposed product listing — title: {title}",
                    "hypothesis": f"The authorized product brand must be {qb0.title()}.",
                    "label_hint": "neutral (seller brand not provided; absence is not a violation)",
                    "esci_label": r.esci_label, "query": query, "source_license": "Apache-2.0",
                })
                review_seen += 1
        # --- brand identity ---
        if m and counts["esci_brand_entailment"] < caps["esci_brand_entailment"]:
            qb = norm_text(m.group(0))
            b = norm_text(brand)
            if b and qb and (qb in b or b in qb):
                premise = f"Proposed product listing — title: {title} Seller-listed brand: {brand}."
                hyp = f"The authorized product brand must be {brand}."
                rows.append(make_record(
                    premise=premise, hypothesis=hyp, label="entailment",
                    family="product_identity", subfamily="esci_brand_entailment",
                    authorization_field="brand_allowlist",
                    evidence_field="product_listing_title_and_brand",
                    source_dataset="esci", source_record_id=str(r.example_id),
                    source_license="Apache-2.0", source_kind="real_commerce",
                    split_group=gq, difficulty="easy", safe_or_attack="safe",
                    entity_family_id=f"esci_p_{pid}", template_family_id="brand_rule",
                    metadata={"esci_label": r.esci_label, "query": query}))
                counts["esci_brand_entailment"] += 1
            elif b and qb and qb not in b and b not in qb:
                premise = f"Proposed product listing — title: {title} Seller-listed brand: {brand}."
                hyp = f"The authorized product brand must be {qb.title()}."
                rows.append(make_record(
                    premise=premise, hypothesis=hyp, label="contradiction",
                    family="product_identity", subfamily="esci_brand_contradiction",
                    authorization_field="brand_allowlist",
                    evidence_field="product_listing_title_and_brand",
                    source_dataset="esci", source_record_id=str(r.example_id),
                    source_license="Apache-2.0", source_kind="real_commerce",
                    split_group=gq, difficulty="medium", safe_or_attack="safe",
                    entity_family_id=f"esci_p_{pid}", template_family_id="brand_rule",
                    metadata={"esci_label": r.esci_label, "query": query}))
                counts["esci_brand_contradiction"] += 1

        if review_seen < 700:
            cw0 = next((c for c in COLOR_WORDS if re.search(rf"\b{c}\b", ql)), None)
            if cw0 and not color and len(title) > 40:
                candidates_out.append({
                    "candidate_id": f"rev_esci_color_{r.example_id}",
                    "provenance": "esci_ambiguous_color_missing",
                    "premise": f"Proposed product listing — title: {title}",
                    "hypothesis": f"The authorized product color must be {cw0}.",
                    "label_hint": "neutral (listing color not provided; absence is not a violation)",
                    "esci_label": r.esci_label, "query": query, "source_license": "Apache-2.0",
                })
                review_seen += 1

        # --- color identity ---
        if counts["esci_color"] < caps["esci_color"]:
            cw = next((c for c in COLOR_WORDS if re.search(rf"\b{c}\b", ql)), None)
            if cw and color:
                cl = norm_text(color)
                premise = f"Proposed product listing — title: {title} Listed color: {color}."
                hyp = f"The authorized product color must be {cw}."
                if cw in cl or any(c in cl for c in (cw,)):
                    label, diff = "entailment", "easy"
                else:
                    label, diff = "contradiction", "medium"
                rows.append(make_record(
                    premise=premise, hypothesis=hyp, label=label,
                    family="product_identity", subfamily="esci_color",
                    authorization_field="attribute_constraint_color",
                    evidence_field="product_listing_color",
                    source_dataset="esci", source_record_id=str(r.example_id),
                    source_license="Apache-2.0", source_kind="real_commerce",
                    split_group=gq, difficulty=diff, safe_or_attack="safe",
                    entity_family_id=f"esci_p_{pid}", template_family_id="color_rule",
                    metadata={"esci_label": r.esci_label, "query": query}))
                counts["esci_color"] += 1

        # --- condition claims (title-grounded, authorization-facing) ---
        if counts["esci_condition"] < caps["esci_condition"]:
            new_m = CONDITION_NEW.search(title)
            used_m = CONDITION_USED.search(title)
            if used_m:
                premise = f"Proposed product listing — title: {title}"
                hyp = "The authorized product condition is new (factory-sealed)."
                rows.append(make_record(
                    premise=premise, hypothesis=hyp, label="contradiction",
                    family="product_condition", subfamily="esci_condition_refurbished",
                    authorization_field="condition_new_only",
                    evidence_field="product_listing_title",
                    source_dataset="esci", source_record_id=str(r.example_id),
                    source_license="Apache-2.0", source_kind="real_commerce",
                    split_group=gq, difficulty="hard", safe_or_attack="safe",
                    entity_family_id=f"esci_p_{pid}", template_family_id="condition_rule",
                    metadata={"esci_label": r.esci_label, "matched": used_m.group(0)}))
                counts["esci_condition"] += 1
            elif new_m and ql and CONDITION_USED.search(ql):
                premise = f"Proposed product listing — title: {title}"
                hyp = "The authorized product condition is refurbished or renewed."
                rows.append(make_record(
                    premise=premise, hypothesis=hyp, label="contradiction",
                    family="product_condition", subfamily="esci_condition_new_vs_refurb_request",
                    authorization_field="condition_refurbished_requested",
                    evidence_field="product_listing_title",
                    source_dataset="esci", source_record_id=str(r.example_id),
                    source_license="Apache-2.0", source_kind="real_commerce",
                    split_group=gq, difficulty="hard", safe_or_attack="safe",
                    entity_family_id=f"esci_p_{pid}", template_family_id="condition_rule",
                    metadata={"esci_label": r.esci_label}))
                counts["esci_condition"] += 1

        # --- model-number identity ---
        if counts["esci_model_identity"] < caps["esci_model_identity"]:
            mt = MODEL_TOKEN.search(ql)
            if mt:
                tok = re.sub(r"[\s-]+", "", mt.group(0).lower())
                if len(tok) >= 4 and tok in re.sub(r"[\s-]+", "", title.lower()):
                    premise = f"Proposed product listing — title: {title}"
                    hyp = f"The authorized product must be model {mt.group(0).upper().replace(' ', '')}."
                    rows.append(make_record(
                        premise=premise, hypothesis=hyp, label="entailment",
                        family="product_equivalence", subfamily="esci_model_identity",
                        authorization_field="product_model_allowlist",
                        evidence_field="product_listing_title",
                        source_dataset="esci", source_record_id=str(r.example_id),
                        source_license="Apache-2.0", source_kind="real_commerce",
                        split_group=gq, difficulty="medium", safe_or_attack="safe",
                        entity_family_id=f"esci_p_{pid}", template_family_id="model_rule",
                        metadata={"esci_label": r.esci_label}))
                    counts["esci_model_identity"] += 1

        # --- genuine real-commerce neutrals: explicit buyer-facing constraint the listing does not address ---
        if counts["esci_brand_neutral"] < caps["esci_brand_neutral"] and m:
            qb = norm_text(m.group(0))
            if brand and qb not in norm_text(brand) and qb not in norm_text(title):
                premise = f"Proposed product listing — title: {title} Listed color: {color or 'not specified'}."
                hyp = f"The authorized product brand must be {qb.title()}."
                rows.append(make_record(
                    premise=premise, hypothesis=hyp, label="neutral",
                    family="product_identity", subfamily="esci_brand_neutral",
                    authorization_field="brand_allowlist",
                    evidence_field="product_listing_title",
                    source_dataset="esci", source_record_id=str(r.example_id),
                    source_license="Apache-2.0", source_kind="real_commerce",
                    split_group=gq, difficulty="hard", safe_or_attack="safe",
                    entity_family_id=f"esci_p_{pid}", template_family_id="brand_rule",
                    metadata={"esci_label": r.esci_label, "note": "brand absent from evidence; absence is not violation"}))
                counts["esci_brand_neutral"] += 1
    return rows


# --------------------------------------------------------------------------
# RazorMesh supervised seed (Source F) + internal adversarial
# --------------------------------------------------------------------------
def razormesh_seed() -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    excluded: list[str] = []
    gold_ids: set[str] = set()
    gold_path = REPO / "data" / "phase3" / "gold" / "gold_decisions.json"
    if gold_path.exists():
        gold_ids = set(json.loads(gold_path.read_text()).keys())
    ood_rows: list[dict[str, Any]] = []
    withheld = {"currency", "delivery_constraint"}  # frozen_v2 family names
    for split in ("train", "val", "test"):
        p = REPO / "data" / "phase3" / "dataset" / "frozen_v2" / f"{split}.jsonl"
        for line in open(p):
            r = json.loads(line)
            if not canonical_guard(r["premise"], r["hypothesis"]):
                excluded.append(f"{split}:{r['record_id']}")
                continue
            if r["family"] in withheld:
                ood_rows.append(r)
                continue
            was_test = split == "test"
            kind = "human_reviewed" if r.get("record_id", "") in gold_ids else "deterministic_derived"
            rows.append(make_record(
                premise=r["premise"], hypothesis=r["hypothesis"], label=r["label"],
                family=r["family"], subfamily=r.get("subfamily", r["family"]),
                authorization_field=r.get("authorization_field", "intent_constraint"),
                evidence_field=r.get("evidence_field", "synthetic_commerce_evidence"),
                source_dataset="razormesh_frozen_v2",
                source_record_id=r["record_id"],
                source_license="project-internal",
                source_kind=kind,
                split_group="rm_" + r.get("split_group", r.get("generator_parent_id", r["record_id"])),
                difficulty=r.get("difficulty", "medium"),
                safe_or_attack=r.get("safe_or_attack", "safe"),
                template_family_id=r.get("template_family_id", ""),
                entity_family_id=r.get("entity_family_id", ""),
                metadata={"historical_split": split, "was_frozen_v2_test": was_test,
                          "orientation": "canonical (revalidated)"}))
    return rows, excluded, ood_rows


def internal_adversarial(cap: int) -> list[dict[str, Any]]:
    """Re-emit the curated attack/lookalike rows from frozen_v2 as synthetic_adversarial."""
    rows: list[dict[str, Any]] = []
    for split in ("train", "val", "test"):
        p = REPO / "data" / "phase3" / "dataset" / "frozen_v2" / f"{split}.jsonl"
        for line in open(p):
            r = json.loads(line)
            if r.get("safe_or_attack") == "attack":
                rows.append(make_record(
                    premise=r["premise"], hypothesis=r["hypothesis"], label=r["label"],
                    family=r["family"], subfamily=r.get("subfamily", r["family"]),
                    authorization_field=r.get("authorization_field", "intent_constraint"),
                    evidence_field=r.get("evidence_field", "adversarial_merchant_evidence"),
                    source_dataset="razormesh_internal_adversarial",
                    source_record_id=r["record_id"],
                    source_license="project-internal",
                    source_kind="synthetic_adversarial",
                    split_group="adv_" + r.get("split_group", r.get("generator_parent_id", r["record_id"])),
                    difficulty=r.get("difficulty", "hard"),
                    safe_or_attack="attack",
                    template_family_id=r.get("template_family_id", ""),
                    entity_family_id=r.get("entity_family_id", ""),
                    metadata={"historical_split": split}))
    return rows[:cap]


# --------------------------------------------------------------------------
# leakage / dedup / assembly
# --------------------------------------------------------------------------
def dedup(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    seen_hash: set[str] = set()
    seen_pair: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    stats = {"exact_content_dups": 0, "normalized_pair_dups": 0}
    for r in rows:
        if r["content_sha256"] in seen_hash:
            stats["exact_content_dups"] += 1
            continue
        pair = (norm_text(r["premise"]), norm_text(r["hypothesis"]))
        if pair in seen_pair:
            stats["normalized_pair_dups"] += 1
            continue
        seen_hash.add(r["content_sha256"])
        seen_pair.add(pair)
        out.append(r)
    return out, stats


def validate(rows: list[dict[str, Any]]) -> list[str]:
    errs: list[str] = []
    forbidden_hyp_tokens = ("evidence:", "checkout shows", "the listing says")
    for r in rows:
        if r["label"] not in LABELS:
            errs.append(f"label {r['label']!r} {r['record_id']}")
        if not r["premise"].strip() or not r["hypothesis"].strip():
            errs.append(f"degenerate pair {r['record_id']}")
        if not canonical_guard(r["premise"], r["hypothesis"]):
            errs.append(f"orientation guard {r['record_id']}")
        if any(t in r["hypothesis"].lower() for t in forbidden_hyp_tokens):
            errs.append(f"hypothesis carries evidence prose {r['record_id']}")
        if len(r["premise"]) > 2400 or len(r["hypothesis"]) > 400:
            errs.append(f"oversized {r['record_id']}")
        if r["source_kind"] not in ("real_human_nli", "real_commerce", "human_reviewed", "deterministic_derived", "synthetic_adversarial"):
            errs.append(f"bad source_kind {r['record_id']}")
    return errs


def make_ood_row(r: dict[str, Any]) -> dict[str, Any]:
    """Tag an existing canonical row as fresh-OOD provenance (content preserved)."""
    out = dict(r)
    out["metadata"] = {**r.get("metadata", {}), "ood_role": "fresh_v2_untouched", "withheld": "family_or_entity"}
    return out


def main() -> int:
    random.seed(SEED)
    CORPUS.mkdir(parents=True, exist_ok=True)
    EVAL.mkdir(parents=True, exist_ok=True)

    review_candidates: list[dict[str, Any]] = []
    cnli, cnli_ood = load_contractnli()
    print("contractnli rows:", len(cnli), "| withheld-entity OOD rows:", len(cnli_ood))
    esci = esci_rows(review_candidates)
    print("esci rows:", len(esci), "| review candidates from esci:", len(review_candidates))
    seed, seed_excluded, family_ood = razormesh_seed()
    print("razormesh seed rows:", len(seed), "| excluded (orientation guard):", len(seed_excluded), seed_excluded[:3], "| withheld-family OOD rows:", len(family_ood))

    train_rows, dup_stats = dedup(cnli + esci + seed)
    print("global pre-split dedup:", dup_stats)
    # adversarial cap: <=10% of final train, computed on grouped-train only
    grouped = defaultdict(list)
    for r in train_rows:
        grouped[group_bucket(r["split_group"])].append(r)
    train_pool = grouped["train"] + grouped["val"] + grouped["test"]  # reassigned below after caps
    adv_all = internal_adversarial(cap=0)  # collect all, cap later
    n_real_train = len(grouped["train"])
    adv_cap = min(len(adv_all), int(n_real_train * 10 / 90))
    rng = random.Random(SEED)
    adv_train = rng.sample(adv_all, adv_cap) if adv_cap < len(adv_all) else adv_all
    # remaining adversarial rows (beyond cap) go to val/test pools as evaluation-only hard rows
    chosen_ids = {r["record_id"] for r in adv_train}
    adv_eval = [r for r in adv_all if r["record_id"] not in chosen_ids]

    all_rows: dict[str, list[dict[str, Any]]] = {"train": list(grouped["train"]), "val": list(grouped["val"]), "test": list(grouped["test"])}
    all_rows["train"].extend(adv_train)
    for split in ("val", "test"):
        all_rows[split].extend(adv_eval)
        # adversarial rows keep their own groups; move any that landed in train pool by bucket
    # regroup adversarial eval rows deterministically into val/test by hash
    fixed_eval = {"val": [], "test": []}
    for r in adv_eval:
        fixed_eval[group_bucket("adveval_" + r["split_group"])].append(r)
    all_rows["val"] = [r for r in all_rows["val"] if r["record_id"] not in {x["record_id"] for x in adv_eval}] + fixed_eval["val"]
    all_rows["test"] = [r for r in all_rows["test"] if r["record_id"] not in {x["record_id"] for x in adv_eval}] + fixed_eval["test"]

    totals = {}
    for split, rows in all_rows.items():
        rows, stats = dedup(rows)
        errs = validate(rows)
        if errs:
            print(f"VALIDATION ERRORS in {split}: {len(errs)}", errs[:5])
            return 1
        totals[split] = rows
        with open(CORPUS / f"{split}.jsonl", "w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n")
        labels = Counter(r["label"] for r in rows)
        kinds = Counter(r["source_kind"] for r in rows)
        fams = len({r["family"] for r in rows})
        groups = len({r["split_group"] for r in rows})
        print(f"{split}: rows={len(rows)} labels={dict(labels)} kinds={dict(kinds)} families={fams} groups={groups}")

    # ---- fresh OOD v2: withheld internal families + withheld real entities (never in corpus)
    ood = [make_ood_row(r) for r in family_ood] + [make_ood_row(r) for r in cnli_ood]
    ood, _ = dedup(ood)
    corpus_hashes = {r["content_sha256"] for r in train_rows}
    ood = [r for r in ood if r["content_sha256"] not in corpus_hashes]
    ood = ood[:400]
    with open(EVAL / "fresh_ood_v2.jsonl", "w") as f:
        for r in ood:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("fresh OOD v2 rows:", len(ood), "(withheld families + withheld entities)")

    # ---- review pack candidates (G human-review): ambiguous real rows first
    with open(CORPUS / "review_candidates.jsonl", "w") as f:
        for c in review_candidates[:900]:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print("review candidates:", min(len(review_candidates), 900))

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "built_from": "data/agentpay_ir_v2/RAW_DATA_MANIFEST.json",
        "orientation": "premise=evidence, hypothesis=authorization (canonical)",
        "counts": {s: len(r) for s, r in totals.items()},
        "seed": SEED,
    }
    (CORPUS / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print("manifest:", manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
