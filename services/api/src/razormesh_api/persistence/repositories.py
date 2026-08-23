"""Repository/data-access layer.

Explicit repositories avoid SQL scattered through route handlers. All writes go
through transactional session scopes; concurrent critical sections use
SELECT ... FOR UPDATE row locks so the durable PostgreSQL state is the authority
(SEC-019). Redis is never the durable truth (SEC-020).
"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from razormesh_api.domain.ids import (
    AuditEventId,
    CheckoutId,
    DecisionId,
    ExecutionAttemptId,
    ExecutionTicketId,
    IntentId,
    MerchantId,
    ProductId,
)
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.models import (
    AuditEvent,
    AuthorizationSpend,
    Checkout,
    Decision,
    ExecutionAttempt,
    ExecutionTicket,
    IntentContract,
    Merchant,
    Product,
)


class RepositoryError(Exception):
    """Base class for repository-level errors."""


class ConcurrencyConflict(RepositoryError):
    """Raised when an optimistic/pessimistic lock cannot be satisfied."""


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Transactional unit-of-work. Commits on success; rolls back on error."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class MerchantRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def save(self, merchant: Merchant) -> Merchant:
        with session_scope(self._factory) as s:
            s.add(merchant)
            s.flush()
            s.refresh(merchant)
            return merchant

    def get(self, merchant_id: MerchantId) -> Merchant | None:
        with session_scope(self._factory) as s:
            return s.get(Merchant, str(merchant_id))

    def list(self, limit: int = 50, offset: int = 0) -> Sequence[Merchant]:
        with session_scope(self._factory) as s:
            return s.execute(select(Merchant).limit(limit).offset(offset)).scalars().all()


class ProductRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def save(self, product: Product) -> Product:
        with session_scope(self._factory) as s:
            s.add(product)
            s.flush()
            s.refresh(product)
            return product

    def get(self, product_id: ProductId) -> Product | None:
        with session_scope(self._factory) as s:
            return s.get(Product, str(product_id))

    def list_by_merchant(
        self, merchant_id: MerchantId, limit: int = 50, offset: int = 0
    ) -> Sequence[Product]:
        with session_scope(self._factory) as s:
            return (
                s.execute(
                    select(Product)
                    .where(Product.merchant_id == str(merchant_id))
                    .limit(limit)
                    .offset(offset)
                )
                .scalars()
                .all()
            )

    def list(
        self,
        category: str | None = None,
        brand: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Product]:
        with session_scope(self._factory) as s:
            stmt = select(Product)
            if category:
                stmt = stmt.where(Product.category == category)
            if brand:
                stmt = stmt.where(Product.brand == brand)
            return s.execute(stmt.limit(limit).offset(offset)).scalars().all()


class IntentRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def save(self, intent: IntentContract) -> IntentContract:
        with session_scope(self._factory) as s:
            s.merge(intent)
            s.flush()
            return intent

    def get_for_update(self, intent_id: IntentId, session: Session) -> IntentContract | None:
        return session.get(IntentContract, str(intent_id), with_for_update=True)

    def get(self, intent_id: IntentId) -> IntentContract | None:
        with session_scope(self._factory) as s:
            return s.get(IntentContract, str(intent_id))


class CheckoutRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def save(self, checkout: Checkout) -> Checkout:
        with session_scope(self._factory) as s:
            s.add(checkout)
            s.flush()
            s.refresh(checkout)
            return checkout

    def get(self, checkout_id: CheckoutId) -> Checkout | None:
        with session_scope(self._factory) as s:
            return s.get(Checkout, str(checkout_id))


class DecisionRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def save(self, decision: Decision) -> Decision:
        with session_scope(self._factory) as s:
            s.add(decision)
            s.flush()
            s.refresh(decision)
            return decision

    def get(self, decision_id: DecisionId) -> Decision | None:
        with session_scope(self._factory) as s:
            return s.get(Decision, str(decision_id))


class AuthorizationSpendRepository:
    """Atomic reservation/commit/release against durable authorization capacity."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def ensure(self, intent_id: IntentId, authorized_minor: int) -> AuthorizationSpend:
        with session_scope(self._factory) as s:
            existing = s.get(AuthorizationSpend, str(intent_id), with_for_update=True)
            if existing is None:
                row = AuthorizationSpend(
                    intent_id=str(intent_id),
                    authorized_minor=authorized_minor,
                    reserved_minor=0,
                    committed_minor=0,
                    version=1,
                    updated_at=datetime.now(UTC),
                )
                s.add(row)
                s.flush()
                return row
            return existing

    def get_for_update(self, intent_id: IntentId, session: Session) -> AuthorizationSpend | None:
        return session.get(AuthorizationSpend, str(intent_id), with_for_update=True)

    def available_minor(self, intent_id: IntentId) -> int:
        with session_scope(self._factory) as s:
            row = s.get(AuthorizationSpend, str(intent_id))
            if row is None:
                return 0
            return row.authorized_minor - row.reserved_minor - row.committed_minor


class TicketRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def save(self, ticket: ExecutionTicket) -> ExecutionTicket:
        with session_scope(self._factory) as s:
            s.add(ticket)
            s.flush()
            s.refresh(ticket)
            return ticket

    def get(self, ticket_id: ExecutionTicketId) -> ExecutionTicket | None:
        with session_scope(self._factory) as s:
            return s.get(ExecutionTicket, str(ticket_id))


class ExecutionAttemptRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def save(self, attempt: ExecutionAttempt) -> ExecutionAttempt:
        with session_scope(self._factory) as s:
            s.add(attempt)
            s.flush()
            s.refresh(attempt)
            return attempt

    def get(self, attempt_id: ExecutionAttemptId) -> ExecutionAttempt | None:
        with session_scope(self._factory) as s:
            return s.get(ExecutionAttempt, str(attempt_id))

    def find_by_idempotency(self, idempotency_key: str) -> ExecutionAttempt | None:
        with session_scope(self._factory) as s:
            return (
                s.execute(
                    select(ExecutionAttempt).where(
                        ExecutionAttempt.idempotency_key == idempotency_key
                    )
                )
                .scalars()
                .first()
            )


class AuditRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def append(self, event: AuditEvent) -> AuditEvent:
        # Append-only at the application layer; the DB trigger also blocks mutation.
        with session_scope(self._factory) as s:
            s.add(event)
            s.flush()
            s.refresh(event)
            return event

    def list_recent(self, limit: int = 100) -> Sequence[AuditEvent]:
        with session_scope(self._factory) as s:
            return (
                s.execute(select(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(limit))
                .scalars()
                .all()
            )

    def get(self, event_id: AuditEventId) -> AuditEvent | None:
        with session_scope(self._factory) as s:
            return s.get(AuditEvent, str(event_id))


class Repositories:
    """Convenience bundle wired from a single engine/session factory."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self.factory = factory
        self.merchants = MerchantRepository(factory)
        self.products = ProductRepository(factory)
        self.intents = IntentRepository(factory)
        self.checkouts = CheckoutRepository(factory)
        self.decisions = DecisionRepository(factory)
        self.spend = AuthorizationSpendRepository(factory)
        self.tickets = TicketRepository(factory)
        self.attempts = ExecutionAttemptRepository(factory)
        self.audit = AuditRepository(factory)

    @classmethod
    def from_url(cls, database_url: str) -> "Repositories":
        from razormesh_api.persistence.db import create_db_engine

        engine = create_db_engine(database_url)
        return cls(create_session_factory(engine))

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        with session_scope(self.factory) as s:
            yield s
