"""M31: durable spend reservations — authorized / reserved / committed / available.

All mutations happen inside a single transaction while holding the row lock on
``authorization_spend`` (SELECT ... FOR UPDATE), so concurrent requests can
never exceed the authorization capacity. PostgreSQL is the authority; no Redis
involvement.

Lifecycle mapping used by later milestones:
- proposal accepted   -> ``reserve()``      (capacity is held)
- definitive failure  -> ``release()``      (capacity returns)
- verified success    -> ``commit()``       (reserved -> committed)
- provider unknown    -> do NOTHING         (reservation stays held)
"""

from datetime import UTC, datetime

from razormesh_api.domain.ids import IntentId
from razormesh_api.persistence.models import AuthorizationSpend
from razormesh_api.persistence.repositories import Repositories


class SpendError(Exception):
    """Base class for spend-management errors."""


class InsufficientCapacity(SpendError):
    def __init__(self, requested: int, available: int) -> None:
        super().__init__(
            f"insufficient authorization capacity: requested {requested}, available {available}"
        )
        self.requested = requested
        self.available = available


class InvalidSpendState(SpendError):
    pass


class SpendManager:
    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    def ensure_authorization(self, intent_id: IntentId, authorized_minor: int) -> None:
        """Create or synchronize durable capacity to the current authorization."""
        try:
            self._repos.spend.ensure(intent_id, authorized_minor=authorized_minor)
        except ValueError as exc:
            raise InvalidSpendState(str(exc)) from exc

    def reserve(self, intent_id: IntentId, amount_minor: int) -> None:
        """Atomically hold capacity for a proposed execution."""
        if amount_minor <= 0:
            raise InvalidSpendState("reservation amount must be positive")
        with self._repos.transaction() as session:
            row = self._repos.spend.get_for_update(intent_id, session)
            if row is None:
                raise InvalidSpendState(f"no authorization capacity for {intent_id}")
            available = row.authorized_minor - row.reserved_minor - row.committed_minor
            if amount_minor > available:
                raise InsufficientCapacity(requested=amount_minor, available=available)
            row.reserved_minor += amount_minor
            row.version += 1
            row.updated_at = datetime.now(UTC)

    def commit(self, intent_id: IntentId, amount_minor: int) -> None:
        """Verified success: convert an open reservation into committed spend."""
        if amount_minor <= 0:
            raise InvalidSpendState("commit amount must be positive")
        with self._repos.transaction() as session:
            row = self._repos.spend.get_for_update(intent_id, session)
            if row is None:
                raise InvalidSpendState(f"no authorization capacity for {intent_id}")
            if row.reserved_minor < amount_minor:
                raise InvalidSpendState(
                    f"cannot commit {amount_minor}: only {row.reserved_minor} reserved"
                )
            row.reserved_minor -= amount_minor
            row.committed_minor += amount_minor
            row.version += 1
            row.updated_at = datetime.now(UTC)

    def release(self, intent_id: IntentId, amount_minor: int) -> None:
        """Definitive failure: return held capacity to the pool."""
        if amount_minor <= 0:
            raise InvalidSpendState("release amount must be positive")
        with self._repos.transaction() as session:
            row = self._repos.spend.get_for_update(intent_id, session)
            if row is None:
                raise InvalidSpendState(f"no authorization capacity for {intent_id}")
            if row.reserved_minor < amount_minor:
                raise InvalidSpendState(
                    f"cannot release {amount_minor}: only {row.reserved_minor} reserved"
                )
            row.reserved_minor -= amount_minor
            row.version += 1
            row.updated_at = datetime.now(UTC)

    def snapshot(self, intent_id: IntentId) -> AuthorizationSpend | None:
        with self._repos.transaction() as session:
            return session.get(AuthorizationSpend, str(intent_id))

    def available(self, intent_id: IntentId) -> int:
        return self._repos.spend.available_minor(intent_id)

    def assert_invariants(self, intent_id: IntentId) -> None:
        row = self.snapshot(intent_id)
        if row is None:
            raise InvalidSpendState("no capacity row")
        if row.reserved_minor < 0 or row.committed_minor < 0:
            raise InvalidSpendState("negative reserved/committed")
        if row.reserved_minor + row.committed_minor > row.authorized_minor:
            raise InvalidSpendState(
                f"over-commitment: reserved {row.reserved_minor} + committed "
                f"{row.committed_minor} > authorized {row.authorized_minor}"
            )
