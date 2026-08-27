"""ACP 2026-01-30 proof matrix tests (Section 4 of pre-human acceptance gate)."""

from __future__ import annotations

from razormesh_api.protocol.acp_proof import ACPSection4


def test_acp_proof_matrix_runs():
    harness = ACPSection4()
    metrics = harness.run_all()
    assert metrics["target_version"] == "2026-01-30"
    assert metrics["total"] >= 30
    assert metrics["passed"] == metrics["total"], (
        f"failed: {[r for r in metrics['results'] if not r['passed']]}"
    )
