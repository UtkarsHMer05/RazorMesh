"""PRE-REVIEW FINAL CORRECTION #7, #12-16: finalizer + Colab bundle/notebook gates.

Everything here runs WITHOUT training and WITHOUT torch/GPU:

- the committed pre-review bundle + notebook must round-trip the EXTERNAL
  archive-hash design (EXPECTED_BUNDLE_SHA256 computed after the zip is built,
  never a manifest['bundle_sha256'] field) and execute their full
  bundle-verification logic locally against the generated ZIP (#13/#15);
- dependencies must come from the bundle's requirements-frozen.txt with the
  actual versions asserted BEFORE training and no torch import before install
  (#14);
- the FROZEN selection rule (min unsafe C→E, then max macro-F1, then max
  contradiction recall; neutral recall / safe false-block reported only) is
  unit-tested over fake candidate metrics, both from the generator module and
  from the code embedded in the generated notebook (#16);
- the bundle builder must honor explicit --corpus-dir / --train/--val paths and
  the FINAL zip's train/val members must hash-equal corpus/final/train.jsonl and
  corpus/final/val.jsonl (#12);
- the entire finalizer is executed end-to-end against a generated complete fake
  decision export in a temporary workspace (#7): final train/val/test, human
  gold, group-level gold isolation, recomputed+validated hashes, conflict
  rejection, final bundle (#24 core path).
"""

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = REPO_ROOT / "scripts"
BUILDER_SCRIPT = SCRIPTS / "rzp_build_colab_bundle_v2.py"
FINALIZER_SCRIPT = SCRIPTS / "rzp_finalize_review_v2.py"
COMMITTED_ZIP = REPO_ROOT / "artifacts" / "agentpay_ir_v2_colab_training_bundle.zip"
COMMITTED_NOTEBOOK = (REPO_ROOT / "notebooks"
                      / "RazorGuard_NLI_AgentPayIR_v2_Training.ipynb")
PYTHON = sys.executable

FROZEN_VERSIONS = {"transformers": "5.15.1", "torch": "2.13.0", "accelerate": "1.14.0"}


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def content_sha256(premise: str, hypothesis: str, label: str) -> str:
    raw = "\x1f".join((premise, hypothesis, label, "canonical")).encode()
    return hashlib.sha256(raw).hexdigest()


def load_builder_module():
    spec = importlib.util.spec_from_file_location("rzp_build_colab_bundle_v2", BUILDER_SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def notebook_code_cells(notebook_path: Path) -> list[str]:
    nb = json.loads(notebook_path.read_text())
    return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]


def run_verify_cell(cell_source: str, bundle: Path) -> dict:
    """Execute the notebook's stdlib-only verification cell against a ZIP (#15)."""
    import os

    old = os.environ.get("BUNDLE_PATH")
    os.environ["BUNDLE_PATH"] = str(bundle)
    try:
        ns: dict = {}
        exec(compile(cell_source, "verify_cell", "exec"), ns)  # noqa: S102 - test rig
        return ns["MANIFEST"]
    finally:
        if old is None:
            os.environ.pop("BUNDLE_PATH", None)
        else:
            os.environ["BUNDLE_PATH"] = old


# ---------------------------------------------------------------------------
# #16 FROZEN selection rule over fake candidate metrics
# ---------------------------------------------------------------------------


def _fake(unsafe: int, f1: float, c_rec: float, n_rec: float = 0.5, sfb: int = 0) -> dict:
    return {"eval_unsafe_c_to_e": unsafe, "eval_macro_f1": f1,
            "eval_contradiction_recall": c_rec, "eval_neutral_recall": n_rec,
            "eval_safe_false_block": sfb}


def test_selection_rule_min_unsafe_then_f1_then_c_recall() -> None:
    select = load_builder_module().select_candidate
    # unsafe C->E dominates everything else
    assert select({"A": _fake(1, 0.99, 0.99), "B": _fake(0, 0.40, 0.10)}) == "B"
    # tie on unsafe -> higher macro-F1
    assert select({"A": _fake(0, 0.80, 0.10), "B": _fake(0, 0.90, 0.10)}) == "B"
    # tie on unsafe + F1 -> higher contradiction recall
    assert select({"A": _fake(0, 0.80, 0.50), "B": _fake(0, 0.80, 0.60)}) == "B"
    # neutral recall and safe false-block are NOT selection inputs
    assert select({"A": _fake(0, 0.80, 0.50, n_rec=0.01, sfb=100),
                   "B": _fake(0, 0.80, 0.50, n_rec=0.99, sfb=0)}) == "A"
    swapped = {"A": _fake(0, 0.80, 0.50, n_rec=0.99, sfb=0),
               "B": _fake(0, 0.80, 0.50, n_rec=0.01, sfb=100)}
    assert select(swapped) == "A"  # reported metrics never flip the frozen ordering


def test_notebook_embeds_the_same_selection_rule() -> None:
    mod = load_builder_module()
    sel_cells = [c for c in notebook_code_cells(COMMITTED_NOTEBOOK) if "def select_candidate" in c]
    assert len(sel_cells) == 1, "notebook must embed select_candidate exactly once"
    ns: dict = {}
    exec(compile(sel_cells[0], "candidate_cell", "exec"), ns)  # noqa: S102 - test rig
    embedded = ns["select_candidate"]
    cases = [{"A": _fake(1, 0.99, 0.99), "B": _fake(0, 0.40, 0.10)},
             {"A": _fake(0, 0.80, 0.50), "B": _fake(0, 0.80, 0.60)},
             {"A": _fake(0, 0.90, 0.10, n_rec=0.01, sfb=50),
              "B": _fake(0, 0.90, 0.10, n_rec=0.99, sfb=0)}]
    for case in cases:
        assert embedded(case) == mod.select_candidate(case)


# ---------------------------------------------------------------------------
# #13/#14/#15 committed bundle + notebook: external hash design, frozen deps
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def committed_bundle() -> tuple[Path, str, list[str]]:
    assert COMMITTED_ZIP.exists(), "run scripts/rzp_build_colab_bundle_v2.py"
    assert COMMITTED_NOTEBOOK.exists()
    return COMMITTED_ZIP, sha256_file(COMMITTED_ZIP), notebook_code_cells(COMMITTED_NOTEBOOK)


