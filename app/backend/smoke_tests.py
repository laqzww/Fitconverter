from __future__ import annotations

import asyncio
import os
import time

import httpx

API_BASE = os.environ.get("SMOKE_API_BASE", "http://localhost:8000")
SEED_ROUTE = "11111111-1111-1111-1111-111111111111"


def log(message: str) -> None:
    print(f"[smoke] {message}")


async def ensure_export(client: httpx.AsyncClient, job_id: str) -> str:
    for attempt in range(20):
        resp = await client.get(f"/export/status/{job_id}")
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        log(f"export status attempt {attempt}: {status}")
        if status == "finished" and data.get("url"):
            return data["url"]
        if status == "failed":
            raise RuntimeError("Export job failed")
        await asyncio.sleep(1.0)
    raise RuntimeError("Export job did not finish in time")


async def run_smoke() -> None:
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        log("checking /healthz")
        resp = await client.get("/healthz")
        resp.raise_for_status()

        log("inserting temporary route")
        route_payload = {
            "name": "Smoke Test Route",
            "geojson": {
                "type": "LineString",
                "coordinates": [
                    [12.5635, 55.6761],
                    [12.5692, 55.6781],
                    [12.5741, 55.6795],
                ],
            },
        }
        resp = await client.post("/routes", json=route_payload)
        resp.raise_for_status()
        route_id = resp.json()["route_id"]
        log(f"created route {route_id}")

        log("running search")
        params = {"route_id": SEED_ROUTE, "radius_m": 800}
        start = time.perf_counter()
        resp = await client.get("/search", params=params)
        resp.raise_for_status()
        data = resp.json()
        count = len(data["items"])
        if count == 0:
            raise RuntimeError("search returned no amenities")
        first_duration = time.perf_counter() - start
        log(f"first search returned {count} items in {first_duration*1000:.1f} ms")

        start = time.perf_counter()
        resp = await client.get("/search", params=params)
        resp.raise_for_status()
        second_duration = time.perf_counter() - start
        log(f"cached search completed in {second_duration*1000:.1f} ms")
        if second_duration > 0.5:
            raise RuntimeError("cached search slower than 500 ms")

        log("requesting GPX export")
        export_payload = {
            "route_id": SEED_ROUTE,
            "radius_m": 1000,
            "filters": ["cafe", "water"],
        }
        resp = await client.post("/export/gpx", json=export_payload)
        resp.raise_for_status()
        job_id = resp.json()["job_id"]
        log(f"export job {job_id}")

        file_url = await ensure_export(client, job_id)
        log(f"export available at {file_url}")
        file_resp = await client.get(file_url)
        file_resp.raise_for_status()
        if not file_resp.text.startswith("<?xml"):
            raise RuntimeError("exported GPX missing XML header")

        log("requesting MVT tile")
        tile_resp = await client.get("/mvt/amenities/14/8801/5371")
        tile_resp.raise_for_status()
        if len(tile_resp.content) == 0:
            raise RuntimeError("empty tile data")

        log("smoke tests passed")


if __name__ == "__main__":
    asyncio.run(run_smoke())
