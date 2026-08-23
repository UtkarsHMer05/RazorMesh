"""M24 acceptance: explicit authorization state machine, fail-closed execution."""

import pytest

from razormesh_api.domain.state_machine import (
    EXECUTABLE,
    AuthorizationStatus,
    IllegalTransitionError,
    NotExecutableError,
    assert_executable,
    is_terminal,
    require_transition,
)

ALL = list(AuthorizationStatus)
_TERMINAL = {
    AuthorizationStatus.BLOCKED,
    AuthorizationStatus.SUPERSEDED,
    AuthorizationStatus.REVOKED,
    AuthorizationStatus.EXPIRED,
}
_LEGAL_PAIRS = {
    (AuthorizationStatus.DRAFT, AuthorizationStatus.AUTHORIZED),
    (AuthorizationStatus.DRAFT, AuthorizationStatus.CHALLENGED),
    (AuthorizationStatus.DRAFT, AuthorizationStatus.SUPERSEDED),
    (AuthorizationStatus.DRAFT, AuthorizationStatus.REVOKED),
    (AuthorizationStatus.AUTHORIZED, AuthorizationStatus.CHALLENGED),
    (AuthorizationStatus.AUTHORIZED, AuthorizationStatus.BLOCKED),
    (AuthorizationStatus.AUTHORIZED, AuthorizationStatus.SUPERSEDED),
    (AuthorizationStatus.AUTHORIZED, AuthorizationStatus.REVOKED),
    (AuthorizationStatus.AUTHORIZED, AuthorizationStatus.EXPIRED),
    (AuthorizationStatus.CHALLENGED, AuthorizationStatus.AUTHORIZED),
    (AuthorizationStatus.CHALLENGED, AuthorizationStatus.BLOCKED),
    (AuthorizationStatus.CHALLENGED, AuthorizationStatus.SUPERSEDED),
    (AuthorizationStatus.CHALLENGED, AuthorizationStatus.REVOKED),
    (AuthorizationStatus.CHALLENGED, AuthorizationStatus.EXPIRED),
}


def test_every_legal_transition_succeeds() -> None:
    for current, target in _LEGAL_PAIRS:
        assert require_transition(current, target) is target


def test_every_other_pair_is_illegal_exhaustive_matrix() -> None:
    for current in ALL:
        for target in ALL:
            if (current, target) in _LEGAL_PAIRS:
                continue
            with pytest.raises(IllegalTransitionError):
                require_transition(current, target)


def test_terminal_states_have_no_exits() -> None:
    for status in ALL:
        assert is_terminal(status) == (status in _TERMINAL)
    for terminal in _TERMINAL:
        for target in ALL:
            if target is terminal:
                continue
            with pytest.raises(IllegalTransitionError):
                require_transition(terminal, target)


def test_only_authorized_is_executable() -> None:
    assert EXECUTABLE == {AuthorizationStatus.AUTHORIZED}
    for status in ALL:
        if status is AuthorizationStatus.AUTHORIZED:
            continue
        with pytest.raises(NotExecutableError):
            assert_executable(status)
    assert_executable(AuthorizationStatus.AUTHORIZED)  # does not raise


def test_blocked_never_executes_and_cannot_be_revived() -> None:
    with pytest.raises(NotExecutableError):
        assert_executable(AuthorizationStatus.BLOCKED)
    for revive_target in (
        AuthorizationStatus.AUTHORIZED,
        AuthorizationStatus.DRAFT,
        AuthorizationStatus.CHALLENGED,
    ):
        with pytest.raises(IllegalTransitionError):
            require_transition(AuthorizationStatus.BLOCKED, revive_target)


def test_challenged_cannot_execute_until_reauthorized() -> None:
    with pytest.raises(NotExecutableError):
        assert_executable(AuthorizationStatus.CHALLENGED)
    # reauthorization path: CHALLENGED -> AUTHORIZED then executable
    assert (
        require_transition(AuthorizationStatus.CHALLENGED, AuthorizationStatus.AUTHORIZED)
        is AuthorizationStatus.AUTHORIZED
    )
    assert_executable(AuthorizationStatus.AUTHORIZED)


def test_intent_status_enum_stays_aligned_with_machine() -> None:
    from razormesh_api.domain.intent import IntentStatus

    machine_names = {s.value for s in AuthorizationStatus}
    intent_names = {s.value for s in IntentStatus}
    assert intent_names == machine_names
