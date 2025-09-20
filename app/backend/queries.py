SEARCH_SQL = """
WITH route AS (
  SELECT ST_LineMerge(geom)::geography AS g, name FROM routes WHERE route_id = $1
),
buf AS (
  SELECT ST_Buffer(g, $2)::geometry AS g FROM route
)
SELECT a.id,
       a.category,
       a.props,
       ST_Distance(a.geom::geography, (SELECT g FROM route)) AS dist_m,
       ST_AsGeoJSON(a.geom) AS geojson
FROM amenities a
WHERE ST_Intersects(a.geom, (SELECT g FROM buf))
  AND ($3::text[] IS NULL OR a.category = ANY($3::text[]))
ORDER BY dist_m
LIMIT 500;
"""

ROUTE_GEOJSON_SQL = """
SELECT route_id,
       name,
       ST_AsGeoJSON(geom) AS geojson,
       encode(ST_AsEWKB(geom), 'hex') AS wkb_hex
FROM routes
WHERE route_id = $1
"""

GEOJSON_TO_WKT_SQL = "SELECT ST_AsText(ST_GeomFromGeoJSON($1))"
