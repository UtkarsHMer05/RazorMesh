#!/usr/bin/env python3
"""Phase-3 paired orientation diagnostic (read-only; no retraining, no wiring).

Question answered:

    Does the EXISTING frozen fine-tuned checkpoint generalize correctly to the
    canonical runtime NLI orientation?

Method: for the SAME underlying semantic case, the SAME hypothesis and the SAME
ground-truth label, only the premise orientation changes.

    LEGACY    premise = 'Session context — human request: "<H>". <EVIDENCE>.'
    CANONICAL premise = <EVIDENCE> only

The hypothesis is byte-identical across the two representations, so any metric
delta is attributable to orientation rather than to case, wording or label.

Development data only: the frozen validation split plus a deterministic
stratified subset of the training split (to reach families validation lacks).
The untouched OOD set and the frozen test split are NEVER loaded here; they are
reserved for post-correction evaluation.

Writes:
  docs/PHASE3_ORIENTATION_DIAGNOSTIC.md
  docs/PHASE3_ORIENTATION_DIAGNOSTIC.json

Usage:
  services/ml-venv/bin/python scripts/rzp_orientation_diagnostic.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

ARTIFACT = REPO_ROOT / "artifacts" / "models" / "incoming" / "phase3-finetuned"
FROZEN = REPO_ROOT / "data" / "phase3" / "dataset" / "frozen_v1"
POLICY_PATH = REPO_ROOT / "data" / "phase3" / "policy" / "semantic_thresholds.json"
DOCS = REPO_ROOT / "docs"

LABELS = ("contradiction", "entailment", "neutral")
IDX = {"contradiction": 0, "entailment": 1, "neutral": 2}

REQUIRED_ARTIFACT_FILES = (
    "model.safetensors",
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "label_map.json",
    "base_model.txt",
)

LEGACY_PREFIX = "Session context — human request:"

# Deterministic evidence-sentence starters observed in the frozen corpus. Used
# only for rows whose quoted human request contains extra double quotes.
EVIDENCE_STARTERS = (
    "Product page states:",
    "Product description field contains",
    "Listing provides only a photo",
    "Listing shows",
    "Listing states",
    "Cart preview states:",
    "Checkout page states:",
    "Checkout disclosure states",
    "Checkout says",
    "Seller name on the invoice",
    "Deal page:",
    "The terms say",
    "Terms page",
    "Invoice line",
    "Product title reads",
    "Renewal notice",
    "A product field says",
    "Merchant text says",
    "Seller text says",
    "A warning says",
    "The listing shows",
)

NUM_RE = re.compile(r"(?:₹|\$|€|£|\b(?:INR|USD|EUR|GBP)\b)\s?[\d,.]+|\b[\d,.]+\s*(?:euros?|rupees|dollars?)")
WORD_RE = re.compile(r"[a-z]{4,}")
STOPWORDS = frozenset(
    {
        "this",
        "that",
        "with",
        "from",
        "have",
        "been",
        "only",
        "into",
        "upon",
        "about",
        "after",
        "before",
        "human",
        "authorized",
        "authoriz",
        "purchase",
        "purchased",
        "purchase_",
        "within",
        "hard",
        "ceiling",
        "limited",
        "forbade",
        "specific",
        "states",
        "product",
        "listing",
        "checkout",
        "page",
        "priced",
        "price",
        "stock",
        "sold",
        "standard",
        "marketplace",
        "terms",
        "flash",
        "sale",
    }
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# 1. Artifact verification (fail loudly before spending any inference time)
# ---------------------------------------------------------------------------


def verify_artifact() -> dict[str, Any]:
    missing = [f for f in REQUIRED_ARTIFACT_FILES if not (ARTIFACT / f).exists()]
    if missing:
        raise SystemExit(f"artifact missing required files: {missing}")
    config = json.loads((ARTIFACT / "config.json").read_text())
    label_map = {int(k): v for k, v in json.loads((ARTIFACT / "label_map.json").read_text()).items()}
    base_model = (ARTIFACT / "base_model.txt").read_text().strip()
    id2label = {int(k): v for k, v in config.get("id2label", {}).items()}
    if label_map != {0: "contradiction", 1: "entailment", 2: "neutral"}:
        raise SystemExit(f"unexpected label_map ordering: {label_map}")
    if id2label != label_map:
        raise SystemExit(f"label_map.json disagrees with config.id2label: {label_map} vs {id2label}")
    # transformers 5.x omits num_labels from the saved config when it equals the
    # label2id-derived count, so derive it rather than demanding the key.
    label2id = {k: int(v) for k, v in config.get("label2id", {}).items()}
    num_labels = config.get("num_labels", len(label2id))
    if num_labels != 3 or config.get("model_type") != "deberta-v2":
        raise SystemExit(f"unexpected config: num_labels={num_labels}")
    if sorted(label2id.values()) != [0, 1, 2] or {v: k for k, v in label2id.items()} != label_map:
        raise SystemExit(f"config.label2id disagrees with label_map.json: {label2id}")
    return {
        "artifact_dir": str(ARTIFACT.relative_to(REPO_ROOT)),
        "declared_base_model": base_model,
        "config_architectures": config.get("architectures"),
        "config_model_type": config.get("model_type"),
        "config_num_labels": num_labels,
        "config_transformers_version": config.get("transformers_version"),
        "config_max_position_embeddings": config.get("max_position_embeddings"),
        "config_vocab_size": config.get("vocab_size"),
        "label_map": {str(k): v for k, v in sorted(label_map.items())},
        "label_map_agrees_with_config_id2label": True,
        "files": {
            f: {"bytes": (ARTIFACT / f).stat().st_size, "sha256": sha256_file(ARTIFACT / f)}
            for f in sorted(REQUIRED_ARTIFACT_FILES)
        },
    }


# ---------------------------------------------------------------------------
# 2. Legacy premise -> (human request, evidence)
# ---------------------------------------------------------------------------


def parse_legacy_premise(premise: str) -> tuple[str, str] | None:
    """Split a LEGACY premise into its embedded request and its evidence.

    Returns None when the row is not in LEGACY form (already canonical).
    """
    if not premise.startswith(LEGACY_PREFIX):
        return None
    body = premise[len(LEGACY_PREFIX) :].strip()
    if not body.startswith('"'):
        return None
    if body.count('"') == 2:
        close = body.index('"', 1)
        request = body[1:close]
        evidence = body[close + 1 :].lstrip(". ").strip()
        return (request, evidence) if evidence else None
    best: tuple[int, str] | None = None
    for starter in EVIDENCE_STARTERS:
        idx = body.find(starter)
        if idx > 0 and (best is None or idx < best[0]):
            best = (idx, starter)
    if best is None:
        return None
    idx = best[0]
    head = body[:idx].rstrip()
    if not head.endswith('"'):
        return None
    return (head[1 : head.rindex('"')], body[idx:].strip())


def content_tokens(text: str) -> set[str]:
    """Numbers/currency strings plus low-frequency content words."""
    toks = {re.sub(r"\s+", "", m.group(0)).lower() for m in NUM_RE.finditer(text)}
    toks |= {w for w in WORD_RE.findall(text.lower()) if w not in STOPWORDS}
    return toks


@dataclass
class PairedCase:
    case_id: str
    family: str
    label: str
    difficulty: str
    source_split: str
    transform: str  # "stripped" | "noop_control"
    legacy_premise: str
    canonical_premise: str
    hypothesis: str
    determinable: bool
    overlap: float = 0.0


def build_paired_case(row: dict[str, Any], source_split: str) -> PairedCase | None:
    label = row.get("label")
    if label not in LABELS:
        return None
    premise = str(row.get("premise", ""))
    hypothesis = str(row.get("hypothesis", ""))
    parsed = parse_legacy_premise(premise)
    if parsed is None:
        canonical = premise
        transform = "noop_control"
    else:
        canonical = parsed[1]
        transform = "stripped"
    if not hypothesis.strip() or not canonical.strip():
        return None
    hyp_tokens = content_tokens(hypothesis)
    ev_tokens = content_tokens(canonical)
    inter = hyp_tokens & ev_tokens
    overlap = len(inter) / len(hyp_tokens) if hyp_tokens else 0.0
    return PairedCase(
        case_id=str(row.get("record_id", "")),
        family=str(row.get("family", "unknown")),
        label=str(label),
        difficulty=str(row.get("difficulty", "")),
        source_split=source_split,
        transform=transform,
        legacy_premise=premise,
        canonical_premise=canonical,
        hypothesis=hypothesis,
        # "Determinable" = the evidence sentence alone carries information that
        # bears on the hypothesis, so the frozen label is still the correct
        # canonical answer rather than an artifact of the request text.
        determinable=overlap >= 0.5,
        overlap=round(overlap, 3),
    )


def stratified_train_sample(rows: list[dict[str, Any]], per_cell: int, seed: int) -> list[dict[str, Any]]:
    """Deterministically take `per_cell` rows per (family, label) cell."""
    cells: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        cells[(str(row.get("family")), str(row.get("label")))].append(row)
    rng = random.Random(seed)
    picked: list[dict[str, Any]] = []
    for key in sorted(cells):
        pool = sorted(cells[key], key=lambda r: str(r.get("record_id")))
        rng.shuffle(pool)
        picked.extend(pool[:per_cell])
    return sorted(picked, key=lambda r: str(r.get("record_id")))


# ---------------------------------------------------------------------------
# 3. Inference
# ---------------------------------------------------------------------------


class Scorer:
    def __init__(self, device: str, max_length: int, batch_size: int) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self.torch_version = torch.__version__
        self.device = device
        self.max_length = max_length
        self.batch_size = batch_size
        self.tokenizer = AutoTokenizer.from_pretrained(str(ARTIFACT))
        self.model = AutoModelForSequenceClassification.from_pretrained(str(ARTIFACT))
        self.model.to(device)
        self.model.eval()

    def score(self, pairs: list[tuple[str, str]]) -> list[tuple[float, float, float]]:
        import torch

        out: list[tuple[float, float, float]] = []
        with torch.inference_mode():
            for start in range(0, len(pairs), self.batch_size):
                chunk = pairs[start : start + self.batch_size]
                feats = self.tokenizer(
                    [p for p, _ in chunk],
                    [h for _, h in chunk],
                    truncation=True,
                    max_length=self.max_length,
                    padding=True,
                    return_tensors="pt",
                ).to(self.device)
                probs = torch.softmax(self.model(**feats).logits.float(), dim=-1)
                for row in probs.tolist():
                    out.append(tuple(float(x) for x in row))
        return out


# ---------------------------------------------------------------------------
# 4. Metrics
# ---------------------------------------------------------------------------


def prf(gold: list[str], pred: list[str], cls: str) -> dict[str, float]:
    tp = sum(1 for g, p in zip(gold, pred, strict=True) if g == cls and p == cls)
    fp = sum(1 for g, p in zip(gold, pred, strict=True) if g != cls and p == cls)
    fn = sum(1 for g, p in zip(gold, pred, strict=True) if g == cls and p != cls)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {
        "support": tp + fn,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def nli_metrics(cases: list[PairedCase], preds: list[str]) -> dict[str, Any]:
    gold = [c.label for c in cases]
    correct = sum(1 for g, p in zip(gold, preds, strict=True) if g == p)
    per_class = {cls: prf(gold, preds, cls) for cls in LABELS}
    present = [cls for cls in LABELS if per_class[cls]["support"] > 0]
    macro_f1 = sum(per_class[c]["f1"] for c in present) / len(present) if present else 0.0
    confusion = {g: {p: 0 for p in LABELS} for g in LABELS}
    for g, p in zip(gold, preds, strict=True):
        confusion[g][p] += 1
    contra = [i for i, c in enumerate(cases) if c.label == "contradiction"]
    entail = [i for i, c in enumerate(cases) if c.label == "entailment"]
    neutral = [i for i, c in enumerate(cases) if c.label == "neutral"]
    return {
        "n": len(cases),
        "accuracy": round(correct / len(cases), 4) if cases else None,
        "macro_f1": round(macro_f1, 4),
        "per_class": per_class,
        "confusion_matrix_gold_rows_pred_cols": confusion,
        "contradiction_recall": per_class["contradiction"]["recall"],
        "entailment_recall": per_class["entailment"]["recall"],
        "neutral_recall": per_class["neutral"]["recall"],
        "unsafe_entailment_on_contradiction": sum(1 for i in contra if preds[i] == "entailment"),
        "contradiction_predicted_as": {
            "contradiction": sum(1 for i in contra if preds[i] == "contradiction"),
            "neutral": sum(1 for i in contra if preds[i] == "neutral"),
            "entailment": sum(1 for i in contra if preds[i] == "entailment"),
        },
        "entailment_predicted_as": {
            "contradiction": sum(1 for i in entail if preds[i] == "contradiction"),
            "neutral": sum(1 for i in entail if preds[i] == "neutral"),
            "entailment": sum(1 for i in entail if preds[i] == "entailment"),
        },
        "neutral_promoted_to_entailment": sum(1 for i in neutral if preds[i] == "entailment"),
        "neutral_predicted_as": {
            "contradiction": sum(1 for i in neutral if preds[i] == "contradiction"),
            "neutral": sum(1 for i in neutral if preds[i] == "neutral"),
            "entailment": sum(1 for i in neutral if preds[i] == "entailment"),
        },
    }


def policy_metrics(
    cases: list[PairedCase], probs: list[tuple[float, float, float]], tau_block: float, tau_entail: float
) -> dict[str, Any]:
    """Frozen semantic-threshold policy, applied unchanged to both orientations."""

    def act(pc: float, pe: float) -> str:
        if pc >= tau_block:
            return "BLOCK"
        if pe >= tau_entail:
            return "PASS"
        return "CHALLENGE"

    actions = [act(pc, pe) for pc, pe, _ in probs]
    dist = dict(sorted(Counter(actions).items()))
    unsafe_allow = sum(1 for c, a in zip(cases, actions, strict=True) if c.label == "contradiction" and a == "PASS")
    contra_not_blocked = sum(
        1 for c, a in zip(cases, actions, strict=True) if c.label == "contradiction" and a != "BLOCK"
    )
    entail_blocked = sum(1 for c, a in zip(cases, actions, strict=True) if c.label == "entailment" and a == "BLOCK")
    neutral_passed = sum(1 for c, a in zip(cases, actions, strict=True) if c.label == "neutral" and a == "PASS")
    return {
        "tau_block": tau_block,
        "tau_entail": tau_entail,
        "action_distribution": dist,
        "contradiction_unsafe_allow": unsafe_allow,
        "contradiction_not_blocked": contra_not_blocked,
        "contradiction_support": sum(1 for c in cases if c.label == "contradiction"),
        "entailment_false_block": entail_blocked,
        "entailment_support": sum(1 for c in cases if c.label == "entailment"),
        "neutral_passed": neutral_passed,
        "neutral_support": sum(1 for c in cases if c.label == "neutral"),
    }


def flip_analysis(cases: list[PairedCase], legacy: list[str], canonical: list[str]) -> dict[str, Any]:
    unchanged = changed = 0
    correct_to_incorrect = incorrect_to_correct = 0
    per_class_flip: dict[str, dict[str, int]] = {
        cls: {"unchanged": 0, "changed": 0, "correct_to_incorrect": 0, "incorrect_to_correct": 0}
        for cls in LABELS
    }
    matrix: dict[str, dict[str, int]] = {g: {p: 0 for p in LABELS} for g in LABELS}
    dangerous: list[str] = []
    for case, lg, cn in zip(cases, legacy, canonical, strict=True):
        same = lg == cn
        was_right, now_right = lg == case.label, cn == case.label
        bucket = per_class_flip[case.label]
        matrix[lg][cn] += 1
        if same:
            unchanged += 1
            bucket["unchanged"] += 1
        else:
            changed += 1
            bucket["changed"] += 1
            if was_right and not now_right:
                correct_to_incorrect += 1
                bucket["correct_to_incorrect"] += 1
            elif not was_right and now_right:
                incorrect_to_correct += 1
                bucket["incorrect_to_correct"] += 1
        if case.label == "contradiction" and lg == "contradiction" and cn == "entailment":
            dangerous.append(case.case_id)
    return {
        "n": len(cases),
        "unchanged": unchanged,
        "changed": changed,
        "change_rate": round(changed / len(cases), 4) if cases else None,
        "correct_to_incorrect": correct_to_incorrect,
        "incorrect_to_correct": incorrect_to_correct,
        "per_class": per_class_flip,
        "legacy_pred_rows_canonical_pred_cols": matrix,
        "dangerous_contradiction_to_entailment_ids": dangerous,
        "dangerous_contradiction_to_entailment_count": len(dangerous),
    }


def per_family(cases: list[PairedCase], legacy: list[str], canonical: list[str]) -> dict[str, Any]:
    by_family: dict[str, list[int]] = defaultdict(list)
    for i, case in enumerate(cases):
        by_family[case.family].append(i)
    out: dict[str, Any] = {}
    for family, idxs in sorted(by_family.items()):
        sub = [cases[i] for i in idxs]
        l_acc = sum(1 for i in idxs if legacy[i] == cases[i].label) / len(idxs)
        c_acc = sum(1 for i in idxs if canonical[i] == cases[i].label) / len(idxs)
        contra = [i for i in idxs if cases[i].label == "contradiction"]
        l_cr = sum(1 for i in contra if legacy[i] == "contradiction") / len(contra) if contra else None
        c_cr = sum(1 for i in contra if canonical[i] == "contradiction") / len(contra) if contra else None
        out[family] = {
            "n": len(idxs),
            "labels": dict(sorted(Counter(c.label for c in sub).items())),
            "legacy_accuracy": round(l_acc, 4),
            "canonical_accuracy": round(c_acc, 4),
            "delta_accuracy": round(c_acc - l_acc, 4),
            "contradiction_support": len(contra),
            "legacy_contradiction_recall": l_cr,
            "canonical_contradiction_recall": c_cr,
            "delta_contradiction_recall": (
                round(c_cr - l_cr, 4) if l_cr is not None and c_cr is not None else None
            ),
        }
    return out


def decide(metrics: dict[str, Any], flips: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """Apply the brief's safety-first decision rule; never accuracy alone."""
    d_f1 = metrics["delta_macro_f1"]
    d_cr = metrics["delta_contradiction_recall"]
    dangerous = flips["dangerous_contradiction_to_entailment_count"]
    unsafe_delta = policy["canonical"]["contradiction_unsafe_allow"] - policy["legacy"]["contradiction_unsafe_allow"]
    not_blocked_delta = (
        policy["canonical"]["contradiction_not_blocked"] - policy["legacy"]["contradiction_not_blocked"]
    )
    reasons: list[str] = []
    if d_f1 is not None and d_f1 <= -0.05:
        reasons.append(f"macro F1 degraded by {abs(d_f1):.4f} (>= 0.05)")
    if d_cr is not None and d_cr <= -0.05:
        reasons.append(f"contradiction recall degraded by {abs(d_cr):.4f} (>= 0.05)")
    if dangerous > 0:
        reasons.append(f"{dangerous} gold contradictions flipped contradiction->entailment")
    if unsafe_delta > 0:
        reasons.append(f"policy unsafe-allow on contradictions rose by {unsafe_delta}")
    if not_blocked_delta > 0:
        reasons.append(f"gold contradictions escaping BLOCK rose by {not_blocked_delta}")
    return {
        "retrain_required": bool(reasons),
        "reasons": reasons,
        "thresholds_used": {
            "macro_f1_degradation": 0.05,
            "contradiction_recall_degradation": 0.05,
            "any_unsafe_contradiction_to_entailment": True,
            "any_policy_escape": True,
        },
    }


