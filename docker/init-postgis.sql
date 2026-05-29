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

-- NYISO interconnection queue; populated by scripts/load_nyiso_queue.py
-- match_method: 'exact' | 'fuzzy' | 'county'
CREATE TABLE IF NOT EXISTS nyiso_queue (
    id                    BIGSERIAL PRIMARY KEY,
    queue_id              TEXT,
    project_name          TEXT,
    summer_mw             DOUBLE PRECISION,
    winter_mw             DOUBLE PRECISION,
    county                TEXT,
    interconnection_point TEXT,
    matched_substation_id BIGINT,
    match_method          TEXT,
    status                TEXT,
    snapshot_date         DATE,
    retrieved_at          DATE,
    geom                  GEOMETRY(Point, 4326)
);

CREATE INDEX IF NOT EXISTS nyiso_queue_geom_idx ON nyiso_queue USING GIST (geom);
