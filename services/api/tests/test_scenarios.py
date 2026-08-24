"""M42 acceptance: scenario registry schema validation + family coverage."""

import pytest
from pydantic import ValidationError

from razormesh_api.scenarios import (
    SCENARIOS,
    ExpectedOutcome,
    ScenarioFamily,
    ScenarioSpec,
    validate_registry,
)


def test_all_registered_scenarios_validate() -> None:
    for spec in SCENARIOS:
        parsed = ScenarioSpec.model_validate(spec.model_dump())
        assert parsed.scenario_id == spec.scenario_id


def test_registry_covers_every_required_family_exactly_once() -> None:
    problems = validate_registry()
    assert not problems, problems
    families = {s.family for s in SCENARIOS}
    assert families == set(ScenarioFamily)


def test_duplicate_ids_rejected_by_validator(tmp_path):  # type: ignore[no-untyped-def]
    dup = ScenarioSpec(
        scenario_id="safe-baseline-single",
        family=ScenarioFamily.SAFE_BASELINE,
        description="duplicate id probe",
        expected_outcome=ExpectedOutcome.ALLOW_EXECUTE_ONCE,
        safe_or_unsafe="safe",
        mutation="none",
    )
    ids = [s.scenario_id for s in (*SCENARIOS, dup)]
    assert len(set(ids)) != len(ids)


@pytest.mark.parametrize(
    "kwargs, err",
    [
        ({"family": ScenarioFamily.CROSS_PRINCIPAL}, "swap_principal_to"),
        ({"replay_count": 1, "family": ScenarioFamily.REPLAY}, "replay_count"),
        ({"family": ScenarioFamily.CHECKOUT_DRIFT}, "drift_field"),
        ({"family": ScenarioFamily.APPROVAL_SPLIT}, "split_parts"),
    ],
)
def test_family_specific_invariants_enforced(kwargs, err) -> None:  # type: ignore[no-untyped-def]
    base = dict(
        scenario_id="probe-1",
        description="invariant probe scenario",
        expected_outcome=ExpectedOutcome.EXECUTION_REJECTED,
        safe_or_unsafe="unsafe",
        mutation="probe mutation",
    )
    with pytest.raises(ValidationError, match=err):
        ScenarioSpec(**base, **kwargs)


def test_scenario_ids_match_required_pattern() -> None:
    import re

    pattern = re.compile(r"^[a-z0-9_\-]+$")
    assert all(pattern.fullmatch(s.scenario_id) for s in SCENARIOS)
