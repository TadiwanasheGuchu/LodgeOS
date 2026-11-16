import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.config import get_settings
from app.core.db import set_tenant_context
from app.core.security import (
    hash_password,
    hash_token,
    new_token,
    password_needs_rehash,
    verify_password,
)
from app.modules.access.service import Grants, load_grants
from app.modules.audit import service as audit
from app.modules.auth.models import User, UserSession
from app.modules.organisations.models import (
    MembershipStatus,
    Organisation,
    OrganisationStatus,
    OrganisationUser,
)


class LoginThrottled(Exception):
    pass


class InvalidCredentials(Exception):
    pass


@dataclass(frozen=True)
class Membership:
    organisation_id: uuid.UUID
    organisation_name: str
    organisation_slug: str
    membership_id: uuid.UUID
    grants: Grants

    @property
    def role(self) -> str:
        return self.grants.primary_role_key or ""


def utcnow() -> datetime:
    return datetime.now(UTC)


async def list_memberships(db: AsyncSession, user_id: uuid.UUID) -> list[Membership]:
    """Active memberships in active organisations. Requires app.current_user_id to be set."""
    rows = await db.execute(
        select(Organisation.id, Organisation.name, Organisation.slug, OrganisationUser.id)
        .join(OrganisationUser, OrganisationUser.organisation_id == Organisation.id)
        .where(
            OrganisationUser.user_id == user_id,
            OrganisationUser.status == MembershipStatus.ACTIVE.value,
            Organisation.status == OrganisationStatus.ACTIVE.value,
        )
        .order_by(Organisation.name)
    )
    return [
        Membership(org_id, name, slug, membership_id, await load_grants(db, membership_id))
        for org_id, name, slug, membership_id in rows.all()
    ]


async def login(
    db: AsyncSession, *, email: str, password: str, ip: str | None, user_agent: str | None
) -> tuple[str, User, UserSession]:
    """Verify credentials and open a session. Returns the raw session token for the cookie."""
    settings = get_settings()
    email_key = email.strip().lower()

    allowed_ip = await rate_limit.hit(
        f"login:ip:{ip or 'unknown'}",
        limit=settings.login_max_attempts * 5,
        window_seconds=settings.login_window_seconds,
    )
    allowed_email = await rate_limit.hit(
        f"login:email:{email_key}",
        limit=settings.login_max_attempts,
        window_seconds=settings.login_window_seconds,
    )
    if not (allowed_ip and allowed_email):
        raise LoginThrottled

    user = await db.scalar(select(User).where(func.lower(User.email) == email_key))
    password_ok = verify_password(user.password_hash if user else None, password)

    if user is None or not password_ok or not user.is_active:
        await audit.record(
            db,
            action="auth.login_failed",
            organisation_id=None,
            actor_user_id=user.id if user else None,
            data={"reason": "inactive" if user and password_ok else "invalid_credentials"},
            ip_address=ip,
        )
        raise InvalidCredentials

    assert user.password_hash is not None
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = utcnow()
    await rate_limit.reset(f"login:email:{email_key}")

    await set_tenant_context(db, user_id=user.id, organisation_id=None)
    memberships = await list_memberships(db, user.id)
    # With exactly one organisation, start there. Otherwise the user picks one.
    active_org = memberships[0].organisation_id if len(memberships) == 1 else None

    token = new_token()
    now = utcnow()
    session = UserSession(
        token_hash=hash_token(token),
        user_id=user.id,
        active_organisation_id=active_org,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(hours=settings.session_absolute_timeout_hours),
        ip_address=ip,
        user_agent=(user_agent or "")[:512] or None,
    )
    db.add(session)
    await db.flush()

    await set_tenant_context(db, user_id=user.id, organisation_id=active_org)
    await audit.record(
        db,
        action="auth.login",
        organisation_id=active_org,
        actor_user_id=user.id,
        entity_type="user_session",
        entity_id=session.id,
        ip_address=ip,
    )
    return token, user, session


async def resolve_session(db: AsyncSession, token: str) -> tuple[UserSession, User] | None:
    """Return the live session and user for a cookie token, or None."""
    settings = get_settings()
    now = utcnow()
    row = (
        await db.execute(
            select(UserSession, User)
            .join(User, User.id == UserSession.user_id)
            .where(
                UserSession.token_hash == hash_token(token),
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
                UserSession.last_seen_at
                > now - timedelta(minutes=settings.session_idle_timeout_minutes),
                User.is_active.is_(True),
            )
        )
    ).first()
    if row is None:
        return None
    session, user = row
    # Avoid a write on every request; one-minute resolution is enough for idle timeout.
    if now - session.last_seen_at > timedelta(minutes=1):
        session.last_seen_at = now
    return session, user


async def revoke_session(db: AsyncSession, session_id: uuid.UUID) -> None:
    await db.execute(
        update(UserSession)
        .where(UserSession.id == session_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
