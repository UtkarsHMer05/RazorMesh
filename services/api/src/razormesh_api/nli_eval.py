"""P3-M28/M29/M30: NLI evaluation harness (model-agnostic, frozen).

Pure-Python metric + label-mapping core (unit-testable without torch);
model loading/inference lives in the eval SCRIPTS which import this module
and lazily import transformers inside functions.

Label maps pinned from official HF model cards (R-020):
- MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli: 0=entailment,1=neutral,
  2=contradiction
- cross-encoder/nli-deberta-v3-base:            0=contradiction,1=entailment,
  2=neutral

Both are NORMALIZED to the project space {entailment, neutral, contradiction}
before any metric is computed — a wrong card mapping would silently invert
labels, so each map is unit-tested against the card-declared order.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LABELS: tuple[str, str, str] = ("entailment", "neutral", "contradiction")

MODEL_LABEL_MAPS: dict[str, dict[int, str]] = {
    "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli": {
        0: "entailment",
        1: "neutral",
        2: "contradiction",
    },
    "cross-encoder/nli-deberta-v3-base": {
        0: "contradiction",
        1: "entailment",
        2: "neutral",
    },
}

# Fine-tuned artifact (P3-M35): map stored alongside the model in label_map.json


def normalize_label(raw_label: str) -> str:
    lab = raw_label.strip().upper()
    if lab.startswith("ENTAIL"):
        return "entailment"
    if lab.startswith("CONTRADIC"):
        return "contradiction"
    if lab.startswith("NEUTRAL"):
        return "neutral"
    raise ValueError(f"unknown NLI label {raw_label!r}")


def argmax_to_project_label(
    logits_or_probs_index: int,
    *,
    model_key: str | None = None,
    label_map: dict[str, str] | None = None,
) -> str:
    """Translate a model's argmax index into the project label space."""
    if label_map is not None:
        idx_map = {int(k): v for k, v in label_map.items()}
    elif model_key is not None:
        idx_map = MODEL_LABEL_MAPS[model_key]
    else:
        raise ValueError("either model_key or label_map required")
    return idx_map[int(logits_or_probs_index)]


@dataclass(frozen=True)
class ClassMetrics:
    precision: float
    recall: float
    f1: float
    support: int


@dataclass(frozen=True)
class EvalMetrics:
    n: int
    accuracy: float
    per_class: dict[str, ClassMetrics]
    macro_f1: float
    confusion: dict[str, dict[str, int]]

    def to_json(self) -> str:
        return json.dumps(
            {
                "n": self.n,
                "accuracy": round(self.accuracy, 6),
                "macro_f1": round(self.macro_f1, 6),
                "per_class": {
                    k: {
                        "precision": round(v.precision, 6),
                        "recall": round(v.recall, 6),
                        "f1": round(v.f1, 6),
                        "support": v.support,
                    }
                    for k, v in self.per_class.items()
                },
                "confusion": self.confusion,
                "labels_sha256": None,
            },
            indent=2,
        )


def compute_metrics(gold: list[str], pred: list[str]) -> EvalMetrics:
    assert len(gold) == len(pred) and gold, "metric input mismatch/empty"
    confusion: dict[str, dict[str, int]] = {g: {p: 0 for p in LABELS} for g in LABELS}
    for g, p in zip(gold, pred):
        confusion.setdefault(g, {q: 0 for q in LABELS})
        confusion[g][p] = confusion[g].get(p, 0) + 1

    per_class: dict[str, ClassMetrics] = {}
    f1s: list[float] = []
    correct = sum(1 for g, p in zip(gold, pred) if g == p)
    for label in LABELS:
        tp = sum(1 for g, p in zip(gold, pred) if g == label and p == label)
        fp = sum(1 for g, p in zip(gold, pred) if g != label and p == label)
        fn = sum(1 for g, p in zip(gold, pred) if g == label and p != label)
        support = sum(1 for g in gold if g == label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = ClassMetrics(precision, recall, f1, support)
        f1s.append(f1)

    macro_f1 = sum(f1s) / len(f1s) if f1s else 0.0
    return EvalMetrics(
        n=len(gold),
        accuracy=correct / len(gold),
        per_class=per_class,
        macro_f1=macro_f1,
        confusion=confusion,
    )


def iter_split(path: Path):
    for line in path.read_text().splitlines():
        if line.strip():
            yield json.loads(line)


def pair_text(row: dict[str, Any]) -> tuple[str, str]:
    return row["premise"], row["hypothesis"]


def content_id(premise: str, hypothesis: str) -> str:
    return hashlib.sha256(f"{premise}||{hypothesis}".encode()).hexdigest()[:16]
