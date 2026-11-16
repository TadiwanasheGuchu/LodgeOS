"""Roles and permissions stored in the database (supersedes ADR-0004).

- ``permissions`` is a global catalogue that mirrors ``Permission`` in code; a test keeps
  the two in sync.
- ``roles`` belong to an organisation. System roles (owner, manager, ...) are created for
  every organisation and cannot be edited; custom roles can be added later.
- ``user_roles`` grants a role to a membership, either for every property
  (``property_id`` NULL) or for one property.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, new_uuid


class PermissionRecord(Base):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class RoleRecord(TimestampMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("organisation_id", "name"),
        UniqueConstraint("organisation_id", "key"),
        UniqueConstraint("id", "organisation_id", name="uq_roles_id_org"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Stable identifier for system roles ("owner", "manager", ...); NULL for custom roles.
    key: Mapped[str | None] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["role_id", "organisation_id"],
            ["roles.id", "roles.organisation_id"],
            name="fk_role_permissions_role_same_org",
            ondelete="CASCADE",
        ),
    )

    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    permission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="RESTRICT"), primary_key=True
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        # One grant of a role per membership per scope; NULL property means "all".
        Index(
            "uq_user_roles_membership_role_property",
            "membership_id",
            "role_id",
            "property_id",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
        ForeignKeyConstraint(
            ["membership_id", "organisation_id"],
            ["organisation_users.id", "organisation_users.organisation_id"],
            name="fk_user_roles_membership_same_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["role_id", "organisation_id"],
            ["roles.id", "roles.organisation_id"],
            name="fk_user_roles_role_same_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["property_id", "organisation_id"],
            ["properties.id", "properties.organisation_id"],
            name="fk_user_roles_property_same_org",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
