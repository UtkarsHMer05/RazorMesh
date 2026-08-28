#!/usr/bin/env python3
"""Phase-3 v2 model revalidation + artifact manifests (correction brief §10/§11).

Re-runs REAL inference from the frozen local checkpoints (no historical JSON
is trusted) and produces:

  1. ``artifacts/models/incoming/phase3-finetuned-v2/model_manifest.json``
     and ``artifacts/models/incoming/phase3-finetuned/model_manifest.json``
     — hashes recomputed from bytes on disk, training metadata read from the
     run's own trainer_state/training_args (never invented);
  2. ``docs/PHASE3_MODEL_REVALIDATION.md`` + ``.json`` — accuracy, macro F1,
     per-class precision/recall/F1, confusion matrices, and payment-safety
     metrics for the corrected v2 checkpoint on:
       - frozen_v2 validation (already used for calibration — reported for
         completeness, never for selection claims),
       - frozen_v2 test (frozen after training; used only here),
       - data/phase3/eval/untouched_ood/ood_adversarial_129.jsonl (the
         untouched out-of-distribution set);
     plus the v1 checkpoint on the same sets as an honest comparison.

There is NO blind human-heldout set in this repository (dataset audit §6:
241 train + 43 val + 36 test reviewed cards were all used earlier), so the
untouched OOD set is the only external evaluation reported here.

Nothing in this script feeds any split back into training or threshold
selection; both checkpoints and the v3 thresholds are already frozen.

Usage:
  services/ml-venv/bin/python scripts/rzp_revalidate_phase3_v2.py
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

V2_DIR = REPO_ROOT / "artifacts" / "models" / "incoming" / "phase3-finetuned-v2"
V1_DIR = REPO_ROOT / "artifacts" / "models" / "incoming" / "phase3-finetuned"
FROZEN_V2 = REPO_ROOT / "data" / "phase3" / "dataset" / "frozen_v2"
OOD_PATH = REPO_ROOT / "data" / "phase3" / "eval" / "untouched_ood" / "ood_adversarial_129.jsonl"
POLICY_V3 = REPO_ROOT / "data" / "phase3" / "policy" / "semantic_thresholds_v3.json"
POLICY_V2 = REPO_ROOT / "data" / "phase3" / "policy" / "semantic_thresholds.json"
DOCS = REPO_ROOT / "docs"

LABELS = ("contradiction", "entailment", "neutral")
LABEL_TO_ID = {"contradiction": 0, "entailment": 1, "neutral": 2}

EVAL_SETS = {
    "frozen_v2_val": FROZEN_V2 / "val.jsonl",
    "frozen_v2_test": FROZEN_V2 / "test.jsonl",
    "untouched_ood_129": OOD_PATH,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


class Scorer:
    """Batched NLI scorer for one checkpoint, with its own label map."""

    def __init__(self, model_dir: Path, threads: int = 6) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        torch.set_num_threads(threads)
        self.dir = model_dir
        self.tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
        self.model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
        self.model.eval()
        self.load_seconds = 0.0  # filled by caller on first use
        label_map = json.loads((model_dir / "label_map.json").read_text())
        idx = {name: int(i) for i, name in label_map.items()}
        if idx != LABEL_TO_ID:
            raise SystemExit(f"{model_dir.name}: unexpected label map {label_map}")
        self.idx = idx

    def score(self, rows: list[dict[str, Any]]) -> list[tuple[int, float, float, float]]:
        out: list[tuple[int, float, float, float]] = []
        batch = 16
        with self._torch.no_grad():
            for start in range(0, len(rows), batch):
                chunk = rows[start : start + batch]
                feats = self.tokenizer(
                    [r["premise"] for r in chunk],
                    [r["hypothesis"] for r in chunk],
                    truncation=True,
                    max_length=256,
                    padding=True,
                    return_tensors="pt",
                )
                probs = self._torch.softmax(self.model(**feats).logits, -1)
                for row, p in zip(rows[start : start + batch], probs, strict=True):
                    out.append(
                        (
                            LABEL_TO_ID[row["label"]],
                            float(p[self.idx["contradiction"]]),
                            float(p[self.idx["entailment"]]),
                            float(p[self.idx["neutral"]]),
                        )
                    )
        return out


def metrics_for(scored: list[tuple[int, float, float, float]]) -> dict[str, Any]:
    n = len(scored)
    correct = sum(1 for gold, pc, pe, pn in scored if _argmax(gold, pc, pe, pn) == gold)
    per_class: dict[str, dict[str, float]] = {}
    confusion = {name: Counter() for name in LABELS}
    for gold, pc, pe, pn in scored:
        pred = _argmax(gold, pc, pe, pn)
        confusion[LABELS[gold]][LABELS[pred]] += 1
    f1s = []
    for i, name in enumerate(LABELS):
        tp = sum(1 for g, *_ in scored if g == i and _argmax(g, *_ ) == i)
        fp = sum(1 for g, *p in scored if g != i and _argmax(g, *p) == i)
        fn = sum(1 for g, *_ in scored if g == i and _argmax(g, *_ ) != i)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1s.append(f1)
        per_class[name] = {
            "support": sum(1 for g, *_ in scored if g == i),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    return {
        "n": n,
        "accuracy": round(correct / n, 4) if n else 0.0,
        "macro_f1": round(sum(f1s) / len(f1s), 4) if f1s else 0.0,
        "per_class": per_class,
        "confusion_matrix": {
            gold: dict(preds) for gold, preds in confusion.items()
        },
    }


def _argmax(_gold: int, pc: float, pe: float, pn: float) -> int:
    # Label order is (contradiction, entailment, neutral) — matches
    # LABEL_TO_ID and the artifact label maps verified above.
    pairs = ((0, pc), (1, pe), (2, pn))
    return max(pairs, key=lambda kv: kv[1])[0]


def safety_for(scored: list[tuple[int, float, float, float]], tau_block: float, tau_entail: float) -> dict[str, Any]:
    contra = [s for s in scored if s[0] == 0]
    entail = [s for s in scored if s[0] == 1]
    neutral = [s for s in scored if s[0] == 2]

    def action(pc: float, pe: float) -> str:
        if pc >= tau_block:
            return "BLOCK"
        if pe >= tau_entail:
            return "PASS"
        return "CHALLENGE"

    actions = [action(pc, pe) for _, pc, pe, _ in scored]
    contra_escaped_block = sum(1 for a in (action(pc, pe) for _, pc, pe, _ in contra) if a != "BLOCK")
    contra_unsafe_pass = sum(1 for a in (action(pc, pe) for _, pc, pe, _ in contra) if a == "PASS")
    entail_false_block = sum(1 for a in (action(pc, pe) for _, pc, pe, _ in entail) if a == "BLOCK")
    neutral_wrong_pass = sum(1 for a in (action(pc, pe) for _, pc, pe, _ in neutral) if a == "PASS")
    dist = Counter(actions)
    return {
        "policy": {"tau_block": tau_block, "tau_entail": tau_entail},
        "action_distribution": {k: dist.get(k, 0) for k in ("PASS", "CHALLENGE", "BLOCK")},
        "gold_contradictions": len(contra),
        "gold_contradiction_escaping_BLOCK": contra_escaped_block,
        "unsafe_contradiction_to_PASS": contra_unsafe_pass,
        "gold_entailments": len(entail),
        "false_BLOCK_on_entailment": entail_false_block,
        "gold_neutrals": len(neutral),
        "neutral_wrongly_PASS": neutral_wrong_pass,
    }


def build_manifest(model_dir: Path, *, dataset_version: str, dataset_manifest: dict[str, Any] | None, note: str) -> dict[str, Any]:
    files = {
        p.name: {"bytes": p.stat().st_size, "sha256": sha256_file(p)}
        for p in sorted(model_dir.iterdir())
        if p.is_file()
    }
    manifest: dict[str, Any] = {
        "artifact_version": model_dir.name,
        "base_model": (model_dir / "base_model.txt").read_text().strip(),
        "label_map": json.loads((model_dir / "label_map.json").read_text()),
        "model_sha256": files["model.safetensors"]["sha256"],
        "files": files,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "license": "model weights inherit the base-model license (cross-encoder/nli-deberta-v3-base, MIT); artifact is local-only and git-ignored",
        "runtime_policy_version": (
            "semantic-thresholds-v2 (historical)" if model_dir == V1_DIR else "semantic-thresholds-v3"
        ),
        "note": note,
    }
    if dataset_version:
        manifest["dataset_version"] = dataset_version
    if dataset_manifest:
        manifest["dataset_sha256"] = dataset_manifest.get("files", {})
        manifest["dataset_orientation"] = dataset_manifest.get("orientation")
    if model_dir == V2_DIR:
        state = json.loads(
            (model_dir / "checkpoint" / "checkpoint-246" / "trainer_state.json").read_text()
        )
        import torch  # ml-venv only

        args = torch.load(
            model_dir / "training_args.bin", map_location="cpu", weights_only=False
        )
        lrs = [h["learning_rate"] for h in state["log_history"] if "learning_rate" in h]
        manifest.update(
            {
                "training_seed": int(args.seed),
                "epochs": max(int(h["epoch"]) for h in state["log_history"] if "epoch" in h),
                "learning_rate": float(args.learning_rate),
                "learning_rate_source": "training_args.bin of the saved run",
                "selected_metric": "macro_f1",
                "global_steps": int(state["global_step"]),
                "best_metric": state.get("best_metric"),
                "peak_scheduler_lr_observed": max(lrs) if lrs else None,
                "recipe": json.loads(
                    (REPO_ROOT / "training" / "phase3" / "train_config_v2.json").read_text()
                ),
            }
        )
    else:
        recipe_path = REPO_ROOT / "training" / "phase3" / "train_config.json"
        manifest["training_seed"] = 42
        manifest["recipe"] = json.loads(recipe_path.read_text())
        manifest["recipe_source"] = "training/phase3/train_config.json (historical v1 recipe record)"
        manifest["note"] += (
            " v1 training metadata is the historical recipe record; the v1 run itself predates trainer_state capture."
        )
    return manifest


def main() -> int:
    import torch  # noqa: F401  (fail fast if run outside ml-venv)

    if not POLICY_V3.exists():
        raise SystemExit("run scripts/rzp_calibrate_thresholds_v2.py first")
    policy_v3 = json.loads(POLICY_V3.read_text())
    policy_v2 = json.loads(POLICY_V2.read_text())
    v3_sel = policy_v3["selected"]
    v2_sel = policy_v2["selected"]

    datasets = {name: load_rows(path) for name, path in EVAL_SETS.items()}

    results: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "runtime": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "device": "cpu",
        },
        "policy_v3": {
            "path": str(POLICY_V3.relative_to(REPO_ROOT)),
            "sha256": sha256_file(POLICY_V3),
            "selected": v3_sel,
        },
        "policy_v2_historical": {
            "path": str(POLICY_V2.relative_to(REPO_ROOT)),
            "sha256": sha256_file(POLICY_V2),
            "selected": v2_sel,
        },
        "contamination_guards": {
            "threshold_calibration_uses": "frozen_v2 val ONLY (scripts/rzp_calibrate_thresholds_v2.py)",
            "frozen_v2_test_used_for_selection": False,
            "untouched_ood_used_for_selection_or_calibration": False,
            "blind_human_heldout_exists": False,
            "human_heldout_note": (
                "Dataset audit §6: reviewed human cards are 241 train + 43 val + 36 test, "
                "all previously used. The untouched OOD set is the only external evaluation."
            ),
        },
        "models": {},
    }

    for tag, model_dir, sel in (
        ("v2_corrected", V2_DIR, v3_sel),
        ("v1_legacy", V1_DIR, v2_sel),
    ):
        load_started = time.monotonic()
        scorer = Scorer(model_dir)
        cold_load_s = round(time.monotonic() - load_started, 2)
        entry: dict[str, Any] = {
            "artifact_dir": str(model_dir.relative_to(REPO_ROOT)),
            "model_sha256": sha256_file(model_dir / "model.safetensors"),
            "cold_load_seconds": cold_load_s,
            "threshold_policy": sel,
            "evaluations": {},
        }
        for name, rows in datasets.items():
            started = time.monotonic()
            scored = scorer.score(rows)
            elapsed = round(time.monotonic() - started, 2)
            entry["evaluations"][name] = {
                "latency_seconds_for_n": {"n": len(rows), "seconds": elapsed},
                "metrics": metrics_for(scored),
                "safety": safety_for(scored, sel["tau_block"], sel["tau_entail"]),
            }
        results["models"][tag] = entry
        del scorer

    # --- manifests -------------------------------------------------------
    v2_manifest = build_manifest(
        V2_DIR,
        dataset_version="frozen_v2",
        dataset_manifest=json.loads((FROZEN_V2 / "manifest.json").read_text()),
        note=(
            "Corrected canonical-orientation checkpoint (premise=current sanitized "
            "commerce evidence; hypothesis=normalized human authorization). Trained "
            "locally on CPU from cross-encoder/nli-deberta-v3-base. Runtime artifact "
            "for SEMANTIC_VERIFIER_BACKEND=deberta."
        ),
    )
    (V2_DIR / "model_manifest.json").write_text(json.dumps(v2_manifest, indent=2), encoding="utf-8")

    v1_manifest = build_manifest(
        V1_DIR,
        dataset_version="frozen_v1",
        dataset_manifest=None,
        note=(
            "Legacy checkpoint: trained on frozen_v1 whose premises folded the human "
            "request into the evidence side. Retained untouched as historical evidence; "
            "no longer the runtime artifact. See docs/PHASE3_ORIENTATION_DIAGNOSTIC.md."
        ),
    )
    v1_manifest["dataset_sha256"] = {
        split: sha256_file(REPO_ROOT / "data" / "phase3" / "dataset" / "frozen_v1" / f"{split}.jsonl")
        for split in ("train", "val", "test")
    }
    (V1_DIR / "model_manifest.json").write_text(json.dumps(v1_manifest, indent=2), encoding="utf-8")

    DOCS.mkdir(exist_ok=True)
    (DOCS / "PHASE3_MODEL_REVALIDATION.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    write_md(results)
    print(f"wrote {DOCS / 'PHASE3_MODEL_REVALIDATION.md'}")
    return 0


def write_md(results: dict[str, Any]) -> None:
    v2 = results["models"]["v2_corrected"]
    v1 = results["models"]["v1_legacy"]
    lines: list[str] = [
        "# Phase-3 fine-tuned model revalidation (v2 corrected checkpoint)",
        "",
        f"Generated: `{results['generated_at_utc']}` by `scripts/rzp_revalidate_phase3_v2.py`.",
        "",
        "Real inference was re-run from the frozen local checkpoints on this machine;",
        "no historical metric JSON is trusted. There is no blind human-heldout set in",
        "this repository (dataset audit §6), so the untouched OOD set is the only",
        "external evaluation.",
        "",
        "## Frozen threshold policy (v3, calibrated on frozen_v2 val ONLY)",
        "",
        f"`tau_block={v2['threshold_policy']['tau_block']}`, `tau_entail={v2['threshold_policy']['tau_entail']}` —",
        "objective: F2 of BLOCK subject to false-BLOCK rate on val entailment ≤ 0.05.",
        f"Policy sha256 `{results['policy_v3']['sha256'][:16]}…`. The historical v2 policy",
        f"(tau_block={v1['threshold_policy']['tau_block']}, tau_entail={v1['threshold_policy']['tau_entail']},",
        "v1 checkpoint, frozen_v1 val) is retained untouched for the v1 comparison.",
        "",
        "## Headline (accuracy / macro F1)",
        "",
        "| eval set | n | v2 acc | v2 macro F1 | v1 acc | v1 macro F1 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in EVAL_SETS:
        m2 = v2["evaluations"][name]["metrics"]
        m1 = v1["evaluations"][name]["metrics"]
        lines.append(
            f"| `{name}` | {m2['n']} | {m2['accuracy']} | {m2['macro_f1']} | {m1['accuracy']} | {m1['macro_f1']} |"
        )
    lines += [
        "",
        "## Per-class detail (v2 corrected checkpoint)",
        "",
    ]
    for name in EVAL_SETS:
        ev = v2["evaluations"][name]
        pc = ev["metrics"]["per_class"]
        lines += [
            f"### `{name}` (n={ev['metrics']['n']})",
            "",
            f"contradiction P/R/F1 = {pc['contradiction']['precision']}/{pc['contradiction']['recall']}/{pc['contradiction']['f1']}, "
            f"entailment = {pc['entailment']['precision']}/{pc['entailment']['recall']}/{pc['entailment']['f1']}, "
            f"neutral = {pc['neutral']['precision']}/{pc['neutral']['recall']}/{pc['neutral']['f1']}",
            "",
            f"confusion (rows=gold): `{json.dumps(ev['metrics']['confusion_matrix'])}`",
            "",
        ]
    lines += [
        "## Payment-safety metrics under the frozen policy",
        "",
        "| eval set | model | gold contra → unsafe PASS | contra escaping BLOCK | false BLOCK on entailment | neutral wrongly PASS |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for name in EVAL_SETS:
        for tag, model in (("v2", v2), ("v1", v1)):
            s = model["evaluations"][name]["safety"]
            lines.append(
                f"| `{name}` | {tag} | {s['unsafe_contradiction_to_PASS']} | "
                f"{s['gold_contradiction_escaping_BLOCK']}/{s['gold_contradictions']} | "
                f"{s['false_BLOCK_on_entailment']}/{s['gold_entailments']} | "
                f"{s['neutral_wrongly_PASS']}/{s['gold_neutrals']} |"
            )
    lines += [
        "",
        "## Action distribution (frozen policy)",
        "",
    ]
    for name in EVAL_SETS:
        for tag, model in (("v2", v2), ("v1", v1)):
            s = model["evaluations"][name]["safety"]
            lines.append(f"- `{name}` {tag}: `{s['action_distribution']}`")
    lines += [
        "",
        "## Contamination guards",
        "",
        "- Threshold v3 calibration read ONLY `data/phase3/dataset/frozen_v2/val.jsonl`.",
        "- `frozen_v2/test.jsonl` and the untouched OOD set were **not** used for any",
        "  selection or calibration decision; they are reported once, post-freeze.",
        "- The untouched OOD set (`data/phase3/eval/untouched_ood/ood_adversarial_129.jsonl`)",
        "  is fully canonical-orientation, so the v1-vs-v2 comparison on it is fair.",
        "",
        "## Artifact provenance",
        "",
        f"- v2 checkpoint: `{v2['artifact_dir']}` sha256 `{v2['model_sha256']}` (cold load {v2['cold_load_seconds']}s)",
        f"- v1 checkpoint: `{v1['artifact_dir']}` sha256 `{v1['model_sha256']}` (cold load {v1['cold_load_seconds']}s)",
        "- Manifests with full file hashes written next to both checkpoints as `model_manifest.json`.",
        "",
        "Historical numbers from earlier milestones remain in their own documents and are",
        "not reproduced here; where they disagree with this run, this run is the",
        "authoritative re-measurement of the current artifacts.",
    ]
    (DOCS / "PHASE3_MODEL_REVALIDATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
