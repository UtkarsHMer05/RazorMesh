"""M43 acceptance: adversarial runner executes every scenario through the real path."""

import pytest

from razormesh_api.evaluation import AdversarialRunner, ScenarioResult
from razormesh_api.scenarios import SCENARIOS


@pytest.fixture(scope="module")
def runner():
    return AdversarialRunner()


def test_every_scenario_actual_matches_expected(runner: AdversarialRunner) -> None:
    results = runner.run_all()
    assert len(results) == len(SCENARIOS)
    failures = [r for r in results if not r.passed]
    for r in failures:
        print(f"FAILED {r.scenario_id}: expected={r.expected} actual={r.actual} {r.detail}")
    assert not failures


def test_safe_baseline_allows_exactly_once(runner: AdversarialRunner) -> None:
    spec = next(s for s in SCENARIOS if s.family.value == "SAFE_BASELINE")
    result: ScenarioResult = runner.run_one(spec)
    assert result.passed and result.actual == "ALLOW_EXECUTE_ONCE"


def test_context_swap_rejected_with_reason_code(runner: AdversarialRunner) -> None:
    spec = next(s for s in SCENARIOS if s.family.value == "CROSS_PRINCIPAL")
    result = runner.run_one(spec)
    assert result.passed
    assert "PRINCIPAL_MISMATCH" in result.detail


def test_replay_yields_single_effect(runner: AdversarialRunner) -> None:
    spec = next(s for s in SCENARIOS if s.family.value == "REPLAY")
    result = runner.run_one(spec)
    assert result.passed and "durable attempts=1" in result.detail


def test_provider_unknown_never_creates_fresh_operation(runner: AdversarialRunner) -> None:
    spec = next(s for s in SCENARIOS if s.family.value == "PROVIDER_UNKNOWN")
    result = runner.run_one(spec)
    assert result.passed and result.actual == "NO_FRESH_OP_AFTER_UNKNOWN"
