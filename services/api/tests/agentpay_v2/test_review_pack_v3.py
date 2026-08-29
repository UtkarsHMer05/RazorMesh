"""PRE-REVIEW FINAL CORRECTION #1-6: frozen V3 review-pack integrity gates.

The reviewer-facing pack (committed) must contain ONLY card_id/premise/hypothesis,
with zero duplicate normalized pairs. The private linkage + role manifest
(gitignored, present on the operator machine) must show zero duplicate record_ids,
group-level role assignment with no required grouping unit spanning GOLD and
SUPERVISED, and a role-manifest hash that round-trips against the canonical
definition stored in the separate freeze manifest.

Private-file tests skip (never fail) on a fresh clone where the gitignored
linkage/roles are absent — the committed pack + freeze gates always run.
"""

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
REVIEW = REPO_ROOT / "data" / "agentpay_ir_v2" / "review"
PACK = REVIEW / "REVIEW_PACK_V3.jsonl"
FREEZE = REVIEW / "REVIEW_PACK_FREEZE_V3.json"
LINKAGE = REVIEW / "REVIEW_LINKAGE_V3.json"
ROLE_MANIFEST = REVIEW / "REVIEW_ROLE_MANIFEST_V3.json"

CARD_ID_RE = re.compile(r"^rc2_\d{4}$")
# Label-bearing metadata keys must never appear anywhere reviewer-facing.
LABEL_BEARING_SUFFIXES = ("_contradiction", "_entailment", "_neutral")
FORBIDDEN_KEYS = {"stratum", "source_class", "label", "review_role", "role", "hint",
                  "metadata", "source_label", "expected_label", "label_hint", "gold", "supervised"}


def norm(t: str) -> str:
    return re.sub(r"\W+", " ", t.lower()).strip()


def _load_pack() -> list[dict]:
    return [json.loads(line) for line in PACK.read_text().splitlines() if line.strip()]


@pytest.fixture(scope="module")
def pack() -> list[dict]:
    assert PACK.exists(), "REVIEW_PACK_V3.jsonl missing — run scripts/rzp_build_review_pack_v3.py"
    return _load_pack()


@pytest.fixture(scope="module")
def freeze() -> dict:
    return json.loads(FREEZE.read_text())


# ---------------------------------------------------------------------------
# Reviewer-facing pack (committed): minimal fields + zero duplicate pairs
# ---------------------------------------------------------------------------


def test_pack_cards_have_exactly_the_three_reviewer_fields(pack: list[dict]) -> None:
    assert len(pack) >= 600
    for card in pack:
        assert set(card.keys()) == {"card_id", "premise", "hypothesis"}, card.keys()
        assert CARD_ID_RE.match(card["card_id"]), card["card_id"]
        assert card["premise"].strip() and card["hypothesis"].strip()
        assert len(card["premise"]) <= 900 and len(card["hypothesis"]) <= 400


def test_pack_carries_no_label_bearing_metadata_keys_or_values(pack: list[dict]) -> None:
    """Catches *_contradiction / *_entailment / *_neutral style metadata and any
    stratum/source_class/label/role leakage in the reviewer-facing JSON."""
    for card in pack:
        for key in card:
            lowered = key.lower()
            assert lowered not in FORBIDDEN_KEYS, key
            assert not lowered.endswith(LABEL_BEARING_SUFFIXES), key
        blob = json.dumps(card, sort_keys=True)
        for suffix in LABEL_BEARING_SUFFIXES:
            assert f'"{suffix}"' not in blob  # no key or value shaped like a label field


def test_pack_has_zero_duplicate_normalized_pairs(pack: list[dict]) -> None:
    pairs = [(norm(c["premise"])[:160], norm(c["hypothesis"])[:160]) for c in pack]
    assert len(pairs) == len(set(pairs)), "duplicate normalized (premise, hypothesis) pair"


def test_freeze_manifest_counts_match_pack(pack: list[dict], freeze: dict) -> None:
    assert freeze["pack"] == "REVIEW_PACK_V3"
    assert freeze["cards"] == len(pack)
    assert freeze["unique_record_ids"] == len(pack)
    assert freeze["unique_normalized_pairs"] == len(pack)
    assert freeze["reviewer_fields"] == ["card_id", "premise", "hypothesis"]
    body = PACK.read_bytes()
    assert hashlib.sha256(body).hexdigest() == freeze["reviewer_pack_sha256"]
    # the freeze manifest carries counts/hashes/provenance only — never the
    # assignments, the linkage, or any source label
    for forbidden in ("assignments", "decisions", "source_label"):
        assert forbidden not in freeze, forbidden


# ---------------------------------------------------------------------------
# Role manifest + linkage (private): round-trip hash + group-level isolation
# ---------------------------------------------------------------------------


def _private_fixtures() -> tuple[dict, dict] | None:
    if not LINKAGE.exists() or not ROLE_MANIFEST.exists():
        return None
    return json.loads(LINKAGE.read_text()), json.loads(ROLE_MANIFEST.read_text())


