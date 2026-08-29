#!/usr/bin/env python3
"""Tiny local smoke fine-tune for the AgentPay-IR v2 training code (§16F).

<=64 rows, <=1 epoch, CPU — proves the EXACT training path the Colab notebook
uses (tokenizer(premise, hypothesis) + 3-class cross-encoder + Trainer) executes
end-to-end on this bundle. Writes artifacts/models/incoming/agentpay-ir-v2-SMOKE/
(NOT a v2 candidate artifact; never wired into the runtime).
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "data" / "agentpay_ir_v2" / "corpus"
OUT = REPO / "artifacts" / "models" / "incoming" / "agentpay-ir-v2-SMOKE"
BASE = "cross-encoder/nli-deberta-v3-base"
REV = "6c749ce3425cd33b46d187e45b92bbf96ee12ec7"
LAB = {"contradiction": 0, "entailment": 1, "neutral": 2}


def main() -> int:
    import torch
    from torch.utils.data import Dataset
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                              Trainer, TrainingArguments, set_seed)

    rng = random.Random(42)
    rows = [json.loads(l) for l in open(CORPUS / "train.jsonl")]
    rows = rng.sample(rows, 64)

    class DS(Dataset):
        def __init__(self, rows, tok):
            self.rows, self.tok = rows, tok
        def __len__(self):
            return len(self.rows)
        def __getitem__(self, i):
            r = self.rows[i]
            enc = self.tok(r["premise"][:1000], r["hypothesis"], truncation=True,
                           max_length=128, padding="max_length", return_tensors="pt")
            return {**{k: v[0] for k, v in enc.items()}, "labels": torch.tensor(LAB[r["label"]])}

    set_seed(42)
    tok = AutoTokenizer.from_pretrained(BASE, revision=REV)
    model = AutoModelForSequenceClassification.from_pretrained(BASE, revision=REV, num_labels=3)
    args = TrainingArguments("artifacts/_smoke_v2_out", num_train_epochs=1,
                             per_device_train_batch_size=4, logging_steps=2,
                             report_to=[], save_strategy="no", use_cpu=True)
    tr = Trainer(model=model, args=args, train_dataset=DS(rows, tok))
    tr.train()
    ev = tr.evaluate(tr.train_dataset)
    OUT.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(OUT, safe_serialization=True)
    tok.save_pretrained(OUT)
    (OUT / "label_map.json").write_text(json.dumps({"0": "contradiction", "1": "entailment", "2": "neutral"}))
    (OUT / "SMOKE_MARKER.json").write_text(json.dumps({
        "purpose": "smoke proof only — NEVER a v2 candidate artifact; never runtime-wired",
        "rows": 64, "epochs": 1, "seed": 42, "base_revision": REV,
        "final_train_loss_sample": ev,
    }, indent=2, default=str))
    print("SMOKE TRAIN OK — loss output:", json.dumps(ev, default=str)[:200])
    return 0


if __name__ == "__main__":
    sys.exit(main())
