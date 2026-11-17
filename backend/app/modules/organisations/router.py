"""Endpoints for the organisation the caller is currently working in.

None of these take an organisation ID from the client: the organisation always comes
from the server-side session, and RLS limits every query to it as well.
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, tuple_

from app.modules.audit import service as audit
from app.modules.audit.models import AuditLog
from app.modules.auth.deps import DB, AuthContext, client_ip, require_permission
from app.modules.auth.models import User
from app.modules.auth.permissions import Permission
from app.modules.organisations.models import Organisation
from app.modules.organisations.schemas import (
    AuditLogOut,
    AuditLogPage,
    OrganisationOut,
    OrganisationUpdate,
)

router = APIRouter(prefix="/api/v1/organisation", tags=["organisation"])


CanView = Annotated[AuthContext, Depends(require_permission(Permission.ORGANISATION_VIEW))]
CanManage = Annotated[AuthContext, Depends(require_permission(Permission.ORGANISATION_MANAGE))]
CanViewMembers = Annotated[AuthContext, Depends(require_permission(Permission.MEMBERS_VIEW))]
CanViewAudit = Annotated[AuthContext, Depends(require_permission(Permission.AUDIT_VIEW))]


async def _current(db: DB, auth: AuthContext) -> Organisation:
    org = await db.scalar(select(Organisation).where(Organisation.id == auth.organisation_id))
    if org is None:  # pragma: no cover - guarded by require_permission
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found.")
    return org


@router.get("", response_model=OrganisationOut)
async def get_organisation(auth: CanView, db: DB) -> Organisation:
    return await _current(db, auth)


@router.patch("", response_model=OrganisationOut)
async def update_organisation(
    body: OrganisationUpdate, auth: CanManage, request: Request, db: DB
) -> Organisation:
    org = await _current(db, auth)
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None:
        raise HTTPException(status_code=422, detail="Name cannot be empty.")
    before = {k: getattr(org, k) for k in changes}
    for key, value in changes.items():
        setattr(org, key, value)
    await db.flush()
    await audit.record(
        db,
        action="organisation.updated",
        organisation_id=org.id,
        actor_user_id=auth.user.id,
        entity_type="organisation",
        entity_id=org.id,
        data={"before": before, "after": changes},
        ip_address=client_ip(request),
    )
    await db.refresh(org)
    return org


@router.get("/audit-logs", response_model=AuditLogPage)
async def list_audit_logs(
    auth: CanViewAudit,
    db: DB,
    cursor: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AuditLogPage:
    stmt = (
        select(AuditLog, User.full_name)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .where(AuditLog.organisation_id == auth.organisation_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit + 1)
    )
    if cursor is not None:
        # Keyset pagination on (created_at, id): rows written in one transaction share a
        # timestamp, so the id breaks ties and no row is skipped or repeated.
        try:
            ts, _, raw_id = cursor.partition("|")
            after = (datetime.fromisoformat(ts), uuid.UUID(raw_id))
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid cursor.") from None
        stmt = stmt.where(tuple_(AuditLog.created_at, AuditLog.id) < after)
    rows = list((await db.execute(stmt)).all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [log for log, _ in rows]
    return AuditLogPage(
        items=[
            AuditLogOut.model_validate(log).model_copy(update={"actor_name": name})
            for log, name in rows
        ],
        next_cursor=f"{items[-1].created_at.isoformat()}|{items[-1].id}" if has_more else None,
    )
