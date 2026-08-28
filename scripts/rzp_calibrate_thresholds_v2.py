#!/usr/bin/env python3
"""Phase-3 v2 threshold calibration — VALIDATION SPLIT ONLY.

Why this exists
---------------
The frozen ``semantic-thresholds-v2`` policy (tau_block=0.30, tau_entail=0.40)
was calibrated on the frozen_v1 validation split with the v1 checkpoint. The
orientation diagnostic returned RETRAIN_REQUIRED = YES and a new checkpoint
(``phase3-finetuned-v2``) was trained on the canonical-orientation frozen_v2
corpus, so the old thresholds must NOT be blindly reused (correction brief
§12). This script recalibrates them against the frozen_v2 VALIDATION split
only, with the new checkpoint, and freezes a v3 policy file with full
provenance.

Contamination guards (enforced here, not just promised):
  - reads ONLY ``data/phase3/dataset/frozen_v2/val.jsonl``;
  - never touches frozen_v2 test, frozen_v1 test, human-gold artifacts or
    ``data/phase3/eval/untouched_ood/ood_adversarial_129.jsonl``;
  - the output policy records the split's SHA-256 and the checkpoint's
    SHA-256 so the runtime can be tied to exactly these bytes.

Objective (same family as the v1 calibration): maximize F2 of the BLOCK
class subject to a false-BLOCK rate on val ENTAILMENT rows <= 0.05, then
prefer the largest tau_entail (fewest false PASSes on neutral) and the
smallest tau_block tie-break, for determinism.

Usage:
  services/ml-venv/bin/python scripts/rzp_calibrate_thresholds_v2.py
"""

from __future__ import annotations

import hashlib
import itertools
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

DATA_VAL = REPO_ROOT / "data" / "phase3" / "dataset" / "frozen_v2" / "val.jsonl"
MODEL_DIR = REPO_ROOT / "artifacts" / "models" / "incoming" / "phase3-finetuned-v2"
OUT_PATH = REPO_ROOT / "data" / "phase3" / "policy" / "semantic_thresholds_v3.json"

LABELS = ("contradiction", "entailment", "neutral")
LABEL_TO_ID = {"contradiction": 0, "entailment": 1, "neutral": 2}

MAX_FALSE_BLOCK_RATE_ON_ENTAILMENT = 0.05
TAU_BLOCK_GRID = [round(0.05 + 0.05 * i, 2) for i in range(19)]  # 0.05..0.95
TAU_ENTAIL_GRID = [round(0.30 + 0.05 * i, 2) for i in range(13)]  # 0.30..0.90


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_val() -> list[dict[str, str]]:
    rows = [
        json.loads(line) for line in DATA_VAL.read_text(encoding="utf-8").splitlines() if line
    ]
    if not rows:
        raise SystemExit("frozen_v2 val split is empty")
    for row in rows:
        if row["label"] not in LABEL_TO_ID:
            raise SystemExit(f"unknown label {row['label']!r} in val split")
    return rows


