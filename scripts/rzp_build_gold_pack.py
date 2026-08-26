#!/usr/bin/env python3
"""P3-M25: build the HUMAN gold-review pack.

Stratifies a >=300-case review set from every available pool (seed,
adversarial, qwen-provisional candidates present at build time), prioritizing:

1. every family represented;
2. hard difficulty over-represented vs easy;
3. adversarial/safe-lookalike/injection families guaranteed seats;
4. per-record suggested_label shown LAST in the CSV so reviewers label first
   and compare after.

Outputs under data/phase3/gold/:
- gold_review.csv          record_id,premise,hypothesis,family,difficulty,suggested_label,priority
- gold_review.html         keyboard-driven local reviewer (1/2/3, arrows, export)
- INSTRUCTIONS.md          exact human procedure
- manifest.json            counts + pool composition + sha256 of csv

No model is called. Nothing here claims gold truth exists yet.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

from razormesh_api.agentpay_ir import AgentPayIRRecord, make_record

DATA = REPO_ROOT / "data" / "phase3"
OUT = DATA / "gold"
TARGET_N = 320

PRIORITY_FAMILIES = {
    "injection_resistance",
    "safe_lookalike",
    "trial_renewal_trap",
    "seller_alias",
    "variant_mismatch",
    "membership_insertion",
}


def _load_jsonl(path: Path) -> list[AgentPayIRRecord]:
    if not path.exists():
        return []
    out: list[AgentPayIRRecord] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        if "label_source" in raw:
            # full AgentPayIRRecord dump
            out.append(AgentPayIRRecord.model_validate(raw))
            continue
        # compact candidate-runner row -> reconstruct a provisional record
        created = raw.get("created_at_utc")
        prov = {
            "generator": "qwen3.8-max-free@tokenrouter",
            "created_at_utc": (
                datetime.fromisoformat(created) if created else datetime.now(UTC)
            ),
            "generator_request_id": raw.get("request_key", "")[:64],
            "source_case_id": raw.get("request_key", "")[:26],
        }
        out.append(
            make_record(
                record_id=raw["record_id"],
                premise=raw["premise"],
                hypothesis=raw["hypothesis"],
                label=raw["label"],  # type: ignore[arg-type]
                label_source="qwen_provisional",
                family=raw["family"],  # type: ignore[arg-type]
                difficulty=raw["difficulty"],  # type: ignore[arg-type]
                provenance=prov,  # type: ignore[arg-type]
            )
        )
    return out


def stratify(records: list[AgentPayIRRecord], n: int) -> list[AgentPayIRRecord]:
    """Round-robin across (family) buckets, hard-first inside each bucket."""
    buckets: dict[str, list[AgentPayIRRecord]] = defaultdict(list)
    for r in records:
        buckets[r.family].append(r)
    for bucket in buckets.values():
        bucket.sort(
            key=lambda r: (
                0 if r.family in PRIORITY_FAMILIES else 1,
                0 if r.difficulty == "hard" else (1 if r.difficulty == "medium" else 2),
                r.record_id,
            )
        )
    result: list[AgentPayIRRecord] = []
    seen: set[str] = set()
    i = 0
    while len(result) < n:
        progressed = False
        for fam in sorted(buckets):
            bucket = buckets[fam]
            if i < len(bucket):
                r = bucket[i]
                if r.record_id not in seen:
                    seen.add(r.record_id)
                    result.append(r)
                    progressed = True
                    if len(result) >= n:
                        break
        if not progressed:
            break
        i += 1
    return result


def write_csv(records: list[AgentPayIRRecord], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "record_id",
                "premise",
                "hypothesis",
                "family",
                "difficulty",
                "suggested_label",
            ]
        )
        for r in records:
            w.writerow(
                [r.record_id, r.premise, r.hypothesis, r.family, r.difficulty, r.label]
            )


HTML_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>RazorMesh Gold Review</title>
<style>
 body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:2rem;max-width:60rem}
 .card{border:1px solid #ddd;border-radius:.5rem;padding:1rem;margin-bottom:1rem}
 pre{white-space:pre-wrap;background:#f7f7f7;padding:.75rem;border-radius:.4rem}
 .tag{display:inline-block;background:#eee;border-radius:.3rem;padding:.1rem .5rem;margin-right:.4rem;font-size:.85rem}
 kbd{background:#222;color:#fff;border-radius:.25rem;padding:.05rem .4rem}
 #bar{height:.5rem;background:#4caf50;width:0%}
 button{margin-right:.5rem}
</style></head><body>
<h1>Gold Review — <span id="pos"></span>/<span id="total"></span></h1>
<div style="background:#eee"><div id="bar"></div></div>
<div class="card"><b>Family:</b> <span class="tag" id="fam"></span>
<b>Difficulty:</b> <span class="tag" id="diff"></span>
<b>Suggested (do not anchor):</b> <span class="tag" id="sug"></span>
<p><b>PREMISE (evidence)</b></p><pre id="prem"></pre>
<p><b>HYPOTHESIS (authorization claim)</b></p><pre id="hyp"></pre>
<p>Your label: <kbd>1</kbd> entailment <kbd>2</kbd> neutral <kbd>3</kbd> contradiction
| <kbd>&larr;</kbd> prev | <kbd>&rarr;</kbd> next | <kbd>E</kbd> export decisions</p>
<p>Decisions saved locally in this browser until you press E.</p>
</div>
<script>
const ROWS = __ROWS__;
const DECISIONS = {};
let i = 0;
function render(){
  const r = ROWS[i];
  document.getElementById('pos').textContent = i+1;
  document.getElementById('total').textContent = ROWS.length;
  document.getElementById('bar').style.width =
    (100*Object.keys(DECISIONS).length/ROWS.length)+'%';
  document.getElementById('fam').textContent = r.family;
  document.getElementById('diff').textContent = r.difficulty;
  document.getElementById('sug').textContent = r.suggested_label;
  document.getElementById('prem').textContent = r.premise;
  document.getElementById('hyp').textContent = r.hypothesis;
}
function decide(label){
  DECISIONS[ROWS[i].record_id] = {label, decided_at_utc:new Date().toISOString()};
  if(i < ROWS.length-1){ i++; }
  render();
}
document.addEventListener('keydown', e=>{
  if(e.key==='1') decide('entailment');
  else if(e.key==='2') decide('neutral');
  else if(e.key==='3') decide('contradiction');
  else if(e.key==='ArrowLeft' && i>0){ i--; render(); }
  else if(e.key==='ArrowRight' && i<ROWS.length-1){ i++; render(); }
  else if(e.key.toLowerCase()==='e'){
    const blob = new Blob([JSON.stringify(DECISIONS,null,2)],{type:'application/json'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'gold_decisions.json';
    a.click();
  }
});
render();
</script></body></html>
"""


