"""CSRF protection using the double-submit cookie pattern.

The API sets a random, non-HttpOnly ``lodgeos_csrf`` cookie. Browser clients copy it into
the ``X-CSRF-Token`` header on every state-changing request. A cross-site page cannot read
the cookie, so it cannot produce a matching header. Session cookies are also SameSite=Lax,
which is a second layer.

Paths in ``EXEMPT_PREFIXES`` (provider webhooks) authenticate with signatures instead.
"""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import get_settings
from app.core.security import constant_time_equals

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
EXEMPT_PREFIXES: tuple[str, ...] = ("/api/v1/webhooks/",)


class CSRFMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in SAFE_METHODS:
            await self.app(scope, receive, send)
            return
        path: str = scope["path"]
        if not path.startswith("/api/") or path.startswith(EXEMPT_PREFIXES):
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        header_token = headers.get(settings.csrf_header_name.lower(), "")
        cookie_token = _read_cookie(headers.get("cookie", ""), settings.csrf_cookie_name)

        if (
            not header_token
            or not cookie_token
            or not constant_time_equals(header_token, cookie_token)
        ):
            response = JSONResponse({"detail": "CSRF token missing or invalid."}, status_code=403)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


def _read_cookie(cookie_header: str, name: str) -> str:
    for part in cookie_header.split(";"):
        key, _, value = part.strip().partition("=")
        if key == name:
            return value
    return ""
