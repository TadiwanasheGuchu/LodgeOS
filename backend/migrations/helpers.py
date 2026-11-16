"""Shared migration helpers."""

from alembic import op


def enable_tenant_rls(table: str, *, grants: str = "SELECT, INSERT, UPDATE") -> None:
    """Standard isolation for a table with an ``organisation_id`` column.

    Grants the runtime role the given privileges (never DELETE by default) and adds one
    policy that limits every command to rows of the current tenant. Use this for every
    tenant-owned table unless it needs a documented custom policy.
    """
    op.execute(f"GRANT {grants} ON {table} TO lodgeos_app")
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {table}_tenant_isolation ON {table} TO lodgeos_app
        USING (organisation_id = app_current_org_id())
        WITH CHECK (organisation_id = app_current_org_id())
        """
    )
