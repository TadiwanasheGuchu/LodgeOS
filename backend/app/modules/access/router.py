"""Staff access: roles, role assignments and member status.

Escalation rule: a caller may grant or remove a role only if they hold every permission
of that role for every property. So a manager cannot make anyone an owner, or demote one.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.errors import not_found
from app.modules.access.models import PermissionRecord, RolePermission, RoleRecord, UserRole
from app.modules.access.schemas import (
    AssignmentCreate,
    AssignmentOut,
    MemberOut,
    MemberStatusUpdate,
    RoleOut,
)
from app.modules.access.service import load_grants
from app.modules.audit import service as audit
from app.modules.auth.deps import DB, AuthContext, client_ip, require_permission
from app.modules.auth.models import User
from app.modules.auth.permissions import Permission
from app.modules.organisations.models import MembershipStatus, OrganisationUser, Role
from app.modules.properties.models import Property, RecordStatus

router = APIRouter(prefix="/api/v1", tags=["staff access"])

CanViewMembers = Annotated[AuthContext, Depends(require_permission(Permission.MEMBERS_VIEW))]
CanManageMembers = Annotated[AuthContext, Depends(require_permission(Permission.MEMBERS_MANAGE))]

FORBIDDEN_ROLE = "You can only give or remove roles whose permissions you hold yourself."


async def _role_permissions(db: DB, role_id: uuid.UUID) -> set[str]:
    return set(
        (
            await db.scalars(
                select(PermissionRecord.code)
                .join(RolePermission, RolePermission.permission_id == PermissionRecord.id)
                .where(RolePermission.role_id == role_id)
            )
        ).all()
    )


async def _check_can_handle_role(db: DB, auth: AuthContext, role_id: uuid.UUID) -> None:
    held = {p.value for p in auth.grants.everywhere}
    if not await _role_permissions(db, role_id) <= held:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=FORBIDDEN_ROLE)


async def _active_owner_count(db: DB, organisation_id: uuid.UUID) -> int:
    """Active members holding the owner role for every property."""
    return int(
        await db.scalar(
            select(func.count(func.distinct(UserRole.membership_id)))
            .join(RoleRecord, RoleRecord.id == UserRole.role_id)
            .join(OrganisationUser, OrganisationUser.id == UserRole.membership_id)
            .where(
                UserRole.organisation_id == organisation_id,
                RoleRecord.key == Role.OWNER,
                UserRole.property_id.is_(None),
                OrganisationUser.status == MembershipStatus.ACTIVE,
            )
        )
        or 0
    )


async def _is_full_owner(db: DB, membership_id: uuid.UUID) -> bool:
    return bool(
        await db.scalar(
            select(func.count())
            .select_from(UserRole)
            .join(RoleRecord, RoleRecord.id == UserRole.role_id)
            .where(
                UserRole.membership_id == membership_id,
                RoleRecord.key == Role.OWNER,
                UserRole.property_id.is_(None),
            )
        )
    )


async def build_members(db: DB, organisation_id: uuid.UUID) -> list[MemberOut]:
    members = (
        await db.execute(
            select(OrganisationUser, User)
            .join(User, User.id == OrganisationUser.user_id)
            .where(OrganisationUser.organisation_id == organisation_id)
            .order_by(User.full_name)
        )
    ).all()
    rows = (
        await db.execute(
            select(UserRole, RoleRecord, Property.name)
            .join(RoleRecord, RoleRecord.id == UserRole.role_id)
            .outerjoin(Property, Property.id == UserRole.property_id)
            .where(UserRole.organisation_id == organisation_id)
            .order_by(RoleRecord.name, Property.name.nulls_first())
        )
    ).all()
    by_member: dict[uuid.UUID, list[AssignmentOut]] = {}
    for ur, role, property_name in rows:
        by_member.setdefault(ur.membership_id, []).append(
            AssignmentOut(
                id=ur.id,
                role_id=role.id,
                role_key=role.key,
                role_name=role.name,
                property_id=ur.property_id,
                property_name=property_name,
            )
        )
    out = []
    for m, u in members:
        grants = await load_grants(db, m.id)
        out.append(
            MemberOut(
                id=m.id,
                user_id=u.id,
                full_name=u.full_name,
                email=u.email,
                role=grants.primary_role_key or "",
                role_label=grants.label,
                status=m.status,
                created_at=m.created_at,
                assignments=by_member.get(m.id, []),
            )
        )
    return out


async def _member(db: DB, organisation_id: uuid.UUID, membership_id: uuid.UUID) -> MemberOut:
    for m in await build_members(db, organisation_id):
        if m.id == membership_id:
            return m
    raise not_found("Team member")


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(auth: CanViewMembers, db: DB) -> list[RoleOut]:
    roles = (await db.scalars(select(RoleRecord).order_by(RoleRecord.name))).all()
    order = {r.value: i for i, r in enumerate(Role)}
    roles = sorted(roles, key=lambda r: (order.get(r.key or "", 99), r.name))
    return [
        RoleOut(
            id=r.id,
            key=r.key,
            name=r.name,
            description=r.description,
            is_system=r.is_system,
            permissions=sorted(await _role_permissions(db, r.id)),
        )
        for r in roles
    ]


@router.get("/organisation/members", response_model=list[MemberOut])
async def list_members(auth: CanViewMembers, db: DB) -> list[MemberOut]:
    assert auth.organisation_id is not None
    return await build_members(db, auth.organisation_id)


@router.post(
    "/members/{membership_id}/roles",
    response_model=MemberOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_assignment(
    membership_id: uuid.UUID,
    body: AssignmentCreate,
    auth: CanManageMembers,
    request: Request,
    db: DB,
) -> MemberOut:
    assert auth.organisation_id is not None
    member = await db.get(OrganisationUser, membership_id)
    if member is None:
        raise not_found("Team member")
    role = await db.get(RoleRecord, body.role_id)
    if role is None:
        raise HTTPException(status_code=422, detail="Choose a role.")
    if body.property_id is not None:
        prop = await db.get(Property, body.property_id)
        if prop is None or prop.status != RecordStatus.ACTIVE:
            raise HTTPException(status_code=422, detail="Choose an active property.")
        if role.key == Role.OWNER:
            raise HTTPException(status_code=422, detail="Owners always have every property.")
    await _check_can_handle_role(db, auth, role.id)

    assignment = UserRole(
        organisation_id=auth.organisation_id,
        membership_id=member.id,
        role_id=role.id,
        property_id=body.property_id,
        created_by=auth.user.id,
    )
    db.add(assignment)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="They already have this role there."
        ) from None
    await audit.record(
        db,
        action="member.role_added",
        organisation_id=auth.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="membership",
        entity_id=member.id,
        data={
            "role": role.name,
            "property_id": str(body.property_id) if body.property_id else None,
        },
        ip_address=client_ip(request),
    )
    return await _member(db, auth.organisation_id, member.id)


@router.delete("/members/{membership_id}/roles/{assignment_id}", response_model=MemberOut)
async def remove_assignment(
    membership_id: uuid.UUID,
    assignment_id: uuid.UUID,
    auth: CanManageMembers,
    request: Request,
    db: DB,
) -> MemberOut:
    assert auth.organisation_id is not None
    assignment = await db.get(UserRole, assignment_id)
    if assignment is None or assignment.membership_id != membership_id:
        raise not_found("Role assignment")
    role = await db.get(RoleRecord, assignment.role_id)
    assert role is not None
    await _check_can_handle_role(db, auth, role.id)

    member = await db.get(OrganisationUser, membership_id)
    assert member is not None
    if (
        role.key == Role.OWNER
        and assignment.property_id is None
        and member.status == MembershipStatus.ACTIVE
        and await _active_owner_count(db, auth.organisation_id) <= 1
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Every organisation needs at least one active owner.",
        )
    await db.delete(assignment)
    await db.flush()
    await audit.record(
        db,
        action="member.role_removed",
        organisation_id=auth.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="membership",
        entity_id=membership_id,
        data={
            "role": role.name,
            "property_id": str(assignment.property_id) if assignment.property_id else None,
        },
        ip_address=client_ip(request),
    )
    return await _member(db, auth.organisation_id, membership_id)


@router.patch("/members/{membership_id}", response_model=MemberOut)
async def update_member_status(
    membership_id: uuid.UUID,
    body: MemberStatusUpdate,
    auth: CanManageMembers,
    request: Request,
    db: DB,
) -> MemberOut:
    assert auth.organisation_id is not None
    member = await db.get(OrganisationUser, membership_id)
    if member is None:
        raise not_found("Team member")
    if member.id == auth.membership_id:
        raise HTTPException(status_code=422, detail="You cannot change your own access.")
    # The caller must outrank everything the member holds (no disabling an owner as manager).
    target = await load_grants(db, member.id)
    for a in target.assignments:
        await _check_can_handle_role(db, auth, a.role_id)
    if (
        body.status == "disabled"
        and member.status == MembershipStatus.ACTIVE
        and await _is_full_owner(db, member.id)
        and await _active_owner_count(db, auth.organisation_id) <= 1
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Every organisation needs at least one active owner.",
        )
    if member.status != body.status:
        before = member.status
        member.status = body.status
        await db.flush()
        await audit.record(
            db,
            action="member.disabled" if body.status == "disabled" else "member.enabled",
            organisation_id=auth.organisation_id,
            actor_user_id=auth.user.id,
            entity_type="membership",
            entity_id=member.id,
            data={"from": before, "to": body.status},
            ip_address=client_ip(request),
        )
    return await _member(db, auth.organisation_id, member.id)
