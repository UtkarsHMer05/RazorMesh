"""AP2 v0.2.0 proof matrix tests (Section 3 of pre-human acceptance gate)."""

from __future__ import annotations

from razormesh_api.protocol.ap2_proof import AP2Section3


def test_ap2_proof_matrix_runs():
    harness = AP2Section3()
    metrics = harness.run_all()
    assert metrics["target_version"] == "v0.2.0"
    assert metrics["total"] >= 28
    assert metrics["passed"] == metrics["total"], (
        f"failed: {[r for r in metrics['results'] if not r['passed']]}"
    )


def test_ap2_critical_g_case_blocks():
    """AP2 sig PASS + IntentContract mismatch → FINAL = BLOCK (P4-S19)."""
    harness = AP2Section3()
    assert harness.g_ap2_sig_pass_intentcontract_mismatch_blocks() is True
