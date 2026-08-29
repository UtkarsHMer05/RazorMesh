#!/usr/bin/env python3
"""Build the Google Colab training bundle + notebook for AgentPay-IR v2 (§16F).

Bundle contains ONLY: final train, final val, schema, label map, source/license
manifest, dataset hashes, pinned base-model revision, training config, code.
It must NOT contain: frozen test, human gold (review roles), untouched OOD.

Usage: services/api/.venv/bin/python scripts/rzp_build_colab_bundle_v2.py
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "data" / "agentpay_ir_v2" / "corpus"
DOCS = REPO / "docs" / "agentpay_ir_v2"
OUT_ZIP = REPO / "artifacts" / "agentpay_ir_v2_colab_training_bundle.zip"
ARTIFACTS = REPO / "artifacts"

BASE_MODEL = "cross-encoder/nli-deberta-v3-base"
BASE_REVISION = "6c749ce3425cd33b46d187e45b92bbf96ee12ec7"  # HF api sha, resolved 2026-08-29
LABEL_MAP = {"0": "contradiction", "1": "entailment", "2": "neutral"}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


TRAIN_CONFIG = {
    "base_model": BASE_MODEL,
    "base_model_revision": BASE_REVISION,
    "label_map": LABEL_MAP,
    "seed": 42,
    "max_length": 256,
    "candidates": {
        "A": {"epochs": 2, "lr": 2e-5},
        "B": {"epochs": 3, "lr": 2e-5},
    },
    "batch_size": 16,
    "warmup_ratio": 0.06,
    "fp16": True,
    "selection": "validation only; FROZEN rule: minimize eval_unsafe_c_to_e, then maximize eval_macro_f1, then maximize eval_contradiction_recall (exact implementation in the notebook; candidate reporting includes neutral recall and safe false-block rate)",
    "forbidden_at_training_time": ["test.jsonl", "human gold (review_role=gold)", "fresh_ood_v2.jsonl"],
}

# Aligned with the API `semantic` uv group (transformers 5.15.1 / torch 2.13.0 /
# accelerate 1.14.0) so the trained artifact round-trips into the runtime with
# identical serialization semantics. scikit-learn/datasets are Colab-side only.
REQUIREMENTS = """\
transformers==5.15.1
torch==2.13.0
accelerate==1.14.0
datasets==4.0.1
scikit-learn==1.7.1
safetensors==0.6.2
"""

NOTEBOOK = {
    "cells": [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# RazorGuard NLI — AgentPay-IR v2 fine-tune (Colab)\n",
                "\n",
                "Base model pinned to `cross-encoder/nli-deberta-v3-base` @ revision\n",
                f"`{BASE_REVISION}`. Label map: 0=contradiction, 1=entailment, 2=neutral.\n",
                "\n",
                "**The bundle contains train+val only** — no frozen test, no human gold, no untouched OOD.\n",
                "Selection uses validation only. Run top-to-bottom on T4/L4.\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import json, hashlib, zipfile, io, os, random\n",
                "import torch\n",
                "assert torch.cuda.is_available(), 'GPU required (Runtime > Change runtime type)'\n",
                "print('GPU:', torch.cuda.get_device_name(0))\n",
                "from google.colab import files\n",
                "up = files.upload()  # upload agentpay_ir_v2_colab_training_bundle.zip\n",
                "BUNDLE = next(iter(up))\n",
                "sha = hashlib.sha256(open(BUNDLE,'rb').read()).hexdigest()\n",
                "print('bundle sha256:', sha)\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "!pip -q install transformers==4.55.4 datasets==4.0.1 accelerate==1.10.1 scikit-learn==1.7.1\n",
                "zf = zipfile.ZipFile(BUNDLE)\n",
                "manifest = json.loads(zf.read('bundle_manifest.json'))\n",
                "assert hashlib.sha256(open(BUNDLE,'rb').read()).hexdigest() == manifest['bundle_sha256'], 'bundle hash mismatch'\n",
                "zf.extractall('bundle')\n",
                "for name, want in manifest['files'].items():  # manifest itself excluded\n",
                "    h = hashlib.sha256(open('bundle/'+name,'rb').read()).hexdigest()\n",
                "    assert h == want, f'hash mismatch {name}'\n",
                "print('bundle verified:', manifest['files'])\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "from transformers import AutoTokenizer, AutoModelForSequenceClassification, set_seed\n",
                "REV = manifest['base_model_revision']\n",
                "tok = AutoTokenizer.from_pretrained(manifest['base_model'], revision=REV)\n",
                "print('label map:', manifest['label_map'])\n",
                "set_seed(42)\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import torch\n",
                "from torch.utils.data import Dataset\n",
                "class NLIDataset(Dataset):\n",
                "    def __init__(self, path, tok, max_len=256):\n",
                "        self.rows = [json.loads(l) for l in open(path)]\n",
                "        self.tok, self.max_len = tok, max_len\n",
                "        self.lab = {'contradiction':0,'entailment':1,'neutral':2}\n",
                "    def __len__(self): return len(self.rows)\n",
                "    def __getitem__(self, i):\n",
                "        r = self.rows[i]\n",
                "        enc = self.tok(r['premise'], r['hypothesis'], truncation=True, max_length=self.max_len, padding='max_length', return_tensors='pt')\n",
                "        return {**{k: v[0] for k, v in enc.items()}, 'labels': torch.tensor(self.lab[r['label']])}\n",
                "train_ds = NLIDataset('bundle/train.jsonl', tok)\n",
                "val_ds = NLIDataset('bundle/val.jsonl', tok)\n",
                "print('train', len(train_ds), 'val', len(val_ds))\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import numpy as np\n",
                "from sklearn.metrics import f1_score\n",
                "from transformers import Trainer, TrainingArguments, AutoModelForSequenceClassification\n",
                "def metrics(eval_pred):\n",
                "    logits, labels = eval_pred\n",
                "    preds = logits.argmax(-1)\n",
                "    unsafe = int(((labels==0)&(preds==1)).sum())  # gold C predicted E\n",
                "    c_rec = float((preds[labels==0]==0).mean()) if (labels==0).any() else 0.0\n",
                "    n_rec = float((preds[labels==2]==2).mean()) if (labels==2).any() else 0.0\n",
                "    e_fp_block = int(((labels==1)&(preds==0)).sum())  # safe entailments hard-blocked\n",
                "    return {'macro_f1': f1_score(labels, preds, average='macro'),\n",
                "            'contradiction_recall': c_rec, 'unsafe_c_to_e': unsafe,\n",
                "            'neutral_recall': n_rec, 'safe_false_block': e_fp_block}\n",
                "def run(epochs):\n",
                "    set_seed(42)\n",
                "    model = AutoModelForSequenceClassification.from_pretrained(manifest['base_model'], revision=REV, num_labels=3)\n",
                "    args = TrainingArguments(f'out_{epochs}', num_train_epochs=epochs, learning_rate=2e-5,\n",
                "        per_device_train_batch_size=16, per_device_eval_batch_size=32, warmup_ratio=0.06,\n",
                "        fp16=True, logging_steps=200, eval_strategy='epoch', save_strategy='no', report_to=[])\n",
                "    tr = Trainer(model=model, args=args, train_dataset=train_ds, eval_dataset=val_ds, compute_metrics=metrics)\n",
                "    tr.train()\n",
                "    ev = tr.evaluate()\n",
                "    del tr, model; torch.cuda.empty_cache()\n",
                "    return ev\n",
                "results = {'A_2ep': run(2), 'B_3ep': run(3)}\n",
                "print(json.dumps(results, indent=1))\n",
                "# FROZEN selection rule (train_config.json): min unsafe C->E, then max macro-F1, then max contradiction recall\n",
                "best = min(results.items(), key=lambda kv: (kv[1]['eval_unsafe_c_to_e'], -kv[1]['eval_macro_f1'], -kv[1]['eval_contradiction_recall']))[0]\n",
                "print('SELECTED (validation only, frozen rule):', best)\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "set_seed(42)\n",
                "epochs = 2 if best=='A_2ep' else 3\n",
                "model = AutoModelForSequenceClassification.from_pretrained(manifest['base_model'], revision=REV, num_labels=3)\n",
                "args = TrainingArguments('final', num_train_epochs=epochs, learning_rate=2e-5,\n",
                "    per_device_train_batch_size=16, warmup_ratio=0.06, fp16=True, logging_steps=200, report_to=[])\n",
                "Trainer(model=model, args=args, train_dataset=train_ds).train()\n",
                "model.save_pretrained('agentpay-ir-v2-finetuned', safe_serialization=True)\n",
                "tok.save_pretrained('agentpay-ir-v2-finetuned')\n",
                "json.dump(manifest['label_map'], open('agentpay-ir-v2-finetuned/label_map.json','w'))\n",
                "open('agentpay-ir-v2-finetuned/base_model.txt','w').write(manifest['base_model'])\n",
                "open('agentpay-ir-v2-finetuned/base_model_revision.txt','w').write(REV)\n",
                "json.dump({'validation_results': results, 'selected': best, 'seed': 42}, open('agentpay-ir-v2-finetuned/training_metrics.json','w'), indent=1)\n",
                "json.dump(manifest, open('agentpay-ir-v2-finetuned/dataset_manifest.json','w'), indent=1)\n",
                "import transformers, accelerate, platform\n",
                "def _sha(p):\n",
                "    import hashlib\n",
                "    return hashlib.sha256(open(p,'rb').read()).hexdigest()\n",
                "artifact_files = {f: _sha('agentpay-ir-v2-finetuned/'+f) for f in os.listdir('agentpay-ir-v2-finetuned') if os.path.isfile('agentpay-ir-v2-finetuned/'+f)}\n",
                "model_manifest = {\n",
                "    'artifact': 'agentpay-ir-v2-finetuned',\n",
                "    'base_model': manifest['base_model'],\n",
                "    'base_model_revision': REV,\n",
                "    'label_map': manifest['label_map'],\n",
                "    'seed': 42,\n",
                "    'selected_candidate': best,\n",
                "    'candidate_results': results,\n",
                "    'selection_rule': manifest and json.load(open('bundle/train_config.json'))['selection'],\n",
                "    'dataset_manifest_files': manifest['files'],\n",
                "    'dependency_versions': {'transformers': transformers.__version__, 'torch': torch.__version__, 'accelerate': accelerate.__version__, 'python': platform.python_version()},\n",
                "    'artifact_files_sha256': artifact_files,\n",
                "    'training_data_excluded': ['frozen test', 'human gold', 'untouched OOD'],\n",
                "}\n",
                "json.dump(model_manifest, open('agentpay-ir-v2-finetuned/model_manifest.json','w'), indent=1)\n",
                "import shutil\n",
                "shutil.make_archive('agentpay-ir-v2-finetuned', 'zip', '.', 'agentpay-ir-v2-finetuned')\n",
                "files.download('agentpay-ir-v2-finetuned.zip')\n",
                "print('DONE — place agentpay-ir-v2-finetuned.zip in artifacts/models/incoming/')\n",
            ],
        },
    ],
    "metadata": {"colab": {"provenance": []}, "kernelspec": {"name": "python3", "display_name": "Python 3"}},
    "nbformat": 4,
    "nbformat_minor": 5,
}


def main() -> int:
    ARTIFACTS.mkdir(exist_ok=True)
    files = {
        "train.jsonl": CORPUS / "train.jsonl",
        "val.jsonl": CORPUS / "val.jsonl",
        "bundle_manifest.json": None,
        "label_map.json": None,
        "train_config.json": None,
        "requirements-frozen.txt": None,
        "SCHEMA.md": DOCS / "SCHEMA.md",
    }
    hashes = {n: sha256_file(p) for n, p in files.items() if p}
    bundle_manifest = {
        "schema_version": "agentpay-ir-v2",
        "base_model": BASE_MODEL,
        "base_model_revision": BASE_REVISION,
        "label_map": LABEL_MAP,
        "files": hashes,
        "excluded": ["test.jsonl (frozen)", "review_candidates_with_roles.jsonl (human roles)",
                     "review_role_manifest.json", "fresh_ood_v2.jsonl (untouched OOD)"],
    }
    tmp = ARTIFACTS / "_bundle_stage"
    tmp.mkdir(exist_ok=True)
    for n, p in files.items():
        if p:
            (tmp / n).write_bytes(p.read_bytes())
    (tmp / "bundle_manifest.json").write_text(json.dumps(bundle_manifest, indent=2))
    (tmp / "label_map.json").write_text(json.dumps(LABEL_MAP, indent=2))
    (tmp / "train_config.json").write_text(json.dumps(TRAIN_CONFIG, indent=2))
    (tmp / "requirements-frozen.txt").write_text(REQUIREMENTS)
    # hash the generated files too, then rewrite manifest with complete hashes
    hashes = {n: sha256_file(tmp / n) for n in ("train.jsonl", "val.jsonl", "label_map.json", "train_config.json", "requirements-frozen.txt", "SCHEMA.md")}
    bundle_manifest["files"] = hashes
    (tmp / "bundle_manifest.json").write_text(json.dumps(bundle_manifest, indent=2))
    if OUT_ZIP.exists():
        OUT_ZIP.unlink()
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for n in ("train.jsonl", "val.jsonl", "bundle_manifest.json", "label_map.json", "train_config.json", "requirements-frozen.txt", "SCHEMA.md"):
            z.write(tmp / n, n)
    nb_path = REPO / "notebooks" / "RazorGuard_NLI_AgentPayIR_v2_Training.ipynb"
    nb_path.parent.mkdir(exist_ok=True)
    json.dump(NOTEBOOK, open(nb_path, "w"), indent=1)
    print("bundle:", OUT_ZIP, OUT_ZIP.stat().st_size, "bytes | sha256:", sha256_file(OUT_ZIP))
    print("notebook:", nb_path)
    # MODEL_SOURCE_MANIFEST (§16B pin)
    (DOCS / "MODEL_SOURCE_MANIFEST.json").write_text(json.dumps({
        "base_model": BASE_MODEL,
        "revision": BASE_REVISION,
        "license": "Apache-2.0",
        "resolved_at": "2026-08-29",
        "source": "https://huggingface.co/api/models/cross-encoder/nli-deberta-v3-base",
        "label_map": LABEL_MAP,
        "pin_rule": "train from this exact revision; never float to main/latest",
    }, indent=2))
    print("MODEL_SOURCE_MANIFEST.json written (revision pinned)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
