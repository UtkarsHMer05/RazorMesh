"""AgentPay-X benchmark tests (M46)."""

from __future__ import annotations

import pytest

from razormesh_api.protocol.agentpay_x import (
    build_scenarios,
    run_benchmark,
    run_scenario,
)


def test_benchmark_runs_to_completion():
    metrics = run_benchmark()
    assert metrics["scenarios_total"] >= 12
    # 100% attack block rate.
    assert metrics["attack_block_rate"] == 1.0
    # 100% safe pass rate.
    assert metrics["safe_pass_rate"] == 1.0


def test_attack_scenarios_all_blocked():
    metrics = run_benchmark()
    for r in metrics["results"]:
        if r["safe"]:
            continue
        assert r["passed"] is True, f"Attack {r['name']} ({r['family']}) did not BLOCK"


def test_safe_scenarios_all_pass():
    metrics = run_benchmark()
    for r in metrics["results"]:
        if not r["safe"]:
            continue
        assert r["passed"] is True, f"Safe {r['name']} did not pass"


def test_families_covered():
    families = {s.family for s in build_scenarios()}
    # 5 attack families in the slice.
    expected = {
        "amount_mutation",
        "merchant_substitution",
        "product_substitution",
        "quantity_mutation",
        "recurring_term_insertion",
        "currency_mutation",
        "equivalent_representation",
        "mcp_protocol_downgrade",
        "ap2_unknown_constraint",
        "ucp_unsupported_version",
        "ucp_invalid_content_digest",
        "acp_illegal_lifecycle_transition",
    }
    assert families == expected


def test_each_scenario_runs():
    for s in build_scenarios():
        result = run_scenario(s)
        # Every scenario must produce a result, not raise.
        assert result.scenario.name == s.name
