#!/usr/bin/env python3
"""Cross-split near-duplicate + template-family overlap analysis (#20).

Extends the quality-gate near-duplicate analysis (which reported WITHIN-split
density) to the cross-split directions train↔val, train↔test and val↔test:

- exact normalized (premise, hypothesis) pair overlap;
- identical premise / identical hypothesis overlaps (the ContractNLI fixed-
  hypothesis effect is reported explicitly instead of hidden);
- near-duplicate pairs (Jaccard >= 0.85 over the combined token set) evaluated
  inside shared template families across splits;
- shared template_family_id / entity_family_id / split_group overlap counts.

If ContractNLI fixed hypotheses cannot be template-held-out (they span all
document groups by construction), that exception is documented in the report and
human gold + untouched OOD are treated as the stronger generalization benchmarks.

Output: docs/agentpay_ir_v2/NEAR_DUP_CROSS_SPLIT_REPORT.{json,md}
"""
from __future__ import annotations

import itertools
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "data/agentpay_ir_v2/corpus"
OUT_JSON = REPO / "docs/agentpay_ir_v2/NEAR_DUP_CROSS_SPLIT_REPORT.json"
OUT_MD = REPO / "docs/agentpay_ir_v2/NEAR_DUP_CROSS_SPLIT_REPORT.md"
JACCARD_THRESHOLD = 0.85


def norm(t: str) -> str:
    return re.sub(r"\W+", " ", t.lower()).strip()


def tokens(t: str) -> frozenset[str]:
    return frozenset(norm(t).split())


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def load() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for split in ("train", "val", "test"):
        out[split] = [json.loads(line) for line in (CORPUS / f"{split}.jsonl").read_text().splitlines()]
    return out


