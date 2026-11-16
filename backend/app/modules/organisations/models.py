import enum
import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, new_uuid


class OrganisationStatus(enum.StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class Role(enum.StrEnum):
    """Organisation-level staff roles.

    Phase 0 keeps roles as a fixed set mapped to permissions in code
    (see app.modules.auth.permissions). Phase 1 replaces this with the roles,
    permissions and user_roles tables and property-level grants (ADR-0004).
    """

    OWNER = "owner"
    MANAGER = "manager"
    RECEPTIONIST = "receptionist"
    HOUSEKEEPING = "housekeeping"
    MAINTENANCE = "maintenance"
    ACCOUNTANT = "accountant"


class MembershipStatus(enum.StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


def _values(e: type[enum.StrEnum]) -> str:
    return ", ".join(f"'{m.value}'" for m in e)


class Organisation(TimestampMixin, Base):
    """A tenant: one hospitality business, which may run several properties."""

    __tablename__ = "organisations"
    __table_args__ = (
        CheckConstraint(f"status IN ({_values(OrganisationStatus)})", name="status"),
        CheckConstraint("default_currency ~ '^[A-Z]{3}$'", name="default_currency_iso4217"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="slug_format"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(63), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OrganisationStatus.ACTIVE.value
    )
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    default_timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(2))


class OrganisationUser(TimestampMixin, Base):
    """Membership of a user in an organisation, with their role there."""

    __tablename__ = "organisation_users"
    __table_args__ = (
        UniqueConstraint("organisation_id", "user_id"),
        CheckConstraint(f"role IN ({_values(Role)})", name="role"),
        CheckConstraint(f"status IN ({_values(MembershipStatus)})", name="status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MembershipStatus.ACTIVE.value
    )
