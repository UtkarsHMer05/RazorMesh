#!/usr/bin/env python3
"""P3-M37 (re-frozen): calibrate semantic thresholds on the VALIDATION split
ONLY, using the FINE-TUNED model from the artifact directory.

Policy shape (frozen after this run; gold_validation_status -> GOLD_VALIDATED):
    BLOCK       p_contradiction >= tau_block
    ENTAIL      p_contradiction <  tau_block AND p_entailment >= tau_entail
    CHALLENGE   otherwise

Objective (security-first, bounded friction; unchanged from prior M37):
    constraint: false-BLOCK rate on gold-entailment rows <= 0.05
    maximize F2 of the BLOCK class (recall-weighted).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

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
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--artifact",
        type=Path,
        default=REPO_ROOT / "artifacts" / "models" / "incoming" / "phase3-finetuned",
    )
    ap.add_argument(
        "--model-id",
        default="phase3-finetuned-cross-encoder",
        help="Model id recorded in the policy manifest",
    )
    ap.add_argument(
        "--label-map-key",
        choices=["c_e_n", "e_n_c"],
        default="c_e_n",
        help="Project-space index order of the artifact (c_e_n = baseline-B / "
        "fine-tuned order; e_n_c = baseline-A order).",
    )
    ap.add_argument(
        "--gold-status",
        choices=["GOLD_VALIDATED", "PENDING_GOLD_VALIDATION"],
        default="GOLD_VALIDATED",
    )
    args = ap.parse_args()

    if not (args.artifact / "config.json").exists():
        print(f"artifact dir missing config.json: {args.artifact}")
        return 1
    if not (args.artifact / "label_map.json").exists():
        print(f"artifact dir missing label_map.json: {args.artifact}")
        return 1

    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    label_map_raw = json.loads((args.artifact / "label_map.json").read_text())
    label_map = {int(k): v for k, v in label_map_raw.items()}
    idx_contradiction = next(i for i, v in label_map.items() if v == "contradiction")
    idx_entailment = next(i for i, v in label_map.items() if v == "entailment")
    idx_neutral = next(i for i, v in label_map.items() if v == "neutral")

    print(f"loading model from {args.artifact}")
    tok = AutoTokenizer.from_pretrained(str(args.artifact))
    model = AutoModelForSequenceClassification.from_pretrained(str(args.artifact))
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
        for r, p in zip(batch, probs.tolist(), strict=True):
            probs_out.append(
                {
                    "record_id": r["record_id"],
                    "gold": r["label"],
                    "p_contradiction": p[idx_contradiction],
                    "p_entailment": p[idx_entailment],
                    "p_neutral": p[idx_neutral],
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
        "policy_version": "semantic-thresholds-v2",
        "model": args.model_id,
        "model_artifact": str(args.artifact),
        "base_model": (args.artifact / "base_model.txt").read_text().strip(),
        "label_map": label_map_raw,
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
        "gold_validation_status": args.gold_status,
        "created_at_utc": datetime.now(UTC).isoformat(),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "semantic_thresholds.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest["selected"], indent=2))
    print("status:", manifest["gold_validation_status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
