#!/usr/bin/env python3
"""P3-M31/M35: verify a training bundle / imported artifact before use.

Bundle mode:  verify every manifest file hash.
Artifact mode: verify model dir contains config+weights+label_map, the label
map covers exactly the project label space, and metrics json parses.

Usage:
  python rzp_verify_training.py bundle   [training/phase3]
  python rzp_verify_training.py artifact models/phase3-finetuned
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

LABELS = {"entailment", "neutral", "contradiction"}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify_bundle(d: Path) -> bool:
    manifest = json.loads((d / "manifest.json").read_text())
    ok = True
    for name, expected in manifest["files"].items():
        actual = _sha(d / name)
        status = "OK" if actual == expected else "MISMATCH"
        if actual != expected:
            ok = False
        print(f"bundle {name}: {status}")
    for name in ("train.jsonl", "val.jsonl"):
        n = sum(1 for l in (d / name).read_text().splitlines() if l.strip())
        if n != manifest["counts"][name]:
            print(f"bundle {name}: COUNT MISMATCH {n} != {manifest['counts'][name]}")
            ok = False
    return ok


def verify_artifact(d: Path) -> bool:
    needed = ["config.json", "label_map.json", "metrics.json"]
    missing = [n for n in needed if not (d / n).exists()]
    weights = list(d.glob("*.safetensors")) or list(d.glob("pytorch_model.bin"))
    if not weights:
        missing.append("<weights>")
    if missing:
        print("artifact INCOMPLETE, missing:", missing)
        return False
    label_map = json.loads((d / "label_map.json").read_text())
    if set(label_map.values()) != LABELS or len(label_map) != 3:
        print("artifact label_map does not cover exactly the project label space")
        return False
    metrics = json.loads((d / "metrics.json").read_text())
    for key in ("eval_macro_f1", "eval_accuracy"):
        if key not in metrics:
            print(f"artifact metrics.json missing {key}")
            return False
    cfg = json.loads((d / "config.json").read_text())
    print(
        f"artifact OK: base={cfg.get('_name_or_path', 'unknown')} "
        f"labels={sorted(label_map.values())} "
        f"macro_f1={metrics['eval_macro_f1']}"
    )
    return True


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "bundle"
    target = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else (
            Path(__file__).resolve().parents[1]
            / "training"
            / "phase3"
        )
    )
    result = verify_bundle(target) if mode == "bundle" else verify_artifact(target)
    print("VERIFY:", "PASS" if result else "FAIL")
    return 0 if result else 1


if __name__ == "__main__":
    raise SystemExit(main())