def write_html(records: list[AgentPayIRRecord], path: Path) -> None:
    rows = [
        {
            "record_id": r.record_id,
            "premise": r.premise,
            "hypothesis": r.hypothesis,
            "family": r.family,
            "difficulty": r.difficulty,
            "suggested_label": r.label,
        }
        for r in records
    ]
    html = HTML_TEMPLATE.replace("__ROWS__", json.dumps(rows, ensure_ascii=False))
    path.write_text(html, encoding="utf-8")


INSTRUCTIONS = """# Gold Review — Instructions

You are labeling whether the EVIDENCE supports the AUTHORIZATION CLAIM.

Orientation (fixed):
- PREMISE  = trusted evidence about the product/listing/seller.
- HYPOTHESIS = a statement about what the human authorized.

Labels:
- 1 entailment      evidence clearly supports the authorization holding;
- 2 neutral         evidence insufficient to decide;
- 3 contradiction   evidence proves the authorization does NOT hold.

Procedure:
1. Open `gold_review.html` in your browser (double-click; no server needed).
2. For each card read PREMISE then HYPOTHESIS, ignore the suggested label
   until you have decided, then press 1 / 2 / 3.
3. Use ← → to move around; progress bar fills as you go.
4. When finished (or anytime), press E to export `gold_decisions.json`.
5. Save that file next to this folder and tell the agent it exists.

Notes:
- The CSV's suggested_label column is machine-suggested ground truth used for
  cross-checking AFTER your pass; try not to anchor on it.
- Target: complete ALL rows. Partial exports are fine — rerun and continue.
"""


def main() -> int:
    pools = {
        "seed": _load_jsonl(DATA / "dataset" / "seed" / "seed_dataset.jsonl"),
        "adversarial": _load_jsonl(
            DATA / "dataset" / "adversarial" / "adversarial_dataset.jsonl"
        ),
        "candidates": _load_jsonl(DATA / "dataset" / "candidates" / "candidates.jsonl"),
    }
    combined: list[AgentPayIRRecord] = []
    for rows in pools.values():
        combined.extend(rows)

    sampled = stratify(combined, TARGET_N)
    OUT.mkdir(parents=True, exist_ok=True)

    csv_path = OUT / "gold_review.csv"
    write_csv(sampled, csv_path)
    html_path = OUT / "gold_review.html"
    write_html(sampled, html_path)
    (OUT / "INSTRUCTIONS.md").write_text(INSTRUCTIONS, encoding="utf-8")

    manifest = {
        "target_n": TARGET_N,
        "sampled": len(sampled),
        "pool_sizes": {k: len(v) for k, v in pools.items()},
        "by_label": _count(sampled, lambda r: r.label),
        "by_difficulty": _count(sampled, lambda r: r.difficulty),
        "families_covered": len({r.family for r in sampled}),
        "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "status": "PENDING_HUMAN_REVIEW",
        "created_at_utc": datetime.now(UTC).isoformat(),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))
    return 0


def _count(records, key):  # type: ignore[no-untyped-def]
    out: dict[str, int] = {}
    for r in records:
        k = str(key(r))
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


if __name__ == "__main__":
    raise SystemExit(main())
