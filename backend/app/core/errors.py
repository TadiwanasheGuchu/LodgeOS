from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError


def not_found(what: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found.")


def conflict_from_integrity(exc: IntegrityError, messages: dict[str, str]) -> HTTPException:
    """Turn a unique-constraint violation into a 409 with a message for a person.

    ``messages`` maps constraint names to text. Unknown constraints re-raise, because an
    unexpected integrity error is a bug, not a user mistake.
    """
    text = str(exc.orig)
    for constraint, message in messages.items():
        if constraint in text:
            return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)
    raise exc
