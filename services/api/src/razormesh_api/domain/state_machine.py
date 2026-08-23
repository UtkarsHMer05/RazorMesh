"""M24: explicit authorization state machine.

The AI proposes, RazorGuard authorizes, the trusted executor executes. This
module makes the authorization lifecycle explicit so illegal transitions fail
closed:

- ``BLOCKED`` never executes and has no exits (a fresh contract/generation is
  required instead of mutating a blocked one).
- ``CHALLENGED`` never executes before successful reauthorization.
- Terminal states (SUPERSEDED / REVOKED / EXPIRED / BLOCKED) cannot be revived.
"""

from enum import StrEnum


class AuthorizationStatus(StrEnum):
    DRAFT = "DRAFT"
    AUTHORIZED = "AUTHORIZED"
    CHALLENGED = "CHALLENGED"
    BLOCKED = "BLOCKED"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class IllegalTransitionError(Exception):
    """Raised when a state change violates the authorization lifecycle."""


class NotExecutableError(Exception):
    """Raised when execution is attempted from a non-executable status."""


_TERMINAL: frozenset[AuthorizationStatus] = frozenset(
    {
        AuthorizationStatus.BLOCKED,
        AuthorizationStatus.SUPERSEDED,
        AuthorizationStatus.REVOKED,
        AuthorizationStatus.EXPIRED,
    }
)

_LEGAL: dict[AuthorizationStatus, frozenset[AuthorizationStatus]] = {
    AuthorizationStatus.DRAFT: frozenset(
        {
            AuthorizationStatus.AUTHORIZED,
            AuthorizationStatus.CHALLENGED,
            AuthorizationStatus.SUPERSEDED,
            AuthorizationStatus.REVOKED,
        }
    ),
    # RazorGuard may demote an active authorization at any time; the human may
    # revoke or supersede it; time may expire it.
    AuthorizationStatus.AUTHORIZED: frozenset(
        {
            AuthorizationStatus.CHALLENGED,
            AuthorizationStatus.BLOCKED,
            AuthorizationStatus.SUPERSEDED,
            AuthorizationStatus.REVOKED,
            AuthorizationStatus.EXPIRED,
        }
    ),
    # Only successful human reauthorization returns CHALLENGED -> AUTHORIZED.
    AuthorizationStatus.CHALLENGED: frozenset(
        {
            AuthorizationStatus.AUTHORIZED,
            AuthorizationStatus.BLOCKED,
            AuthorizationStatus.SUPERSEDED,
            AuthorizationStatus.REVOKED,
            AuthorizationStatus.EXPIRED,
        }
    ),
}

# Execution may ONLY proceed from an active AUTHORIZED authorization.
EXECUTABLE: frozenset[AuthorizationStatus] = frozenset({AuthorizationStatus.AUTHORIZED})


def is_terminal(status: AuthorizationStatus) -> bool:
    return status in _TERMINAL


def require_transition(
    current: AuthorizationStatus, target: AuthorizationStatus
) -> AuthorizationStatus:
    """Validate a proposed transition; return the target or raise."""
    if current == target:
        raise IllegalTransitionError(f"self-transition {current} is not a state change")
    if is_terminal(current):
        raise IllegalTransitionError(f"terminal status {current} has no exits")
    legal = _LEGAL[current]
    if target not in legal:
        raise IllegalTransitionError(f"illegal transition {current} -> {target}")
    return target


def assert_executable(status: AuthorizationStatus) -> None:
    """Fail closed unless the status permits payment execution."""
    if status not in EXECUTABLE:
        raise NotExecutableError(f"status {status} may never execute")
