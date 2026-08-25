"""P3-M22: exact + near-duplicate detection semantics."""

from datetime import UTC, datetime

from razormesh_api.agentpay_ir import make_record
from razormesh_api.dataset_dedup import analyze

PROV = {
    "generator": "seed-template-v1",
    "created_at_utc": datetime.now(UTC),
}


def _rec_ids(n: int) -> str:
    return f"air_{str(n).zfill(26)}"


def _rec(
    rid_num: int, premise: str, hypothesis: str, *, family="budget_ceiling", label="entailment"
) -> object:  # type: ignore[no-untyped-def]
    return make_record(
        record_id=f"air_{str(rid_num).zfill(26)}",
        premise=premise,
        hypothesis=hypothesis,
        label=label,  # type: ignore[arg-type]
        label_source="template_truth",
        family=family,  # type: ignore[arg-type]
        difficulty="easy",
        provenance=PROV,
    )


P1 = "Product page states wireless earbuds priced at ₹2,000 in stock with free shipping."
H1 = "The human authorized buying earbuds within ₹2,000."


def test_identical_content_is_exact_duplicate() -> None:
    a = _rec(1, P1, H1)
    b = _rec(2, P1, H1)
    report = analyze([a, b])
    assert report.duplicate_of == {_rec_ids(2): _rec_ids(1)}
    assert _rec_ids(1) in report.canonical_ids
    assert _rec_ids(2) not in report.canonical_ids


def test_high_overlap_paraphrase_caught_at_threshold() -> None:
    a = _rec(1, P1, H1)
    paraphrase_p = P1.replace("in stock with free shipping", "in stock w/ free shipping only")
    paraphrase_h = H1.replace("within ₹2,000", "under ₹2,000")
    b = _rec(2, paraphrase_p, paraphrase_h)
    report = analyze([a, b], near_threshold=0.85)
    assert len(report.clusters) >= 1


def test_distinct_records_all_canonical() -> None:
    a = _rec(1, P1, H1)
    b = _rec(
        2,
        "Seller listing describes a refurbished laptop at ₹45,000 with 90-day warranty.",
        "The human authorized buying a new laptop under ₹30,000.",
        family="condition_new_only",
        label="contradiction",
    )
    report = analyze([a, b])
    assert not report.duplicate_of
    assert len(report.canonical_ids) == 2


def test_cross_class_collision_reported_not_merged() -> None:
    same_text = "Listing shows the gadget enrolls buyers into monthly auto-renew."
    a = _rec(
        1,
        same_text,
        "The human authorized this recurring purchase.",
        family="trial_renewal_trap",
        label="contradiction",
    )
    b = _rec(
        2,
        same_text,
        "The human authorized this recurring purchase.",
        family="membership_insertion",
        label="entailment",
    )
    report = analyze([a, b])
    assert len(report.cross_class_collisions) == 1


def test_deterministic_cluster_ordering() -> None:
    a = _rec(3, P1, H1)
    b = _rec(1, P1, H1)
    c = _rec(2, P1, H1)
    r1 = analyze([a, b, c])
    r2 = analyze([c, b, a])
    assert r1 == r2
    canonical_member = next(cl for cl in r1.clusters if len(cl) == 3)
    assert canonical_member[0] == _rec_ids(1)  # smallest id canonical
