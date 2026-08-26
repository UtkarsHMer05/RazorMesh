#!/usr/bin/env python3
"""P3-M37: calibrate semantic thresholds on the VALIDATION split only.

Policy shape (frozen after this run; PENDING_GOLD_VALIDATION):
    BLOCK       p_contradiction >= tau_block
    ENTAIL      p_contradiction <  tau_block AND p_entailment >= tau_entail
    CHALLENGE   otherwise

Objective (security-first, bounded friction):
    constraint: false-BLOCK rate on gold-entailment rows <= 0.05
    maximize F2 of the BLOCK class (recall-weighted); achieved precision is
    recorded verbatim even when low — downstream fusion only lets semantics
    STRICTEN deterministic RazorGuard decisions, and humans see every step.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL_KEY = "cross-encoder/nli-deberta-v3-base"
LOCAL = REPO_ROOT / "models" / "cross-encoder__nli-deberta-v3-base"
VAL = REPO_ROOT / "data" / "phase3" / "dataset" / "frozen_v1" / "val.jsonl"
OUT_DIR = REPO_ROOT / "data" / "phase3" / "policy"
MAX_FALSE_BLOCK_RATE = 0.05
BETA = 2.0


def action_for(p_contra: float, p_ent: float, tb: float, te: float) -> str:
    if p_contra >= tb:
        return "BLOCK"
    if p_ent >= te:
        return "ENTAIL"
    return "CHALLENGE"


def main() -> int:
    tok = AutoTokenizer.from_pretrained(str(LOCAL))
    model = AutoModelForSequenceClassification.from_pretrained(str(LOCAL))
    model.eval()

    rows = [json.loads(l) for l in VAL.read_text().splitlines() if l.strip()]
    probs_out: list[dict] = []
    for i in range(0, len(rows), 8):
        batch = rows[i : i + 8]
        feats = tok(
            [r["premise"] for r in batch],
            [r["hypothesis"] for r in batch],
            truncation=True,
            max_length=256,
            padding=True,
            return_tensors="pt",
        )
        with torch.no_grad():
            probs = torch.softmax(model(**feats).logits, -1)
        # project-space order for THIS checkpoint: 0=contradiction,1=entailment,2=neutral
        for r, p in zip(batch, probs.tolist(), strict=True):
            probs_out.append(
                {
                    "record_id": r["record_id"],
                    "gold": r["label"],
                    "p_contradiction": p[0],
                    "p_entailment": p[1],
                    "p_neutral": p[2],
                }
            )

    ent_total = sum(1 for r in probs_out if r["gold"] == "entailment")
    contra_total = sum(1 for r in probs_out if r["gold"] == "contradiction")

    best: dict | None = None
    best_score: tuple[float, float] | None = None
    for ti in range(36):
        tb = round(0.30 + 0.02 * ti, 2)
        for tj in range(13):
            te = round(0.40 + 0.05 * tj, 2)

            false_blocks = sum(
                1
                for r in probs_out
                if r["gold"] == "entailment"
                and action_for(r["p_contradiction"], r["p_entailment"], tb, te)
                == "BLOCK"
            )
            if ent_total and false_blocks / ent_total > MAX_FALSE_BLOCK_RATE:
                continue
            blocks = [
                r
                for r in probs_out
                if action_for(r["p_contradiction"], r["p_entailment"], tb, te)
                == "BLOCK"
            ]
            contra_caught = sum(1 for r in blocks if r["gold"] == "contradiction")
            recall = contra_caught / contra_total if contra_total else 0.0
            precision = (
                sum(1 for r in blocks if r["gold"] == "contradiction") / len(blocks)
                if blocks
                else 0.0
            )
            f2 = (
                (1 + BETA**2) * precision * recall / (BETA**2 * precision + recall)
                if precision + recall
                else 0.0
            )
            score = (round(f2, 4), round(recall, 4))
            cand = {
                "tau_block": tb,
                "tau_entail": te,
                "contradiction_recall_on_val": round(recall, 4),
                "block_precision_on_val": round(precision, 4),
                "block_f2_on_val": round(f2, 4),
                "false_blocks_on_val_entailment": false_blocks,
            }
            if best_score is None or score > best_score:
                best_score = score
                best = {**cand, "_score": score}

    assert best is not None, "no threshold pair satisfies the safety constraints"

    manifest = {
        "policy_version": "semantic-thresholds-v1",
        "model": MODEL_KEY,
        "calibrated_on": "validation split ONLY (never gold, never test)",
        "rows_used": len(rows),
        "selected": {k: v for k, v in best.items() if not k.startswith("_")},
        "constraints": {
            "max_false_block_rate_on_entailment": MAX_FALSE_BLOCK_RATE,
            "objective": f"F{BETA} of BLOCK class (recall-weighted)",
        },
        "action_rule": (
            "BLOCK if p_contradiction>=tau_block; else ENTAIL if "
            "p_entailment>=tau_entail; else CHALLENGE"
        ),
        "fusion_note": "semantics can only STRICTEN deterministic RazorGuard decisions",
        "gold_validation_status": "PENDING_GOLD_VALIDATION",
        "created_at_utc": datetime.now(UTC).isoformat(),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "semantic_thresholds.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest["selected"], indent=2))
    print("status:", manifest["gold_validation_status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
