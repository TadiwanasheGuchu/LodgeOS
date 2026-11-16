"""Staff invitations.

There is no email provider yet, so creating an invitation returns a one-time link that the
owner or manager shares (for example by WhatsApp). The link expires after 7 days and works
once. The raw token is returned only at creation; the database stores its SHA-256.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError

from app.core import rate_limit
from app.core.db import set_tenant_context
from app.core.errors import not_found
from app.core.security import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    hash_password,
    hash_token,
    new_token,
    verify_password,
)
from app.modules.access.models import Invitation, RoleRecord, UserRole
from app.modules.access.router import _check_can_handle_role
from app.modules.audit import service as audit
from app.modules.auth.deps import DB, AuthContext, client_ip, require_permission
from app.modules.auth.models import User
from app.modules.auth.permissions import Permission
from app.modules.auth.router import build_me, set_session_cookies
from app.modules.auth.schemas import MeResponse
from app.modules.auth.service import open_session
from app.modules.organisations.models import (
    MembershipStatus,
    Organisation,
    OrganisationStatus,
    OrganisationUser,
    Role,
)
from app.modules.properties.models import Property, RecordStatus

router = APIRouter(prefix="/api/v1/invitations", tags=["invitations"])

CanViewMembers = Annotated[AuthContext, Depends(require_permission(Permission.MEMBERS_VIEW))]
CanManageMembers = Annotated[AuthContext, Depends(require_permission(Permission.MEMBERS_MANAGE))]

INVITATION_LIFETIME = timedelta(days=7)
INVALID_LINK = "This invitation link is not valid. Ask for a new one."


def _now() -> datetime:
    return datetime.now(UTC)


class InvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(max_length=320)
    full_name: str = Field(min_length=2, max_length=200)
    role_id: uuid.UUID
    property_id: uuid.UUID | None = None

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        try:
            return validate_email(v, check_deliverability=False).normalized.lower()
        except EmailNotValidError as exc:
            raise ValueError(str(exc)) from None


InvitationState = Literal["pending", "accepted", "revoked", "expired"]


class InvitationOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role_id: uuid.UUID
    role_name: str
    property_id: uuid.UUID | None
    property_name: str | None
    state: InvitationState
    expires_at: datetime
    created_at: datetime


class InvitationCreated(InvitationOut):
    # Shown once. The frontend builds the link from it.
    token: str


class InvitationPreview(BaseModel):
    organisation_name: str
    email: str
    full_name: str
    role_name: str
    property_name: str | None
    has_account: bool


class AcceptInvitation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    token: str = Field(min_length=20, max_length=100)
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


def _state(inv: Invitation) -> InvitationState:
    if inv.accepted_at:
        return "accepted"
    if inv.revoked_at:
        return "revoked"
    if inv.expires_at <= _now():
        return "expired"
    return "pending"


async def _out(db: DB, inv: Invitation) -> InvitationOut:
    role = await db.get(RoleRecord, inv.role_id)
    prop = await db.get(Property, inv.property_id) if inv.property_id else None
    assert role is not None
    return InvitationOut(
        id=inv.id,
        email=inv.email,
        full_name=inv.full_name,
        role_id=inv.role_id,
        role_name=role.name,
        property_id=inv.property_id,
        property_name=prop.name if prop else None,
        state=_state(inv),
        expires_at=inv.expires_at,
        created_at=inv.created_at,
    )


@router.get("", response_model=list[InvitationOut])
async def list_invitations(auth: CanViewMembers, db: DB) -> list[InvitationOut]:
    """Invitations not yet accepted or revoked (including expired ones, so they can be
    re-sent)."""
    rows = await db.scalars(
        select(Invitation)
        .where(Invitation.accepted_at.is_(None), Invitation.revoked_at.is_(None))
        .order_by(Invitation.created_at.desc())
    )
    return [await _out(db, inv) for inv in rows.all()]


@router.post("", response_model=InvitationCreated, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    body: InvitationCreate, auth: CanManageMembers, request: Request, db: DB
) -> InvitationCreated:
    assert auth.organisation_id is not None
    role = await db.get(RoleRecord, body.role_id)
    if role is None:
        raise HTTPException(status_code=422, detail="Choose a role.")
    await _check_can_handle_role(db, auth, role.id)
    if body.property_id is not None:
        if role.key == Role.OWNER:
            raise HTTPException(status_code=422, detail="Owners always have every property.")
        prop = await db.get(Property, body.property_id)
        if prop is None or prop.status != RecordStatus.ACTIVE:
            raise HTTPException(status_code=422, detail="Choose an active property.")

    existing_member = await db.scalar(
        select(OrganisationUser.id)
        .join(User, User.id == OrganisationUser.user_id)
        .where(
            OrganisationUser.organisation_id == auth.organisation_id,
            func.lower(User.email) == body.email,
        )
    )
    if existing_member is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This person is already on the team. Change their roles instead.",
        )

    # A new invitation for the same email replaces any earlier pending one.
    await db.execute(
        update(Invitation)
        .where(
            func.lower(Invitation.email) == body.email,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
        )
        .values(revoked_at=_now())
    )
    token = new_token()
    inv = Invitation(
        organisation_id=auth.organisation_id,
        email=body.email,
        full_name=body.full_name,
        role_id=role.id,
        property_id=body.property_id,
        token_hash=hash_token(token),
        expires_at=_now() + INVITATION_LIFETIME,
        created_by=auth.user.id,
        created_at=_now(),
    )
    db.add(inv)
    await db.flush()
    await audit.record(
        db,
        action="invitation.created",
        organisation_id=auth.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="invitation",
        entity_id=inv.id,
        data={"email": inv.email, "role": role.name},
        ip_address=client_ip(request),
    )
    return InvitationCreated(**(await _out(db, inv)).model_dump(), token=token)


@router.post("/{invitation_id}/revoke", response_model=InvitationOut)
async def revoke_invitation(
    invitation_id: uuid.UUID, auth: CanManageMembers, request: Request, db: DB
) -> InvitationOut:
    inv = await db.get(Invitation, invitation_id)
    if inv is None:
        raise not_found("Invitation")
    if _state(inv) in ("pending", "expired"):
        inv.revoked_at = _now()
        await db.flush()
        await audit.record(
            db,
            action="invitation.revoked",
            organisation_id=inv.organisation_id,
            actor_user_id=auth.user.id,
            entity_type="invitation",
            entity_id=inv.id,
            data={"email": inv.email},
            ip_address=client_ip(request),
        )
    return await _out(db, inv)


# --- public: used by the person who received the link -----------------------------------


async def _resolve(db: DB, token: str, ip: str | None) -> Invitation:
    """Find a usable invitation for a token and enter its organisation's tenant context."""
    if not await rate_limit.hit(f"invite:ip:{ip or 'unknown'}", limit=30, window_seconds=900):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please wait a few minutes and try again.",
        )
    row = (
        await db.execute(
            text("SELECT invitation_id, organisation_id FROM invitation_for_token(:h)"),
            {"h": hash_token(token)},
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=INVALID_LINK)
    await set_tenant_context(db, user_id=None, organisation_id=row.organisation_id)
    inv = await db.get(Invitation, row.invitation_id)
    org = await db.get(Organisation, row.organisation_id)
    if inv is None or org is None or org.status != OrganisationStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=INVALID_LINK)
    state = _state(inv)
    if state != "pending":
        detail = {
            "accepted": "This invitation has already been used. Sign in instead.",
            "revoked": "This invitation was withdrawn. Ask for a new one.",
            "expired": "This invitation has expired. Ask for a new one.",
        }[state]
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=detail)
    return inv


