CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS routes (
    route_id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    geom geometry(LineString, 4326) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS amenities (
    id UUID PRIMARY KEY,
    category TEXT NOT NULL,
    props JSONB NOT NULL DEFAULT '{}'::jsonb,
    geom geometry(Point, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS amenities_geom_gix ON amenities USING GIST (geom);
CREATE INDEX IF NOT EXISTS amenities_category_idx ON amenities (category);
