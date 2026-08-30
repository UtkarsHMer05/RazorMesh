#!/usr/bin/env python3
"""Build the Google Colab training bundle + notebook for AgentPay-IR v2 (§16F).

PRE-REVIEW FINAL CORRECTION #12-16:

- the bundle builder accepts an explicit ``--corpus-dir`` or explicit
  ``--train``/``--val`` paths so the POST-REVIEW finalizer can build the FINAL
  bundle from ``corpus/final`` without the builder silently falling back to the
  PRE-REVIEW corpus (the #12 defect);
- the notebook uses an EXTERNAL archive-hash design (#13): the ZIP is built
  first, its SHA256 is computed, and the notebook is generated OUTSIDE the zip
  with ``EXPECTED_BUNDLE_SHA256=<sha>``. The notebook never reads a
  ``manifest['bundle_sha256']`` field (which never existed); internal files are
  still verified from bundle_manifest.json;
- dependencies install from the bundle's requirements-frozen.txt (#14) — one
  single version source (transformers 5.15.1 / torch 2.13.0 / accelerate
  1.14.0) — and torch is NOT imported before install+reconciliation; actual
  runtime versions are asserted against the frozen requirements before training;
- the candidate-selection rule is generated from ``select_candidate`` in THIS
  module (#16) so the notebook and the unit tests exercise one implementation:
  minimize unsafe contradiction→entailment, then maximize macro-F1, then
  maximize contradiction recall (neutral recall + safe false-block are
  reported but are NOT selection inputs).

Bundle contains ONLY: train, val, schema, label map, pinned base-model
revision, training config, requirements. It must NOT contain: frozen test,
human gold (review roles), untouched OOD, decisions, linkage.

Usage:
  services/api/.venv/bin/python scripts/rzp_build_colab_bundle_v2.py
  services/api/.venv/bin/python scripts/rzp_build_colab_bundle_v2.py --corpus-dir data/agentpay_ir_v2/corpus/final
  services/api/.venv/bin/python scripts/rzp_build_colab_bundle_v2.py --train T.jsonl --val V.jsonl --out-zip FINAL.zip
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "data" / "agentpay_ir_v2" / "corpus"
DOCS = REPO / "docs" / "agentpay_ir_v2"
OUT_ZIP = REPO / "artifacts" / "agentpay_ir_v2_colab_training_bundle.zip"
NOTEBOOK_PATH = REPO / "notebooks" / "RazorGuard_NLI_AgentPayIR_v2_Training.ipynb"
ARTIFACTS = REPO / "artifacts"

BASE_MODEL = "cross-encoder/nli-deberta-v3-base"
BASE_REVISION = "6c749ce3425cd33b46d187e45b92bbf96ee12ec7"  # HF api sha, resolved 2026-08-29
LABEL_MAP = {"0": "contradiction", "1": "entailment", "2": "neutral"}

BUNDLE_FILES = ("train.jsonl", "val.jsonl", "label_map.json", "train_config.json",
                "requirements-frozen.txt", "SCHEMA.md")
MANIFEST_REQUIRED_FIELDS = ("schema_version", "base_model", "base_model_revision",
                            "label_map", "files", "excluded")
VERSIONED_PACKAGES = ("transformers", "torch", "accelerate", "datasets", "scikit-learn")

SELECTION_RULE = ("minimize eval_unsafe_c_to_e, then maximize eval_macro_f1, then maximize "
                  "eval_contradiction_recall; neutral recall and safe false-block are reported "
                  "but are NOT selection inputs")


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
    "selection": "validation only; FROZEN rule: minimize eval_unsafe_c_to_e, then maximize "
                 "eval_macro_f1, then maximize eval_contradiction_recall (implemented by "
                 "select_candidate(); candidate reporting includes neutral recall and safe "
                 "false-block rate, which are NOT selection inputs)",
    "forbidden_at_training_time": ["test.jsonl", "human gold (review_role=gold)", "fresh_ood_v2.jsonl"],
}

# THE single version source: the bundle's requirements-frozen.txt. Aligned with
# the API `semantic` uv group so the trained artifact round-trips into the
# runtime with identical serialization semantics.
REQUIREMENTS = """\
transformers==5.15.1
torch==2.13.0
accelerate==1.14.0
scikit-learn==1.7.1
safetensors==0.8.0
"""


# ---------------------------------------------------------------------------
# FROZEN selection rule (#16) — single implementation, embedded into the
# notebook verbatim and unit-tested over fake candidate metrics.
# ---------------------------------------------------------------------------

def select_candidate(results: dict[str, dict]) -> str:
    """FROZEN validation-only selection over candidate metric dicts.

    Each value must carry: eval_unsafe_c_to_e, eval_macro_f1,
    eval_contradiction_recall (decision inputs) and may carry
    eval_neutral_recall / eval_safe_false_block (reported only).
    """
    def key(item: tuple[str, dict]) -> tuple[int, float, float]:
        m = item[1]
        return (int(m["eval_unsafe_c_to_e"]), -float(m["eval_macro_f1"]),
                -float(m["eval_contradiction_recall"]))

    return min(results.items(), key=key)[0]


# ---------------------------------------------------------------------------
# Notebook cell sources (generated OUTSIDE the zip; #13/#14/#15)
# ---------------------------------------------------------------------------

VERIFY_CELL_STDLIB = '''
import json, hashlib, zipfile, os

EXPECTED_BUNDLE_SHA256 = "{expected_sha}"  # computed AFTER the zip was built (external design)


def verify_bundle(path: str, expected_sha: str) -> dict:
    """Verify the training bundle BEFORE anything is imported or installed.

    External archive-hash design: the notebook embeds EXPECTED_BUNDLE_SHA256
    (computed from the final zip bytes by the generator); the internal files
    are verified against bundle_manifest.json. Stdlib only — no torch, no
    transformers, nothing installed yet.
    """
    data = open(path, "rb").read()
    sha = hashlib.sha256(data).hexdigest()
    assert sha == expected_sha, f"bundle sha256 mismatch: {{sha}} != {{expected_sha}}"
    zf = zipfile.ZipFile(path)
    names = set(zf.namelist())
    manifest = json.loads(zf.read("bundle_manifest.json"))
    required = set({required_fields})
    missing = sorted(required - set(manifest))
    assert not missing, f"bundle_manifest.json missing fields: {{missing}}"
    files = manifest["files"]
    expected_names = set(files) | {{"bundle_manifest.json"}}
    assert names == expected_names, f"zip contents {{sorted(names)}} != manifest {{sorted(expected_names)}}"
    for name, want in files.items():
        h = hashlib.sha256(zf.read(name)).hexdigest()
        assert h == want, f"hash mismatch {{name}}"
    train_cfg = json.loads(zf.read("train_config.json"))
    assert train_cfg["base_model"] == manifest["base_model"]
    assert train_cfg["base_model_revision"] == manifest["base_model_revision"]
    req = parse_requirements(zf.read("requirements-frozen.txt").decode())
    assert req["transformers"] and req["torch"] and req["accelerate"], req
    print("bundle verified:", path)
    print("files:", json.dumps(files, indent=1))
    return manifest


def parse_requirements(text: str) -> dict:
    req = {{}}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "==" in line:
            name, ver = line.split("==", 1)
            req[name.strip()] = ver.strip()
    return req


try:  # Colab upload; locally set BUNDLE_PATH to run the same verification
    from google.colab import files as colab_files

    up = colab_files.upload()
    BUNDLE = next(iter(up))
except ImportError:
    BUNDLE = os.environ.get("BUNDLE_PATH", "agentpay_ir_v2_colab_training_bundle.zip")
    assert os.path.exists(BUNDLE), f"bundle not found: {{BUNDLE}}"

MANIFEST = verify_bundle(BUNDLE, EXPECTED_BUNDLE_SHA256)
'''

INSTALL_CELL = '''
import zipfile

zf = zipfile.ZipFile(BUNDLE)
# EXTRACT FIRST (pre-label correction): a fresh Colab runtime has no
# bundle/ directory yet, so requirements-frozen.txt must exist on disk
# BEFORE the pip-install step that consumes it.
zf.extractall("bundle")
REQ = parse_requirements(open("bundle/requirements-frozen.txt").read())
print("frozen requirements:", REQ)

# Install EXACTLY the frozen requirement set (#14) — before ANY torch import.
%pip install -q -r bundle/requirements-frozen.txt

# Colab preinstalls torchvision/torchaudio builds PINNED to its stock torch
# (torchvision 0.26.0+cpu requires torch==2.11.0). Against the frozen torch
# 2.13.0 they break transformers' lazy imports ("operator torchvision::nms does
# not exist" -> ModuleNotFoundError: set_seed). The text-only NLI notebook uses
# neither package, so remove them before importing (the semantic runtime group
# has no torchvision either).
%pip uninstall -y -q torchvision torchaudio

# NOW import the runtime and reconcile actual versions against the frozen file.
import accelerate
import importlib.metadata as importlib_metadata
import torch
import transformers

# PRIMARY gate: pinned DISTRIBUTION versions via importlib.metadata (robust to
# runtime-report quirks); every package in requirements-frozen.txt is checked.
# The PEP 440 LOCAL segment (+cu120 etc.) is ignored for equality — it is a
# build variant, not a different release — while the release itself stays strict.
for _pkg in REQ:
    _installed = importlib_metadata.version(_pkg).split("+", 1)[0]
    assert _installed == REQ[_pkg], f"{_pkg} {_installed} != frozen {REQ[_pkg]}"
print("installed distributions:", {p: importlib_metadata.version(p) for p in REQ})

# EVIDENCE (recorded, not equality-gated): runtime-reported torch version and
# the CUDA build the runtime was compiled against.
print("torch.__version__ (runtime report):", torch.__version__)
print("torch.version.cuda (runtime build):", getattr(torch.version, "cuda", "unavailable"))
assert torch.cuda.is_available(), "GPU required (Runtime > Change runtime type)"
print("GPU:", torch.cuda.get_device_name(0))
print("runtime versions OK:", transformers.__version__, torch.__version__, accelerate.__version__)
'''

TRAIN_SETUP_CELL = '''
import json
import random

import numpy as np
from sklearn.metrics import f1_score
from transformers import AutoTokenizer, set_seed

REV = MANIFEST["base_model_revision"]
tok = AutoTokenizer.from_pretrained(MANIFEST["base_model"], revision=REV)
print("label map:", MANIFEST["label_map"])

from torch.utils.data import Dataset


class NLIDataset(Dataset):
    def __init__(self, path, tok, max_len=256):
        self.rows = [json.loads(l) for l in open(path)]
        self.tok, self.max_len = tok, max_len
        self.lab = {"contradiction": 0, "entailment": 1, "neutral": 2}

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        enc = self.tok(r["premise"], r["hypothesis"], truncation=True, max_length=self.max_len,
                       padding="max_length", return_tensors="pt")
        return {**{k: v[0] for k, v in enc.items()}, "labels": torch.tensor(self.lab[r["label"]])}


train_ds = NLIDataset("bundle/train.jsonl", tok)
val_ds = NLIDataset("bundle/val.jsonl", tok)
print("train", len(train_ds), "val", len(val_ds))


def metrics(eval_pred):
    logits, labels = eval_pred
    preds = logits.argmax(-1)
    unsafe = int(((labels == 0) & (preds == 1)).sum())  # gold C predicted E
    c_rec = float((preds[labels == 0] == 0).mean()) if (labels == 0).any() else 0.0
    n_rec = float((preds[labels == 2] == 2).mean()) if (labels == 2).any() else 0.0
    e_fp_block = int(((labels == 1) & (preds == 0)).sum())  # safe entailments hard-blocked
    return {"macro_f1": f1_score(labels, preds, average="macro"),
            "contradiction_recall": c_rec, "unsafe_c_to_e": unsafe,
            "neutral_recall": n_rec, "safe_false_block": e_fp_block}
'''

SELECTION_CELL = '''
{select_source}
'''

CANDIDATE_CELL = '''
import math

from transformers import AutoModelForSequenceClassification, Trainer, TrainingArguments

# transformers 5.x removed TrainingArguments(warmup_ratio=...); the warmup
# semantics stay frozen by deriving warmup_steps from the bundle's frozen
# train_config.json (6% of total optimizer steps per candidate).
WARMUP_RATIO = json.load(open("bundle/train_config.json")).get("warmup_ratio", 0.06)


def run(epochs):
    set_seed(42)
    model = AutoModelForSequenceClassification.from_pretrained(
        MANIFEST["base_model"], revision=REV, num_labels=3)
    warmup_steps = math.ceil(WARMUP_RATIO * math.ceil(len(train_ds) / 16) * epochs)
    args = TrainingArguments(f"cand_{{epochs}}ep", num_train_epochs=epochs, learning_rate=2e-5,
                             per_device_train_batch_size=16, per_device_eval_batch_size=32,
                             warmup_steps=warmup_steps, fp16=True, logging_steps=200,
                             eval_strategy="epoch", save_strategy="no", report_to=[])
    tr = Trainer(model=model, args=args, train_dataset=train_ds, eval_dataset=val_ds,
                 compute_metrics=metrics)
    tr.train()
    ev = tr.evaluate()
    # SAVE THE EXACT WEIGHTS THAT PRODUCED ev. No training happens after
    # evaluate, so the checkpoint and its validation_metrics.json are the same
    # model — packaging later copies THESE files, never a fresh retrain.
    tr.save_model(f"cand_{{epochs}}ep")
    tok.save_pretrained(f"cand_{{epochs}}ep")
    json.dump(MANIFEST["label_map"], open(f"cand_{{epochs}}ep/label_map.json", "w"))
    open(f"cand_{{epochs}}ep/base_model_revision.txt", "w").write(REV)
    json.dump(ev, open(f"cand_{{epochs}}ep/validation_metrics.json", "w"), indent=1)
    del tr, model
    torch.cuda.empty_cache()
    return ev


results = {{"A_2ep": run(2), "B_3ep": run(3)}}
print(json.dumps(results, indent=1))

best = select_candidate(results)
print("SELECTED (validation only, FROZEN rule: {selection_rule}):", best)
'''

FINAL_CELL = '''
# Package the EXACT selected checkpoint — never retrain from base. The winning
# validation metrics were produced by cand_*ep, so those weights are the artifact.
# NOTE: this cell is inserted verbatim (no str.format), so braces are literal.
import shutil

cand_dir = "cand_2ep" if best == "A_2ep" else "cand_3ep"
if os.path.exists("agentpay-ir-v2-finetuned"):
    shutil.rmtree("agentpay-ir-v2-finetuned")
shutil.copytree(cand_dir, "agentpay-ir-v2-finetuned")
# Bind proof: the copied checkpoint carries the exact winning validation metrics.
copied_metrics = json.load(open("agentpay-ir-v2-finetuned/validation_metrics.json"))
assert copied_metrics == results[best], "packaged checkpoint metrics != selected metrics"
open("agentpay-ir-v2-finetuned/base_model.txt", "w").write(MANIFEST["base_model"])
json.dump({"validation_results": results, "selected": best, "seed": 42,
           "selected_checkpoint_source_dir": cand_dir},
          open("agentpay-ir-v2-finetuned/training_metrics.json", "w"), indent=1)
json.dump(MANIFEST, open("agentpay-ir-v2-finetuned/dataset_manifest.json", "w"), indent=1)


def _sha(p):
    import hashlib

    return hashlib.sha256(open(p, "rb").read()).hexdigest()


artifact_files = {f: _sha("agentpay-ir-v2-finetuned/" + f)
                  for f in os.listdir("agentpay-ir-v2-finetuned")
                  if os.path.isfile("agentpay-ir-v2-finetuned/" + f)}
model_manifest = {
    "artifact": "agentpay-ir-v2-finetuned",
    "base_model": MANIFEST["base_model"],
    "base_model_revision": REV,
    "label_map": MANIFEST["label_map"],
    "seed": 42,
    "selected_candidate": best,
    "selected_checkpoint_source_dir": cand_dir,
    "selected_candidate_metrics": results[best],
    "packaging": "exact selected candidate checkpoint copied; never retrained from base",
    "candidate_results": results,
    "selection_rule": json.load(open("bundle/train_config.json"))["selection"],
    "dataset_manifest_files": MANIFEST["files"],
    "expected_bundle_sha256": EXPECTED_BUNDLE_SHA256,
    "dependency_versions": {"transformers": transformers.__version__, "torch": torch.__version__,
                            "accelerate": accelerate.__version__,
                            "python": __import__("platform").python_version()},
    "artifact_files_sha256": artifact_files,
    "training_data_excluded": ["frozen test", "human gold", "untouched OOD"],
}
json.dump(model_manifest, open("agentpay-ir-v2-finetuned/model_manifest.json", "w"), indent=1)

shutil.make_archive("agentpay-ir-v2-finetuned", "zip", ".", "agentpay-ir-v2-finetuned")
colab_files.download("agentpay-ir-v2-finetuned.zip")
print("DONE — place agentpay-ir-v2-finetuned.zip in artifacts/models/incoming/")
'''

INTRO_MD = '''# RazorGuard NLI — AgentPay-IR v2 fine-tune (Colab)

Base model pinned to `cross-encoder/nli-deberta-v3-base` @ revision `{revision}`.
Label map: 0=contradiction, 1=entailment, 2=neutral.

**The bundle contains train+val only** — no frozen test, no human gold, no untouched OOD.

Integrity design: the notebook embeds `EXPECTED_BUNDLE_SHA256` (computed from the
final ZIP bytes by the generator, OUTSIDE the archive). Cell 1 verifies the
uploaded archive against it and every internal file against
`bundle_manifest.json` — before installing anything. Dependencies then install
from the bundle's `requirements-frozen.txt` and the actual runtime versions are
asserted before any training. Run top-to-bottom on T4/L4.
'''


def _cell_md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def _cell_code(source: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
            "source": source.splitlines(keepends=True)}


def render_notebook(expected_bundle_sha: str) -> dict:
    """Generate the notebook OUTSIDE the zip with the EXTERNAL archive hash (#13)."""
    verify_cell = VERIFY_CELL_STDLIB.format(
        expected_sha=expected_bundle_sha,
        required_fields=json.dumps(sorted(MANIFEST_REQUIRED_FIELDS)),
    )
    selection_cell = SELECTION_CELL.format(
        select_source=inspect.getsource(select_candidate).rstrip())
    candidate_cell = CANDIDATE_CELL.format(selection_rule=SELECTION_RULE)
    return {
        "cells": [
            _cell_md(INTRO_MD.format(revision=BASE_REVISION)),
            _cell_code(verify_cell),
            _cell_code(INSTALL_CELL),
            _cell_code(TRAIN_SETUP_CELL),
            _cell_code(selection_cell),
            _cell_code(candidate_cell),
            _cell_code(FINAL_CELL),
        ],
        "metadata": {"colab": {"provenance": []}, "kernelspec": {"name": "python3",
                                                                 "display_name": "Python 3"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def resolve_train_val(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.train and args.val:
        train, val = Path(args.train), Path(args.val)
    elif args.corpus_dir:
        d = Path(args.corpus_dir)
        train, val = d / "train.jsonl", d / "val.jsonl"
    else:
        train, val = CORPUS / "train.jsonl", CORPUS / "val.jsonl"
    for p in (train, val):
        if not p.exists():
            raise SystemExit(f"FINALIZE FAIL: required corpus file missing: {p}")
    return train, val


def build_bundle(train: Path, val: Path, out_zip: Path, schema_doc: Path) -> tuple[Path, str, dict]:
    """Stage + write the ZIP; return (zip path, zip sha256, manifest)."""
    ARTIFACTS.mkdir(exist_ok=True)
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    files: dict[str, Path] = {
        "train.jsonl": train,
        "val.jsonl": val,
        "SCHEMA.md": schema_doc,
    }
    stage = ARTIFACTS / "_bundle_stage"
    stage.mkdir(exist_ok=True)
    for n, p in files.items():
        (stage / n).write_bytes(p.read_bytes())
    (stage / "label_map.json").write_text(json.dumps(LABEL_MAP, indent=2))
    (stage / "train_config.json").write_text(json.dumps(TRAIN_CONFIG, indent=2))
    (stage / "requirements-frozen.txt").write_text(REQUIREMENTS)
    bundle_manifest = {
        "schema_version": "agentpay-ir-v2",
        "base_model": BASE_MODEL,
        "base_model_revision": BASE_REVISION,
        "label_map": LABEL_MAP,
        "files": {n: sha256_file(stage / n) for n in BUNDLE_FILES},
        "excluded": ["test.jsonl (frozen)", "human gold (review_role=gold)",
                     "fresh_ood_v2.jsonl (untouched OOD)", "decisions/linkage/role manifests"],
    }
    for k in MANIFEST_REQUIRED_FIELDS:
        assert k in bundle_manifest, k
    (stage / "bundle_manifest.json").write_text(json.dumps(bundle_manifest, indent=2))
    if out_zip.exists():
        out_zip.unlink()
    # Deterministic archive: fixed member order + fixed timestamps, so rebuilding
    # the bundle from the same inputs yields byte-identical zip bytes and the
    # notebook's externally pinned EXPECTED_BUNDLE_SHA256 stays valid.
    members = ["train.jsonl", "val.jsonl", "bundle_manifest.json", *BUNDLE_FILES[2:]]
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for n in members:
            info = zipfile.ZipInfo(n, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, (stage / n).read_bytes())
    return out_zip, sha256_file(out_zip), bundle_manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus-dir", default=None,
                    help="corpus directory providing train.jsonl/val.jsonl (e.g. corpus/final)")
    ap.add_argument("--train", default=None, help="explicit train.jsonl path (overrides --corpus-dir)")
    ap.add_argument("--val", default=None, help="explicit val.jsonl path (overrides --corpus-dir)")
    ap.add_argument("--out-zip", default=str(OUT_ZIP))
    ap.add_argument("--schema-doc", default=str(DOCS / "SCHEMA.md"))
    ap.add_argument("--notebook-out", default=str(NOTEBOOK_PATH))
    ap.add_argument("--no-notebook", action="store_true",
                    help="write the ZIP only; skip notebook generation")
    args = ap.parse_args()

    train, val = resolve_train_val(args)
    out_zip, zip_sha, _manifest = build_bundle(train, val, Path(args.out_zip),
                                           Path(args.schema_doc))
    print("bundle:", out_zip, out_zip.stat().st_size, "bytes | sha256:", zip_sha)
    print("train:", sha256_file(train))
    print("val:  ", sha256_file(val))

    if not args.no_notebook:
        nb = render_notebook(zip_sha)
        nb_path = Path(args.notebook_out)
        nb_path.parent.mkdir(parents=True, exist_ok=True)
        nb_path.write_text(json.dumps(nb, indent=1))
        print("notebook:", nb_path, "| EXPECTED_BUNDLE_SHA256:", zip_sha[:16], "…")

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
