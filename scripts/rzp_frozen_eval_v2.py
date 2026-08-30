#!/usr/bin/env python3
"""M2 ONE-SHOT frozen evaluation for AgentPay-IR v2 acceptance (LOCKED).

Executes exactly once per --tag: refuses to run if the output directory
already exists. Evaluates one local artifact directory on the three FINAL
frozen sets and nothing else:

  - final test split   data/agentpay_ir_v2/corpus/final/test.jsonl     (2,227)
  - human gold         data/agentpay_ir_v2/review/GOLD_FROZEN_V3.jsonl (301)
  - fresh OOD          data/agentpay_ir_v2/eval/fresh_ood_v2.jsonl     (665)

Every input SHA256 is verified against the pinned freeze values before any
model runs; a mismatch aborts. Predictions are argmax only (no thresholds,
no calibration, no tuning). Label orientation is driven by the artifact's
own label_map.json. Metrics come from the canonical razormesh_api.nli_eval.

Derived safety metrics per split:
  - unsafe_c_to_e  : gold contradiction -> predicted entailment (unsafe)
  - safe_e_to_c    : gold entailment  -> predicted contradiction (false block)
The fresh-OOD split additionally gets a per-security-family breakdown.

Usage (one invocation per model; each tag runs once ever):
  services/api/.venv/bin/python scripts/rzp_frozen_eval_v2.py \
      --artifact artifacts/models/incoming/phase3-finetuned-v2 \
      --tag pre_v2_baseline
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

FROZEN_INPUTS: dict[str, tuple[Path, str, int]] = {
    "final_test": (
        REPO_ROOT / "data/agentpay_ir_v2/corpus/final/test.jsonl",
        "ceae19519291836e7daeb7773a7a1c1534b2affe6deb185b8ca9f387bdda8166",
        2227,
    ),
    "human_gold": (
        REPO_ROOT / "data/agentpay_ir_v2/review/GOLD_FROZEN_V3.jsonl",
        "57f9c469341b7d79936a3674b46f63581dcde1b0aa416a646276714100ade58f",
        301,
    ),
    "fresh_ood": (
        REPO_ROOT / "data/agentpay_ir_v2/eval/fresh_ood_v2.jsonl",
        "8948a8e3750410a51ab0e3e8ce5b61a662b5d28daa1311a711558db2f2888ade",
        665,
    ),
}
LABELS = ("entailment", "neutral", "contradiction")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def infer_split(
    tokenizer,
    model,
    device: str,
    rows: list[dict[str, object]],
    label_map: dict[int, str],
    *,
    batch: int,
    max_length: int,
    split_name: str,
) -> list[dict[str, object]]:
    import torch

    out: list[dict[str, object]] = []
    t0 = time.time()
    with torch.inference_mode():
        for i in range(0, len(rows), batch):
            chunk = rows[i : i + batch]
            features = tokenizer(
                [str(r["premise"]) for r in chunk],
                [str(r["hypothesis"]) for r in chunk],
                truncation=True,
                max_length=max_length,
                padding=True,
                return_tensors="pt",
            ).to(device)
            logits = model(**features).logits
            probs = torch.softmax(logits, dim=-1).to("cpu")
            confs, idxs = probs.max(dim=-1)
            for r, p_vec, idx, conf in zip(
                chunk, probs.tolist(), idxs.tolist(), confs.tolist(), strict=True
            ):
                out.append(
                    {
                        "record_id": str(r.get("record_id", "")),
                        "gold": str(r["label"]),
                        "pred": label_map[int(idx)],
                        "confidence": round(float(conf), 6),
                        "probs": {
                            label_map[j]: round(float(p_vec[j]), 6)
                            for j in range(len(label_map))
                        },
                    }
                )
            done = min(i + batch, len(rows))
            print(
                f"  [{split_name}] {done}/{len(rows)} pairs "
                f"({time.time() - t0:.0f}s)",
                flush=True,
            )
    return out


def derive_metrics(
    gold: list[str], pred: list[str]
) -> dict[str, object]:
    from razormesh_api.nli_eval import compute_metrics

    m = compute_metrics(gold, pred)
    d: dict[str, object] = json.loads(m.to_json())
    n = len(gold)
    unsafe = sum(
        1 for g, p in zip(gold, pred, strict=True) if g == "contradiction" and p == "entailment"
    )
    safe_false_block = sum(
        1 for g, p in zip(gold, pred, strict=True) if g == "entailment" and p == "contradiction"
    )
    d["recalls"] = {
        lab: d["per_class"][lab]["recall"] for lab in LABELS
    }
    d["unsafe_c_to_e"] = {"count": unsafe, "rate": round(unsafe / n, 6)}
    d["safe_e_to_c"] = {
        "count": safe_false_block,
        "rate": round(safe_false_block / n, 6),
    }
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", type=Path, required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--max-length", type=int, default=256)
    ap.add_argument(
        "--outdir-root",
        type=Path,
        default=REPO_ROOT / "docs/agentpay_ir_v2/frozen_eval",
    )
    args = ap.parse_args()

    artifact = args.artifact.resolve()
    outdir = args.outdir_root / args.tag
    if outdir.exists():
        print(
            f"ONE-SHOT VIOLATION: output dir already exists: {outdir}\n"
            "Frozen evaluation is one-shot per tag; refusing to overwrite.",
            flush=True,
        )
        return 2

    print(f"=== M2 FROZEN EVAL tag={args.tag} artifact={artifact} ===", flush=True)

    # 1. Verify frozen inputs against pinned hashes/counts BEFORE anything else.
    verified: dict[str, dict[str, object]] = {}
    for name, (path, pin, count) in FROZEN_INPUTS.items():
        if not path.exists():
            print(f"FROZEN INPUT MISSING: {path}")
            return 1
        digest = sha256_file(path)
        if digest != pin:
            print(
                f"FROZEN INPUT HASH MISMATCH: {path}\n  expected {pin}\n  actual   {digest}"
            )
            return 1
        rows = load_rows(path)
        if len(rows) != count:
            print(f"FROZEN INPUT COUNT MISMATCH: {path}: {len(rows)} != {count}")
            return 1
        labels = {str(r["label"]) for r in rows}
        if not labels <= set(LABELS):
            print(f"FROZEN INPUT UNKNOWN LABELS in {path}: {labels - set(LABELS)}")
            return 1
        verified[name] = {
            "path": str(path.relative_to(REPO_ROOT)),
            "sha256": digest,
            "rows": len(rows),
        }
        print(f"  input {name}: {len(rows)} rows, sha256 OK")
    ood_rows_by_split: dict[str, list[dict[str, object]]] = {
        name: load_rows(path) for name, (path, _, _) in FROZEN_INPUTS.items()
    }

    # 2. Load artifact; orientation from its own label_map.json.
    for required in ("config.json", "label_map.json"):
        if not (artifact / required).exists():
            print(f"ARTIFACT MISSING {required}: {artifact}")
            return 1
    label_map_raw = json.loads((artifact / "label_map.json").read_text())
    label_map = {int(k): str(v) for k, v in label_map_raw.items()}
    if set(label_map.values()) != set(LABELS) or len(label_map) != 3:
        print(f"LABEL MAP INVALID: {label_map_raw}")
        return 1

    import torch
    import transformers
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    print("loading model (this may take ~30s)...", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(str(artifact))
    model = AutoModelForSequenceClassification.from_pretrained(str(artifact))
    model.eval()
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model.to(device)
    print(f"device={device} transformers={transformers.__version__}", flush=True)

    weights_sha = {
        p.name: sha256_file(p)
        for p in sorted(artifact.glob("*.safetensors"))
    }
    if not weights_sha:
        print(f"ARTIFACT MISSING weight file (*.safetensors): {artifact}")
        return 1

    # 3. One-shot inference + metrics per split.
    outdir.mkdir(parents=True)
    all_metrics: dict[str, object] = {}
    for name, rows in ood_rows_by_split.items():
        print(f"--- split={name} rows={len(rows)} ---", flush=True)
        preds = infer_split(
            tokenizer,
            model,
            device,
            rows,
            label_map,
            batch=args.batch,
            max_length=args.max_length,
            split_name=name,
        )
        gold = [p["gold"] for p in preds]
        pred = [p["pred"] for p in preds]
        metrics = derive_metrics(gold, pred)
        if name == "fresh_ood":
            families: dict[str, dict[str, object]] = {}
            by_family: dict[str, list[int]] = {}
            for i, r in enumerate(rows):
                fam = str(r.get("family", "unknown"))
                by_family.setdefault(fam, []).append(i)
            for fam in sorted(by_family):
                idxs = by_family[fam]
                fm = derive_metrics([gold[i] for i in idxs], [pred[i] for i in idxs])
                families[fam] = {
                    "n": len(idxs),
                    "accuracy": fm["accuracy"],
                    "macro_f1": fm["macro_f1"],
                    "unsafe_c_to_e": fm["unsafe_c_to_e"],
                    "safe_e_to_c": fm["safe_e_to_c"],
                }
            metrics["family_breakdown"] = families
        with (outdir / f"predictions_{name}.jsonl").open("w") as f:
            for p in preds:
                f.write(json.dumps(p) + "\n")
        all_metrics[name] = metrics
        print(
            f"  [{name}] acc={metrics['accuracy']} macro_f1={metrics['macro_f1']} "
            f"unsafe_c_to_e={metrics['unsafe_c_to_e']} "
            f"safe_e_to_c={metrics['safe_e_to_c']}",
            flush=True,
        )

    metrics_payload = {
        "tag": args.tag,
        "artifact_dir": str(artifact),
        "model_weights_sha256": weights_sha,
        "label_map": label_map_raw,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "device": device,
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "python": platform.python_version(),
        "max_length": args.max_length,
        "batch": args.batch,
        "frozen_inputs_verified": verified,
        "splits": all_metrics,
    }
    (outdir / "metrics.json").write_text(json.dumps(metrics_payload, indent=2))
    print(f"written: {outdir / 'metrics.json'}")
    print(f"ONE-SHOT COMPLETE for tag={args.tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
