"""Async Redis client with connection pooling and health checks."""

import logging
from typing import Optional

import redis.asyncio as aioredis
from redis.asyncio import ConnectionPool, Redis

from backend.core.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[ConnectionPool] = None
_client: Optional[Redis] = None


async def get_redis_pool() -> ConnectionPool:
    """Get or create the Redis connection pool."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            settings.redis_url,
            max_connections=settings.redis_pool_size,
            decode_responses=True,
        )
        logger.info(
            "Redis connection pool created (max_connections=%d)",
            settings.redis_pool_size,
        )
    return _pool


async def get_redis() -> Redis:
    """Get the async Redis client."""
    global _client
    if _client is None:
        pool = await get_redis_pool()
        _client = Redis(connection_pool=pool)
    return _client


async def close_redis() -> None:
    """Close the Redis client and connection pool."""
    global _client, _pool
    if _client is not None:
        await _client.aclose()
        _client = None
    if _pool is not None:
        await _pool.aclose()
        _pool = None
    logger.info("Redis connections closed")


async def redis_health_check() -> dict:
    """Check Redis connectivity. Returns status dict."""
    try:
        client = await get_redis()
        await client.ping()
        return {"status": "ok"}
    except Exception as e:
        logger.error("Redis health check failed: %s", e)
        return {"status": "error", "detail": str(e)}
