#!/usr/bin/env python3
"""AgentPay-IR v2 runtime policy calibration — VALIDATION SPLIT ONLY (LOCKED).

Why this exists
---------------
The deployed runtime policy ``semantic-thresholds-v3`` (tau_block=0.05,
tau_entail=0.90) was calibrated for the PRE_V2 checkpoint
(``phase3-finetuned-v2``, sha256 163864e0…) on the pre-correction frozen_v2
validation split. Its provenance pins THAT model's sha256. When the verified
AgentPay-IR v2 artifact is activated (backend ``deberta_v2``), the runtime
must use a policy whose provenance binds THE ACTIVE ARTIFACT — reusing the v3
file would put a contradictory model hash in every audit record.

This script recalibrates the thresholds against the FINAL corpus validation
split ONLY, with the verified v2 artifact, and freezes a v4 policy file with
full provenance. It runs BEFORE any frozen evaluation and never reads the
frozen test split, human gold, or fresh OOD — so no frozen result can
influence it (master prompt: thresholds are never tuned from frozen results).

Contamination guards (enforced here, not just promised):
  - reads ONLY ``data/agentpay_ir_v2/corpus/final/val.jsonl``;
  - never touches corpus/final/test.jsonl, GOLD_FROZEN_V3.jsonl,
    fresh_ood_v2.jsonl, or any eval/ artifact;
  - the output policy records the split's SHA-256 and the artifact's
    model-weight SHA-256 so the runtime can be tied to exactly these bytes.

Objective (identical family to the v3 calibration): maximize F2 of the BLOCK
class subject to a false-BLOCK rate on val ENTAILMENT rows <= 0.05; tie-break
smallest tau_block, then largest tau_entail, for determinism. The artifact's
own label_map.json drives index orientation.

One-shot: refuses to overwrite an existing v4 policy file.

Usage (AFTER M1 artifact promotion):
  services/api/.venv/bin/python scripts/rzp_calibrate_thresholds_v4.py \
      --artifact artifacts/models/incoming/agentpay-ir-v2-finetuned
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

DATA_VAL = REPO_ROOT / "data" / "agentpay_ir_v2" / "corpus" / "final" / "val.jsonl"
EXPECTED_VAL_SHA256 = "cf308d9e1d32bc16501f2061e89f4e7d0860a5966180d42618056022f9e7e067"
EXPECTED_VAL_ROWS = 2261
OUT_PATH = REPO_ROOT / "data" / "phase3" / "policy" / "semantic_thresholds_v4.json"

LABELS = ("contradiction", "entailment", "neutral")

MAX_FALSE_BLOCK_RATE_ON_ENTAILMENT = 0.05
TAU_BLOCK_GRID = [round(0.05 + 0.05 * i, 2) for i in range(19)]  # 0.05..0.95
TAU_ENTAIL_GRID = [round(0.30 + 0.05 * i, 2) for i in range(13)]  # 0.30..0.90


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_val() -> list[dict[str, str]]:
    digest = sha256_file(DATA_VAL)
    if digest != EXPECTED_VAL_SHA256:
        raise SystemExit(
            f"val split hash mismatch:\n  expected {EXPECTED_VAL_SHA256}\n  actual   {digest}"
        )
    rows = [
        json.loads(line)
        for line in DATA_VAL.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != EXPECTED_VAL_ROWS:
        raise SystemExit(f"val row count {len(rows)} != {EXPECTED_VAL_ROWS}")
    for row in rows:
        if row["label"] not in LABELS:
            raise SystemExit(f"unknown label {row['label']!r} in val split")
    return rows


def score_rows(
    artifact: Path, rows: list[dict[str, str]]
) -> tuple[list[tuple[str, float, float, float]], dict[str, str]]:
    """Return (gold_label, p_contra, p_entail, p_neutral) per row + label map."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(artifact))
    model = AutoModelForSequenceClassification.from_pretrained(str(artifact))
    model.eval()
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model.to(device)

    label_map = {int(k): str(v) for k, v in json.loads((artifact / "label_map.json").read_text()).items()}
    if set(label_map.values()) != set(LABELS) or len(label_map) != 3:
        raise SystemExit(f"unexpected artifact label map: {label_map}")
    idx = {name: i for i, name in label_map.items()}

    out: list[tuple[str, float, float, float]] = []
    batch = 32
    with torch.inference_mode():
        for start in range(0, len(rows), batch):
            chunk = rows[start : start + batch]
            feats = tokenizer(
                [r["premise"] for r in chunk],
                [r["hypothesis"] for r in chunk],
                truncation=True,
                max_length=256,
                padding=True,
                return_tensors="pt",
            ).to(device)
            probs = torch.softmax(model(**feats).logits, -1).to("cpu")
            for row, p in zip(chunk, probs, strict=True):
                out.append(
                    (
                        str(row["label"]),
                        float(p[idx["contradiction"]]),
                        float(p[idx["entailment"]]),
                        float(p[idx["neutral"]]),
                    )
                )
            print(f"  scored {min(start + batch, len(rows))}/{len(rows)}", flush=True)
    return out, {str(i): name for i, name in label_map.items()}