def main() -> int:
    data = load()
    rows = {s: [{**r, "_pair": (norm(r["premise"]), norm(r["hypothesis"])),
                 "_tok": tokens(r["premise"] + " " + r["hypothesis"])} for r in data[s]]
            for s in data}

    report: dict = {
        "analysis": "cross-split near-duplicate + template-family overlap (PRE-REVIEW FINAL CORRECTION #20)",
        "jaccard_threshold": JACCARD_THRESHOLD,
        "splits": {s: len(rs) for s, rs in rows.items()},
        "directions": {},
        "contractnli_exception": None,
    }

    for a, b in itertools.combinations(("train", "val", "test"), 2):
        ra, rb = rows[a], rows[b]
        pairs_a = {r["_pair"] for r in ra}
        pairs_b = {r["_pair"] for r in rb}
        prem_a = {r["_pair"][0] for r in ra}
        prem_b = {r["_pair"][0] for r in rb}
        hyp_a = {r["_pair"][1] for r in ra}
        hyp_b = {r["_pair"][1] for r in rb}
        groups_a = {r["split_group"] for r in ra}
        groups_b = {r["split_group"] for r in rb}
        tf_a: dict[str, list[dict]] = defaultdict(list)
        tf_b: dict[str, list[dict]] = defaultdict(list)
        for r in ra:
            if r.get("template_family_id"):
                tf_a[r["template_family_id"]].append(r)
        for r in rb:
            if r.get("template_family_id"):
                tf_b[r["template_family_id"]].append(r)
        shared_tfs = set(tf_a) & set(tf_b)
        near_pairs = []
        for tf in sorted(shared_tfs):
            for x, y in itertools.product(tf_a[tf], tf_b[tf]):
                j = jaccard(x["_tok"], y["_tok"])
                if j >= JACCARD_THRESHOLD:
                    near_pairs.append({"template_family": tf,
                                       f"{a}_record": x["record_id"], f"{b}_record": y["record_id"],
                                       "jaccard": round(j, 4)})
        ent_a = {r["entity_family_id"] for r in ra if r.get("entity_family_id")}
        ent_b = {r["entity_family_id"] for r in rb if r.get("entity_family_id")}
        report["directions"][f"{a}<->{b}"] = {
            f"rows_{a}": len(ra), f"rows_{b}": len(rb),
            "exact_pair_overlap": len(pairs_a & pairs_b),
            "same_premise_only": len(prem_a & prem_b),
            "same_hypothesis_only": len(hyp_a & hyp_b),
            "shared_split_groups": len(groups_a & groups_b),
            "shared_entity_families": len(ent_a & ent_b),
            "shared_template_families": len(shared_tfs),
            "rows_in_shared_template_families": {a: sum(len(v) for k, v in tf_a.items() if k in shared_tfs),
                                                 b: sum(len(v) for k, v in tf_b.items() if k in shared_tfs)},
            "near_duplicate_pairs_ge_threshold": len(near_pairs),
            "near_duplicate_top_families": dict(Counter(p["template_family"]
                                                        for p in near_pairs).most_common(10)),
            "max_jaccard_in_shared_families": max((p["jaccard"] for p in near_pairs), default=0.0),
            "near_dup_examples": sorted(near_pairs, key=lambda p: -p["jaccard"])[:5],
        }

    # ContractNLI fixed-hypothesis exception: quantify it honestly
    cnli_hyp: dict[str, set[str]] = defaultdict(set)
    cnli_by_hyp: dict[str, set[str]] = defaultdict(set)
    for s in rows:
        for r in rows[s]:
            if r["source_dataset"] == "contractnli":
                cnli_hyp[r["_pair"][1]].add(s)
                cnli_by_hyp[r["_pair"][1]].add(r["template_family_id"] or "none")
    cross_hyps = {h: sorted(ss) for h, ss in cnli_hyp.items() if len(ss) > 1}
    report["contractnli_exception"] = {
        "documented": True,
        "distinct_contractnli_hypotheses": len(cnli_hyp),
        "hypotheses_appearing_in_multiple_splits": len(cross_hyps),
        "note": ("ContractNLI premises share a small set of FIXED clause hypotheses; these cannot "
                 "be template-held-out across splits without destroying the real-human-NLI "
                 "component. Cross-split hypothesis overlap is therefore dominated by this "
                 "source and is reported, not hidden. Human-gold review cards and untouched "
                 "OOD are the stronger generalization benchmarks for these families."),
        "template_families_per_fixed_hypothesis_top5": dict(
            sorted(({h: len(fams) for h, fams in cnli_by_hyp.items()}).items(),
                   key=lambda kv: -kv[1])[:5]),
    }

    lines = [
        "# Cross-Split Near-Duplicate + Template-Family Overlap Report",
        "",
        f"**Corpus:** AgentPay-IR v2 frozen splits — "
        f"{report['splits']['train']} train / {report['splits']['val']} val / "
        f"{report['splits']['test']} test · near-dup rule: Jaccard >= "
        f"{JACCARD_THRESHOLD} (premise+hypothesis tokens) inside shared template families",
        "",
        "| direction | exact pair overlap | same premise | same hypothesis | shared TFs | near-dup pairs | max J |",
        "|---|---|---|---|---|---|---|",
    ]
    for d, m in report["directions"].items():
        lines.append(
            f"| {d} | {m['exact_pair_overlap']} | {m['same_premise_only']} "
            f"| {m['same_hypothesis_only']} | {m['shared_template_families']} "
            f"| {m['near_duplicate_pairs_ge_threshold']} | {m['max_jaccard_in_shared_families']:.2f} |")
    ce = report["contractnli_exception"]
    lines += [
        "",
        "## ContractNLI fixed-hypothesis exception (documented)",
        "",
        f"- distinct ContractNLI hypotheses: **{ce['distinct_contractnli_hypotheses']}**; "
        f"appearing in more than one split: **{ce['hypotheses_appearing_in_multiple_splits']}**.",
        "- Same-hypothesis overlap across splits is therefore EXPECTED for the ContractNLI",
        "  component (fixed clause hypotheses shared by many documents). It cannot be",
        "  template-held-out without discarding the real human NLI data. Per the correction",
        "  contract, **human-gold review cards and the untouched OOD set are the stronger",
        "  generalization benchmarks** for these families.",
        "",
        "## Zero-tolerance facts (must be 0)",
        "",
    ]
    for d, m in report["directions"].items():
        lines.append(f"- {d}: exact pair overlap = {m['exact_pair_overlap']}, "
                     f"shared split groups = {m['shared_split_groups']}, "
                     f"shared entity families = {m['shared_entity_families']}")
    lines += [
        "",
        "Near-duplicate pairs inside shared template families remain a TEMPLATE_OVERFIT_RISK",
        "indicator for the v2 training read (see QUALITY_GATES.json); they are disclosed,",
        "not hidden, and are cross-checked against the frozen selection rule at calibration.",
        "",
    ]
    OUT_JSON.write_text(json.dumps(report, indent=1))
    OUT_MD.write_text("\n".join(lines))
    print("wrote", OUT_JSON.name)
    for d, m in report["directions"].items():
        print(f"{d}: exact_pair={m['exact_pair_overlap']} same_hyp={m['same_hypothesis_only']} "
              f"shared_tfs={m['shared_template_families']} near_dup={m['near_duplicate_pairs_ge_threshold']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
