from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.csrf import CSRFMiddleware
from app.core.db import dispose_engine, get_sessionmaker
from app.core.redis import close_redis, get_redis
from app.modules.access.router import router as access_router
from app.modules.auth.router import router as auth_router
from app.modules.organisations.router import router as organisation_router
from app.modules.properties.router import router as properties_router
from app.modules.rooms.router import router as rooms_router

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_engine()
    await close_redis()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="LodgeOS API",
        version="0.1.0",
        lifespan=lifespan,
        # Interactive docs are disabled in production; the OpenAPI schema is published
        # with each release instead.
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
        openapi_url=None if settings.environment == "production" else "/openapi.json",
    )

    app.add_middleware(CSRFMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", settings.csrf_header_name],
    )

    @app.middleware("http")
    async def security_headers(request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    async def ready(response: Response) -> dict[str, str]:
        checks = {"database": "ok", "redis": "ok"}
        try:
            async with get_sessionmaker()() as session:
                await session.execute(text("SELECT 1"))
        except (SQLAlchemyError, OSError) as exc:
            log.error("health.database_unavailable", error=str(exc))
            checks["database"] = "unavailable"
        try:
            await get_redis().ping()
        except (RedisError, OSError) as exc:
            log.error("health.redis_unavailable", error=str(exc))
            checks["redis"] = "unavailable"
        if any(v != "ok" for v in checks.values()):
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return checks

    app.include_router(auth_router)
    app.include_router(organisation_router)
    app.include_router(properties_router)
    app.include_router(rooms_router)
    app.include_router(access_router)
    return app


app = create_app()
