#!/usr/bin/env bash
# Load USFWS National Wetlands Inventory (NWI) into PostGIS.
#
# Download NY wetland shapefiles from the NWI data portal:
#   https://www.fws.gov/program/national-wetlands-inventory/data-download
# Select "New York" → download the statewide geodatabase or shapefile.
# The relevant layer is the wetlands polygon layer (typically named
# NY_Wetlands.gdb / NWIplus_NY_wetlands_geodatabase.gdb, layer "Wetlands").
#
# Usage:
#   DATABASE_URL=postgresql://user:pass@host:5432/dbname \
#     ./scripts/load_nwi.sh /path/to/NWI.gdb
#
# Or with a flat shapefile:
#   ./scripts/load_nwi.sh /path/to/Wetlands.shp
#
# Requires ogr2ogr (part of GDAL). Install with: apt-get install gdal-bin
# or: brew install gdal

set -euo pipefail

SRC="${1:?Usage: $0 <path-to-NWI.gdb or Wetlands.shp>}"
: "${DATABASE_URL:?DATABASE_URL must be set}"

echo "Loading USFWS NWI wetlands from: $SRC"

if [[ "$SRC" == *.gdb ]]; then
    LAYER_ARG="Wetlands"
else
    LAYER_ARG=""
fi

ogr2ogr \
    -f PostgreSQL \
    PG:"${DATABASE_URL}" \
    "${SRC}" \
    ${LAYER_ARG} \
    -nln wetlands \
    -nlt PROMOTE_TO_MULTI \
    -nlt CONVERT_TO_LINEAR \
    -t_srs EPSG:4326 \
    -lco GEOMETRY_NAME=geom \
    -lco FID=id \
    -select "WETLAND_TYPE,ATTRIBUTE" \
    -overwrite \
    --config PG_USE_COPY YES

echo "Creating spatial index..."
psql "${DATABASE_URL}" -c "
    CREATE INDEX IF NOT EXISTS wetlands_geom_idx ON wetlands USING GIST (geom);
" 2>/dev/null \
  || echo "psql not found on PATH; index creation skipped (run manually if needed)"

echo "Done. Row count:"
psql "${DATABASE_URL}" -c "SELECT COUNT(*) FROM wetlands;" 2>/dev/null \
  || echo "psql not found on PATH; verify with: SELECT COUNT(*) FROM wetlands;"