def policy_action(
    p_contra: float, p_entail: float, tau_block: float, tau_entail: float
) -> str:
    if p_contra >= tau_block:
        return "BLOCK"
    if p_entail >= tau_entail:
        return "ENTAIL"
    return "CHALLENGE"


def evaluate(
    scored: list[tuple[str, float, float, float]], tau_block: float, tau_entail: float
) -> dict[str, float]:
    tp = fp = fn = tn = 0
    entail_rows = contra_rows = 0
    false_blocks_on_entailment = 0
    unsafe_entailments_on_contradiction = 0
    for gold, pc, pe, _pn in scored:
        action = policy_action(pc, pe, tau_block, tau_entail)
        if gold == "contradiction":
            contra_rows += 1
            if action == "BLOCK":
                tp += 1
            else:
                fn += 1
            if action == "ENTAIL":
                unsafe_entailments_on_contradiction += 1
        elif gold == "entailment":
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
        "unsafe_entailment_on_contradiction": float(
            unsafe_entailments_on_contradiction
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--artifact",
        type=Path,
        default=REPO_ROOT / "artifacts/models/incoming/agentpay-ir-v2-finetuned",
    )
    args = ap.parse_args()
    artifact = args.artifact.resolve()

    if OUT_PATH.exists():
        print(f"ONE-SHOT VIOLATION: policy file already exists: {OUT_PATH}")
        return 2

    rows = load_val()
    print(f"calibrating on {len(rows)} FINAL-corpus validation rows", flush=True)
    scored, label_map_out = score_rows(artifact, rows)
    print(f"scored {len(scored)} rows with artifact {artifact}", flush=True)

    candidates: list[dict[str, float | tuple[float, float]]] = []
    for tau_block, tau_entail in itertools.product(TAU_BLOCK_GRID, TAU_ENTAIL_GRID):
        metrics = evaluate(scored, tau_block, tau_entail)
        if metrics["false_block_rate_on_entailment"] <= MAX_FALSE_BLOCK_RATE_ON_ENTAILMENT:
            candidates.append({"tau_block": tau_block, "tau_entail": tau_entail, **metrics})
    if not candidates:
        raise SystemExit("no threshold pair satisfies the false-block cap on the val split")

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
        label_counts[str(row["label"])] += 1

    weights = sorted(artifact.glob("*.safetensors"))
    if not weights:
        raise SystemExit(f"no *.safetensors in {artifact}")

    policy = {
        "policy_version": "semantic-thresholds-v4",
        "model": "agentpay-ir-v2",
        "model_artifact": str(artifact),
        "model_sha256": sha256_file(weights[0]),
        "base_model": (artifact / "base_model.txt").read_text().strip(),
        "label_map": label_map_out,
        "calibrated_on": "FINAL corpus validation split ONLY (never test, never OOD, never human-gold)",
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
        "calibration_order_note": "executed BEFORE any frozen-eval contact; never tuned from test/gold/OOD results",
        "supersedes": "semantic-thresholds-v3 (calibrated for the PRE_V2 checkpoint phase3-finetuned-v2; retained untouched)",
        "created_at_utc": datetime.now(UTC).isoformat(),
    }
    OUT_PATH.write_text(json.dumps(policy, indent=2), encoding="utf-8")
    print(json.dumps(policy["selected"], indent=2))
    print(f"frozen -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
