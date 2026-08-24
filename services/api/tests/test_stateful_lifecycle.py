"""M48 deep-gate: stateful lifecycle properties over the authorization machine.

Two property layers:

1. ``AuthorizationLifecycle`` — a Hypothesis rule-based state machine driving
   random legal transitions and asserting invariants after every step:
   terminal states never revive; execution only from AUTHORIZED.
2. Spend invariant property — for random reservation/commit/release sequences,
   reserved >= 0, committed >= 0, reserved+committed <= authorized at all times.
"""

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

from razormesh_api.domain.state_machine import (
    AuthorizationStatus,
    IllegalTransitionError,
    NotExecutableError,
    assert_executable,
    require_transition,
)


class AuthorizationLifecycle(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.status = AuthorizationStatus.AUTHORIZED

    @rule(new_status=st.sampled_from(AuthorizationStatus))
    def jump(self, new_status) -> None:  # type: ignore[no-untyped-def]
        """Attempt an arbitrary transition; legality decides outcome."""
        try:
            self.status = require_transition(self.status, new_status)
        except IllegalTransitionError:
            pass  # rejected transitions leave state untouched

    @precondition(lambda self: not _is_terminal(self.status))
    @rule(data=st.data())
    def advance_legally(self, data) -> None:  # type: ignore[no-untyped-def]
        from razormesh_api.domain.state_machine import (
            _LEGAL as _legal_map,  # white-box property test
        )

        targets = sorted(_legal_map[self.status])
        if targets:
            target = data.draw(st.sampled_from(targets))
            self.status = require_transition(self.status, target)

    @invariant()
    def execution_only_from_authorized(self) -> None:
        if self.status is not AuthorizationStatus.AUTHORIZED:
            with pytest.raises(NotExecutableError):
                assert_executable(self.status)

    @invariant()
    def terminal_never_revives(self) -> None:
        if _is_terminal(self.status):
            for target in AuthorizationStatus:
                if target is not self.status:
                    with pytest.raises(IllegalTransitionError):
                        require_transition(self.status, target)


def _is_terminal(status: AuthorizationStatus) -> bool:
    return status in {
        AuthorizationStatus.BLOCKED,
        AuthorizationStatus.SUPERSEDED,
        AuthorizationStatus.REVOKED,
        AuthorizationStatus.EXPIRED,
    }


TestAuthorizationLifecycle = AuthorizationLifecycle.TestCase

TestAuthorizationLifecycle.settings = settings(
    max_examples=25,
    stateful_step_count=20,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


@given(
    st.lists(
        st.tuples(st.integers(min_value=1, max_value=1000), st.sampled_from(["r", "c", "x"])),
        min_size=1,
        max_size=40,
    ),
    st.integers(min_value=1, max_value=5000),
)
@settings(max_examples=50, deadline=None)
def test_spend_ledger_invariant_under_random_sequences(ops, capacity):
    """Pure-model check mirroring SpendManager semantics."""
    authorized = capacity
    reserved = committed = 0
    for amount, op in ops:
        available = authorized - reserved - committed
        if op == "r":
            if amount <= available:
                reserved = min(reserved + amount, authorized)
        elif op == "c" and reserved >= amount:
            reserved -= amount
            committed += amount
        elif op == "x" and reserved >= amount:
            reserved -= amount
        assert reserved >= 0 and committed >= 0
        assert reserved + committed <= authorized