@dataclass
class RunState:
    cases: list[PairedCase] = field(default_factory=list)
    legacy_probs: list[tuple[float, float, float]] = field(default_factory=list)
    canonical_probs: list[tuple[float, float, float]] = field(default_factory=list)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cpu", help="cpu or mps (cpu is the measured-safe default)")
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--train-per-cell", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    artifact = verify_artifact()
    policy = json.loads(POLICY_PATH.read_text())
    tau_block = float(policy["selected"]["tau_block"])
    tau_entail = float(policy["selected"]["tau_entail"])

    val_rows = load_jsonl(FROZEN / "val.jsonl")
    train_rows = stratified_train_sample(load_jsonl(FROZEN / "train.jsonl"), args.train_per_cell, args.seed)

    cases: list[PairedCase] = []
    skipped = 0
    for source, rows in (("val", val_rows), ("train_stratified", train_rows)):
        for row in rows:
            case = build_paired_case(row, source)
            if case is None:
                skipped += 1
                continue
            cases.append(case)
    if not cases:
        raise SystemExit("no paired cases built")

    t0 = time.perf_counter()
    scorer = Scorer(args.device, args.max_length, args.batch_size)
    load_seconds = round(time.perf_counter() - t0, 2)

    def run(orientation: str) -> list[tuple[float, float, float]]:
        key = "legacy_premise" if orientation == "legacy" else "canonical_premise"
        pairs = [(getattr(c, key), c.hypothesis) for c in cases]
        started = time.perf_counter()
        probs = scorer.score(pairs)
        elapsed = time.perf_counter() - started
        print(
            f"{orientation}: {len(probs)} pairs in {elapsed:.1f}s "
            f"({1000 * elapsed / max(1, len(probs)):.1f} ms/pair)",
            file=sys.stderr,
        )
        return probs

    legacy_probs = run("legacy")
    canonical_probs = run("canonical")

    legacy_pred = [LABELS[int(max(range(3), key=lambda i: p[i]))] for p in legacy_probs]
    canonical_pred = [LABELS[int(max(range(3), key=lambda i: p[i]))] for p in canonical_probs]

    def subset(pred_ok: bool) -> list[PairedCase]:
        return [c for c in cases if c.determinable is pred_ok]

    def slice_metrics(idx: list[int]) -> dict[str, Any]:
        sub = [cases[i] for i in idx]
        return {
            "legacy": nli_metrics(sub, [legacy_pred[i] for i in idx]),
            "canonical": nli_metrics(sub, [canonical_pred[i] for i in idx]),
        }

    all_idx = list(range(len(cases)))
    det_idx = [i for i, c in enumerate(cases) if c.determinable]
    overall = slice_metrics(all_idx)
    determinable = slice_metrics(det_idx)
    val_idx = [i for i, c in enumerate(cases) if c.source_split == "val"]
    train_idx = [i for i, c in enumerate(cases) if c.source_split == "train_stratified"]

    def delta(a: dict[str, Any], b: dict[str, Any], key: str) -> float | None:
        if a[key] is None or b[key] is None:
            return None
        return round(b[key] - a[key], 4)

    flips = flip_analysis(cases, legacy_pred, canonical_pred)
    pol_legacy = policy_metrics(cases, legacy_probs, tau_block, tau_entail)
    pol_canonical = policy_metrics(cases, canonical_probs, tau_block, tau_entail)
    summary = {
        "legacy_macro_f1": overall["legacy"]["macro_f1"],
        "canonical_macro_f1": overall["canonical"]["macro_f1"],
        "delta_macro_f1": delta(overall["legacy"], overall["canonical"], "macro_f1"),
        "legacy_accuracy": overall["legacy"]["accuracy"],
        "canonical_accuracy": overall["canonical"]["accuracy"],
        "delta_accuracy": delta(overall["legacy"], overall["canonical"], "accuracy"),
        "legacy_contradiction_recall": overall["legacy"]["contradiction_recall"],
        "canonical_contradiction_recall": overall["canonical"]["contradiction_recall"],
        "delta_contradiction_recall": delta(
            overall["legacy"], overall["canonical"], "contradiction_recall"
        ),
        "legacy_unsafe_entailment_on_contradiction": overall["legacy"][
            "unsafe_entailment_on_contradiction"
        ],
        "canonical_unsafe_entailment_on_contradiction": overall["canonical"][
            "unsafe_entailment_on_contradiction"
        ],
        "delta_unsafe_entailment_count": overall["canonical"]["unsafe_entailment_on_contradiction"]
        - overall["legacy"]["unsafe_entailment_on_contradiction"],
    }
    decision = decide(summary, flips, {"legacy": pol_legacy, "canonical": pol_canonical})

    report: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "purpose": "Decide whether the frozen checkpoint generalizes to the canonical runtime orientation.",
        "scope_guards": {
            "retrained": False,
            "runtime_wired": False,
            "thresholds_changed": False,
            "dataset_files_modified": False,
            "ood_loaded": False,
            "frozen_test_loaded": False,
            "phase4_touched": False,
            "ui_touched": False,
        },
        "artifact": artifact,
        "runtime": {
            "device": args.device,
            "torch_version": scorer.torch_version,
            "max_length": args.max_length,
            "batch_size": args.batch_size,
            "model_cold_load_seconds": load_seconds,
        },
        "policy": {
            "path": str(POLICY_PATH.relative_to(REPO_ROOT)),
            "sha256": sha256_file(POLICY_PATH),
            "policy_version": policy["policy_version"],
            "tau_block": tau_block,
            "tau_entail": tau_entail,
            "applied_unchanged": True,
        },
        "dataset_hashes": {
            "val": sha256_file(FROZEN / "val.jsonl"),
            "train": sha256_file(FROZEN / "train.jsonl"),
        },
        "diagnostic_set": {
            "paired_n": len(cases),
            "rows_skipped": skipped,
            "by_source_split": dict(sorted(Counter(c.source_split for c in cases).items())),
            "by_transform": dict(sorted(Counter(c.transform for c in cases).items())),
            "by_label": dict(sorted(Counter(c.label for c in cases).items())),
            "by_family": dict(sorted(Counter(c.family for c in cases).items())),
            "by_difficulty": dict(sorted(Counter(c.difficulty for c in cases).items())),
            "determinable_n": len(det_idx),
            "not_determinable_n": len(cases) - len(det_idx),
            "train_cells_per_family_label": args.train_per_cell,
            "seed": args.seed,
        },
        "summary": summary,
        "metrics_all_paired": overall,
        "metrics_determinable_subset": determinable,
        "metrics_val_only": slice_metrics(val_idx),
        "metrics_train_stratified_only": slice_metrics(train_idx),
        "noop_control": _control(cases, legacy_pred, canonical_pred),
        "policy_legacy": pol_legacy,
        "policy_canonical": pol_canonical,
        "paired_flips": flips,
        "per_family": per_family(cases, legacy_pred, canonical_pred),
        "decision": decision,
        "cases": [
            {
                "case_id": c.case_id,
                "family": c.family,
                "label": c.label,
                "source_split": c.source_split,
                "transform": c.transform,
                "determinable": c.determinable,
                "legacy_pred": lp,
                "canonical_pred": cp,
                "legacy_probs": [round(x, 4) for x in lpr],
                "canonical_probs": [round(x, 4) for x in cpr],
            }
            for c, lp, cp, lpr, cpr in zip(
                cases, legacy_pred, canonical_pred, legacy_probs, canonical_probs, strict=True
            )
        ],
    }

    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "PHASE3_ORIENTATION_DIAGNOSTIC.json").write_text(json.dumps(report, indent=2) + "\n")
    (DOCS / "PHASE3_ORIENTATION_DIAGNOSTIC.md").write_text(_markdown(report))
    print(json.dumps({"summary": summary, "decision": decision}, indent=2))
    return 0


