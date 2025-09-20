from __future__ import annotations

import asyncio
from typing import Any, Iterable, Optional

import asyncpg

from config import settings


class Database:
    def __init__(self) -> None:
        self._pool: Optional[asyncpg.Pool] = None

    async def init_pool(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=settings.postgres_host,
                database=settings.postgres_db,
                user=settings.postgres_user,
                password=settings.postgres_password,
                min_size=1,
                max_size=10,
            )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    def _ensure_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database pool is not initialised")
        return self._pool

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> Optional[asyncpg.Record]:
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def execute(self, query: str, *args: Any) -> str:
        pool = self._ensure_pool()
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)


# Singleton database instance used by the FastAPI app
_database = Database()


async def init_db() -> Database:
    await _database.init_pool()
    return _database


async def close_db() -> None:
    await _database.close()


def get_db() -> Database:
    return _database


async def main() -> None:
    await init_db()
    try:
        version = await _database.fetchval("SELECT version()")
        print(version)
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
