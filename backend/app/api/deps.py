from __future__ import annotations

import hashlib
from typing import Annotated

import asyncpg
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.infrastructure.db.session import get_pool

_bearer = HTTPBearer(auto_error=True)

_LOOKUP = """
    SELECT agent_id FROM agent_keys
    WHERE key_hash = $1 AND revoked_at IS NULL
    LIMIT 1
"""


async def _get_pool() -> asyncpg.Pool:
    return get_pool()


async def verify_agent_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Security(_bearer)],
    pool: Annotated[asyncpg.Pool, Depends(_get_pool)],
) -> str:
    """Validate Bearer token against agent_keys; return agent_id on success."""
    key_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_LOOKUP, key_hash)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return str(row["agent_id"])