def _control(cases: list[PairedCase], legacy: list[str], canonical: list[str]) -> dict[str, Any]:
    idx = [i for i, c in enumerate(cases) if c.transform == "noop_control"]
    return {
        "n": len(idx),
        "note": "Rows already canonical in the frozen corpus: legacy and canonical inputs are byte-identical, "
        "so any flip here is harness nondeterminism rather than orientation.",
        "flips": sum(1 for i in idx if legacy[i] != canonical[i]),
    }


def _markdown(r: dict[str, Any]) -> str:
    s = r["summary"]
    lines: list[str] = []
    add = lines.append
    add("# Phase-3 paired orientation diagnostic")
    add("")
    add(f"Generated: `{r['generated_at_utc']}` by `scripts/rzp_orientation_diagnostic.py`.")
    add("")
    add("**Question:** does the existing frozen checkpoint generalize to the canonical runtime NLI")
    add("orientation? Read-only. No retraining, no runtime wiring, no threshold or dataset change.")
    add("")
    add("## RETRAIN_REQUIRED = " + ("YES" if r["decision"]["retrain_required"] else "NO"))
    add("")
    for reason in r["decision"]["reasons"] or ["no material orientation mismatch detected"]:
        add(f"- {reason}")
    add("")
    add("## Headline")
    add("")
    add("| metric | legacy (training) | canonical (runtime) | delta |")
    add("|---|---:|---:|---:|")
    add(f"| accuracy | {s['legacy_accuracy']} | {s['canonical_accuracy']} | {s['delta_accuracy']} |")
    add(f"| macro F1 | {s['legacy_macro_f1']} | {s['canonical_macro_f1']} | {s['delta_macro_f1']} |")
    add(
        f"| contradiction recall | {s['legacy_contradiction_recall']} | "
        f"{s['canonical_contradiction_recall']} | {s['delta_contradiction_recall']} |"
    )
    add(
        f"| unsafe entailment on gold contradiction | "
        f"{s['legacy_unsafe_entailment_on_contradiction']} | "
        f"{s['canonical_unsafe_entailment_on_contradiction']} | "
        f"{s['delta_unsafe_entailment_count']} |"
    )
    add("")
    d = r["diagnostic_set"]
    add("## Paired diagnostic set")
    add("")
    add(f"- paired cases: **{d['paired_n']}** (rows skipped: {d['rows_skipped']})")
    add(f"- by source: `{json.dumps(d['by_source_split'])}`")
    add(f"- by transform: `{json.dumps(d['by_transform'])}`")
    add(f"- by label: `{json.dumps(d['by_label'])}`")
    add(f"- families covered: {len(d['by_family'])}")
    add(f"- evidence-determinable: {d['determinable_n']} / not determinable: {d['not_determinable_n']}")
    add(f"- device `{r['runtime']['device']}`, torch `{r['runtime']['torch_version']}`, "
        f"cold load `{r['runtime']['model_cold_load_seconds']}s`")
    add("")
    add("The hypothesis string is byte-identical across the two representations; only the premise")
    add("orientation changes. Ground-truth labels are carried over unchanged.")
    add("")
    add("## Per-class detail")
    add("")
    add("| class | support | legacy P/R/F1 | canonical P/R/F1 |")
    add("|---|---:|---|---|")
    for cls in LABELS:
        lm = r["metrics_all_paired"]["legacy"]["per_class"][cls]
        cm = r["metrics_all_paired"]["canonical"]["per_class"][cls]
        add(
            f"| {cls} | {lm['support']} | {lm['precision']}/{lm['recall']}/{lm['f1']} | "
            f"{cm['precision']}/{cm['recall']}/{cm['f1']} |"
        )
    add("")
    add("### Confusion matrices (rows = gold, cols = predicted)")
    add("")
    for side in ("legacy", "canonical"):
        add(f"- **{side}**: `{json.dumps(r['metrics_all_paired'][side]['confusion_matrix_gold_rows_pred_cols'])}`")
    add("")
    add("### Where gold contradictions went")
    add("")
    for side in ("legacy", "canonical"):
        add(f"- **{side}**: `{json.dumps(r['metrics_all_paired'][side]['contradiction_predicted_as'])}`")
    add("")
    add("## Frozen threshold policy (unchanged)")
    add("")
    add(f"`tau_block={r['policy']['tau_block']}`, `tau_entail={r['policy']['tau_entail']}`, "
        f"policy `{r['policy']['policy_version']}`.")
    add("")
    add("| policy outcome | legacy | canonical |")
    add("|---|---:|---:|")
    for act in ("PASS", "CHALLENGE", "BLOCK"):
        add(
            f"| {act} | {r['policy_legacy']['action_distribution'].get(act, 0)} | "
            f"{r['policy_canonical']['action_distribution'].get(act, 0)} |"
        )
    add(
        f"| gold contradiction → unsafe PASS | {r['policy_legacy']['contradiction_unsafe_allow']} | "
        f"{r['policy_canonical']['contradiction_unsafe_allow']} |"
    )
    add(
        f"| gold contradiction escaping BLOCK | {r['policy_legacy']['contradiction_not_blocked']}"
        f"/{r['policy_legacy']['contradiction_support']} | "
        f"{r['policy_canonical']['contradiction_not_blocked']}"
        f"/{r['policy_canonical']['contradiction_support']} |"
    )
    add(
        f"| gold entailment false BLOCK | {r['policy_legacy']['entailment_false_block']}"
        f"/{r['policy_legacy']['entailment_support']} | "
        f"{r['policy_canonical']['entailment_false_block']}"
        f"/{r['policy_canonical']['entailment_support']} |"
    )
    add(
        f"| gold neutral wrongly PASS | {r['policy_legacy']['neutral_passed']}"
        f"/{r['policy_legacy']['neutral_support']} | "
        f"{r['policy_canonical']['neutral_passed']}/{r['policy_canonical']['neutral_support']} |"
    )
    add("")
    f = r["paired_flips"]
    add("## Paired flips (same case, orientation is the only variable)")
    add("")
    add(f"- unchanged: **{f['unchanged']}**, changed: **{f['changed']}** "
        f"(change rate {f['change_rate']})")
    add(f"- correct → incorrect: **{f['correct_to_incorrect']}**")
    add(f"- incorrect → correct: **{f['incorrect_to_correct']}**")
    add(f"- **gold contradiction, legacy=contradiction, canonical=entailment: "
        f"{f['dangerous_contradiction_to_entailment_count']}** (most dangerous failure mode)")
    add(f"- no-op control flips: {r['noop_control']['flips']} of {r['noop_control']['n']}")
    add("")
    add("| gold class | unchanged | changed | correct→incorrect | incorrect→correct |")
    add("|---|---:|---:|---:|---:|")
    for cls in LABELS:
        pc = f["per_class"][cls]
        add(
            f"| {cls} | {pc['unchanged']} | {pc['changed']} | {pc['correct_to_incorrect']} | "
            f"{pc['incorrect_to_correct']} |"
        )
    add("")
    add("## Per-family degradation")
    add("")
    add("| family | n | legacy acc | canonical acc | Δacc | Δcontradiction recall |")
    add("|---|---:|---:|---:|---:|---:|")
    for family, row in sorted(
        r["per_family"].items(), key=lambda kv: (kv[1]["delta_accuracy"] or 0, kv[0])
    ):
        add(
            f"| `{family}` | {row['n']} | {row['legacy_accuracy']} | {row['canonical_accuracy']} | "
            f"{row['delta_accuracy']} | {row['delta_contradiction_recall']} |"
        )
    add("")
    add("## Held-out contamination guards")
    add("")
    add("- `data/phase3/eval/untouched_ood/ood_adversarial_129.jsonl`: **not loaded** by this run.")
    add("- `data/phase3/dataset/frozen_v1/test.jsonl`: **not loaded** by this run.")
    add("- Train-derived cells measure generalization on already-seen cases, which can only")
    add("  *understate* orientation risk. Val-only numbers are reported separately for that reason.")
    add("")
    add("## Val-only and train-only slices")
    add("")
    for name in ("metrics_val_only", "metrics_train_stratified_only", "metrics_determinable_subset"):
        blk = r[name]
        add(
            f"- `{name}`: legacy acc {blk['legacy']['accuracy']} / F1 {blk['legacy']['macro_f1']} / "
            f"contra-recall {blk['legacy']['contradiction_recall']} (n={blk['legacy']['n']}); "
            f"canonical acc {blk['canonical']['accuracy']} / F1 {blk['canonical']['macro_f1']} / "
            f"contra-recall {blk['canonical']['contradiction_recall']}"
        )
    add("")
    add("## Artifact provenance")
    add("")
    a = r["artifact"]
    add(f"- declared base model: `{a['declared_base_model']}`")
    add(f"- architectures: `{a['config_architectures']}`, model_type `{a['config_model_type']}`")
    add(f"- label map: `{json.dumps(a['label_map'])}` (agrees with `config.id2label`)")
    add(f"- `transformers` version recorded in config: `{a['config_transformers_version']}`")
    add("")
    add("| file | bytes | SHA-256 |")
    add("|---|---:|---|")
    for name, meta in a["files"].items():
        add(f"| `{name}` | {meta['bytes']} | `{meta['sha256']}` |")
    add("")
    add("Per-case predictions are in `docs/PHASE3_ORIENTATION_DIAGNOSTIC.json` under `cases`.")
    add("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
