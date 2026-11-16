"""Database engine, sessions and tenant context.

Tenant isolation works in two layers:

1. Application code only ever reads the organisation from the authenticated server-side
   session. Organisation IDs supplied by the client are never trusted.
2. Each request runs in one transaction. At the start of that transaction we set the
   transaction-local settings ``app.current_user_id`` and ``app.current_org_id``.
   Row-Level Security policies on every tenant table compare rows against those
   settings, so even a query that forgets a WHERE clause cannot read another tenant.

``set_config(..., is_local => true)`` scopes the values to the current transaction,
which makes them safe with pooled connections.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import datetime

from sqlalchemy import DateTime, MetaData, func, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url.get_secret_value(),
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=10,
        )
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


async def set_tenant_context(
    session: AsyncSession, *, user_id: uuid.UUID | None, organisation_id: uuid.UUID | None
) -> None:
    """Set the RLS context for the current transaction."""
    await session.execute(
        text(
            "SELECT set_config('app.current_user_id', :user_id, true),"
            " set_config('app.current_org_id', :org_id, true)"
        ),
        {
            "user_id": str(user_id) if user_id else "",
            "org_id": str(organisation_id) if organisation_id else "",
        },
    )


async def get_db() -> AsyncIterator[AsyncSession]:
    """One transaction per request. Commits on success, rolls back on any exception."""
    async with get_sessionmaker()() as session, session.begin():
        # Start every request with an empty tenant context.
        await set_tenant_context(session, user_id=None, organisation_id=None)
        yield session
