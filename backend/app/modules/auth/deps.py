"""Request dependencies that establish who is calling and which tenant they act for."""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db, set_tenant_context
from app.modules.auth.models import User, UserSession
from app.modules.auth.permissions import Permission, permissions_for
from app.modules.auth.service import resolve_session
from app.modules.organisations.models import (
    MembershipStatus,
    Organisation,
    OrganisationStatus,
    OrganisationUser,
)

DB = Annotated[AsyncSession, Depends(get_db)]


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: UserSession
    organisation_id: uuid.UUID | None
    role: str | None
    permissions: frozenset[Permission]

    def require_organisation(self) -> uuid.UUID:
        if self.organisation_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Select an organisation before continuing.",
            )
        return self.organisation_id


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def get_auth(request: Request, db: DB) -> AuthContext:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    resolved = await resolve_session(db, token) if token else None
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in.")
    session, user = resolved

    org_id = session.active_organisation_id
    await set_tenant_context(db, user_id=user.id, organisation_id=org_id)

    role: str | None = None
    if org_id is not None:
        # Re-check membership on every request so that disabling a member or suspending
        # an organisation takes effect immediately, not at the next sign-in.
        role = await db.scalar(
            select(OrganisationUser.role)
            .join(Organisation, Organisation.id == OrganisationUser.organisation_id)
            .where(
                OrganisationUser.organisation_id == org_id,
                OrganisationUser.user_id == user.id,
                OrganisationUser.status == MembershipStatus.ACTIVE.value,
                Organisation.status == OrganisationStatus.ACTIVE.value,
            )
        )
        if role is None:
            session.active_organisation_id = None
            org_id = None
            await set_tenant_context(db, user_id=user.id, organisation_id=None)

    return AuthContext(
        user=user,
        session=session,
        organisation_id=org_id,
        role=role,
        permissions=permissions_for(role) if role else frozenset(),
    )


Auth = Annotated[AuthContext, Depends(get_auth)]


def require_permission(permission: Permission) -> Callable[[AuthContext], Awaitable[AuthContext]]:
    async def dependency(auth: Auth) -> AuthContext:
        auth.require_organisation()
        if permission not in auth.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to do this.",
            )
        return auth

    return dependency
