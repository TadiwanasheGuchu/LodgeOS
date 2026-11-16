"""Shared column helpers."""

import enum


def enum_check(column: str, e: type[enum.StrEnum]) -> str:
    """SQL for a CHECK constraint restricting ``column`` to the enum's values."""
    values = ", ".join(f"'{m.value}'" for m in e)
    return f"{column} IN ({values})"
