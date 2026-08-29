"""PRE-REVIEW FINAL CORRECTION #19: frozen v2 OOD integrity gates.

The expanded OOD must stay hash/group-disjoint from the corpus, carry the full
v2 provenance contract on every row, meaningfully cover the RazorMesh security
semantics families (recurring/trial/membership/fee/seller/quantity/condition/
prompt-injection/lookalike/negation) with a contradiction-heavy expansion, and
remain frozen (sha-pinned) before any training.
"""

import json
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
EVAL = REPO_ROOT / "data" / "agentpay_ir_v2" / "eval"
OOD = EVAL / "fresh_ood_v2.jsonl"
FROZEN = EVAL / "fresh_ood_v2_FROZEN.json"
CORPUS = REPO_ROOT / "data" / "agentpay_ir_v2" / "corpus"

SECURITY_FAMILIES = (
    "recurring_subscription", "trial_to_paid_renewal", "membership_insertion",
    "semantic_fees", "seller_authorization", "quantity", "product_condition",
    "prompt_injection_like_merchant_text", "safe_lookalikes", "misleading_negation",
)

# fresh synthetic entities from the security expansion must stay corpus-absent
EXPANSION_ENTITIES = ("AuroraBrew", "NimbusFit", "ZephyrAir", "LumaView", "TerraCore",
                      "VoltEdge", "CirrusFlow", "StonePeak", "VertexMart", "BluePeak Outlet",
                      "QuickShip Depot", "MegaDeals Hub", "PrimeVend Traders")


@pytest.fixture(scope="module")
def ood() -> list[dict]:
    assert OOD.exists() and FROZEN.exists(), "run scripts/rzp_expand_ood_v2.py"
    return [json.loads(line) for line in OOD.read_text().splitlines() if line.strip()]


@pytest.fixture(scope="module")
def frozen() -> dict:
    return json.loads(FROZEN.read_text())


def test_ood_matches_its_freeze_manifest(ood: list[dict], frozen: dict) -> None:
    import hashlib

    assert frozen["rows"] == len(ood)
    assert hashlib.sha256(OOD.read_bytes()).hexdigest() == frozen["sha256"]
    assert "frozen BEFORE training" in frozen["rule"]


def test_ood_rows_carry_full_v2_provenance(ood: list[dict]) -> None:
    for r in ood:
        for field in ("record_id", "schema_version", "premise", "hypothesis", "label",
                      "source_dataset", "source_kind", "source_license", "split_group",
                      "generator_parent_id", "template_family_id", "entity_family_id",
                      "safe_or_attack", "content_sha256"):
            assert r.get(field) or r.get(field) == "", (r.get("record_id"), field)
        assert r["schema_version"] == "agentpay-ir-v2"
        assert r["label"] in ("contradiction", "entailment", "neutral")


def test_ood_hash_and_group_disjoint_from_corpus(ood: list[dict]) -> None:
    corpus_hashes: set[str] = set()
    corpus_groups: set[str] = set()
    for split in ("train", "val", "test"):
        for line in (CORPUS / f"{split}.jsonl").read_text().splitlines():
            r = json.loads(line)
            corpus_hashes.add(r["content_sha256"])
            corpus_groups.add(r["split_group"])
    assert not ({r["content_sha256"] for r in ood} & corpus_hashes)
    assert not ({r["split_group"] for r in ood} & corpus_groups)


def test_ood_security_expansion_covers_all_ten_families(ood: list[dict], frozen: dict) -> None:
    fams = Counter(r["family"] for r in ood)
    for family in SECURITY_FAMILIES:
        assert fams[family] >= 10, f"security family {family} under-covered: {fams[family]}"
    expansion = frozen["expansion"]
    assert expansion["added_rows"] >= 250
    assert expansion["entity_held_out"] is True
    new_labels = expansion["added_labels"]
    assert new_labels["contradiction"] >= 120
    assert new_labels["contradiction"] / expansion["added_rows"] >= 0.45


def test_ood_total_contradiction_share_is_meaningful(ood: list[dict], frozen: dict) -> None:
    labels = Counter(r["label"] for r in ood)
    assert labels["contradiction"] / len(ood) >= 0.25, dict(labels)
    assert frozen["composition"]["labels"]["contradiction"] == labels["contradiction"]


def test_ood_expansion_entities_are_corpus_absent(ood: list[dict]) -> None:
    corpus_blob = " ".join(
        json.loads(line)["premise"]
        for split in ("train", "val", "test")
        for line in (CORPUS / f"{split}.jsonl").read_text().splitlines())
    expansion_rows = [r for r in ood if r["metadata"].get("ood_role") == "security_expansion_v2"]
    assert len(expansion_rows) >= 250
    for r in expansion_rows:
        # no unrendered template placeholders may survive into frozen data
        assert "{" not in r["premise"] and "}" not in r["premise"], r["record_id"]
        assert "{" not in r["hypothesis"], r["record_id"]
    for tok in EXPANSION_ENTITIES:
        assert tok not in corpus_blob, f"expansion entity {tok!r} leaked into the corpus"
    assert all(any(tok in r["premise"] for tok in EXPANSION_ENTITIES) for r in expansion_rows)


def test_ood_rows_keep_authorization_out_of_premise(ood: list[dict]) -> None:
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from rzp_build_agentpay_ir_v2_corpus import canonical_guard

    for r in ood:
        assert canonical_guard(r["premise"], r["hypothesis"]), r["record_id"]