def test_notebook_expected_bundle_sha256_matches_zip(committed_bundle) -> None:
    _, zip_sha, cells = committed_bundle
    assigning = [c for c in cells if re.search(r'EXPECTED_BUNDLE_SHA256 = "([0-9a-f]{64})"', c)]
    assert len(assigning) == 1, "exactly one cell assigns the literal expected archive hash"
    m = re.search(r'EXPECTED_BUNDLE_SHA256 = "([0-9a-f]{64})"', assigning[0])
    assert m and m.group(1) == zip_sha  # generated OUTSIDE the zip, after it was built


def test_notebook_never_references_manifest_bundle_sha256(committed_bundle) -> None:
    _, _, cells = committed_bundle
    with zipfile.ZipFile(COMMITTED_ZIP) as z:
        assert "bundle_sha256" not in json.loads(z.read("bundle_manifest.json"))
    for cell in cells:
        assert not re.search(r"manifest\[.bundle_sha256.\]", cell), \
            "notebook must not read a self-referential manifest['bundle_sha256']"


def test_bundle_verification_logic_executes_against_generated_zip(committed_bundle) -> None:
    """No-training Colab preflight: execute the full stdlib verification against
    the real ZIP — proves the archive hash AND that no manifest field the
    notebook relies on is missing (#15)."""
    bundle, _, cells = committed_bundle
    verify_cell = next(c for c in cells if "def verify_bundle" in c)
    manifest = run_verify_cell(verify_cell, bundle)
    assert manifest["base_model"] == "cross-encoder/nli-deberta-v3-base"
    assert manifest["label_map"] == {"0": "contradiction", "1": "entailment", "2": "neutral"}
    mod = load_builder_module()
    assert mod.MANIFEST_REQUIRED_FIELDS and set(mod.MANIFEST_REQUIRED_FIELDS) <= set(manifest)
    with zipfile.ZipFile(bundle) as z:
        assert set(z.namelist()) == set(manifest["files"]) | {"bundle_manifest.json"}
        assert "test.jsonl" not in z.namelist()  # frozen test never travels


def test_bundle_requirements_are_the_single_version_source(committed_bundle) -> None:
    bundle, _, cells = committed_bundle
    with zipfile.ZipFile(bundle) as z:
        req_text = z.read("requirements-frozen.txt").decode()
    req = {k.strip(): v.strip() for line in req_text.splitlines() if "==" in line
           for k, v in [line.split("==", 1)]}
    for pkg, ver in FROZEN_VERSIONS.items():
        assert req[pkg] == ver, f"{pkg} must pin {ver} (single version source)"
    install_cell = next(c for c in cells if "%pip install" in c)
    assert "%pip install -q -r bundle/requirements-frozen.txt" in install_cell
    # Colab's stock torchvision/torchaudio pin torch==2.11.0 and break
    # transformers' lazy imports against torch 2.13; they must be removed
    # BEFORE the post-install imports (notebook uses neither package).
    assert "%pip uninstall -y -q torchvision torchaudio" in install_cell
    assert install_cell.index("%pip uninstall -y -q torchvision torchaudio") \
        < install_cell.index("import accelerate")
    # Colab runtime-correctness regression: `datasets` was pinned but is never
    # imported by the notebook, and the unavailable pin aborted the whole frozen
    # install on Colab (leaving stale torch). The pin must never come back, and
    # the metadata gate must ignore PEP 440 local segments (+cuXXX build variants).
    assert "datasets" not in req_text
    for cell in cells:
        assert "import datasets" not in cell
    assert req.get("safetensors") == "0.8.0"  # must match the semantic runtime group
    assert 'split("+", 1)[0]' in install_cell  # local-segment-normalized equality
    # no hardcoded 4.55.4 / 1.10.1 legacy pins anywhere
    assert "4.55.4" not in req_text and "1.10.1" not in req_text
    for cell in cells:
        assert "transformers==4.55.4" not in cell and "accelerate==1.10.1" not in cell


def test_no_torch_import_before_install_and_versions_asserted(committed_bundle) -> None:
    _, _, cells = committed_bundle
    install_idx = next(i for i, c in enumerate(cells) if "%pip install" in c)
    for i, cell in enumerate(cells):
        imports_torch = "import torch" in cell or "import transformers" in cell
        if i < install_idx:
            assert not imports_torch, f"cell {i} imports torch/transformers before the install cell"
        elif i == install_idx:
            assert cell.index("%pip install") < cell.index("import torch"), \
                "torch must be imported only AFTER the frozen install"
            # primary gate: pinned DISTRIBUTION versions via importlib.metadata
            assert "import importlib.metadata as importlib_metadata" in cell
            assert "for _pkg in REQ:" in cell
            assert 'assert _installed == REQ[_pkg]' in cell
            # evidence: runtime-reported torch/CUDA versions recorded, not gated
            assert 'print("torch.__version__ (runtime report):", torch.__version__)' in cell
            assert "torch.version.cuda" in cell


