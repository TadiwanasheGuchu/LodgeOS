"""Test harness.

Tests run against a real PostgreSQL database (``lodgeos_test``) and Redis (db 15), because
the properties that matter most here - Row-Level Security, constraints, transactions -
cannot be tested against mocks or SQLite.

The API under test connects as ``lodgeos_app`` exactly as in production. Fixtures that
create data connect as ``lodgeos_owner``, which bypasses RLS.
"""

import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

# Configure before any app module reads settings.
_PG_HOST = os.environ.get("TEST_PG_HOST", "127.0.0.1")
_OWNER_PW = os.environ.get("LODGEOS_OWNER_PASSWORD", "owner-dev-only")
_APP_PW = os.environ.get("LODGEOS_APP_PASSWORD", "app-dev-only")
TEST_DB = "lodgeos_test"
OWNER_URL = f"postgresql+asyncpg://lodgeos_owner:{_OWNER_PW}@{_PG_HOST}:5432/{TEST_DB}"
APP_URL = f"postgresql+asyncpg://lodgeos_app:{_APP_PW}@{_PG_HOST}:5432/{TEST_DB}"
os.environ["LODGEOS_ENVIRONMENT"] = "test"
os.environ["LODGEOS_DATABASE_URL"] = APP_URL
os.environ["LODGEOS_MIGRATION_DATABASE_URL"] = OWNER_URL
os.environ["LODGEOS_REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ["LODGEOS_COOKIE_SECURE"] = "false"

import asyncpg  # noqa: E402
import httpx  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine  # noqa: E402

from app.core.redis import get_redis  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.access.models import UserRole  # noqa: E402
from app.modules.access.service import seed_system_roles, system_role  # noqa: E402
from app.modules.auth.models import User  # noqa: E402
from app.modules.organisations.models import Organisation, OrganisationUser, Role  # noqa: E402

PASSWORD = "correct horse battery staple"
_TABLES = (
    "refunds, payment_allocations, payments, "
    "credit_note_items, credit_notes, invoice_items, invoices, document_sequences, "
    "housekeeping_tasks, room_blocks, maintenance_tickets, "
    "reservation_status_history, reservation_rooms, reservations, guests, "
    "seasonal_rates, rate_plan_prices, rate_plans, taxes, "
    "user_roles, role_permissions, roles, "
    "rooms, room_types, buildings, properties, "
    "audit_logs, user_sessions, organisation_users, users, organisations"
)


async def _recreate_database() -> None:
    conn = await asyncpg.connect(
        user="lodgeos_owner", password=_OWNER_PW, host=_PG_HOST, database="lodgeos"
    )
    try:
        await conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        await conn.execute(f"CREATE DATABASE {TEST_DB} OWNER lodgeos_owner")
    finally:
        await conn.close()
    conn = await asyncpg.connect(
        user="lodgeos_owner", password=_OWNER_PW, host=_PG_HOST, database=TEST_DB
    )
    try:
        await conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        await conn.execute("GRANT USAGE ON SCHEMA public TO lodgeos_app")
    finally:
        await conn.close()


def _alembic_config() -> Config:
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option(
        "script_location", os.path.join(os.path.dirname(__file__), "..", "migrations")
    )
    cfg.attributes["database_url"] = OWNER_URL
    return cfg


@pytest.fixture(scope="session", autouse=True)
async def database() -> AsyncIterator[None]:
    await _recreate_database()
    cfg = _alembic_config()
    # Upgrade, downgrade and upgrade again so every migration is proven reversible.
    for step in ("upgrade", "downgrade", "upgrade"):
        target = "head" if step == "upgrade" else "base"
        await _run_sync(getattr(command, step), cfg, target)
    yield


async def _run_sync(fn: object, *args: object) -> None:
    import asyncio

    await asyncio.to_thread(fn, *args)  # type: ignore[arg-type]


@pytest.fixture(scope="session")
async def owner_engine(database: None) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(OWNER_URL)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def app_engine(database: None) -> AsyncIterator[AsyncEngine]:
    """Raw connection as lodgeos_app, for testing RLS directly."""
    engine = create_async_engine(APP_URL)
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_state(owner_engine: AsyncEngine) -> AsyncIterator[None]:
    async with owner_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {_TABLES} CASCADE"))
    await get_redis().flushdb()
    yield


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@dataclass
class Tenant:
    org_id: uuid.UUID
    owner_email: str


class Factory:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self._n = 0

    async def user(self, email: str | None = None, *, active: bool = True) -> User:
        self._n += 1
        async with AsyncSession(self.engine, expire_on_commit=False) as db, db.begin():
            user = User(
                email=email or f"user{self._n}-{uuid.uuid4().hex[:6]}@example.com",
                full_name=f"Test User {self._n}",
                password_hash=hash_password(PASSWORD),
                is_active=active,
            )
            db.add(user)
        return user

    async def organisation(self, name: str = "Test Lodge") -> Organisation:
        self._n += 1
        async with AsyncSession(self.engine, expire_on_commit=False) as db, db.begin():
            org = Organisation(
                name=name,
                slug=f"org-{self._n}-{uuid.uuid4().hex[:6]}",
                default_currency="NAD",
                default_timezone="Africa/Windhoek",
                country_code="NA",
            )
            db.add(org)
            await db.flush()
            await seed_system_roles(db, org.id)
        return org

    async def member(
        self,
        org: Organisation,
        user: User,
        role: Role = Role.OWNER,
        status: str = "active",
        property_id: uuid.UUID | None = None,
    ) -> OrganisationUser:
        async with AsyncSession(self.engine, expire_on_commit=False) as db, db.begin():
            m = OrganisationUser(organisation_id=org.id, user_id=user.id, status=status)
            db.add(m)
            await db.flush()
            await self._grant(db, org.id, m.id, role, property_id)
        return m

    async def grant(
        self, membership: OrganisationUser, role: Role, property_id: uuid.UUID | None = None
    ) -> None:
        async with AsyncSession(self.engine, expire_on_commit=False) as db, db.begin():
            await self._grant(db, membership.organisation_id, membership.id, role, property_id)

    @staticmethod
    async def _grant(
        db: AsyncSession,
        org_id: uuid.UUID,
        membership_id: uuid.UUID,
        role: Role,
        property_id: uuid.UUID | None,
    ) -> None:
        role_record = await system_role(db, org_id, role.value)
        db.add(
            UserRole(
                organisation_id=org_id,
                membership_id=membership_id,
                role_id=role_record.id,
                property_id=property_id,
            )
        )

    async def execute(self, sql: str, **params: object) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text(sql), params)


@pytest.fixture
def factory(owner_engine: AsyncEngine) -> Factory:
    return Factory(owner_engine)


async def csrf(client: httpx.AsyncClient) -> dict[str, str]:
    """Fetch a CSRF cookie and return the matching header."""
    if "lodgeos_csrf" not in client.cookies:
        r = await client.get("/api/v1/auth/csrf")
        assert r.status_code == 204
    return {"X-CSRF-Token": client.cookies["lodgeos_csrf"]}


async def login(client: httpx.AsyncClient, email: str, password: str = PASSWORD) -> httpx.Response:
    headers = await csrf(client)
    return await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}, headers=headers
    )