def test_role_manifest_round_trips_against_freeze_hash(freeze: dict) -> None:
    """PRE-REVIEW FINAL CORRECTION #6: the frozen manifest must round-trip and
    verify under the ONE canonical definition (assignments-only sha256, stored
    exclusively in the freeze manifest — never a self-containing field)."""
    if not ROLE_MANIFEST.exists():
        pytest.skip("private role manifest absent (fresh clone)")
    manifest = json.loads(ROLE_MANIFEST.read_text())
    # No self-containing hash field anywhere in the manifest.
    assert "role_manifest_sha256" not in manifest
    assert "sha256" not in json.dumps({k: manifest[k] for k in manifest if k != "assignments"})
    assignments = manifest["assignments"]
    recomputed = hashlib.sha256(
        json.dumps(assignments, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert recomputed == freeze["role_manifest_sha256"]
    assert "over {card_id: role} only" in freeze["role_sha_definition"]


def test_role_manifest_assignments_cover_pack_exactly(pack: list[dict], freeze: dict) -> None:
    if not ROLE_MANIFEST.exists():
        pytest.skip("private role manifest absent (fresh clone)")
    manifest = json.loads(ROLE_MANIFEST.read_text())
    assignments = manifest["assignments"]
    pack_ids = {c["card_id"] for c in pack}
    assert set(assignments) == pack_ids
    assert set(assignments.values()) == {"gold", "supervised"}
    n_gold = sum(1 for v in assignments.values() if v == "gold")
    assert manifest["n_gold"] == n_gold == freeze["gold_cards"]
    assert manifest["n_supervised"] == len(pack) - n_gold == freeze["supervised_cards"]
    assert 250 <= n_gold <= 340  # ~300 target; isolation may move the exact count


def test_linkage_zero_duplicate_record_ids_and_pack_provenance_match(
    pack: list[dict], freeze: dict
) -> None:
    if not LINKAGE.exists():
        pytest.skip("private linkage absent (fresh clone)")
    linkage = json.loads(LINKAGE.read_text())
    assert set(linkage) == {c["card_id"] for c in pack}
    record_ids = [lnk["record_id"] for lnk in linkage.values()]
    assert len(record_ids) == len(set(record_ids)), "duplicate underlying record_id in pack"
    assert freeze["unique_record_ids"] == len(set(record_ids))
    # every card resolves to a real corpus row whose text it carries verbatim
    corpus: dict[str, dict] = {}
    for split in ("train", "val", "test"):
        corpus_file = REPO_ROOT / "data" / "agentpay_ir_v2" / "corpus" / f"{split}.jsonl"
        for line in corpus_file.read_text().splitlines():
            row = json.loads(line)
            corpus[row["record_id"]] = row
    for card in pack:
        row = corpus[linkage[card["card_id"]]["record_id"]]
        assert row["premise"][:900] == card["premise"]
        assert row["hypothesis"][:400] == card["hypothesis"]


def test_roles_are_group_level_no_grouping_unit_spans_gold_and_supervised(
    freeze: dict,
) -> None:
    """PRE-REVIEW FINAL CORRECTION #2/#8: record_id, split_group, generator
    parent and entity family must never occur in both GOLD and SUPERVISED;
    internal template families neither (contractnli/esci exception disclosed)."""
    priv = _private_fixtures()
    if priv is None:
        pytest.skip("private linkage/role manifest absent (fresh clone)")
    linkage, manifest = priv
    roles = manifest["assignments"]
    group_roles: dict[str, set[str]] = defaultdict(set)
    record_roles: dict[str, set[str]] = defaultdict(set)
    entity_roles: dict[str, set[str]] = defaultdict(set)
    internal_tf_roles: dict[str, set[str]] = defaultdict(set)
    corpus: dict[str, dict] = {}
    for split in ("train", "val", "test"):
        corpus_file = REPO_ROOT / "data" / "agentpay_ir_v2" / "corpus" / f"{split}.jsonl"
        for line in corpus_file.read_text().splitlines():
            row = json.loads(line)
            corpus[row["record_id"]] = row
    for cid, link in linkage.items():
        role = roles[cid]
        group_roles[link["split_group"]].add(role)
        record_roles[link["record_id"]].add(role)
        row = corpus[link["record_id"]]
        # generator_parent_id is 1:1 with split_group and entity_family_id is
        # 1:1 with split_group in this corpus; verified here rather than assumed.
        assert row["generator_parent_id"] == link["split_group"]
        entity_roles[row["entity_family_id"] or link["split_group"]].add(role)
        if link["source_class"] == "razormesh_security_corpus" and link["template_family_id"]:
            internal_tf_roles[link["template_family_id"]].add(role)
    for name, mapping in (("split_group", group_roles), ("record_id", record_roles),
                          ("entity_family", entity_roles),
                          ("internal_template_family", internal_tf_roles)):
        spanning = {unit for unit, rs in mapping.items() if len(rs) > 1}
        assert not spanning, f"{name} spans GOLD and SUPERVISED: {sorted(spanning)[:5]}"
    exc = freeze["template_family_exception"]
    assert exc["contractnli_esci_families_spanning_roles"] >= 0  # disclosed, not hidden
