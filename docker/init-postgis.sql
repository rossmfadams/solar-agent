CREATE EXTENSION IF NOT EXISTS postgis;
-- Confirm PostGIS is available; startup fails if this errors
SELECT PostGIS_Version();
