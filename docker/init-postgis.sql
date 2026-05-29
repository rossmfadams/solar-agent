CREATE EXTENSION IF NOT EXISTS postgis;
-- Confirm PostGIS is available; startup fails if this errors
SELECT PostGIS_Version();

-- NY GIS statewide parcel table; populated by scripts/load_parcels.sh
CREATE TABLE IF NOT EXISTS parcels (
    id         BIGSERIAL PRIMARY KEY,
    print_key  TEXT,
    county_name TEXT,
    muni_name  TEXT,
    geom       GEOMETRY(Geometry, 4326)
);

CREATE INDEX IF NOT EXISTS parcels_geom_idx ON parcels USING GIST (geom);
