from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID

import asyncpg
import orjson
from redis import Redis
from rq import Connection, Queue, Worker, get_current_job

from config import settings
from gpx import build_gpx
from queries import ROUTE_GEOJSON_SQL, SEARCH_SQL

GPX_RESULT_TTL = 60 * 60 * 24  # 24 hours
QUEUE_NAME = "gpx"


def _parse_filters(filters: Iterable[str] | None) -> list[str] | None:
    if not filters:
        return None
    filtered = [f for f in filters if f]
    return filtered or None


async def _fetch_route_and_pois(
    route_id: UUID,
    radius_m: float,
    filters: Iterable[str] | None,
    conn: asyncpg.Connection,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    route_row = await conn.fetchrow(ROUTE_GEOJSON_SQL, route_id)
    if route_row is None:
        raise ValueError("Route not found")

    route_geojson = json.loads(route_row["geojson"])
    route = {
        "route_id": str(route_row["route_id"]),
        "name": route_row["name"],
        "geometry": route_geojson,
        "coordinates": route_geojson.get("coordinates", []),
    }

    categories = _parse_filters(filters)
    pois_rows = await conn.fetch(
        SEARCH_SQL,
        route_id,
        radius_m,
        categories,
    )

    pois: list[dict[str, Any]] = []
    for row in pois_rows:
        pois.append(
            {
                "id": str(row["id"]),
                "category": row["category"],
                "props": row["props"],
                "distance_m": float(row["dist_m"]) if row["dist_m"] is not None else None,
                "geometry": json.loads(row["geojson"]),
            }
        )

    return route, pois


def process_gpx_job(payload: dict[str, Any]) -> str:
    job = get_current_job()
    job_id = job.id if job else None
    if job_id is None:
        raise RuntimeError("RQ job context missing")

    route_id = UUID(payload["route_id"])
    radius_m = float(payload.get("radius_m", 500))
    filters = payload.get("filters") or None
    poi_ids = set(payload.get("poi_ids") or [])

    async def runner() -> tuple[dict[str, Any], list[dict[str, Any]]]:
        conn = await asyncpg.connect(
            host=settings.postgres_host,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
        )
        try:
            route, pois = await _fetch_route_and_pois(route_id, radius_m, filters, conn)
        finally:
            await conn.close()
        return route, pois

    route, pois = asyncio.run(runner())

    if poi_ids:
        pois = [poi for poi in pois if poi["id"] in poi_ids]

    output_dir = Path(settings.gpx_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{job_id}.gpx"

    build_gpx(route, pois, output_path)

    result_url = f"/files/{output_path.name}"
    redis_conn = Redis.from_url(settings.redis_url)
    redis_conn.setex(f"gpx:{job_id}", GPX_RESULT_TTL, orjson.dumps({"url": result_url}))
    redis_conn.close()

    return result_url


def run_worker() -> None:
    redis_conn = Redis.from_url(settings.redis_url)
    with Connection(redis_conn):
        worker = Worker([QUEUE_NAME])
        worker.work(with_scheduler=True)


if __name__ == "__main__":
    run_worker()
