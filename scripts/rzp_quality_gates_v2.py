#!/usr/bin/env python3
"""AgentPay-IR v2 quality gates (PVB correction #14) — run before freezing any
final training set. Emits docs/agentpay_ir_v2/QUALITY_GATES.json + .md.

Gates: source distribution, difficulty distribution, honest real/human vs
deterministic/synthetic ratio, lexical shortcut analysis (unigram/bigram label
predictors), hypothesis-template concentration, premise-source concentration,
token-Jaccard near-duplicate check, family-coverage report.

Usage: services/api/.venv/bin/python scripts/rzp_quality_gates_v2.py [--corpus-dir NAME]
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs" / "agentpay_ir_v2"
CORPUS = REPO / "data" / "agentpay_ir_v2" / "corpus"


def norm(t: str) -> str:
    return re.sub(r"\W+", " ", t.lower()).strip()


def tokens(t: str) -> set[str]:
    return set(norm(t).split())


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus-dir", default=str(CORPUS))
    args = ap.parse_args()
    cdir = Path(args.corpus_dir)

    splits = {s: [json.loads(l) for l in open(cdir / f"{s}.jsonl")] for s in ("train", "val", "test")}
    report: dict = {"corpus_dir": str(cdir), "gates": {}}

    # ---- source + difficulty + honest ratio ----
    for s, rows in splits.items():
        report["gates"][s] = {
            "rows": len(rows),
            "source_distribution": dict(Counter(r["source_dataset"] for r in rows)),
            "source_kind_distribution": dict(Counter(r["source_kind"] for r in rows)),
            "difficulty_distribution": dict(Counter(r.get("difficulty", "unknown") for r in rows)),
            "label_distribution": dict(Counter(r["label"] for r in rows)),
        }
    train = splits["train"]
    n = len(train)
    real_human = sum(1 for r in train if r["source_kind"] in ("real_human_nli", "real_commerce", "human_reviewed"))
    deterministic = sum(1 for r in train if r["source_kind"] == "deterministic_derived")
    synthetic = sum(1 for r in train if r["source_kind"] == "synthetic_adversarial")
    report["honest_composition"] = {
        "real_or_human_derived_pct": round(100 * real_human / n, 1),
        "targeted_deterministic_internal_pct": round(100 * deterministic / n, 1),
        "synthetic_pct": round(100 * synthetic / n, 1),
        "claim": (f"train is {100 * real_human / n:.1f}% real/human-derived and "
                  f"{100 * deterministic / n:.1f}% targeted deterministic internal security/domain data"),
        "synthetic_cap_pct": 10,
        "synthetic_cap_ok": synthetic / n <= 0.10,
    }

    # ---- lexical shortcut analysis: tokens that perfectly predict a label ----
    shortcuts = []
    tok_labels: dict[str, set[str]] = defaultdict(set)
    tok_counts: Counter[str] = Counter()
    for r in train:
        for t in tokens(r["premise"]) | tokens(r["hypothesis"]):
            tok_labels[t].add(r["label"])
            tok_counts[t] += 1
    for t, labs in tok_labels.items():
        if len(labs) == 1 and tok_counts[t] >= 12:
            shortcuts.append({"token": t, "label": next(iter(labs)), "count": tok_counts[t]})
    shortcuts.sort(key=lambda x: -x["count"])
    report["lexical_shortcuts"] = {
        "count_over_12_occurrences": len(shortcuts),
        "top": shortcuts[:15],
        "note": "tokens appearing >=12 times with a single label; review for memorization shortcuts",
    }

    # ---- hypothesis-template concentration ----
    def templ(h: str) -> str:
        return re.sub(r"\b(₹|rs\.?|inr)?\s?\d[\d,\.]*\b", "#", h.lower())[:80]
    hyp_counter = Counter(templ(r["hypothesis"]) for r in train)
    top_hyp = hyp_counter.most_common(10)
    report["hypothesis_template_concentration"] = {
        "distinct_templates_80char": len(hyp_counter),
        "top10_share_pct": round(100 * sum(c for _, c in top_hyp) / n, 1),
        "top10": [{"template": t, "count": c} for t, c in top_hyp],
    }

    # ---- premise-source concentration ----
    prem_counter = Counter(norm(r["premise"])[:100] for r in train)
    report["premise_source_concentration"] = {
        "distinct_premise_prefixes_100char": len(prem_counter),
        "max_single_premise_count": prem_counter.most_common(1)[0][1],
        "top10_share_pct": round(100 * sum(c for _, c in prem_counter.most_common(10)) / n, 1),
    }

    # ---- token-Jaccard near-duplicate check within each split ----
    near_dup = {}
    for s, rows in splits.items():
        # deterministic sample for O(n^2) containment: compare within family buckets
        by_fam: dict[str, list[tuple[int, set[str]]]] = defaultdict(list)
        for i, r in enumerate(rows):
            by_fam[r["family"]].append((i, tokens(r["premise"]) | tokens(r["hypothesis"])))
        worst = 0.0
        worst_pair = None
        count85 = 0
        comparisons = 0
        for fam, items in by_fam.items():
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    comparisons += 1
                    if comparisons > 4_000_000:
                        break
                    ja = jaccard(items[i][1], items[j][1])
                    if ja >= 0.85:
                        count85 += 1
                    if ja > worst:
                        worst, worst_pair = ja, (rows[items[i][0]]["record_id"], rows[items[j][0]]["record_id"])
        near_dup[s] = {"max_intra_family_jaccard": round(worst, 3),
                       "pairs_ge_085": count85,
                       "comparisons": comparisons,
                       "worst_pair": worst_pair}
    report["near_duplicate_check"] = near_dup

    # ---- family coverage ----
    fam_rows: dict[str, set[str]] = defaultdict(set)
    for s, rows in splits.items():
        for r in rows:
            fam_rows[r["family"]].add(s)
    coverage = {f: sorted(v) for f, v in sorted(fam_rows.items())}
    report["family_coverage"] = {
        "families_total": len(coverage),
        "in_all_splits": sorted(f for f, v in coverage.items() if len(v) == 3),
        "train_only": sorted(f for f, v in coverage.items() if v == ["train"]),
        "coverage_map": coverage,
    }

    out_json = DOCS / "QUALITY_GATES.json"
    out_json.write_text(json.dumps(report, indent=1))
    lines = ["# AgentPay-IR v2 Quality Gates", "",
             f"Corpus: `{cdir}` · train rows: {n}", "",
             f"**Honest composition:** {report['honest_composition']['claim']}.", "",
             f"- Lexical shortcut tokens (>=12 occurrences, single label): **{len(shortcuts)}** (top: {shortcuts[:5]})",
             f"- Distinct hypothesis templates (80-char normalized): **{len(hyp_counter)}**, top-10 share {report['hypothesis_template_concentration']['top10_share_pct']}%",
             f"- Max single premise-prefix reuse: **{report['premise_source_concentration']['max_single_premise_count']}**",
             "- Near-duplicate (Jaccard>=0.85) within-split, family-bucketed: " + ", ".join(f"{s}={near_dup[s]['pairs_ge_085']}" for s in splits),
             f"- Families covered: **{len(coverage)}** (in all three splits: {len(report['family_coverage']['in_all_splits'])})", "",
             "Full machine-readable report: QUALITY_GATES.json"]
    (DOCS / "QUALITY_GATES.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
