#!/usr/bin/env python3
"""Phase-3 v0.2 fine-tune: canonical-orientation DeBERTa NLI cross-encoder.

Why this exists
---------------
The v1 checkpoint was trained on a corpus whose premises folded the human's own
request into the evidence side, while the runtime ``SemanticEvidenceBuilder``
emits evidence-only premises. The paired orientation diagnostic measured the
consequence on the frozen checkpoint and returned RETRAIN_REQUIRED = YES, so
this script retrains on ``data/phase3/dataset/frozen_v2`` (canonical only).

Trust posture (unchanged by training):
  - the model learns evidence -> authorization entailment only;
  - it gains no payment, ticket, provider or repository capability;
  - deterministic RazorGuard remains the financial authority;
  - the artifact is written to a NEW directory; the v1 artifact is never
    overwritten, so the historical evidence stays inspectable.

Hardware note: this runs on the local CPU box (Apple M2, 8 GB). No GPU, no
Modal, no cloud. The pinned hyperparameters match train_config.json so the run
is comparable with the v1 recipe.

Usage:
  services/ml-venv/bin/python scripts/rzp_train_phase3_v2.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

DATA_DIR = REPO_ROOT / "data" / "phase3" / "dataset" / "frozen_v2"
OUT_DIR = REPO_ROOT / "artifacts" / "models" / "incoming" / "phase3-finetuned-v2"
CONFIG_PATH = REPO_ROOT / "training" / "phase3" / "train_config_v2.json"

LABELS = ("contradiction", "entailment", "neutral")
LABEL_TO_ID = {"contradiction": 0, "entailment": 1, "neutral": 2}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows(split: str) -> list[dict[str, Any]]:
    path = DATA_DIR / f"{split}.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    for row in rows:
        if "Session context" in row["premise"]:
            raise SystemExit(f"non-canonical premise reached training: {row['record_id']}")
    return rows


def compute_metrics(eval_pred: Any) -> dict[str, float]:
    import numpy as np

    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    acc = float((preds == labels).mean())
    f1s: list[float] = []
    out: dict[str, float] = {"accuracy": acc}
    for index, cls in enumerate(LABELS):
        tp = float(((preds == index) & (labels == index)).sum())
        fp = float(((preds == index) & (labels != index)).sum())
        fn = float(((preds != index) & (labels == index)).sum())
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        f1s.append(f1)
        out[f"f1_{cls}"] = f1
        out[f"recall_{cls}"] = recall
        out[f"precision_{cls}"] = precision
    out["macro_f1"] = float(sum(f1s) / len(f1s))
    # Safety counter: a gold contradiction scored as entailment is the one
    # failure mode that could loosen a payment decision.
    out["unsafe_entailment_on_contradiction"] = float(
        ((preds == 1) & (labels == 0)).sum()
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--weight-decay", type=float, default=None)
    parser.add_argument("--threads", type=int, default=6)
    args = parser.parse_args()

    cfg: dict[str, Any] = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    epochs = args.epochs or int(cfg["epochs"])
    batch_size = args.batch_size or int(cfg["per_device_train_batch_size"])
    learning_rate = args.lr if args.lr is not None else float(cfg["learning_rate"])
    weight_decay = (
        args.weight_decay if args.weight_decay is not None else float(cfg["weight_decay"])
    )

    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    import numpy as np  # noqa: F401  (imported early so torch sees a stable BLAS)
    import torch
    from datasets import Dataset
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        DataCollatorWithPadding,
        Trainer,
        TrainingArguments,
    )

    torch.set_num_threads(max(1, args.threads))

    train_rows = load_rows("train")
    val_rows = load_rows("val")
    print(
        f"canonical corpus: train={len(train_rows)} val={len(val_rows)} "
        f"device=cpu threads={torch.get_num_threads()}",
        flush=True,
    )

    def to_dataset(rows: list[dict[str, Any]]) -> Dataset:
        return Dataset.from_dict(
            {
                "premise": [r["premise"] for r in rows],
                "hypothesis": [r["hypothesis"] for r in rows],
                "label": [LABEL_TO_ID[r["label"]] for r in rows],
            }
        )

    base_model = cfg["baseline_model"]
    tokenizer = AutoTokenizer.from_pretrained(base_model)

    def tokenize(batch: dict[str, list[str]]) -> dict[str, Any]:
        return tokenizer(
            batch["premise"],
            batch["hypothesis"],
            truncation=True,
            max_length=int(cfg["max_length"]),
        )

    train_ds = to_dataset(train_rows).map(
        tokenize, batched=True, remove_columns=["premise", "hypothesis"]
    )
    val_ds = to_dataset(val_rows).map(
        tokenize, batched=True, remove_columns=["premise", "hypothesis"]
    )

    model = AutoModelForSequenceClassification.from_pretrained(
        base_model,
        num_labels=int(cfg["num_labels"]),
        id2label={str(i): name for i, name in enumerate(LABELS)},
        label2id=LABEL_TO_ID,
    )

    seed = int(cfg["seed"])
    torch.manual_seed(seed)
    np.random.seed(seed)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    accum = int(cfg["gradient_accumulation_steps"])
    steps_per_epoch = max(1, -(-len(train_ds) // (batch_size * accum)))
    total_steps = steps_per_epoch * epochs
    # transformers 5.x dropped TrainingArguments.warmup_ratio, so the ratio in
    # the recipe is resolved to an absolute step count here.
    warmup_steps = max(1, int(float(cfg["warmup_ratio"]) * total_steps))
    training_args = TrainingArguments(
        output_dir=str(OUT_DIR / "checkpoint"),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=int(cfg["per_device_eval_batch_size"]),
        gradient_accumulation_steps=accum,
        learning_rate=learning_rate,
        warmup_steps=warmup_steps,
        weight_decay=weight_decay,
        seed=seed,
        data_seed=seed,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model=cfg["metric_for_best_model"],
        greater_is_better=bool(cfg["greater_is_better"]),
        report_to=[],
        use_cpu=True,
        logging_steps=10,
    )

    started = time.monotonic()
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
    )
    result = trainer.train()
    elapsed = time.monotonic() - started

    trainer.save_model(OUT_DIR)
    tokenizer.save_pretrained(OUT_DIR)
    (OUT_DIR / "label_map.json").write_text(
        json.dumps({str(i): name for i, name in enumerate(LABELS)}, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "base_model.txt").write_text(base_model, encoding="utf-8")

    eval_result = trainer.evaluate()
    final_metrics = {
        key[len("eval_") :]: float(value)
        for key, value in eval_result.items()
        if key.startswith("eval_") and key != "eval_loss"
    }
    final_metrics.setdefault("accuracy", 0.0)
    final_metrics.setdefault("macro_f1", 0.0)
    (OUT_DIR / "metrics.json").write_text(
        json.dumps(
            {
                "eval_accuracy": final_metrics["accuracy"],
                "eval_macro_f1": final_metrics["macro_f1"],
                "eval_loss": float(result.training_loss),
                "eval_recall_contradiction": final_metrics["recall_contradiction"],
                "eval_unsafe_entailment_on_contradiction": final_metrics[
                    "unsafe_entailment_on_contradiction"
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    run_record = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "runtime": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "device": "cpu",
            "threads": torch.get_num_threads(),
        },
        "config": cfg,
        "effective_epochs": epochs,
        "effective_batch_size": batch_size,
        "effective_learning_rate": learning_rate,
        "effective_weight_decay": weight_decay,
        "effective_warmup_steps": warmup_steps,
        "total_steps_estimate": total_steps,
        "steps_per_epoch_estimate": steps_per_epoch,
        "train_seconds": round(elapsed, 2),
        "counts": {"train": len(train_rows), "val": len(val_rows)},
        "dataset_sha256": {
            f"{split}.jsonl": sha256_file(DATA_DIR / f"{split}.jsonl")
            for split in ("train", "val", "test")
        },
        "per_epoch": [
            {k: float(v) for k, v in log.items() if k.startswith("eval_")}
            for log in trainer.log_history
            if any(k.startswith("eval_") for k in log)
        ],
        "final_val_metrics": final_metrics,
    }
    (OUT_DIR / "training_run.json").write_text(json.dumps(run_record, indent=2), encoding="utf-8")
    print(json.dumps({"final_val_metrics": final_metrics, "train_seconds": round(elapsed, 1)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
