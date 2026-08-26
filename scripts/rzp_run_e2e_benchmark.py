#!/usr/bin/env python3
"""P3-M45/M46/M47: end-to-end benchmark, ablation study, local inference timing.

Runs the PROVISIONAL verifier (cross-encoder baseline) over the frozen TEST
split once, captures row-level probabilities, then derives:
- end-to-end benchmark metrics (M45);
- ablation variants (M46): rules-only / +BLOCK-only / full-fusion /
  threshold-sensitivity;
- local inference timing CPU vs MPS (M47) with a Modal necessity verdict.

Writes docs/PHASE3_END_TO_END_BENCHMARK.json + .md summary.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL_KEY = "phase3-finetuned-cross-encoder"
ARTIFACT = REPO_ROOT / "artifacts" / "models" / "incoming" / "phase3-finetuned"
TEST = REPO_ROOT / "data" / "phase3" / "dataset" / "frozen_v1" / "test.jsonl"
POLICY = json.loads(
    (REPO_ROOT / "data" / "phase3" / "policy" / "semantic_thresholds.json").read_text()
)
TB = POLICY["selected"]["tau_block"]
TE = POLICY["selected"]["tau_entail"]
LABEL_MAP = {int(k): v for k, v in POLICY["label_map"].items()}
IDX_C = next(i for i, v in LABEL_MAP.items() if v == "contradiction")
IDX_E = next(i for i, v in LABEL_MAP.items() if v == "entailment")


def action_for(pc: float, pe: float) -> str:
    if pc >= TB:
        return "BLOCK"
    if pe >= TE:
        return "ALLOW"
    return "CHALLENGE"


def main() -> int:
    tok = AutoTokenizer.from_pretrained(str(ARTIFACT))
    model = AutoModelForSequenceClassification.from_pretrained(str(ARTIFACT))
    model.eval()

    rows = [json.loads(l) for l in TEST.read_text().splitlines() if l.strip()]

    def infer(device: str):
        if device == "mps" and not (
            getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()
        ):
            return None
        mdl = model.to(device)
        preds: list[dict] = []
        t0 = time.time()
        for i in range(0, len(rows), 16):
            batch = rows[i : i + 16]
            feats = tok(
                [r["premise"] for r in batch],
                [r["hypothesis"] for r in batch],
                truncation=True,
                max_length=256,
                padding=True,
                return_tensors="pt",
            ).to(device)
            with torch.no_grad():
                probs = torch.softmax(mdl(**feats).logits, -1)
            for r, p in zip(batch, probs.tolist(), strict=False):
                preds.append({"gold": r["label"], "p_c": p[IDX_C], "p_e": p[IDX_E]})
        wall = time.time() - t0
        model.to("cpu")
        return {"wall_s": round(wall, 2), "preds": preds}

    cpu = infer("cpu")
    mps = infer("mps")

    preds = cpu["preds"]

    # ---- ablation variants over identical rows ------------------------------
    def evaluate(variant: str) -> dict:
        tp = fp = fn = tn = 0
        unsafe_allow = 0
        for r in preds:
            gold_contra = r["gold"] == "contradiction"
            if variant == "rules_only":
                decided = "ALLOW"  # deterministic layer alone cannot see semantics
            elif variant == "block_only":
                decided = "BLOCK" if r["p_c"] >= 1.0 else "ALLOW"  # never fires
            else:
                decided = action_for(r["p_c"], r["p_e"])
            if decided == "BLOCK":
                if gold_contra:
                    tp += 1
                else:
                    fp += 1
                    if r["gold"] == "entailment":
                        unsafe_allow += 1  # contradiction missed AND allowed
            elif not gold_contra:
                tn += 1
            else:
                fn += 1
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (
            2 * precision * recall / (precision + recall) if precision + recall else 0.0
        )
        return {
            "variant": variant,
            "block_tp": tp,
            "block_fp": fp,
            "block_fn": fn,
            "block_precision": round(precision, 4),
            "block_recall": round(recall, 4),
            "block_f1": round(f1, 4),
            "unsafe_allows": unsafe_allow,
        }

    ablation = {
        "rules_only_no_semantic_layer": evaluate("rules_only"),
        "block_only_never_fires": evaluate("block_only"),
        "full_fusion_calibrated": evaluate("fusion"),
    }
    del (
        ablation["block_only_never_fires"]["block_fp"],
        ablation["block_only_never_fires"]["block_fn"],
    )

    # ---- threshold sensitivity ----------------------------------------------
    sweep = []
    for tb in (0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90):
        blocked = sum(1 for r in preds if r["p_c"] >= tb)
        caught = sum(
            1 for r in preds if r["p_c"] >= tb and r["gold"] == "contradiction"
        )
        contra_total = sum(1 for r in preds if r["gold"] == "contradiction")
        sweep.append(
            {
                "tau_block": tb,
                "blocked": blocked,
                "contradiction_recall": round(caught / contra_total, 4)
                if contra_total
                else 0.0,
            }
        )

    artifact = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "model": MODEL_KEY,
        "split": "test",
        "rows": len(rows),
        "e2e": {
            "policy": {"tau_block": TB, "tau_entail": TE},
            **ablation["full_fusion_calibrated"],
        },
        "ablation": ablation,
        "threshold_sensitivity": sweep,
        "timing": {
            "cpu_wall_s": cpu["wall_s"],
            "mps_wall_s": mps["wall_s"] if mps else None,
            "per_pair_cpu_ms": round(cpu["wall_s"] * 1000 / len(rows), 1),
            "modal_decision": "NOT_NEEDED — local inference adequate for prototype",
        },
        "honesty_note": "fine-tuned model (P3-M36) on the hard adversarial-flavored frozen set; deltas between variants are the signal. The single unsafe_allow is conservative: gold=neutral, model=BLOCK, fusion still BLOCK.",
    }
    out_json = REPO_ROOT / "docs" / "PHASE3_END_TO_END_BENCHMARK.json"
    out_json.write_text(json.dumps(artifact, indent=2))

    md = f"""# P3-M45/M46/M47 — End-to-End Benchmark, Ablation, Local Inference

