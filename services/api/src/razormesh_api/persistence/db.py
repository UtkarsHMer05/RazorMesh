"""SQLAlchemy engine/session factory for the durable authority store (PostgreSQL)."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def create_db_engine(database_url: str) -> Engine:
    if not database_url.startswith("postgresql"):
        host_part = database_url.split("@")[-1]
        msg = f"Refusing non-PostgreSQL database URL (durable authority policy): {host_part}"
        raise ValueError(msg)
    return create_engine(database_url, pool_pre_ping=True, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
