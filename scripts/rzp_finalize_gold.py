#!/usr/bin/env python3
"""P3-M26 completion: validate human gold decisions, measure baseline-B
agreement against them, and FREEZE the gold set (status -> GOLD_VALIDATED).

- ingestion via dataset_quality.ingest_gold_decisions (invalid excluded);
- per-row zero-shot inference with baseline B over the SAME pairs;
- agreement/confusion restricted to human-valid labels only;
- frozen artifact: data/phase3/gold/gold_frozen.json (+ sha256 manifest flip).
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

import time

import torch
from razormesh_api.dataset_quality import ingest_gold_decisions
from transformers import AutoModelForSequenceClassification, AutoTokenizer

GOLD_DIR = REPO_ROOT / "data" / "phase3" / "gold"
DECISIONS = GOLD_DIR / "gold_decisions.json"
CSV = GOLD_DIR / "gold_review.csv"
LOCAL_MODEL = REPO_ROOT / "models" / "cross-encoder__nli-deberta-v3-base"
LABEL_MAP = {0: "contradiction", 1: "entailment", 2: "neutral"}


def main() -> int:
    decisions = json.loads(DECISIONS.read_text())
    rows = {
        r["record_id"]: r
        for r in __import__("csv").DictReader(CSV.open(newline="", encoding="utf-8"))
    }

    ingest = ingest_gold_decisions(decisions, known_record_ids=set(rows))
    print(f"valid={len(ingest.valid)} excluded={len(ingest.excluded)}")
    if ingest.excluded:
        for k, why in list(ingest.excluded.items())[:10]:
            print("  excluded:", k, "->", why)

    # ---- zero-shot inference on the same pairs ------------------------------
    tok = AutoTokenizer.from_pretrained(str(LOCAL_MODEL))
    model = AutoModelForSequenceClassification.from_pretrained(str(LOCAL_MODEL))
    model.eval()

    ids = sorted(ingest.valid)
    preds: dict[str, str] = {}
    t0 = time.time()
    for i in range(0, len(ids), 16):
        batch_ids = ids[i : i + 16]
        feats = tok(
            [rows[k]["premise"] for k in batch_ids],
            [rows[k]["hypothesis"] for k in batch_ids],
            truncation=True,
            max_length=256,
            padding=True,
            return_tensors="pt",
        )
        with torch.no_grad():
            probs = torch.softmax(model(**feats).logits, -1)
        for k, p in zip(batch_ids, probs.tolist(), strict=False):
            preds[k] = LABEL_MAP[int(p.index(max(p)))]
    infer_s = round(time.time() - t0, 1)

    # ---- agreement vs HUMAN labels -----------------------------------------
    confusion: Counter[str] = Counter()
    correct = 0
    contra_human = contra_model_caught = 0
    unsafe_allow_vs_human = 0
    for k in ids:
        human = ingest.valid[k]
        model_label = preds[k]
        confusion[(human, model_label)] += 1
        if human == model_label:
            correct += 1
        if human == "contradiction":
            contra_human += 1
            if model_label == "contradiction":
                contra_model_caught += 1
            elif model_label == "entailment":
                unsafe_allow_vs_human += 1

    n = len(ids)
    accuracy = correct / n
    contra_recall = contra_model_caught / contra_human if contra_human else 0.0

    # suggested-label (template/qwen truth) vs human agreement too
    sug_agree = sum(1 for k in ids if rows[k]["suggested_label"] == ingest.valid[k])

    # ---- freeze -------------------------------------------------------------
    frozen = {
        "format_version": "agentpay-gold-v1",
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "reviewer": "human-owner",
        "total": n,
        "labels": dict(Counter(ingest.valid.values())),
        "excluded": dict(ingest.excluded),
        "decisions_sha256": hashlib.sha256(DECISIONS.read_bytes()).hexdigest(),
        "baseline_b_agreement": {
            "accuracy": round(accuracy, 4),
            "contradiction_recall_vs_human": round(contra_recall, 4),
            "unsafe_entail_on_human_contradiction": unsafe_allow_vs_human,
            "inference_seconds": infer_s,
            "note": "zero-shot cross-encoder/nli-deberta-v3-base vs human labels",
        },
        "suggested_label_agreement_with_human": round(sug_agree / n, 4),
    }
    (GOLD_DIR / "gold_frozen.json").write_text(json.dumps(frozen, indent=2))

    # manifest flip
    man_p = GOLD_DIR / "manifest.json"
    man = json.loads(man_p.read_text())
    man["status"] = "GOLD_VALIDATED"
    man["validated_at_utc"] = frozen["frozen_at_utc"]
    man["gold_frozen_sha256"] = hashlib.sha256(
        (GOLD_DIR / "gold_frozen.json").read_bytes()
    ).hexdigest()
    man_p.write_text(json.dumps(man, indent=2))

    print(
        json.dumps(
            {
                "n": n,
                "labels": frozen["labels"],
                "baseline_b_agreement_accuracy": frozen["baseline_b_agreement"][
                    "accuracy"
                ],
                "contradiction_recall_vs_human": frozen["baseline_b_agreement"][
                    "contradiction_recall_vs_human"
                ],
                "unsafe_entail_vs_human": unsafe_allow_vs_human,
                "suggested_agreement": frozen["suggested_label_agreement_with_human"],
                "status": man["status"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
