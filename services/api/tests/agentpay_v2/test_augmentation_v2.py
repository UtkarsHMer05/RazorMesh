"""Pre-label correction: prompt-injection augmentation staging-set gates.

The set is PREPARED but NOT integrated (nothing in the training pipeline reads
it). These tests pin its integrity so it cannot silently rot or drift into the
frozen data: fixed size/labels, full v2 provenance, hash/group/text disjointness
from corpus, OOD, gold and the PVB008 grid, and an integration state that stays
"NOT integrated".
"""

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
AUG = REPO_ROOT / "data" / "agentpay_ir_v2" / "augmentation"
AUG_JSONL = AUG / "prompt_injection_aug_v2.jsonl"
AUG_MANIFEST = AUG / "PROMPT_INJECTION_AUG_V2_MANIFEST.json"
CORPUS = REPO_ROOT / "data" / "agentpay_ir_v2" / "corpus"
OOD = REPO_ROOT / "data" / "agentpay_ir_v2" / "eval" / "fresh_ood_v2.jsonl"
PVB008 = REPO_ROOT / "docs" / "agentpay_ir_v2" / "PRE_V2_TEMPLATE_ROBUSTNESS.json"
FINALIZER = (REPO_ROOT / "scripts" / "rzp_finalize_review_v2.py").read_text()


def norm(t: str) -> str:
    return re.sub(r"\W+", " ", t.lower()).strip()


@pytest.fixture(scope="module")
def aug() -> list[dict]:
    assert AUG_JSONL.exists() and AUG_MANIFEST.exists(), \
        "run scripts/rzp_build_prompt_injection_augmentation_v2.py"
    return [json.loads(line) for line in AUG_JSONL.read_text().splitlines() if line.strip()]


def test_augmentation_matches_manifest_and_is_not_integrated(aug: list[dict]) -> None:
    import hashlib

    manifest = json.loads(AUG_MANIFEST.read_text())
    assert manifest["rows"] == len(aug) == 96
    assert hashlib.sha256(AUG_JSONL.read_bytes()).hexdigest() == manifest["sha256"]
    assert manifest["labels"] == {"neutral": 48, "contradiction": 48}
    assert manifest["integration"]["status"].startswith("NOT integrated into any frozen artifact")
    assert manifest["integration"]["cap"]["fraction_of_train"] <= 0.10
    # integration is reachable ONLY behind the explicit opt-in flag (default off):
    # the finalizer may reference the staging set, but the bundle builder/notebook
    # must never reference it at all.
    assert "--integrate-prompt-injection-augmentation" in FINALIZER
    squashed = " ".join(FINALIZER.split())
    assert ('add_argument("--integrate-prompt-injection-augmentation",'
            ' action="store_true"' in squashed)
    builder_src = (REPO_ROOT / "scripts" / "rzp_build_colab_bundle_v2.py").read_text()
    assert "prompt_injection_aug" not in builder_src


def test_augmentation_rows_carry_v2_contract_and_aug_namespace(aug: list[dict]) -> None:
    for r in aug:
        for field in ("record_id", "schema_version", "source_dataset", "source_kind",
                      "source_license", "split_group", "generator_parent_id",
                      "template_family_id", "entity_family_id", "content_sha256"):
            assert r.get(field), (r.get("record_id"), field)
        assert r["schema_version"] == "agentpay-ir-v2"
        assert r["source_dataset"] == "razormesh_internal_adversarial"
        assert r["source_kind"] == "synthetic_adversarial"
        assert r["split_group"].startswith("aug_pi_")
        assert r["template_family_id"].startswith("augpi_")
        assert r["metadata"]["integration"] == "NOT integrated; requires explicit human decision"
        assert canonical_guard_ok(r)


def canonical_guard_ok(r: dict) -> bool:
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from rzp_build_agentpay_ir_v2_corpus import canonical_guard

    return canonical_guard(r["premise"], r["hypothesis"])


def test_augmentation_disjoint_from_corpus_ood_gold_and_pvb008(aug: list[dict]) -> None:
    corpus_hashes: set[str] = set()
    corpus_groups: set[str] = set()
    corpus_blob = ""
    for split in ("train", "val", "test"):
        for line in (CORPUS / f"{split}.jsonl").read_text().splitlines():
            r = json.loads(line)
            corpus_hashes.add(r["content_sha256"])
            corpus_groups.add(r["split_group"])
            corpus_blob += norm(r["premise"]) + norm(r["hypothesis"])
    ood_hashes: set[str] = set()
    ood_groups: set[str] = set()
    ood_blob = ""
    for line in OOD.read_text().splitlines():
        r = json.loads(line)
        ood_hashes.add(r["content_sha256"])
        ood_groups.add(r["split_group"])
        ood_blob += norm(r["premise"]) + norm(r["hypothesis"])
    gold_path = REPO_ROOT / "data/agentpay_ir_v2/review/GOLD_FROZEN_V3.jsonl"
    gold_hashes = ({json.loads(ln)["content_sha256"]
                   for ln in gold_path.read_text().splitlines()}
                   if gold_path.exists() else set())
    pvb_blob = ""
    for fam in json.loads(PVB008.read_text())["families"]:
        for pair in fam["pairs"]:
            pvb_blob += norm(pair["premise"]) + norm(pair["hypothesis"])

    for r in aug:
        assert r["content_sha256"] not in corpus_hashes
        assert r["content_sha256"] not in ood_hashes
        assert r["content_sha256"] not in gold_hashes
        assert r["split_group"] not in corpus_groups and r["split_group"] not in ood_groups
        assert norm(r["premise"]) not in pvb_blob and norm(r["hypothesis"]) not in pvb_blob
