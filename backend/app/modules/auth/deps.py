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
from app.modules.access.service import Grants, load_grants
from app.modules.auth.models import User, UserSession
from app.modules.auth.permissions import Permission
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
    membership_id: uuid.UUID | None
    grants: Grants

    @property
    def permissions(self) -> frozenset[Permission]:
        """Permissions granted for every property (organisation-wide)."""
        return self.grants.everywhere

    @property
    def role(self) -> str | None:
        return self.grants.primary_role_key

    def require_for_property(self, permission: Permission, property_id: uuid.UUID) -> None:
        """Allow ``permission`` at one property. A property the caller has no access to at
        all is reported as not found, like another tenant's."""
        if not self.grants.can_see_property(property_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")
        if not self.grants.has_for(permission, property_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to do this.",
            )

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

    membership_id: uuid.UUID | None = None
    grants = Grants()
    if org_id is not None:
        # Re-check membership on every request so that disabling a member or suspending
        # an organisation takes effect immediately, not at the next sign-in.
        membership_id = await db.scalar(
            select(OrganisationUser.id)
            .join(Organisation, Organisation.id == OrganisationUser.organisation_id)
            .where(
                OrganisationUser.organisation_id == org_id,
                OrganisationUser.user_id == user.id,
                OrganisationUser.status == MembershipStatus.ACTIVE.value,
                Organisation.status == OrganisationStatus.ACTIVE.value,
            )
        )
        if membership_id is None:
            session.active_organisation_id = None
            org_id = None
            await set_tenant_context(db, user_id=user.id, organisation_id=None)
        else:
            grants = await load_grants(db, membership_id)

    return AuthContext(
        user=user,
        session=session,
        organisation_id=org_id,
        membership_id=membership_id,
        grants=grants,
    )


Auth = Annotated[AuthContext, Depends(get_auth)]


def require_permission(permission: Permission) -> Callable[[AuthContext], Awaitable[AuthContext]]:
    """Permission granted for every property (or for the organisation itself)."""

    async def dependency(auth: Auth) -> AuthContext:
        auth.require_organisation()
        if not auth.grants.has(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to do this.",
            )
        return auth

    return dependency


def require_permission_anywhere(
    permission: Permission,
) -> Callable[[AuthContext], Awaitable[AuthContext]]:
    """Permission held for at least one property. The handler must then limit results or
    check the specific property with ``auth.require_for_property``."""

    async def dependency(auth: Auth) -> AuthContext:
        auth.require_organisation()
        if not auth.grants.has_anywhere(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to do this.",
            )
        return auth

    return dependency