@router.get("/token/{token}", response_model=InvitationPreview)
async def preview_invitation(token: str, request: Request, db: DB) -> InvitationPreview:
    inv = await _resolve(db, token, client_ip(request))
    org = await db.get(Organisation, inv.organisation_id)
    out = await _out(db, inv)
    has_account = await db.scalar(select(User.id).where(func.lower(User.email) == inv.email))
    assert org is not None
    return InvitationPreview(
        organisation_name=org.name,
        email=inv.email,
        full_name=inv.full_name,
        role_name=out.role_name,
        property_name=out.property_name,
        has_account=has_account is not None,
    )


@router.post("/accept", response_model=MeResponse)
async def accept_invitation(
    body: AcceptInvitation, request: Request, response: Response, db: DB
) -> MeResponse:
    ip = client_ip(request)
    inv = await _resolve(db, body.token, ip)
    user = await db.scalar(select(User).where(func.lower(User.email) == inv.email))

    if user is not None:
        # An existing account must prove it is theirs; the link alone is not enough.
        if not user.is_active or not verify_password(user.password_hash, body.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Enter the password of your existing LodgeOS account.",
            )
    else:
        if not MIN_PASSWORD_LENGTH <= len(body.password) <= MAX_PASSWORD_LENGTH:
            raise HTTPException(
                status_code=422,
                detail=f"Choose a password of at least {MIN_PASSWORD_LENGTH} characters.",
            )
        user = User(
            email=inv.email,
            full_name=body.full_name or inv.full_name,
            password_hash=hash_password(body.password),
        )
        db.add(user)
        await db.flush()

    await set_tenant_context(db, user_id=user.id, organisation_id=inv.organisation_id)
    # RLS also shows the user's memberships in other organisations, so filter explicitly.
    membership = await db.scalar(
        select(OrganisationUser).where(
            OrganisationUser.user_id == user.id,
            OrganisationUser.organisation_id == inv.organisation_id,
        )
    )
    if membership is not None and membership.status != MembershipStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Your access to this organisation was turned off. Contact the owner.",
        )
    if membership is None:
        membership = OrganisationUser(organisation_id=inv.organisation_id, user_id=user.id)
        db.add(membership)
        await db.flush()
    db.add(
        UserRole(
            organisation_id=inv.organisation_id,
            membership_id=membership.id,
            role_id=inv.role_id,
            property_id=inv.property_id,
            created_by=inv.created_by,
        )
    )
    inv.accepted_at = _now()
    inv.accepted_by = user.id
    user.last_login_at = _now()
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have this role. Sign in instead.",
        ) from None
    await audit.record(
        db,
        action="invitation.accepted",
        organisation_id=inv.organisation_id,
        actor_user_id=user.id,
        entity_type="invitation",
        entity_id=inv.id,
        data={"email": inv.email},
        ip_address=ip,
    )
    token, _session = await open_session(
        db, user, inv.organisation_id, ip, request.headers.get("user-agent")
    )
    set_session_cookies(response, token)
    return await build_me(db, user, inv.organisation_id)