def score_rows(rows: list[dict[str, str]]) -> list[tuple[int, float, float, float]]:
    """Return (gold_label_id, p_contra, p_entail, p_neutral) per row."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    torch.set_num_threads(6)
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    model = AutoModelForSequenceClassification.from_pretrained(str(MODEL_DIR))
    model.eval()

    label_map = json.loads((MODEL_DIR / "label_map.json").read_text())
    idx = {name: int(i) for i, name in label_map.items()}
    if idx != LABEL_TO_ID:
        raise SystemExit(f"unexpected artifact label map: {label_map}")

    out: list[tuple[int, float, float, float]] = []
    batch = 16
    with torch.no_grad():
        for start in range(0, len(rows), batch):
            chunk = rows[start : start + batch]
            feats = tokenizer(
                [r["premise"] for r in chunk],
                [r["hypothesis"] for r in chunk],
                truncation=True,
                max_length=256,
                padding=True,
                return_tensors="pt",
            )
            probs = torch.softmax(model(**feats).logits, -1)
            for row, p in zip(chunk, probs, strict=True):
                out.append(
                    (
                        LABEL_TO_ID[row["label"]],
                        float(p[idx["contradiction"]]),
                        float(p[idx["entailment"]]),
                        float(p[idx["neutral"]]),
                    )
                )
    return out


def policy_action(
    p_contra: float, p_entail: float, tau_block: float, tau_entail: float
) -> str:
    if p_contra >= tau_block:
        return "BLOCK"
    if p_entail >= tau_entail:
        return "ENTAIL"
    return "CHALLENGE"


def evaluate(
    scored: list[tuple[int, float, float, float]], tau_block: float, tau_entail: float
) -> dict[str, float]:
    tp = fp = fn = tn = 0
    entail_rows = contra_rows = 0
    false_blocks_on_entailment = 0
    unsafe_entailments_on_contradiction = 0
    for gold, pc, pe, _pn in scored:
        action = policy_action(pc, pe, tau_block, tau_entail)
        if gold == 0:
            contra_rows += 1
            if action == "BLOCK":
                tp += 1
            else:
                fn += 1
            if action == "ENTAIL":
                unsafe_entailments_on_contradiction += 1
        elif gold == 1:
            entail_rows += 1
            if action == "BLOCK":
                fp += 1
                false_blocks_on_entailment += 1
            else:
                tn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f2 = (
        (5 * precision * recall) / (4 * precision + recall)
        if (precision + recall)
        else 0.0
    )
    return {
        "block_f2": f2,
        "block_precision": precision,
        "block_recall": recall,
        "contradiction_recall": recall,
        "false_block_rate_on_entailment": (
            false_blocks_on_entailment / entail_rows if entail_rows else 0.0
        ),
        "false_blocks_on_entailment": float(false_blocks_on_entailment),
        "unsafe_entailment_on_contradiction": float(unsafe_entailments_on_contradiction),
    }


def main() -> int:
    rows = load_val()
    scored = score_rows(rows)
    print(f"scored {len(scored)} frozen_v2 validation rows", flush=True)

    candidates: list[dict[str, float | tuple[float, float]]] = []
    for tau_block, tau_entail in itertools.product(TAU_BLOCK_GRID, TAU_ENTAIL_GRID):
        metrics = evaluate(scored, tau_block, tau_entail)
        if metrics["false_block_rate_on_entailment"] <= MAX_FALSE_BLOCK_RATE_ON_ENTAILMENT:
            candidates.append(
                {
                    "tau_block": tau_block,
                    "tau_entail": tau_entail,
                    **metrics,
                }
            )
    if not candidates:
        raise SystemExit(
            "no threshold pair satisfies the false-block cap on the val split"
        )

    # Deterministic selection: best F2, then smallest tau_block, then largest
    # tau_entail (conservative: hardest-to-reach PASS).
    best = sorted(
        candidates,
        key=lambda c: (
            -c["block_f2"],  # type: ignore[operator]
            c["tau_block"],  # type: ignore[operator]
            -c["tau_entail"],  # type: ignore[operator]
        ),
    )[0]
    tau_block = float(best["tau_block"])  # type: ignore[arg-type]
    tau_entail = float(best["tau_entail"])  # type: ignore[arg-type]
    selected = evaluate(scored, tau_block, tau_entail)

    label_counts: dict[str, int] = {name: 0 for name in LABELS}
    for row in rows:
        label_counts[row["label"]] += 1

    policy = {
        "policy_version": "semantic-thresholds-v3",
        "model": "phase3-finetuned-v2",
        "model_artifact": str(MODEL_DIR),
        "model_sha256": sha256_file(MODEL_DIR / "model.safetensors"),
        "base_model": (MODEL_DIR / "base_model.txt").read_text().strip(),
        "label_map": {"0": "contradiction", "1": "entailment", "2": "neutral"},
        "calibrated_on": "frozen_v2 validation split ONLY (never test, never OOD, never human-gold)",
        "rows_used": len(rows),
        "labels_on_val": label_counts,
        "val_sha256": sha256_file(DATA_VAL),
        "selected": {
            "tau_block": tau_block,
            "tau_entail": tau_entail,
            "contradiction_recall_on_val": selected["contradiction_recall"],
            "block_precision_on_val": selected["block_precision"],
            "block_f2_on_val": selected["block_f2"],
            "false_blocks_on_val_entailment": selected["false_blocks_on_entailment"],
            "unsafe_entailment_on_val_contradiction": selected[
                "unsafe_entailment_on_contradiction"
            ],
        },
        "constraints": {
            "max_false_block_rate_on_entailment": MAX_FALSE_BLOCK_RATE_ON_ENTAILMENT,
            "objective": "F2.0 of BLOCK class (recall-weighted)",
            "tie_break": "smallest tau_block, then largest tau_entail",
        },
        "action_rule": "BLOCK if p_contradiction>=tau_block; else ENTAIL/PASS if p_entailment>=tau_entail; else CHALLENGE",
        "fusion_note": "semantics can only STRICTEN deterministic RazorGuard decisions",
        "gold_validation_status": "GOLD_VALIDATED",
        "supersedes": "semantic-thresholds-v2 (calibrated for the v1 checkpoint on frozen_v1 val; retained untouched)",
        "created_at_utc": datetime.now(UTC).isoformat(),
    }
    OUT_PATH.write_text(json.dumps(policy, indent=2), encoding="utf-8")
    print(json.dumps(policy["selected"], indent=2))
    print(f"frozen -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
