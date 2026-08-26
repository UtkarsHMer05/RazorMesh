"""P3-M41: semantic Security Lab suite."""

from razormesh_api.semantic_lab import run_semantic_scenarios


def test_all_semantic_scenarios_pass() -> None:
    results = run_semantic_scenarios()
    assert len(results) == 5
    failures = [r for r in results if not r["passed"]]
    assert not failures, failures


def test_injection_cannot_raise_allow() -> None:
    results = run_semantic_scenarios()
    inj = next(r for r in results if r["scenario_id"] == "sem-injection-price-hike")
    assert inj["final"] == "BLOCK"


def test_hard_decisions_supreme() -> None:
    results = run_semantic_scenarios()
    challenge = next(r for r in results if r["scenario_id"] == "sem-hard-challenge-stays")
    block = next(r for r in results if r["scenario_id"] == "sem-hard-block-supreme")
    assert challenge["final"] == "CHALLENGE"
    assert block["final"] == "BLOCK"
