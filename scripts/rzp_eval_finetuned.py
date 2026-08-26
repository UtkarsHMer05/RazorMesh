#!/usr/bin/env python3
"""P3-M36: fine-tuned NLI evaluation.

Loads the FINE-TUNED model from the artifact directory produced by the Colab
training notebook, reads its label_map.json (so label-index normalization is
driven by the artifact, not by a hard-coded mapping), and evaluates on:

  - the FROZEN test split (frozen_v1/test.jsonl) — same harness as M28/M29;
  - the FROZEN val split (frozen_v1/val.jsonl) for parity;
  - the human gold set (data/phase3/gold/gold_decisions.json filtered through
    ingest_gold_decisions, projected onto the AgentPay-IR record_id) — this is
    the central M36 deliverable (close the M26 gap).

Writes:
  docs/PHASE3_NLI_FINETUNED_METRICS.json
    (single artifact with per-split metrics + label map provenance)
  docs/PHASE3_NLI_FINETUNE_EVAL.md
    (one-page comparison against baseline B)

Usage:
  services/ml-venv/bin/python scripts/rzp_eval_finetuned.py
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

DEFAULT_ARTIFACT = REPO_ROOT / "artifacts" / "models" / "incoming" / "phase3-finetuned"
FROZEN = REPO_ROOT / "data" / "phase3" / "dataset" / "frozen_v1"
GOLD_DECISIONS = REPO_ROOT / "data" / "phase3" / "gold" / "gold_decisions.json"
FROZEN_TEST = FROZEN / "test.jsonl"
FROZEN_VAL = FROZEN / "val.jsonl"
DOCS = REPO_ROOT / "docs"


def _load_records(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _human_gold_pairs() -> dict[str, list[tuple[str, str, str, str]]]:
    """Return split-aware human-gold pairs.

    The 320 human-gold cards were drawn stratified from the FULL seed (so they
    span train/val/test). P3-S09 forbids any training-set card from being
    reported as a holdout. The honest breakdown is:

      heldout: cards in val or test (never seen by training)
      in_train: cards in train (in the training pool; reported separately for
                transparency, NOT as a holdout number)
      total:    all 320 valid cards (excludes INVALID/UNLABELED)

    Filters out INVALID/UNLABELED rows via ingest_gold_decisions so metrics
    never include cards the human rejected.
    """
    from razormesh_api.dataset_quality import ingest_gold_decisions

    decisions = json.loads(GOLD_DECISIONS.read_text())
    test_records = {r["record_id"]: r for r in _load_records(FROZEN_TEST)}
    val_records = {r["record_id"]: r for r in _load_records(FROZEN_VAL)}
    train_records = {r["record_id"]: r for r in _load_records(REPO_ROOT / "data" / "phase3" / "dataset" / "frozen_v1" / "train.jsonl")}

    all_known = {**test_records, **val_records, **train_records}
    ingest = ingest_gold_decisions(decisions, known_record_ids=set(all_known))
    heldout: list[tuple[str, str, str, str]] = []
    in_train: list[tuple[str, str, str, str]] = []
    for record_id, label in ingest.valid.items():
        rec = all_known.get(record_id)
        if rec is None:
            continue
        tup = (
            record_id,
            str(rec["premise"]),
            str(rec["hypothesis"]),
            label,
        )
        if record_id in test_records or record_id in val_records:
            heldout.append(tup)
        else:
            in_train.append(tup)
    excluded = dict(ingest.excluded)
    return {
        "heldout": heldout,
        "in_train": in_train,
        "excluded": excluded,
        "valid_total": len(heldout) + len(in_train),
    }


def _infer(
    tokenizer,
    model,
    rows: list[dict[str, object]],
    label_map: dict[int, str],
    *,
    batch: int,
) -> tuple[list[str], list[str]]:
    import torch

    gold: list[str] = []
    pred: list[str] = []
    t0 = time.time()
    for i in range(0, len(rows), batch):
        batch_rows = rows[i : i + batch]
        features = tokenizer(
            [str(r["premise"]) for r in batch_rows],
            [str(r["hypothesis"]) for r in batch_rows],
            truncation=True,
            max_length=256,
            padding=True,
            return_tensors="pt",
        )
        with torch.no_grad():
            logits = model(**features).logits
        probs = torch.softmax(logits, dim=-1)
        confs, idxs = probs.max(dim=-1)
        for r, idx, conf in zip(batch_rows, idxs.tolist(), confs.tolist()):
            gold.append(str(r["label"]))
            pred.append(label_map[int(idx)])
        if (i // batch) % 5 == 0:
            done = min(i + batch, len(rows))
            print(
                f"  {done}/{len(rows)} pairs ({time.time() - t0:.0f}s)", flush=True
            )
    return gold, pred


def _infer_triples(
    tokenizer,
    model,
    rows: list[tuple[str, str, str, str]],
    label_map: dict[int, str],
    *,
    batch: int,
) -> tuple[list[str], list[str]]:
    """Like _infer but for the gold format (id, premise, hypothesis, label)."""
    import torch

    gold: list[str] = []
    pred: list[str] = []
    t0 = time.time()
    for i in range(0, len(rows), batch):
        batch_rows = rows[i : i + batch]
        features = tokenizer(
            [r[1] for r in batch_rows],
            [r[2] for r in batch_rows],
            truncation=True,
            max_length=256,
            padding=True,
            return_tensors="pt",
        )
        with torch.no_grad():
            logits = model(**features).logits
        probs = torch.softmax(logits, dim=-1)
        _, idxs = probs.max(dim=-1)
        for r, idx in zip(batch_rows, idxs.tolist()):
            gold.append(r[3])
            pred.append(label_map[int(idx)])
        if (i // batch) % 5 == 0:
            done = min(i + batch, len(rows))
            print(
                f"  {done}/{len(rows)} pairs ({time.time() - t0:.0f}s)", flush=True
            )
    return gold, pred


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--artifact",
        type=Path,
        default=DEFAULT_ARTIFACT,
        help="Path to unzipped fine-tuned model dir",
    )
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument(
        "--limit", type=int, default=0, help="cap rows per split (0 = all)"
    )
    args = ap.parse_args()

    if not (args.artifact / "config.json").exists():
        print(f"artifact dir missing config.json: {args.artifact}")
        return 1
    if not (args.artifact / "label_map.json").exists():
        print(f"artifact dir missing label_map.json: {args.artifact}")
        return 1
    if not list(args.artifact.glob("*.safetensors")) and not (
        args.artifact / "pytorch_model.bin"
    ).exists():
        print(f"artifact dir has no weights file: {args.artifact}")
        return 1

    label_map_raw = json.loads((args.artifact / "label_map.json").read_text())
    label_map = {int(k): v for k, v in label_map_raw.items()}
    metrics_in_artifact = json.loads((args.artifact / "metrics.json").read_text())
    base_model = (args.artifact / "base_model.txt").read_text().strip()
    config = json.loads((args.artifact / "config.json").read_text())

    print(f"loading fine-tuned model from {args.artifact}")
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(args.artifact))
    model = AutoModelForSequenceClassification.from_pretrained(str(args.artifact))
    model.eval()

    from razormesh_api.nli_eval import compute_metrics

    splits: dict[str, dict[str, object]] = {}
    artifact_payload: dict[str, object] = {
        "model_artifact": str(args.artifact),
        "base_model": base_model,
        "transformers_version": config.get("transformers_version"),
        "label_map": label_map_raw,
        "artifact_metrics": metrics_in_artifact,
        "generated_at_utc": datetime.now(UTC).isoformat(),
    }

    for split_name, split_path in (("val", FROZEN_VAL), ("test", FROZEN_TEST)):
        rows = _load_records(split_path)
        if args.limit:
            rows = rows[: args.limit]
        print(f"--- split={split_name} rows={len(rows)} ---")
        gold, pred = _infer(
            tokenizer, model, rows, label_map, batch=args.batch
        )
        m = compute_metrics(gold, pred)
        splits[split_name] = json.loads(m.to_json())
        splits[split_name]["unsafe_entail_on_contradiction"] = next(
            (
                c
                for g, row in splits[split_name]["confusion"].items()
                for p, c in row.items()
                if g == "contradiction" and p == "entailment"
            ),
            0,
        )
        print(
            f"  acc={splits[split_name]['accuracy']:.4f} "
            f"macro_f1={splits[split_name]['macro_f1']:.4f} "
            f"unsafe_entail={splits[split_name]['unsafe_entail_on_contradiction']}"
        )

    gold_split = _human_gold_pairs()
    for split_name, pairs in (
        ("human_gold_heldout", gold_split["heldout"]),
        ("human_gold_in_train", gold_split["in_train"]),
        ("human_gold_all", gold_split["heldout"] + gold_split["in_train"]),
    ):
        if args.limit:
            pairs = pairs[: args.limit]
        print(
            f"--- {split_name} pairs={len(pairs)} "
            f"excluded={len(gold_split['excluded'])} ---"
        )
        if not pairs:
            continue
        gold, pred = _infer_triples(
            tokenizer, model, pairs, label_map, batch=args.batch
        )
        m = compute_metrics(gold, pred)
        splits[split_name] = json.loads(m.to_json())
        splits[split_name]["unsafe_entail_on_contradiction"] = next(
            (
                c
                for g, row in splits[split_name]["confusion"].items()
                for p, c in row.items()
                if g == "contradiction" and p == "entailment"
            ),
            0,
        )
        splits[split_name]["excluded_count"] = len(gold_split["excluded"])
        print(
            f"  acc={splits[split_name]['accuracy']:.4f} "
            f"macro_f1={splits[split_name]['macro_f1']:.4f} "
            f"unsafe_entail={splits[split_name]['unsafe_entail_on_contradiction']}"
        )

    artifact_payload["splits"] = splits
    out = DOCS / "PHASE3_NLI_FINETUNED_METRICS.json"
    out.write_text(json.dumps(artifact_payload, indent=2))
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
