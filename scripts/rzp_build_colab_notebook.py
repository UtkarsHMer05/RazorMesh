#!/usr/bin/env python3
"""P3-M32: generate the self-contained Colab training notebook."""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "notebooks"
OUT = OUT_DIR / "RazorGuard_NLI_Phase3_Training.ipynb"


def md(text: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": text.splitlines(keepends=True),
    }


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }


cells = [
    md(
        """# RazorMesh Trust — Phase 3 NLI Fine-Tuning (human-run)

You are running the OFFICIAL Phase-3 fine-tuning for the SemanticVerifier.

Trust rules while training:
- The model learns to relate EVIDENCE (premise) to an AUTHORIZATION CLAIM
  (hypothesis). It never gains payment or system privileges.
- Inputs are the FROZEN, hash-verified bundles produced by the agent
  (train/val splits are whole-group and leakage-checked).
- After training finishes, download `phase3-finetuned.zip` and hand it back to
  the agent, which verifies hashes before anything is imported."""
    ),
    md("## 1. Environment check (GPU expected)"),
    code(
        """!nvidia-smi -L || echo 'NO GPU RUNTIME - use Runtime > Change runtime type > T4'
import torch, platform
print('torch', torch.__version__, '| cuda', torch.cuda.is_available())
assert torch.cuda.is_available(), 'GPU required for this notebook'"""
    ),
    md("## 2. Install pinned dependencies"),
    code(
        '''%pip install -q "transformers==5.15.1" "accelerate==1.14.0" "sentencepiece"'''
    ),
    md("## 3. Upload the training bundle (`phase3_training_bundle.zip`)"),
    code(
        """from google.colab import files
uploaded = files.upload()  # choose artifacts/phase3_training_bundle.zip
assert "phase3_training_bundle.zip" in uploaded, "upload the bundle zip"
!unzip -oq phase3_training_bundle.zip -d /content/rm
!ls /content/rm/training/phase3"""
    ),
    md("## 4. Verify bundle hashes BEFORE any training"),
    code(
        """import hashlib, json, pathlib
d = pathlib.Path('/content/rm/training/phase3')
man = json.loads((d/'manifest.json').read_text())
for name, expected in man['files'].items():
    actual = hashlib.sha256((d/name).read_bytes()).hexdigest()
    assert actual == expected, f'hash mismatch {name}'
print('bundle verified:', man['counts'])"""
    ),
    md("## 5. Train (config from train_config.json, seed pinned)"),
    code(
        """import json
from datasets import Dataset
from transformers import (
    AutoModelForSequenceClassification, AutoTokenizer, Trainer,
    TrainingArguments,
)

cfg = json.loads((d/'train_config.json').read_text())
BASE = cfg['baseline_model']
LMAP = {int(k): v for k, v in cfg['label_map'].items()}
INV = {v: int(k) for k, v in LMAP.items()}
MAXLEN = cfg['max_length']; SEED = cfg['seed']

def load(split):
    rows = [json.loads(l) for l in (d/f'{split}.jsonl').read_text().splitlines() if l.strip()]
    return Dataset.from_dict({
        'premise': [r['premise'] for r in rows],
        'hypothesis': [r['hypothesis'] for r in rows],
        'label': [INV[r['label']] for r in rows],
    })

train_ds = load('train'); val_ds = load('val')
tok = AutoTokenizer.from_pretrained(BASE)
def tok_fn(b):
    return tok(b['premise'], b['hypothesis'], truncation=True, max_length=cfg['max_length'])
train_ds = train_ds.map(tok_fn, batched=True)
val_ds = val_ds.map(tok_fn, batched=True)

model = AutoModelForSequenceClassification.from_pretrained(BASE, num_labels=cfg['num_labels'])

import numpy as np
def metrics_fn(eval_pred):
    logits, labels = eval_pred
    preds = logits.argmax(-1)
    acc = float((preds == labels).mean())
    f1s = []
    for c in range(cfg['num_labels']):
        tp = ((preds==c)&(labels==c)).sum(); fp=((preds==c)&(labels!=c)).sum(); fn=((preds!=c)&(labels==c)).sum()
        p = tp/(tp+fp) if tp+fp else 0.0; r_ = tp/(tp+fn) if tp+fn else 0.0
        f1s.append(2*p*r_/(p+r_) if p+r_ else 0.0)
    macro = sum(f1s)/len(f1s)
    return {'accuracy': acc, 'macro_f1': macro}

args = TrainingArguments(
    output_dir='/content/out',
    num_train_epochs=cfg['epochs'],
    learning_rate=cfg['learning_rate'],
    per_device_train_batch_size=cfg['per_device_train_batch_size'],
    per_device_eval_batch_size=cfg['per_device_eval_batch_size'],
    warmup_steps=cfg.get('warmup_ratio', 0.1),
    weight_decay=cfg['weight_decay'],
    fp16=cfg['fp16'],
    seed=SEED,
    eval_strategy='epoch',
    save_strategy='epoch',
    load_best_model_at_end=True,
    metric_for_best_model='macro_f1',
    greater_is_better=True,
    logging_steps=20,
    report_to=[],
)

from dataclasses import dataclass as _dc
trainer = Trainer(
    model=model,
    args=args,
    train_dataset=train_ds,
    eval_dataset=val_ds,
    processing_class=tok,
    compute_metrics=metrics_fn,
)
trainer.train()
final = trainer.evaluate()
print(final)"""
    ),
    md("## 6. Package artifact for hand-back"),
    code(
        """out = pathlib.Path('/content/phase3-finetuned')
out.mkdir(exist_ok=True)
trainer.save_model(out)
tok.save_pretrained(out)
lm = {'0': LMAP[0], '1': LMAP[1], '2': LMAP[2]}
(out/'label_map.json').write_text(json.dumps(lm, indent=2))
metrics = {k: float(v) for k, v in final.items()}
(out/'metrics.json').write_text(json.dumps(metrics, indent=2))
(out/'base_model.txt').write_text(BASE)
!zip -qr /content/phase3-finetuned.zip /content/phase3-finetuned
from google.colab import files
files.download('/content/phase3-finetuned.zip')
print('DONE — download complete. Hand phase3-finetuned.zip back to the agent.')"""
    ),
]

nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "colab": {"provenance": [], "gpuType": "T4"},
        "kernelspec": {"name": "python3", "display_name": "Python 3"},
        "accelerator": "GPU",
    },
    "cells": cells,
}
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(nb, indent=1), encoding="utf-8")
print(f"written: {OUT} ({len(cells)} cells)")