def test_install_cell_extracts_bundle_before_pip_in_dependency_free_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fresh Colab runtimes have no bundle/ directory, so the install cell must
    extract the archive BEFORE the %pip step that consumes requirements-frozen.txt.
    Asserted statically AND exercised for real in a clean temp dir where the
    executed code is PURE STDLIB: the post-install import/version block is cut
    entirely (stubbed separately), so the exercise does not depend on
    accelerate/torch/transformers being importable."""
    cells = notebook_code_cells(COMMITTED_NOTEBOOK)
    install = next(c for c in cells if "%pip install" in c)
    # static ordering: extract -> pip -> post-install imports
    assert install.index('zf.extractall("bundle")') < install.index("%pip install")
    assert install.index("%pip install") < install.index("import accelerate")
    assert install.index("%pip install") < install.index("import torch")

    # dependency-free exercise: cut everything from the post-install import block
    marker = "# NOW import the runtime"
    python_only = install[: install.index(marker)]
    for pkg in ("accelerate", "torch", "transformers"):
        assert f"import {pkg}" not in python_only, f"exercise must stay free of {pkg}"
    # %pip is an IPython magic, not Python: replace it IN PLACE so its position
    # (after extraction, before imports) is preserved while the exec stays stdlib.
    python_only = python_only.replace(
        "%pip install -q -r bundle/requirements-frozen.txt",
        "PIP_STUBBED_AT_SAME_POSITION = True",
    ).replace(
        "%pip uninstall -y -q torchvision torchaudio",
        "PIP_UNINSTALL_STUBBED_AT_SAME_POSITION = True",
    )
    assert "PIP_STUBBED_AT_SAME_POSITION" in python_only

    import os

    monkeypatch.chdir(tmp_path)
    old_env = os.environ.get("BUNDLE_PATH")
    os.environ["BUNDLE_PATH"] = str(COMMITTED_ZIP)
    ns: dict = {}
    try:
        verify = next(c for c in cells if "def verify_bundle" in c)
        exec(compile(verify, "verify_cell", "exec"), ns)  # noqa: S102 - test rig
        exec(compile(python_only, "install_cell", "exec"), ns)  # noqa: S102 - test rig
    finally:
        if old_env is None:
            os.environ.pop("BUNDLE_PATH", None)
        else:
            os.environ["BUNDLE_PATH"] = old_env
    # extraction landed in the clean cwd and BEFORE the pip dependency path
    assert (tmp_path / "bundle" / "requirements-frozen.txt").exists()
    assert (tmp_path / "bundle" / "train.jsonl").exists()
    assert ns["REQ"]["torch"] == FROZEN_VERSIONS["torch"]
    assert ns["PIP_STUBBED_AT_SAME_POSITION"] is True


def test_notebook_packages_the_exact_selected_candidate() -> None:
    """The artifact must be the checkpoint that produced the winning validation
    metrics: both candidates are saved, the frozen rule selects one, and the
    selected checkpoint is COPIED — never a third, unevaluated retrain from base."""
    cells = notebook_code_cells(COMMITTED_NOTEBOOK)
    cand = next(c for c in cells if "def run(epochs)" in c)
    final = next(c for c in cells if "agentpay-ir-v2-finetuned" in c and "model_manifest" in c)
    # both candidates saved with their exact validation metrics bound to them
    assert 'tr.save_model(f"cand_{epochs}ep")' in cand
    assert "validation_metrics.json" in cand
    import ast as _ast
    _calls = [n for n in _ast.walk(_ast.parse(cand))
              if isinstance(n, _ast.Call) and getattr(n.func, "id", "") == "TrainingArguments"]
    assert len(_calls) == 1, "exactly one TrainingArguments construction per candidate"
    # packaging copies the selected checkpoint; it never trains or reloads from base
    assert 'shutil.copytree(cand_dir, "agentpay-ir-v2-finetuned")' in final
    assert "Trainer(" not in final and "from_pretrained(" not in final
    assert 'cand_dir = "cand_2ep" if best == "A_2ep" else "cand_3ep"' in final
    # model_manifest binds the selected metrics to the packaged files
    assert '"selected_candidate_metrics": results[best]' in final
    copied_assert = 'copied_metrics = json.load(open("agentpay-ir-v2-finetuned/'
    assert copied_assert + 'validation_metrics.json"))' in final
    assert "copied_metrics == results[best]" in final
    assert '"artifact_files_sha256": artifact_files' in final
    assert ('"packaging": "exact selected candidate checkpoint copied; '
            'never retrained from base"' in final)


# ---------------------------------------------------------------------------
# #12 builder honors explicit --corpus-dir / --train/--val paths
# ---------------------------------------------------------------------------


def _write_mini_corpus(d: Path, n: int = 4) -> tuple[Path, Path]:
    d.mkdir(parents=True, exist_ok=True)
    train, val = d / "train.jsonl", d / "val.jsonl"
    rows_t = [{"premise": f"t evidence {i}", "hypothesis": f"t constraint {i}",
               "label": ["contradiction", "entailment", "neutral", "entailment"][i % 4]}
              for i in range(n)]
    rows_v = [{"premise": f"v evidence {i}", "hypothesis": f"v constraint {i}", "label": "neutral"}
              for i in range(n)]
    train.write_text("".join(json.dumps(r) + "\n" for r in rows_t))
    val.write_text("".join(json.dumps(r) + "\n" for r in rows_v))
    return train, val


def test_builder_zip_train_val_hashes_equal_explicit_corpus_dir(tmp_path: Path) -> None:
    train, val = _write_mini_corpus(tmp_path / "final")
    out_zip = tmp_path / "bundle.zip"
    proc = subprocess.run(  # noqa: S603 - fixed argv, test constants
        [PYTHON, str(BUILDER_SCRIPT), "--corpus-dir", str(tmp_path / "final"),
         "--out-zip", str(out_zip),
         "--notebook-out", str(tmp_path / "nb.ipynb")],
        capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    with zipfile.ZipFile(out_zip) as z:
        assert hashlib.sha256(z.read("train.jsonl")).hexdigest() == sha256_file(train)
        assert hashlib.sha256(z.read("val.jsonl")).hexdigest() == sha256_file(val)
    nb_text = "".join(notebook_code_cells(tmp_path / "nb.ipynb"))
    m = re.search(r'EXPECTED_BUNDLE_SHA256 = "([0-9a-f]{64})"', nb_text)
    assert m and m.group(1) == sha256_file(out_zip)  # external hash = final zip sha


def test_builder_explicit_train_val_paths_and_no_notebook(tmp_path: Path) -> None:
    train, val = _write_mini_corpus(tmp_path)
    out_zip = tmp_path / "b2.zip"
    proc = subprocess.run(  # noqa: S603 - fixed argv, test constants
        [PYTHON, str(BUILDER_SCRIPT), "--train", str(train), "--val", str(val),
         "--out-zip", str(out_zip), "--no-notebook",
         "--notebook-out", str(tmp_path / "none.ipynb")],
        capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    with zipfile.ZipFile(out_zip) as z:
        assert hashlib.sha256(z.read("train.jsonl")).hexdigest() == sha256_file(train)
    assert not (tmp_path / "none.ipynb").exists()


# ---------------------------------------------------------------------------
# #7/#24 synthetic workspace + full finalizer execution
# ---------------------------------------------------------------------------


def synth_record(group: str, idx: int, label: str) -> dict:
    premise = f"Merchant evidence for {group} #{idx}: the listing states the offer terms."
    hypothesis = f"The human authorized the {group} constraint variant {idx}."
    src = f"src-{group}-{idx}"
    rid = "ap2_" + hashlib.sha256("\x1f".join(
        ("razormesh_frozen_v2", src, premise, hypothesis)).encode()).hexdigest()[:26]
    return {
        "record_id": rid, "schema_version": "agentpay-ir-v2",
        "premise": premise, "hypothesis": hypothesis, "label": label,
        "family": "quantity", "subfamily": "quantity",
        "authorization_field": "quantity", "evidence_field": "product_summary",
        "source_dataset": "razormesh_frozen_v2", "source_record_id": src,
        "source_license": "project-internal", "source_kind": "deterministic_derived",
        "source_provenance": json.dumps({"generator_parent_id": group,
                                         "template_family_id": f"tf_{group}",
                                         "entity_family_id": f"ef_{group}"}, sort_keys=True),
        "generator_parent_id": group, "template_family_id": f"tf_{group}",
        "entity_family_id": f"ef_{group}", "safe_lookalike_family_id": "",
        "split_group": group, "difficulty": "easy", "safe_or_attack": "safe",
        "content_sha256": content_sha256(premise, hypothesis, label), "metadata": {},
    }


# group layout: each group lives in exactly one split; gold groups carry extra
# rows that must DISAPPEAR from train/val, and only the reviewed record survives
# as gold.
SPLIT_GROUPS = {
    "train": ["t1", "t2", "t3", "t4", "t5", "t6"],
    "val": ["v1", "v2", "v3"],
    "test": ["x1", "x2", "x3"],
}
GOLD_GROUPS = {"t1", "t2", "v1"}  # reviewed as gold
AMBIGUOUS_CARD_GROUP = "t4"  # supervised card marked ambiguous/bad by the human


def build_workspace(root: Path) -> dict:
    """Temporary corpus + review pack + frozen roles (schema-faithful)."""
    corpus = root / "data" / "agentpay_ir_v2" / "corpus"
    review = root / "data" / "agentpay_ir_v2" / "review"
    eval_dir = root / "data" / "agentpay_ir_v2" / "eval"
    for d in (corpus, review, eval_dir):
        d.mkdir(parents=True, exist_ok=True)

    records: dict[tuple[str, int], dict] = {}
    for split, groups in SPLIT_GROUPS.items():
        rows = []
        for group in groups:
            for idx in range(3):
                label = ["contradiction", "entailment", "neutral"][idx % 3]
                r = synth_record(group, idx, label)
                records[(group, idx)] = {**r, "_split": split}
                rows.append(r)
        (corpus / f"{split}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))

    # review pack: every record of gold groups + one supervised record per
    # selected non-gold group (t3/t4 from train, v2 from val, x1 from test)
    gold_keys = [(g, i) for g in sorted(GOLD_GROUPS) for i in range(3)]
    sup_keys = [("t3", 0), ("t4", 0), ("v2", 0), ("x1", 0)]
    pack_rows, linkage, assignments, by_key = [], {}, {}, {}
    for i, key in enumerate(sorted(gold_keys) + sup_keys, 1):
        cid = f"rc2_{i:04d}"
        r = records[key]
        pack_rows.append({"card_id": cid, "premise": r["premise"], "hypothesis": r["hypothesis"]})
        linkage[cid] = {"record_id": r["record_id"], "split_group": r["split_group"],
                        "template_family_id": r["template_family_id"],
                        "source_label": r["label"], "stratum": "quantity",
                        "source_class": "razormesh_security_corpus"}
        assignments[cid] = "gold" if key in gold_keys else "supervised"
        by_key[key] = cid
    (review / "REVIEW_PACK_V3.jsonl").write_text("".join(json.dumps(c) + "\n" for c in pack_rows))

    role_sha = hashlib.sha256(json.dumps(assignments, sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()
    (review / "REVIEW_ROLE_MANIFEST_V3.json").write_text(json.dumps({
        "pack": "REVIEW_PACK_V3", "frozen_at": "2026-08-29T00:00:00+00:00", "seed": 42,
        "n_gold": sum(1 for v in assignments.values() if v == "gold"),
        "n_supervised": sum(1 for v in assignments.values() if v == "supervised"),
        "group_level": True, "assignments": assignments}, indent=1))
    (review / "REVIEW_LINKAGE_V3.json").write_text(json.dumps(linkage, indent=1, sort_keys=True))
    (review / "REVIEW_PACK_FREEZE_V3.json").write_text(json.dumps({
        "pack": "REVIEW_PACK_V3", "cards": len(pack_rows),
        "unique_record_ids": len(pack_rows), "unique_normalized_pairs": len(pack_rows),
        "gold_cards": sum(1 for v in assignments.values() if v == "gold"),
        "supervised_cards": sum(1 for v in assignments.values() if v == "supervised"),
        "reviewer_pack_sha256": sha256_file(review / "REVIEW_PACK_V3.jsonl"),
        "role_manifest_sha256": role_sha,
        "role_sha_definition":
            "sha256 over {card_id: role} only; stored HERE, never inside the role manifest",
    }, indent=1))

    ood = [synth_record("ood", 0, "contradiction"), synth_record("ood", 1, "entailment")]
    (eval_dir / "fresh_ood_v2.jsonl").write_text("".join(json.dumps(r) + "\n" for r in ood))

    return {"records": records, "linkage": linkage, "assignments": assignments,
            "by_key": by_key, "review": review, "corpus": corpus}


def human_export(ws: dict, flips: dict[str, str] | None = None,
                 ambiguous_card: str | None = None, drop_card: str | None = None) -> dict:
    """Complete fake decision export in the real UI export shape."""
    flips = flips or {}
    rows = []
    for cid in sorted(ws["assignments"]):
        if cid == drop_card:
            continue
        if cid == ambiguous_card:
            decision = "ambiguous_bad_record"
        elif cid in flips:
            decision = flips[cid]
        else:
            decision = ws["linkage"][cid]["source_label"]
        rows.append({"card_id": cid, "decision": decision})
    return {"export_version": 1, "rows": rows}


def run_finalizer(root: Path, export: dict) -> subprocess.CompletedProcess:
    dec = root / "decisions_export.json"
    dec.write_text(json.dumps(export, indent=1))
    return subprocess.run(  # noqa: S603 - fixed argv, test constants
        [PYTHON, str(FINALIZER_SCRIPT), "--decisions", str(dec), "--root", str(root)],
        capture_output=True, text=True, timeout=300)


@pytest.fixture(scope="module")
def finalized(tmp_path_factory: pytest.TempPathFactory) -> dict:
    root = tmp_path_factory.mktemp("finalizer_ws")
    ws = build_workspace(root)
    # human label flips on 2 supervised cards + 1 gold card (label changes)
    flips = {}
    gold_flip_card = ws["by_key"][("v1", 0)]
    flips[gold_flip_card] = ("entailment" if ws["linkage"][gold_flip_card]["source_label"]
                             != "entailment" else "neutral")
    sup_flip_card = ws["by_key"][("t3", 0)]
    flips[sup_flip_card] = ("contradiction" if ws["linkage"][sup_flip_card]["source_label"]
                            != "contradiction" else "neutral")
    ambiguous = ws["by_key"][("t4", 0)]
    proc = run_finalizer(root, human_export(ws, flips=flips, ambiguous_card=ambiguous))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return {"root": root, "ws": ws, "proc": proc, "flips": flips, "ambiguous": ambiguous}


def _export_decisions(finalized: dict) -> dict[str, str]:
    return {r["card_id"]: r["decision"]
            for r in json.loads((finalized["root"] / "decisions_export.json").read_text())["rows"]}


def test_finalizer_produces_final_splits_and_human_gold(finalized: dict) -> None:
    root, ws = finalized["root"], finalized["ws"]
    final = root / "data" / "agentpay_ir_v2" / "corpus" / "final"
    for split in ("train", "val", "test"):
        assert (final / f"{split}.jsonl").exists()
    gold_path = root / "data" / "agentpay_ir_v2" / "review" / "GOLD_FROZEN_V3.jsonl"
    assert gold_path.exists()
    gold_rows = [json.loads(line) for line in gold_path.read_text().splitlines()]
    gold_records = {link["record_id"] for cid, link in ws["linkage"].items()
                    if ws["assignments"][cid] == "gold"}
    assert {g["record_id"] for g in gold_rows} == gold_records  # ONLY reviewed records
    # HUMAN decision is the label; provenance human-reviewed; no source label kept
    decisions = _export_decisions(finalized)
    for g in gold_rows:
        cid = next(c for c, lnk in ws["linkage"].items() if lnk["record_id"] == g["record_id"])
        assert g["label"] == decisions[cid]
        assert g["source_kind"] == "human_reviewed"
        assert g["metadata"]["review_role"] == "gold_frozen"
        assert g["metadata"]["human_label_override"] is True
        assert g["metadata"]["label_agrees_with_source"] == (
            ws["records"][next(k for k, v in ws["records"].items()
                               if v["record_id"] == g["record_id"])]["label"] == decisions[cid])
        assert "source_label" not in json.dumps(g)


def test_finalizer_gold_isolation_is_group_level(finalized: dict) -> None:
    root, ws = finalized["root"], finalized["ws"]
    final = root / "data" / "agentpay_ir_v2" / "corpus" / "final"
    gold_groups = {lnk["split_group"] for c, lnk in ws["linkage"].items()
                   if ws["assignments"][c] == "gold"}
    for split in ("train", "val", "test"):
        rows = [json.loads(line) for line in (final / f"{split}.jsonl").read_text().splitlines()]
        leaked = gold_groups & {r["split_group"] for r in rows}
        assert not leaked, f"gold group leaked into {split}"
    # the gold groups' unreviewed rows are gone entirely (t1/t2 from train, v1 from val)
    train_rows = [json.loads(line) for line in (final / "train.jsonl").read_text().splitlines()]
    assert not any(r["split_group"] in {"t1", "t2"} for r in train_rows)
    val_rows = [json.loads(line) for line in (final / "val.jsonl").read_text().splitlines()]
    assert not any(r["split_group"] == "v1" for r in val_rows)


def test_finalizer_recomputes_and_validates_hashes(finalized: dict) -> None:
    root, ws = finalized["root"], finalized["ws"]
    final = root / "data" / "agentpay_ir_v2" / "corpus" / "final"
    all_rows = []
    for split in ("train", "val", "test"):
        all_rows += [json.loads(line)
                     for line in (final / f"{split}.jsonl").read_text().splitlines()]
    gold_file = root / "data/agentpay_ir_v2/review/GOLD_FROZEN_V3.jsonl"
    all_rows += [json.loads(line) for line in gold_file.read_text().splitlines()]
    for r in all_rows:  # canonical contract on EVERY final row
        assert content_sha256(r["premise"], r["hypothesis"], r["label"]) == r["content_sha256"]
    # a flipped supervised row got a NEW hash and human provenance
    decisions = _export_decisions(finalized)
    sup_flip = next(cid for cid in finalized["flips"] if ws["assignments"][cid] == "supervised")
    flip_record = ws["linkage"][sup_flip]["record_id"]
    orig_key = next(k for k, v in ws["records"].items() if v["record_id"] == flip_record)
    row = next(r for r in all_rows if r["record_id"] == flip_record)
    assert row["label"] == decisions[sup_flip] != ws["records"][orig_key]["label"]
    assert row["metadata"]["human_label_override"] is True
    assert row["content_sha256"] != ws["records"][orig_key]["content_sha256"]
    # ambiguous card's record removed entirely
    amb_record = ws["linkage"][finalized["ambiguous"]]["record_id"]
    assert all(r["record_id"] != amb_record for r in all_rows)
    manifest = json.loads((final / "FINAL_FREEZE_MANIFEST.json").read_text())
    for split in ("train", "val", "test"):
        assert manifest["files"][f"{split}.jsonl"] == sha256_file(final / f"{split}.jsonl")
    assert manifest["gold_frozen_sha256"] == sha256_file(gold_file)


def test_finalizer_bundle_train_val_hashes_equal_final_corpus(finalized: dict) -> None:
    """#12 end-to-end proof: the FINAL zip carries corpus/final train/val, and the
    regenerated notebook embeds the FINAL zip's external sha (#13)."""
    root = finalized["root"]
    final = root / "data" / "agentpay_ir_v2" / "corpus" / "final"
    zip_path = root / "artifacts" / "agentpay_ir_v2_colab_training_bundle.zip"
    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as z:
        assert hashlib.sha256(z.read("train.jsonl")).hexdigest() == sha256_file(
            final / "train.jsonl")
        assert hashlib.sha256(z.read("val.jsonl")).hexdigest() == sha256_file(
            final / "val.jsonl")
        assert "test.jsonl" not in z.namelist()
    nb_text = "".join(notebook_code_cells(
        root / "notebooks" / "RazorGuard_NLI_AgentPayIR_v2_Training.ipynb"))
    m = re.search(r'EXPECTED_BUNDLE_SHA256 = "([0-9a-f]{64})"', nb_text)
    assert m and m.group(1) == sha256_file(zip_path)
    cells = [c for c in notebook_code_cells(
        root / "notebooks" / "RazorGuard_NLI_AgentPayIR_v2_Training.ipynb")]
    run_verify_cell(next(c for c in cells if "def verify_bundle" in c), zip_path)


