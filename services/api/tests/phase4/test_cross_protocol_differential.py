"""Cross-protocol differential proof tests (Section 5)."""

from __future__ import annotations

import json

from razormesh_api.protocol.cross_protocol_differential import (
    cross_protocol_equivalence_proof,
    differential_proof,
    run_all,
    trust_path_cannot_allow_mismatched,
)


def test_equivalence_proof():
    eq = cross_protocol_equivalence_proof()
    assert eq["all_distinct"] is True
    assert len(eq["commitments"]) == 6
    # All 6 representations share the same commitment hash.
    assert len(set(eq["commitments"].values())) == 1


def test_material_mutations_block():
    diff = differential_proof()
    assert diff["material_pass"] == diff["material_total"], (
        f"failed: {[r for r in diff['results'] if r['material'] and not r['passed']]}"
    )
    assert diff["material_total"] >= 15


def test_presentation_mutations_pass_through():
    diff = differential_proof()
    assert diff["presentation_pass"] == diff["presentation_total"], (
        f"failed: {[r for r in diff['results'] if not r['material'] and not r['passed']]}"
    )


def test_trust_path_cannot_allow_mismatched():
    assert trust_path_cannot_allow_mismatched() is True


def test_no_secret_in_differential():
    blob = json.dumps(run_all(), default=str)
    for forbidden in ("BEGIN PRIVATE KEY", "Bearer ", "razorpay_key", "whsec_"):
        assert forbidden not in blob
