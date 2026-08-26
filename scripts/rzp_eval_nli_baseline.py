#!/usr/bin/env python3
"""P3-M28/M29: zero-shot NLI baseline evaluation on the FROZEN split.

Runs the selected HF model over premise/hypothesis pairs of one frozen split,
normalizes argmax through the card-pinned label map, computes metrics with the
shared pure core, and writes a metrics artifact.

Usage (from repo root):
  services/ml-venv/bin/python scripts/rzp_eval_nli_baseline.py --model A --split val
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

MODEL_KEYS = {
    "A": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
    "B": "cross-encoder/nli-deberta-v3-base",
}
FROZEN = REPO_ROOT / "data" / "phase3" / "dataset" / "frozen_v1"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["A", "B"], required=True)
    ap.add_argument("--split", choices=["val", "test", "train"], default="test")
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="cap rows (0 = all)")
    args = ap.parse_args()

    import torch  # heavy: lazy
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    model_key = MODEL_KEYS[args.model]
    label_map = {
        str(k): v
        for k, v in __import__("razormesh_api.nli_eval", fromlist=["MODEL_LABEL_MAPS"])
        .MODEL_LABEL_MAPS[model_key]
        .items()
    }

    local_dir = REPO_ROOT / "models" / model_key.replace("/", "__")
    if local_dir.exists():
        src = str(local_dir)
        print(f"loading model from local cache: {src}")
    else:
        src = model_key  # HF hub download (authorized)

    tokenizer = AutoTokenizer.from_pretrained(src)
    model = AutoModelForSequenceClassification.from_pretrained(src)
    model.eval()

    rows = [
        json.loads(line)
        for line in (FROZEN / f"{args.split}.jsonl").read_text().splitlines()
        if line.strip()
    ]
    if args.limit:
        rows = rows[: args.limit]

    from razormesh_api.nli_eval import compute_metrics

    gold: list[str] = []
    pred: list[str] = []
    t0 = time.time()
    for i in range(0, len(rows), args.batch):
        batch = rows[i : i + args.batch]
        features = tokenizer(
            [r["premise"] for r in batch],
            [r["hypothesis"] for r in batch],
            truncation=True,
            max_length=256,
            padding=True,
            return_tensors="pt",
        )
        with torch.no_grad():
            logits = model(**features).logits
        probs = torch.softmax(logits, dim=-1)
        confs, idxs = probs.max(dim=-1)
        for r, idx, conf in zip(batch, idxs.tolist(), confs.tolist()):
            label = label_map[str(idx)]
            gold.append(r["label"])
            pred.append(label)
        if (i // args.batch) % 5 == 0:
            done = min(i + args.batch, len(rows))
            print(f"  {done}/{len(rows)} pairs ({time.time() - t0:.0f}s)", flush=True)

    metrics = compute_metrics(gold, pred)
    artifact = {
        "model": model_key,
        "local_dir": str(local_dir) if local_dir.exists() else None,
        "label_map": label_map,
        "split": args.split,
        "rows": len(rows),
        "wall_seconds": round(time.time() - t0, 1),
        "metrics": json.loads(metrics.to_json()),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "device": "mps"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()
        else "cpu",
    }

    name = f"PHASE3_NLI_BASELINE_{'A' if args.model == 'A' else 'B'}_METRICS.json"
    out = REPO_ROOT / "docs" / name
    out.write_text(json.dumps(artifact, indent=2))
    print(
        f"accuracy={artifact['metrics']['accuracy']} macro_f1={artifact['metrics']['macro_f1']}"
    )
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
