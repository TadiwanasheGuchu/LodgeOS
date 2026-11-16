"""Fixed-window rate limiting backed by Redis.

If Redis cannot be reached the limiter fails closed: the protected action is refused
with 503 rather than allowed without throttling.
"""

import structlog
from fastapi import HTTPException, status
from redis.exceptions import RedisError

from app.core.redis import get_redis

log = structlog.get_logger()


async def hit(key: str, *, limit: int, window_seconds: int) -> bool:
    """Record one attempt. Returns False once the key has exceeded ``limit`` in the window."""
    redis = get_redis()
    try:
        pipe = redis.pipeline(transaction=True)
        pipe.incr(key)
        pipe.expire(key, window_seconds, nx=True)
        count, _ = await pipe.execute()
    except RedisError as exc:
        log.error("rate_limit.unavailable", key=key, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again shortly.",
        ) from exc
    return int(count) <= limit


async def reset(key: str) -> None:
    try:
        await get_redis().delete(key)
    except RedisError as exc:
        log.warning("rate_limit.reset_failed", key=key, error=str(exc))
