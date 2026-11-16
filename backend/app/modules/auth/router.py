import uuid

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import set_tenant_context
from app.core.security import new_token
from app.modules.audit import service as audit
from app.modules.auth import service
from app.modules.auth.deps import DB, Auth, client_ip
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    ActiveOrganisationOut,
    LoginRequest,
    MembershipOut,
    MeResponse,
    SwitchOrganisationRequest,
    UserOut,
)
from app.modules.organisations.models import Organisation

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _set_csrf_cookie(response: Response) -> str:
    settings = get_settings()
    token = new_token()
    response.set_cookie(
        settings.csrf_cookie_name,
        token,
        httponly=False,  # the browser client must read it to echo it in a header
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
        path="/",
    )
    return token


@router.get("/csrf", status_code=status.HTTP_204_NO_CONTENT)
async def issue_csrf(response: Response) -> None:
    """Issue a CSRF cookie. Call before the first state-changing request."""
    _set_csrf_cookie(response)


@router.post("/login", response_model=MeResponse)
async def login(body: LoginRequest, request: Request, response: Response, db: DB) -> MeResponse:
    settings = get_settings()
    try:
        token, user, session = await service.login(
            db,
            email=body.email,
            password=body.password,
            ip=client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except service.LoginThrottled:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many sign-in attempts. Please wait a few minutes and try again.",
        ) from None
    except service.InvalidCredentials:
        # Commit the audit record of the failure, then refuse. The message does not say
        # whether the email exists.
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Email or password is incorrect."
        ) from None

    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
        path="/",
        max_age=settings.session_absolute_timeout_hours * 3600,
    )
    _set_csrf_cookie(response)  # rotate on sign-in
    return await _me(db, user, session.active_organisation_id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(auth: Auth, request: Request, response: Response, db: DB) -> None:
    settings = get_settings()
    await service.revoke_session(db, auth.session.id)
    await audit.record(
        db,
        action="auth.logout",
        organisation_id=auth.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="user_session",
        entity_id=auth.session.id,
        ip_address=client_ip(request),
    )
    response.delete_cookie(settings.session_cookie_name, path="/", domain=settings.cookie_domain)


@router.get("/me", response_model=MeResponse)
async def me(auth: Auth, db: DB) -> MeResponse:
    return await _me(db, auth.user, auth.organisation_id)


@router.post("/active-organisation", response_model=MeResponse)
async def switch_organisation(
    body: SwitchOrganisationRequest, auth: Auth, request: Request, db: DB
) -> MeResponse:
    memberships = await service.list_memberships(db, auth.user.id)
    match = next((m for m in memberships if m.organisation_id == body.organisation_id), None)
    if match is None:
        # Same response whether the organisation does not exist or the user is not a
        # member, so IDs of other tenants cannot be probed.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found.")

    auth.session.active_organisation_id = match.organisation_id
    await set_tenant_context(db, user_id=auth.user.id, organisation_id=match.organisation_id)
    await audit.record(
        db,
        action="auth.organisation_switched",
        organisation_id=match.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="user_session",
        entity_id=auth.session.id,
        ip_address=client_ip(request),
    )
    return await _me(db, auth.user, match.organisation_id)


async def _me(db: DB, user: User, org_id: uuid.UUID | None) -> MeResponse:
    memberships = await service.list_memberships(db, user.id)
    active = None
    if org_id is not None:
        current = next((m for m in memberships if m.organisation_id == org_id), None)
        if current is not None:
            org = await db.scalar(select(Organisation).where(Organisation.id == org_id))
            assert org is not None
            active = ActiveOrganisationOut(
                id=org.id,
                name=org.name,
                slug=org.slug,
                role=current.role,
                role_label=current.grants.label,
                permissions=sorted(p.value for p in current.grants.everywhere),
                property_permissions={
                    pid: sorted(p.value for p in perms)
                    for pid, perms in current.grants.by_property.items()
                },
            )
    return MeResponse(
        user=UserOut.model_validate(user),
        memberships=[
            MembershipOut(
                organisation_id=m.organisation_id,
                organisation_name=m.organisation_name,
                organisation_slug=m.organisation_slug,
                role=m.role,
                role_label=m.grants.label,
            )
            for m in memberships
        ],
        active_organisation=active,
    )