# ---------------------------------------------------------------------------
# finalizer failure modes (release-blocking rejects)
# ---------------------------------------------------------------------------


def test_finalizer_rejects_incomplete_decisions(tmp_path: Path) -> None:
    ws = build_workspace(tmp_path)
    export = human_export(ws, drop_card=sorted(ws["assignments"])[0])
    proc = run_finalizer(tmp_path, export)
    assert proc.returncode == 1
    assert "missing decisions" in proc.stdout


def test_finalizer_stops_when_too_many_gold_cards_marked_ambiguous(tmp_path: Path) -> None:
    """Post-review guard: a materially shrunken usable human-gold set must STOP
    the finalizer, never silently continue with a tiny gold evaluation set."""
    ws = build_workspace(tmp_path)
    gold_cards = sorted(c for c, role in ws["assignments"].items() if role == "gold")
    ambiguous = set(gold_cards[:3])  # 3 of 9 gold cards -> usable 6 < floor 8
    export = human_export(ws, ambiguous_card=None)
    for row in export["rows"]:
        if row["card_id"] in ambiguous:
            row["decision"] = "ambiguous_bad_record"
    proc = run_finalizer(tmp_path, export)
    assert proc.returncode == 1
    assert "human-gold set too small" in proc.stdout


def test_finalizer_warns_but_proceeds_at_adequate_gold_level(tmp_path: Path) -> None:
    ws = build_workspace(tmp_path)
    gold_cards = sorted(c for c, role in ws["assignments"].items() if role == "gold")
    proc = run_finalizer(tmp_path, human_export(ws, ambiguous_card=gold_cards[0]))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "gold adequacy: 8/9 usable" in proc.stdout
    assert "WARNING: usable human gold" in proc.stdout  # 8 < 0.95 * 9


