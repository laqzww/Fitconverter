from __future__ import annotations

import asyncio
from typing import Any, Optional

import orjson
from redis.asyncio import Redis

from config import settings

redis_client: Redis | None = None


async def init_redis() -> None:
    global redis_client
    if redis_client is None:
        redis_client = Redis.from_url(settings.redis_url, decode_responses=False)


async def close_redis() -> None:
    global redis_client
    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None


def _ensure_client() -> Redis:
    if redis_client is None:
        raise RuntimeError("Redis client not initialised")
    return redis_client


async def get_json(key: str) -> Optional[Any]:
    client = _ensure_client()
    data = await client.get(key)
    if data is None:
        return None
    return orjson.loads(data)


async def set_json(key: str, value: Any, ttl: int) -> None:
    client = _ensure_client()
    await client.set(key, orjson.dumps(value), ex=ttl)


async def get_bytes(key: str) -> Optional[bytes]:
    client = _ensure_client()
    return await client.get(key)


async def set_bytes(key: str, value: bytes, ttl: int) -> None:
    client = _ensure_client()
    await client.set(key, value, ex=ttl)


async def ping() -> bool:
    client = _ensure_client()
    try:
        await client.ping()
        return True
    except Exception:
        return False


async def main() -> None:
    await init_redis()
    try:
        await set_json("hello", {"value": 1}, 1)
        print(await get_json("hello"))
    finally:
        await close_redis()


if __name__ == "__main__":
    asyncio.run(main())
