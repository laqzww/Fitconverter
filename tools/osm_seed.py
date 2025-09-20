"""Optional helper to fetch amenities from Overpass API.

Usage:
    python tools/osm_seed.py --bbox 55.66 12.54 55.69 12.60 --categories toilet water cafe

The script prints INSERT statements that can be appended to sql/02_seed_demo.sql.
It is intentionally simple and does not write to the database directly.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from typing import Iterable

import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def build_query(bbox: list[float], categories: Iterable[str]) -> str:
    south, west, north, east = bbox
    cat_filters = "".join(f"node[amenity={cat}](%s,%s,%s,%s);" % (south, west, north, east) for cat in categories)
    return f"[out:json][timeout:25];({cat_filters});out body;"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bbox", nargs=4, type=float, metavar=("S", "W", "N", "E"), required=True)
    parser.add_argument("--categories", nargs="*", default=["toilets", "drinking_water", "cafe"])
    args = parser.parse_args()

    query = build_query(args.bbox, args.categories)
    response = requests.post(OVERPASS_URL, data={"data": query}, timeout=60)
    response.raise_for_status()
    data = response.json()

    for element in data.get("elements", []):
        if element.get("type") != "node":
            continue
        lon = element.get("lon")
        lat = element.get("lat")
        tags = element.get("tags", {})
        amenity = tags.get("amenity")
        name = tags.get("name", amenity)
        identifier = uuid.uuid4()
        props = json.dumps({"name": name, "source": "overpass"})
        print(
            "INSERT INTO amenities (id, category, props, geom) VALUES (",
            f"'{identifier}',",
            f"'{amenity}',",
            f"'{props.replace("'", "''")}'::jsonb,",
            f"ST_SetSRID(ST_Point({lon}, {lat}), 4326));",
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - helper script
        sys.stderr.write(f"Failed to fetch OSM data: {exc}\n")
        sys.exit(1)