def test_finalizer_rejects_conflicting_decisions_same_record(tmp_path: Path) -> None:
    ws = build_workspace(tmp_path)
    # two cards forced onto the same underlying record with different decisions
    cids = sorted(ws["assignments"])
    ws["linkage"][cids[1]]["record_id"] = ws["linkage"][cids[0]]["record_id"]
    (ws["review"] / "REVIEW_LINKAGE_V3.json").write_text(json.dumps(ws["linkage"], indent=1))
    export = human_export(ws)
    export["rows"][0]["decision"] = "contradiction"
    export["rows"][1]["decision"] = "entailment"
    proc = run_finalizer(tmp_path, export)
    assert proc.returncode == 1
    assert "conflicting human decisions" in proc.stdout


def test_finalizer_rejects_tampered_role_manifest(tmp_path: Path) -> None:
    ws = build_workspace(tmp_path)
    manifest_path = ws["review"] / "REVIEW_ROLE_MANIFEST_V3.json"
    manifest = json.loads(manifest_path.read_text())
    some = sorted(manifest["assignments"])[0]
    manifest["assignments"][some] = ("supervised" if manifest["assignments"][some] == "gold"
                                     else "gold")
    manifest_path.write_text(json.dumps(manifest, indent=1))
    proc = run_finalizer(tmp_path, human_export(ws))
    assert proc.returncode == 1
    assert "hash changed since freeze" in proc.stdout


