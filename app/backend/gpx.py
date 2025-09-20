from __future__ import annotations

from pathlib import Path
from typing import Iterable

import gpxpy.gpx


class GPXBuildError(Exception):
    """Raised when GPX output cannot be produced."""


def build_gpx(
    route: dict,
    pois: Iterable[dict],
    output_file: Path,
) -> Path:
    """Create a GPX file with a track for the route and waypoints for amenities."""

    if "coordinates" not in route:
        raise GPXBuildError("Route data must include coordinates")

    gpx = gpxpy.gpx.GPX()
    gpx.name = route.get("name", "Route")

    track = gpxpy.gpx.GPXTrack(name=route.get("name", "Route"))
    gpx.tracks.append(track)
    segment = gpxpy.gpx.GPXTrackSegment()
    track.segments.append(segment)

    for coord in route["coordinates"]:
        # Coordinates are expected as [lon, lat]
        segment.points.append(gpxpy.gpx.GPXTrackPoint(latitude=coord[1], longitude=coord[0]))

    for poi in pois:
        geojson = poi.get("geometry")
        if not geojson:
            continue
        coords = geojson.get("coordinates")
        if not coords:
            continue
        name = poi.get("category", "POI")
        props = poi.get("props", {})
        label = props.get("name") or name
        distance = poi.get("distance_m")
        description_parts = [f"Category: {name}"]
        if distance is not None:
            description_parts.append(f"Distance: {distance:.0f} m")
        if props:
            description_parts.append(f"Props: {props}")
        description = " | ".join(description_parts)
        waypoint = gpxpy.gpx.GPXWaypoint(
            latitude=coords[1],
            longitude=coords[0],
            name=label,
            description=description,
        )
        gpx.waypoints.append(waypoint)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as fh:
        fh.write(gpx.to_xml())

    return output_file
