from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

import asyncpg
import gpxpy
import orjson
from fastapi import (
    Body,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from redis import Redis
from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.job import Job

import cache
from config import settings
from db import Database, get_db, init_db
from queries import GEOJSON_TO_WKT_SQL, ROUTE_GEOJSON_SQL, SEARCH_SQL
from worker import QUEUE_NAME, process_gpx_job

GPX_QUEUE_NAME = QUEUE_NAME
SEARCH_CACHE_TTL = 90
MVT_CACHE_TTL = 600

MVT_SQL = """
WITH bounds AS (
  SELECT ST_TileEnvelope($1, $2, $3) AS geom_3857
)
SELECT ST_AsMVT(tile, 'amenities', 4096, 'geom') FROM (
  SELECT
    a.id,
    a.category,
    a.props,
    ST_AsMVTGeom(ST_Transform(a.geom, 3857), bounds.geom_3857, 4096, 64, true) AS geom
  FROM amenities a, bounds
  WHERE ST_Intersects(ST_Transform(a.geom, 3857), bounds.geom_3857)
    AND ($4::text[] IS NULL OR a.category = ANY($4::text[]))
) AS tile;
"""


class GeoJSONLineString(BaseModel):
    type: str = Field(pattern="^LineString$")
    coordinates: list[list[float]]


class RouteCreateRequest(BaseModel):
    name: str
    geojson: GeoJSONLineString


class RouteCreateResponse(BaseModel):
    route_id: UUID


class AmenityFeature(BaseModel):
    id: UUID
    category: str
    props: dict[str, Any] | None = None
    distance_m: float | None = None
    geometry: dict[str, Any]


class SearchResponse(BaseModel):
    route: dict[str, Any]
    items: list[AmenityFeature]


class ExportRequest(BaseModel):
    route_id: UUID
    radius_m: float = Field(gt=0)
    filters: list[str] | None = None
    poi_ids: list[UUID] | None = None


class ExportJobResponse(BaseModel):
    job_id: str


class ExportStatusResponse(BaseModel):
    status: str
    url: str | None = None


app = FastAPI(title="Route Amenities Demo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()
    await cache.init_redis()
    Path(settings.gpx_output_dir).mkdir(parents=True, exist_ok=True)
    app.state.redis_queue = Queue(GPX_QUEUE_NAME, connection=Redis.from_url(settings.redis_url))


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await cache.close_redis()
    queue: Queue | None = getattr(app.state, "redis_queue", None)
    if queue is not None:
        queue.connection.close()


app.mount(
    "/files",
    StaticFiles(directory=settings.gpx_output_dir),
    name="files",
)


def parse_filters(filters_param: str | None) -> list[str] | None:
    if not filters_param:
        return None
    try:
        parsed = json.loads(filters_param)
        if isinstance(parsed, list):
            return [str(item) for item in parsed if item]
    except json.JSONDecodeError:
        pass
    if "," in filters_param:
        return [part.strip() for part in filters_param.split(",") if part.strip()]
    return [filters_param]


def make_search_cache_key(route_wkb_hex: str, radius_m: float, filters: list[str] | None) -> str:
    payload = {
        "route": route_wkb_hex,
        "radius": radius_m,
        "filters": sorted(filters) if filters else [],
    }
    digest = hashlib.sha1(orjson.dumps(payload)).hexdigest()
    return f"q:{digest}"


def make_mvt_cache_key(z: int, x: int, y: int, filters: list[str] | None) -> str:
    payload = {
        "z": z,
        "x": x,
        "y": y,
        "filters": sorted(filters) if filters else [],
    }
    digest = hashlib.sha1(orjson.dumps(payload)).hexdigest()
    return f"mvt:amenities:{digest}"


async def ensure_route(db: Database, route_id: UUID) -> asyncpg.Record:
    record = await db.fetchrow(ROUTE_GEOJSON_SQL, route_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Route not found")
    return record


async def convert_geojson_to_wkt(db: Database, geojson: dict[str, Any]) -> str:
    geojson_str = orjson.dumps(geojson).decode()
    wkt = await db.fetchval(GEOJSON_TO_WKT_SQL, geojson_str)
    if not wkt:
        raise HTTPException(status_code=400, detail="Invalid GeoJSON geometry")
    return wkt


async def insert_route(db: Database, route_id: UUID, name: str, wkt: str) -> None:
    await db.execute(
        """
        INSERT INTO routes(route_id, name, geom, created_at)
        VALUES($1, $2, ST_GeomFromText($3, 4326), NOW())
        """,
        route_id,
        name,
        wkt,
    )


def get_queue() -> Queue:
    queue: Queue | None = getattr(app.state, "redis_queue", None)
    if queue is None:
        raise HTTPException(status_code=503, detail="queue not ready")
    return queue


@app.get("/healthz")
async def healthz(db: Database = Depends(get_db)) -> dict[str, Any]:
    try:
        await db.fetchval("SELECT 1")
    except Exception as exc:  # pragma: no cover - best effort health check
        raise HTTPException(status_code=503, detail=f"database error: {exc}") from exc

    if not await cache.ping():
        raise HTTPException(status_code=503, detail="redis unreachable")

    return {"status": "ok"}


@app.post("/routes", response_model=RouteCreateResponse, status_code=201)
async def create_route(
    db: Database = Depends(get_db),
    payload: RouteCreateRequest | None = Body(None),
    gpx_file: UploadFile | None = File(None),
    name: str | None = Form(None),
    geojson: str | None = Form(None),
) -> RouteCreateResponse:
    route_id = uuid4()
    route_name: str
    wkt: str

    if gpx_file is not None:
        contents = await gpx_file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Empty GPX file")
        gpx = gpxpy.parse(contents.decode())
        points: list[tuple[float, float]] = []
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    points.append((point.longitude, point.latitude))
        if len(points) < 2:
            raise HTTPException(status_code=400, detail="GPX must contain at least two points")
        coords = ", ".join(f"{lon} {lat}" for lon, lat in points)
        wkt = f"LINESTRING({coords})"
        route_name = name or gpx.name or "Uploaded route"
    elif payload is not None:
        route_name = payload.name
        wkt = await convert_geojson_to_wkt(db, payload.geojson.model_dump())
    elif geojson:
        try:
            parsed = json.loads(geojson)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid GeoJSON in form field") from exc
        route_name = name or "Route"
        wkt = await convert_geojson_to_wkt(db, parsed)
    else:
        raise HTTPException(status_code=400, detail="Provide GeoJSON payload or GPX upload")

    await insert_route(db, route_id, route_name, wkt)
    return RouteCreateResponse(route_id=route_id)


@app.get("/search", response_model=SearchResponse)
async def search_route_amenities(
    route_id: UUID = Query(...),
    radius_m: float = Query(500.0, gt=0),
    filters: str | None = Query(None),
    db: Database = Depends(get_db),
) -> SearchResponse:
    record = await ensure_route(db, route_id)
    route_geojson = json.loads(record["geojson"])
    route_info = {
        "route_id": str(route_id),
        "name": record["name"],
        "geometry": route_geojson,
    }
    filters_list = parse_filters(filters)
    cache_key = make_search_cache_key(record["wkb_hex"], radius_m, filters_list)

    cached = await cache.get_json(cache_key)
    if cached:
        return SearchResponse(**cached)

    categories = filters_list or None
    rows = await db.fetch(SEARCH_SQL, route_id, radius_m, categories)
    items = [
        AmenityFeature(
            id=row["id"],
            category=row["category"],
            props=row["props"],
            distance_m=float(row["dist_m"]) if row["dist_m"] is not None else None,
            geometry=json.loads(row["geojson"]),
        )
        for row in rows
    ]
    response = SearchResponse(route=route_info, items=items)
    await cache.set_json(cache_key, response.model_dump(mode="json"), SEARCH_CACHE_TTL)
    return response


@app.post("/export/gpx", response_model=ExportJobResponse)
async def export_gpx(request: ExportRequest, q: Queue = Depends(get_queue)) -> ExportJobResponse:
    job = q.enqueue(process_gpx_job, request.model_dump(mode="json"))
    return ExportJobResponse(job_id=job.id)


@app.get("/export/status/{job_id}", response_model=ExportStatusResponse)
async def export_status(job_id: str) -> ExportStatusResponse:
    redis_conn = Redis.from_url(settings.redis_url)
    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except NoSuchJobError:
        redis_conn.close()
        raise HTTPException(status_code=404, detail="Job not found")

    status = job.get_status(refresh=True)
    url_data = redis_conn.get(f"gpx:{job_id}")
    redis_conn.close()
    url: Optional[str] = None
    if url_data:
        url = orjson.loads(url_data).get("url")
    return ExportStatusResponse(status=status, url=url)


@app.get(
    "/mvt/amenities/{z}/{x}/{y}",
    responses={200: {"content": {"application/vnd.mapbox-vector-tile": {}}}},
)
async def amenities_tile(
    z: int,
    x: int,
    y: int,
    filters: str | None = Query(None),
    db: Database = Depends(get_db),
) -> Response:
    filters_list = parse_filters(filters)
    cache_key = make_mvt_cache_key(z, x, y, filters_list)
    cached = await cache.get_bytes(cache_key)
    if cached:
        return Response(content=cached, media_type="application/vnd.mapbox-vector-tile")

    categories = filters_list or None
    row = await db.fetchrow(MVT_SQL, z, x, y, categories)
    tile = row["st_asmvt"] if row and row["st_asmvt"] else b""

    await cache.set_bytes(cache_key, tile, MVT_CACHE_TTL)
    return Response(content=tile, media_type="application/vnd.mapbox-vector-tile")
