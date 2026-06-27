from __future__ import annotations

import asyncpg

from app.config import get_settings

_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool:
    """Create the global asyncpg connection pool (idempotent)."""
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=1,
            max_size=max(settings.PROBE_CONCURRENCY, 10),
            command_timeout=30,
        )
    return _pool


def get_pool() -> asyncpg.Pool:
    """Return the active connection pool.

    Raises:
        RuntimeError: if the pool has not been initialised via ``init_pool``.
    """
    if _pool is None:
        raise RuntimeError("Database pool is not initialised. Call init_pool() first.")
    return _pool


async def close_pool() -> None:
    """Close the global connection pool and reset the singleton."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
