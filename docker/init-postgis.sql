CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_raster;
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

-- Solar ordinance cache; populated by scripts/seed_ordinance_cache.py or live research
-- TTL is enforced at read time: rows older than 30 days are treated as stale.
CREATE TABLE IF NOT EXISTS ordinance_cache (
    id                  BIGSERIAL PRIMARY KEY,
    muni                TEXT NOT NULL,
    county              TEXT NOT NULL,
    muni_norm           TEXT NOT NULL,
    county_norm         TEXT NOT NULL,
    found               BOOLEAN NOT NULL DEFAULT FALSE,
    source_name         TEXT,
    source_url          TEXT,
    document_section    TEXT,
    setbacks            TEXT,
    sup_requirements    TEXT,
    moratorium_active   BOOLEAN NOT NULL DEFAULT FALSE,
    moratorium_section  TEXT,
    moratorium_quote    TEXT,
    summary             TEXT,
    retrieved_at        DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE UNIQUE INDEX IF NOT EXISTS ordinance_cache_town_idx
    ON ordinance_cache (muni_norm, county_norm);

-- Screening results; populated by POST /screen
CREATE TABLE IF NOT EXISTS screens (
    site_id         UUID PRIMARY KEY,
    address         TEXT,
    resolved_lat    DOUBLE PRECISION,
    resolved_lng    DOUBLE PRECISION,
    parcel_id       TEXT,
    parcel_geojson  JSONB,
    parcel_fallback BOOLEAN NOT NULL DEFAULT FALSE,
    memo            JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