def test_finalizer_rejects_self_hashed_role_manifest(tmp_path: Path) -> None:
    ws = build_workspace(tmp_path)
    manifest_path = ws["review"] / "REVIEW_ROLE_MANIFEST_V3.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["role_manifest_sha256"] = "0" * 64  # self-containing hash must be rejected
    manifest_path.write_text(json.dumps(manifest, indent=1))
    proc = run_finalizer(tmp_path, human_export(ws))
    assert proc.returncode == 1
    assert "self-referential hash field" in proc.stdout


def test_finalizer_rejects_ood_hash_collision(tmp_path: Path) -> None:
    ws = build_workspace(tmp_path)
    collision = dict(ws["records"][("t5", 0)])  # non-gold group: survives into final train
    ood_path = tmp_path / "data" / "agentpay_ir_v2" / "eval" / "fresh_ood_v2.jsonl"
    ood_path.write_text(json.dumps(collision) + "\n")
    proc = run_finalizer(tmp_path, human_export(ws))
    assert proc.returncode == 1
    assert "ood hash" in proc.stdout


# ---------------------------------------------------------------------------
# pre-label correction: opt-in prompt-injection augmentation (train-only)
# ---------------------------------------------------------------------------


def _stage_augmentation(root: Path) -> None:
    aug_src = REPO_ROOT / "data" / "agentpay_ir_v2" / "augmentation"
    aug_dst = root / "data" / "agentpay_ir_v2" / "augmentation"
    aug_dst.mkdir(parents=True, exist_ok=True)
    for f in aug_src.iterdir():
        (aug_dst / f.name).write_bytes(f.read_bytes())


