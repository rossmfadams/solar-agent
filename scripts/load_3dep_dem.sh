#!/usr/bin/env bash
# Load USGS 3D Elevation Program (3DEP) 10m DEM into PostGIS as a raster.
#
# Download the NY statewide 1/3 arc-second (~10m) DEM from USGS:
#   https://apps.nationalmap.gov/downloader/
# Select "Elevation Products (3DEP)" → "1/3 arc-second DEM" → "New York"
# or use the USGS National Map API:
#   https://tnmaccess.nationalmap.gov/api/v1/products?
#     datasets=National%20Elevation%20Dataset%20(NED)%201/3%20arc-second&
#     bbox=-79.76,40.49,-71.78,45.02&outputFormat=JSON
#
# Tiles are distributed as GeoTIFF files (.tif). Either merge them first
# with gdal_merge.py or run this script once per tile (the -a flag appends):
#
# Merge multiple tiles first (recommended for NY statewide):
#   gdal_merge.py -o data/ny_10m_dem.tif data/dem_tiles/*.tif
#
# Then load:
#   DATABASE_URL=postgresql://user:pass@host:5432/dbname \
#     ./scripts/load_3dep_dem.sh data/ny_10m_dem.tif
#
# NOTE: raster2pgsql ships with PostGIS. If not available on the host, run inside
# the running DB container (volume-mount the data dir):
#   docker compose -p helios exec -T db bash -c \
#     "raster2pgsql -s 4326 -I -C -M -t 100x100 /data/ny_10m_dem.tif public.dem | \
#      psql \"\$DATABASE_URL\""
#
# Requires: raster2pgsql (postgis-gdal package), psql

set -euo pipefail

SRC="${1:?Usage: $0 <path-to-ny_dem.tif>}"
: "${DATABASE_URL:?DATABASE_URL must be set}"

echo "Enabling postgis_raster extension..."
psql "${DATABASE_URL}" -c "CREATE EXTENSION IF NOT EXISTS postgis_raster;"

echo "Loading 3DEP DEM raster from: $SRC (this may take several minutes)..."
# -s 4326  : source SRID WGS84
# -I       : build GIST index on rast column after load
# -C       : apply raster constraints (SRID, scale, alignment)
# -M       : vacuum analyze after load
# -t 100x100 : tile size (100x100 pixels per row; tunes query performance)
# -d       : drop table and recreate (idempotent re-load)
raster2pgsql \
    -s 4326 \
    -I \
    -C \
    -M \
    -t 100x100 \
    -d \
    "${SRC}" \
    public.dem \
  | psql "${DATABASE_URL}"

echo "Done. Tile count:"
psql "${DATABASE_URL}" -c "SELECT COUNT(*) FROM dem;" 2>/dev/null \
  || echo "psql not found on PATH; verify with: SELECT COUNT(*) FROM dem;"
