"""Operator commands. These connect as lodgeos_owner, so they bypass Row-Level Security.
Run them only from a trusted shell, never from the API.

    uv run python -m app.cli bootstrap-organisation \\
        --name "Kalahari Rest Guesthouse" --slug kalahari-rest \\
        --currency NAD --timezone Africa/Windhoek --country NA \\
        --owner-email owner@example.com --owner-name "Owner Name"

    uv run python -m app.cli add-member --org kalahari-rest \\
        --email frontdesk@example.com --name "Front Desk" --role receptionist

Passwords for new users are read from LODGEOS_BOOTSTRAP_PASSWORD or prompted for.
These commands exist until staff invitations are built.
"""

import argparse
import asyncio
import getpass
import os
import re
import sys

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, hash_password
from app.modules.audit.models import AuditLog
from app.modules.auth.models import User
from app.modules.organisations.models import Organisation, OrganisationUser, Role
from app.modules.organisations.schemas import validate_timezone


async def bootstrap_organisation(args: argparse.Namespace, password: str) -> None:
    engine = create_async_engine(get_settings().migration_database_url.get_secret_value())
    try:
        async with async_sessionmaker(engine)() as db, db.begin():
            email = args.owner_email.strip().lower()
            user = await db.scalar(select(User).where(func.lower(User.email) == email))
            if user is None:
                user = User(
                    email=email, full_name=args.owner_name, password_hash=hash_password(password)
                )
                db.add(user)
                await db.flush()
                print(f"Created user {email}")
            else:
                print(f"Using existing user {email} (password unchanged)")

            org = Organisation(
                name=args.name,
                slug=args.slug,
                default_currency=args.currency,
                default_timezone=args.timezone,
                country_code=args.country,
            )
            db.add(org)
            await db.flush()
            db.add(OrganisationUser(organisation_id=org.id, user_id=user.id, role=Role.OWNER.value))
            db.add(
                AuditLog(
                    organisation_id=org.id,
                    actor_user_id=None,
                    action="organisation.bootstrapped",
                    entity_type="organisation",
                    entity_id=org.id,
                    data={"owner_user_id": str(user.id), "via": "cli"},
                )
            )
            print(f"Created organisation {org.name} ({org.slug}) id={org.id}")
    finally:
        await engine.dispose()


async def add_member(args: argparse.Namespace, password: str | None) -> None:
    engine = create_async_engine(get_settings().migration_database_url.get_secret_value())
    try:
        async with async_sessionmaker(engine)() as db, db.begin():
            org = await db.scalar(select(Organisation).where(Organisation.slug == args.org))
            if org is None:
                raise SystemExit(f"No organisation with slug {args.org!r}")
            email = args.email.strip().lower()
            user = await db.scalar(select(User).where(func.lower(User.email) == email))
            if user is None:
                if password is None:
                    raise SystemExit("A password is required for a new user")
                user = User(email=email, full_name=args.name, password_hash=hash_password(password))
                db.add(user)
                await db.flush()
                print(f"Created user {email}")
            existing = await db.scalar(
                select(OrganisationUser).where(
                    OrganisationUser.organisation_id == org.id,
                    OrganisationUser.user_id == user.id,
                )
            )
            if existing is not None:
                raise SystemExit(f"{email} is already a member of {org.slug} ({existing.role})")
            db.add(OrganisationUser(organisation_id=org.id, user_id=user.id, role=args.role))
            db.add(
                AuditLog(
                    organisation_id=org.id,
                    actor_user_id=None,
                    action="member.added",
                    entity_type="user",
                    entity_id=user.id,
                    data={"role": args.role, "via": "cli"},
                )
            )
            print(f"Added {email} to {org.slug} as {args.role}")
    finally:
        await engine.dispose()


def _read_password(parser: argparse.ArgumentParser, prompt: str) -> str:
    password = os.environ.get("LODGEOS_BOOTSTRAP_PASSWORD") or getpass.getpass(prompt)
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        parser.error(f"Password must be {MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} characters")
    return password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lodgeos")
    sub = parser.add_subparsers(dest="command", required=True)

    boot = sub.add_parser("bootstrap-organisation", help="Create an organisation and its owner")
    boot.add_argument("--name", required=True)
    boot.add_argument("--slug", required=True)
    boot.add_argument("--currency", required=True, help="ISO 4217 code, e.g. NAD")
    boot.add_argument("--timezone", required=True, help="IANA name, e.g. Africa/Windhoek")
    boot.add_argument("--country", help="ISO 3166-1 alpha-2, e.g. NA")
    boot.add_argument("--owner-email", required=True)
    boot.add_argument("--owner-name", required=True)

    member = sub.add_parser("add-member", help="Add a user to an organisation with a role")
    member.add_argument("--org", required=True, help="Organisation slug")
    member.add_argument("--email", required=True)
    member.add_argument("--name", required=True)
    member.add_argument("--role", required=True, choices=[r.value for r in Role])

    args = parser.parse_args(argv)

    if args.command == "add-member":
        try:
            validate_email(args.email, check_deliverability=False)
        except EmailNotValidError as exc:
            parser.error(f"--email: {exc}")
        asyncio.run(add_member(args, _read_password(parser, "Password for new user: ")))
        return 0

    try:
        validate_email(args.owner_email, check_deliverability=False)
    except EmailNotValidError as exc:
        parser.error(f"--owner-email: {exc}")
    if not re.fullmatch(r"[A-Z]{3}", args.currency):
        parser.error("--currency must be a 3-letter uppercase ISO 4217 code")
    try:
        validate_timezone(args.timezone)
    except ValueError as exc:
        parser.error(str(exc))

    asyncio.run(bootstrap_organisation(args, _read_password(parser, "Owner password: ")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