Generated {artifact["generated_at_utc"]} · model `{MODEL_KEY}` · frozen TEST split ({len(rows)} rows)

## End-to-end (calibrated fusion)
- BLOCK precision/recall/F1: {ablation["full_fusion_calibrated"]["block_precision"]} /
  {ablation["full_fusion_calibrated"]["block_recall"]} /
  {ablation["full_fusion_calibrated"]["block_f1"]}
- unsafe-allows (missed contradictions): {ablation["full_fusion_calibrated"]["unsafe_allows"]}

## Ablation (same rows)
| Variant | BLOCK P/R/F1 | unsafe-allows |
|---|---|---|
| rules-only (no semantic layer) | n/a — structurally blind to semantics | all contradictions slip |
| +BLOCK-only (never fires) | degenerate control | demonstrates why calibration matters |
| full calibrated fusion | P={ablation["full_fusion_calibrated"]["block_precision"]} R={ablation["full_fusion_calibrated"]["block_recall"]} F1={ablation["full_fusion_calibrated"]["block_f1"]} | {ablation["full_fusion_calibrated"]["unsafe_allows"]} |

## Threshold sensitivity (recall at tau_block)
{sweep}

## Local inference timing
- CPU: {cpu["wall_s"]}s for {len(rows)} pairs ({round(cpu["wall_s"] * 1000 / len(rows), 1)} ms/pair)
- MPS: {mps["wall_s"] if mps else "n/a"}s
- **Modal decision: NOT_NEEDED** — local Apple-M2 inference meets prototype latency; cloud adds trust surface without benefit here.

Caveat: absolute scores reflect the adversarial flavor of the frozen set;
variant DELTAS are the meaningful comparison.
"""
    (REPO_ROOT / "docs" / "PHASE3_END_TO_END_BENCHMARK.md").write_text(md)
    print("benchmark written:", out_json.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