def run_finalizer_args(root: Path, export: dict, extra: list[str]) -> subprocess.CompletedProcess:
    dec = root / "decisions_export.json"
    dec.write_text(json.dumps(export, indent=1))
    return subprocess.run(  # noqa: S603 - fixed argv, test constants
        [PYTHON, str(FINALIZER_SCRIPT), "--decisions", str(dec), "--root", str(root), *extra],
        capture_output=True, text=True, timeout=300)


def test_finalizer_augmentation_train_only_and_gates_rerun(tmp_path: Path) -> None:
    ws = build_workspace(tmp_path)
    _stage_augmentation(tmp_path)
    export = human_export(ws)

    base = tmp_path / "baseline"
    base.mkdir()
    ws_base = build_workspace(base)
    base_proc = run_finalizer_args(base, human_export(ws_base), [])
    assert base_proc.returncode == 0, base_proc.stdout + base_proc.stderr

    proc = run_finalizer_args(tmp_path, export, [
        "--integrate-prompt-injection-augmentation",
        # tiny synthetic workspace: the absolute 96-row set dominates the split,
        # so raise the cap for THIS test only (real runs keep the 0.10 default)
        "--max-synthetic-fraction", "0.9"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "INTEGRATED into train only: 96 rows" in proc.stdout

    final = tmp_path / "data" / "agentpay_ir_v2" / "corpus" / "final"
    base_final = base / "data" / "agentpay_ir_v2" / "corpus" / "final"
    manifest = json.loads((final / "FINAL_FREEZE_MANIFEST.json").read_text())
    base_manifest = json.loads((base_final / "FINAL_FREEZE_MANIFEST.json").read_text())
    assert manifest["counts"]["train"] == base_manifest["counts"]["train"] + 96
    assert manifest["counts"]["val"] == base_manifest["counts"]["val"]
    assert manifest["counts"]["test"] == base_manifest["counts"]["test"]
    assert manifest["augmentation_integrated"]["rows"] == 96
    # this run raised the cap (tiny workspace); real runs keep the 0.10 default
    assert manifest["augmentation_integrated"]["train_synthetic_adversarial_fraction"] <= 0.9

    train = [json.loads(line) for line in (final / "train.jsonl").read_text().splitlines()]
    val = [json.loads(line) for line in (final / "val.jsonl").read_text().splitlines()]
    test_rows = [json.loads(line) for line in (final / "test.jsonl").read_text().splitlines()]
    gold_file = tmp_path / "data/agentpay_ir_v2/review/GOLD_FROZEN_V3.jsonl"
    gold = [json.loads(line) for line in gold_file.read_text().splitlines()]
    aug_rows = [r for r in train if r["split_group"].startswith("aug_pi_")]
    assert len(aug_rows) == 96
    assert not any(r["split_group"].startswith("aug_pi_") for r in [*val, *test_rows, *gold])
    # every merged row kept its content hash and carries the integration stamp
    for r in aug_rows:
        assert content_sha256(r["premise"], r["hypothesis"], r["label"]) == r["content_sha256"]
        assert "integrated into TRAIN" in r["metadata"]["integration"]
    # gold file byte-identical to the baseline run (augmentation never touches gold)
    base_gold = base / "data/agentpay_ir_v2/review/GOLD_FROZEN_V3.jsonl"
    assert gold_file.read_bytes() == base_gold.read_bytes()


def test_finalizer_without_flag_never_integrates_augmentation(finalized: dict) -> None:
    root = finalized["root"]
    train = (root / "data" / "agentpay_ir_v2" / "corpus" / "final" / "train.jsonl").read_text()
    assert "aug_pi_" not in train


# ---------------------------------------------------------------------------
# runtime-correctness fix: the generated FINAL cell must EXECUTE and package
# the exact selected candidate (fake checkpoints, mocked download, no training)
# ---------------------------------------------------------------------------


def test_final_cell_executes_and_packages_exact_selected_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib as _hashlib
    import json as _json
    import os as _os
    import types as _types
    import zipfile as _zipfile

    cells = notebook_code_cells(COMMITTED_NOTEBOOK)
    final_src = next(c for c in cells if "selected_checkpoint_source_dir" in c)
    # FINAL_CELL is inserted verbatim (no .format): doubled braces would become
    # set-literals-of-dicts and crash at runtime — none may remain.
    assert "{{" not in final_src and "}}" not in final_src
    for verbatim_cell_name, marker in (("install", "%pip install"), ("train setup", "NLIDataset")):
        verbatim = next(c for c in cells if marker in c)
        assert "{{" not in verbatim, f"{verbatim_cell_name} cell must not use format escapes"

    monkeypatch.chdir(tmp_path)
    old_env = _os.environ.get("BUNDLE_PATH")
    _os.environ["BUNDLE_PATH"] = str(COMMITTED_ZIP)
    ns: dict = {}
    try:
        exec(compile(next(c for c in cells if "def verify_bundle" in c),  # noqa: S102 - test rig
                      "verify_cell", "exec"), ns)
        install = next(c for c in cells if "%pip install" in c)
        python_only = install[: install.index("# NOW import the runtime")].replace(
            "%pip install -q -r bundle/requirements-frozen.txt",
            "PIP_STUBBED_IN_PREFLIGHT = True").replace(
            "%pip uninstall -y -q torchvision torchaudio",
            "PIP_UNINSTALL_STUBBED_IN_PREFLIGHT = True")
        exec(compile(python_only, "install_cell", "exec"), ns)  # noqa: S102 - test rig
        exec(compile(python_only, "install_cell", "exec"), ns)  # noqa: S102 - test rig
    finally:
        if old_env is None:
            _os.environ.pop("BUNDLE_PATH", None)
        else:
            _os.environ["BUNDLE_PATH"] = old_env

    # fake candidate checkpoints with DISTINCT weights and their exact metrics
    results = {
        "A_2ep": {"eval_unsafe_c_to_e": 0, "eval_macro_f1": 0.91,
                  "eval_contradiction_recall": 0.82, "eval_neutral_recall": 0.70,
                  "eval_safe_false_block": 1},
        "B_3ep": {"eval_unsafe_c_to_e": 0, "eval_macro_f1": 0.88,
                  "eval_contradiction_recall": 0.79, "eval_neutral_recall": 0.66,
                  "eval_safe_false_block": 0},
    }
    for cand, metrics in (("cand_2ep", results["A_2ep"]), ("cand_3ep", results["B_3ep"])):
        d = tmp_path / cand
        d.mkdir()
        (d / "model.safetensors").write_bytes(cand.encode() * 256)  # distinct per candidate
        (d / "config.json").write_text('{"model_type": "fake"}')
        (d / "tokenizer.json").write_text('{"fake": true}')
        (_json.dumps(metrics, indent=1) + "\n").encode()
        (d / "validation_metrics.json").write_text(_json.dumps(metrics, indent=1))
        (d / "base_model_revision.txt").write_text("6c749ce3425cd33b46d187e45b92bbf96ee12ec7")

    downloads: list[str] = []
    ns.update(
        best="A_2ep",  # frozen rule: unsafe tie -> higher macro-F1 -> A wins
        results=results,
        REV="6c749ce3425cd33b46d187e45b92bbf96ee12ec7",
        transformers=_types.SimpleNamespace(__version__="5.15.1"),
        torch=_types.SimpleNamespace(__version__="2.13.0",
                                     version=_types.SimpleNamespace(cuda="12.4")),
        accelerate=_types.SimpleNamespace(__version__="1.14.0"),
        colab_files=_types.SimpleNamespace(download=downloads.append),
    )
    exec(compile(final_src, "final_cell", "exec"), ns)  # noqa: S102 - test rig

    # download mocked, no training happened (pure file operations above)
    assert downloads == ["agentpay-ir-v2-finetuned.zip"]
    art = tmp_path / "agentpay-ir-v2-finetuned"
    assert art.is_dir()

    tm = _json.loads((art / "training_metrics.json").read_text())
    assert tm["selected"] == "A_2ep"
    assert tm["selected_checkpoint_source_dir"] == "cand_2ep"
    assert tm["validation_results"] == results

    mm = _json.loads((art / "model_manifest.json").read_text())
    assert mm["selected_candidate"] == "A_2ep"
    assert mm["selected_checkpoint_source_dir"] == "cand_2ep"
    assert mm["selected_candidate_metrics"] == results["A_2ep"]
    assert "never retrained from base" in mm["packaging"]
    import platform as _platform

    assert mm["dependency_versions"] == {"transformers": "5.15.1", "torch": "2.13.0",
                                         "accelerate": "1.14.0",
                                         "python": _platform.python_version()}

    # the packaged weights are the SELECTED candidate's exact files (not B's)
    assert (art / "model.safetensors").read_bytes() == \
        (tmp_path / "cand_2ep" / "model.safetensors").read_bytes()
    assert (art / "model.safetensors").read_bytes() != \
        (tmp_path / "cand_3ep" / "model.safetensors").read_bytes()
    assert _json.loads((art / "validation_metrics.json").read_text()) == results["A_2ep"]

    # recorded artifact hashes are valid for the packaged files
    for fname, want in mm["artifact_files_sha256"].items():
        assert _hashlib.sha256((art / fname).read_bytes()).hexdigest() == want

    # the final ZIP exists and carries the artifact directory
    zip_path = tmp_path / "agentpay-ir-v2-finetuned.zip"
    assert zip_path.exists()
    with _zipfile.ZipFile(zip_path) as z:
        assert any(n.startswith("agentpay-ir-v2-finetuned/") for n in z.namelist())
        assert "agentpay-ir-v2-finetuned/model_manifest.json" in z.namelist()


def test_committed_bundle_is_the_post_review_final_bundle() -> None:
    """Regression guard (2026-08-30): after post-review finalization, the tracked
    bundle must be the one built from corpus/final — a rebuild with the builder's
    PRE-REVIEW default corpus would silently replace it and is caught here."""
    if not (REPO_ROOT / "data/agentpay_ir_v2/corpus/final/train.jsonl").exists():
        pytest.skip("post-review final freeze not present")
    with zipfile.ZipFile(COMMITTED_ZIP) as z:
        train_member = hashlib.sha256(z.read("train.jsonl")).hexdigest()
        val_member = hashlib.sha256(z.read("val.jsonl")).hexdigest()
    final = REPO_ROOT / "data/agentpay_ir_v2/corpus/final"
    assert train_member == sha256_file(final / "train.jsonl"), (
        "committed bundle train is not corpus/final — rebuild with --corpus-dir")
    assert val_member == sha256_file(final / "val.jsonl"), (
        "committed bundle val is not corpus/final — rebuild with --corpus-dir")


def test_trainingarguments_kwargs_match_installed_transformers() -> None:
    """Colab/5.15.1 drift guard: transformers 5.x removed TrainingArguments
    warmup_ratio — the exact Colab failure. Every TrainingArguments kwarg the
    notebook uses must exist in the INSTALLED transformers signature (the test
    venv pins the same frozen 5.15.1 that Colab installs)."""
    import ast
    import inspect

    from transformers import TrainingArguments

    cand = next(c for c in notebook_code_cells(COMMITTED_NOTEBOOK) if "def run(epochs)" in c)
    tree = ast.parse(cand)
    kwargs_used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "TrainingArguments":
            kwargs_used.update(kw.arg for kw in node.keywords if kw.arg is not None)
    assert kwargs_used, "notebook must construct TrainingArguments"
    assert "warmup_ratio" not in kwargs_used, "removed in transformers 5.x — use warmup_steps"
    params = set(inspect.signature(TrainingArguments.__init__).parameters)
    missing = sorted(kwargs_used - params)
    assert not missing, f"TrainingArguments kwargs unsupported by installed transformers: {missing}"
    # warmup semantics stay frozen: derived from the bundle's train_config ratio
    assert "WARMUP_RATIO" in cand and "warmup_steps" in cand
