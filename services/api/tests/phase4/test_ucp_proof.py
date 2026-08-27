"""Tests for the UCP 2026-04-08 proof harness (Section 2)."""

from __future__ import annotations

from razormesh_api.protocol.ucp_proof import (
    UCPSection2,
    content_digest,
    verify_content_digest,
)


def test_ucp_proof_matrix_runs():
    harness = UCPSection2()
    metrics = harness.run_all()
    assert metrics["target_version"] == "2026-04-08"
    assert metrics["total"] >= 30
    # Per gate, no required item should fail. The harness is built
    # to be deterministic.
    assert metrics["passed"] == metrics["total"], (
        f"failed: {[r for r in metrics['results'] if not r['passed']]}"
    )


def test_content_digest_round_trip():
    body = b'{"a":1}'
    d = content_digest(body)
    assert verify_content_digest(body, d)


def test_content_digest_one_byte_mutation():
    body = b'{"a":1}'
    d = content_digest(body)
    mutated = bytearray(body)
    mutated[0] ^= 0x01
    assert not verify_content_digest(bytes(mutated), d)


def test_content_digest_reserialization_changes_bytes():
    body1 = b'{"a":1}'
    d = content_digest(body1)
    body2 = b'{"a": 1}'  # space
    assert not verify_content_digest(body2, d)
