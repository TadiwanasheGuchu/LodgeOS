"""Operator CLI, run as a subprocess against the test database."""

import asyncio
import os
import subprocess
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import PASSWORD, login


async def _cli(*args: str, password: str | None = PASSWORD) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if password is not None:
        env["LODGEOS_BOOTSTRAP_PASSWORD"] = password
    return await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-m", "app.cli", *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


async def test_bootstrap_then_add_member_then_sign_in(client, owner_engine: AsyncEngine) -> None:
    r = await _cli(
        "bootstrap-organisation", "--name", "Sossus Camp", "--slug", "sossus-camp",
        "--currency", "NAD", "--timezone", "Africa/Windhoek", "--country", "NA",
        "--owner-email", "owner@sossus-camp.example.com", "--owner-name", "Camp Owner",
    )  # fmt: skip
    assert r.returncode == 0, r.stderr
    r = await _cli(
        "add-member", "--org", "sossus-camp", "--email", "desk@sossus-camp.example.com",
        "--name", "Front Desk", "--role", "receptionist",
    )  # fmt: skip
    assert r.returncode == 0, r.stderr

    me = (await login(client, "desk@sossus-camp.example.com")).json()
    assert me["active_organisation"]["name"] == "Sossus Camp"
    assert me["active_organisation"]["role"] == "receptionist"

    # Adding the same person twice is refused, not duplicated.
    r = await _cli(
        "add-member", "--org", "sossus-camp", "--email", "desk@sossus-camp.example.com",
        "--name", "Front Desk", "--role", "manager",
    )  # fmt: skip
    assert r.returncode != 0
    assert "already a member" in r.stderr
    async with owner_engine.connect() as conn:
        assert (await conn.execute(text("SELECT count(*) FROM organisation_users"))).scalar() == 2


async def test_cli_rejects_invalid_input() -> None:
    base = ["--name", "X", "--slug", "x", "--owner-name", "X"]
    bad = [
        [
            *base,
            "--currency",
            "nad",
            "--timezone",
            "Africa/Windhoek",
            "--owner-email",
            "a@b.example.com",
        ],
        [*base, "--currency", "NAD", "--timezone", "Mars/Base", "--owner-email", "a@b.example.com"],
        [
            *base,
            "--currency",
            "NAD",
            "--timezone",
            "Africa/Windhoek",
            "--owner-email",
            "a@lodge.test",
        ],
    ]
    for args in bad:
        r = await _cli("bootstrap-organisation", *args)
        assert r.returncode == 2, args
    r = await _cli(
        "bootstrap-organisation", *base, "--currency", "NAD", "--timezone", "Africa/Windhoek",
        "--owner-email", "a@b.example.com", password="short",
    )  # fmt: skip
    assert r.returncode == 2
