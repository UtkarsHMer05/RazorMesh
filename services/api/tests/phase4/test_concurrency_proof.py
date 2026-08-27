"""Concurrency / replay / exactly-once proof tests (Section 6)."""

from __future__ import annotations

from razormesh_api.protocol.concurrency_proof import ConcurrencySection6


def test_concurrency_proof_runs():
    harness = ConcurrencySection6()
    metrics = harness.run_all()
    assert metrics["total"] >= 9
    # Per gate, every concurrency scenario must show exactly-once
    # property (effect_count == 1) or the conflict case.
    assert metrics["passed"] == metrics["total"], (
        f"failed: {[r for r in metrics['results'] if not r['passed']]}"
    )


def test_a_exactly_once_20_workers():
    h = ConcurrencySection6()
    r = h.a_20_workers_same_authorized_completion()
    assert r["effect_count"] == 1


def test_b_exactly_once_same_request():
    h = ConcurrencySection6()
    r = h.b_20_workers_same_idempotency_same_request()
    assert r["effect_count"] == 1


def test_c_conflict_at_most_one_effect():
    h = ConcurrencySection6()
    r = h.c_20_workers_same_key_conflicting_bodies()
    assert r["effect_count"] <= 1


def test_d_ap2_mandate_replay_exactly_once():
    h = ConcurrencySection6()
    r = h.d_ap2_mandate_replay_storm()
    assert r["effect_count"] == 1


def test_e_mcp_duplicate_storm_exactly_once():
    h = ConcurrencySection6()
    r = h.e_mcp_duplicate_tool_call_storm()
    assert r["effect_count"] == 1


def test_f_ucp_duplicate_storm_exactly_once():
    h = ConcurrencySection6()
    r = h.f_ucp_duplicate_request_event_storm()
    assert r["effect_count"] == 1


def test_g_acp_complete_storm_exactly_once():
    h = ConcurrencySection6()
    r = h.g_acp_complete_storm()
    assert r["effect_count"] == 1


def test_h_race_one_settlement():
    h = ConcurrencySection6()
    r = h.h_callback_webhook_protocol_reconciliation_race()
    assert r["effect_count"] == 1


def test_i_lost_response_no_blind_payment():
    h = ConcurrencySection6()
    r = h.i_lost_response_no_blind_fresh_payment()
    assert r["exactly_once"] is True
