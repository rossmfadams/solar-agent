#!/usr/bin/env bash
# Load NY GIS statewide parcel dataset into PostGIS.
#
# Download the statewide parcel dataset from:
#   https://gis.ny.gov/parcels  (NYS Office of Information Technology Services)
#
# The dataset is a ZIP containing a File Geodatabase (.gdb). Extract it, then run:
#   DATABASE_URL=postgresql://user:pass@host:5432/dbname ./scripts/load_parcels.sh /path/to/NYS_Tax_Parcels.gdb
#
# Requires ogr2ogr (part of GDAL). Install with: apt-get install gdal-bin
# or: brew install gdal

set -euo pipefail

SRC="${1:?Usage: $0 <path-to-parcels.gdb or .shp>}"
: "${DATABASE_URL:?DATABASE_URL must be set}"

echo "Loading parcels from: $SRC"

ogr2ogr \
    -f PostgreSQL \
    PG:"${DATABASE_URL}" \
    "${SRC}" \
    NYS_Tax_Parcels_Public \
    -nln parcels \
    -nlt PROMOTE_TO_MULTI \
    -nlt CONVERT_TO_LINEAR \
    -t_srs EPSG:4326 \
    -lco GEOMETRY_NAME=geom \
    -lco FID=id \
    -select "PRINT_KEY,COUNTY_NAME,MUNI_NAME" \
    -overwrite \
    --config PG_USE_COPY YES

echo "Rebuilding spatial index..."
psql "${DATABASE_URL}" -c "REINDEX INDEX parcels_geom_idx;" 2>/dev/null \
  || echo "psql not found on PATH; index rebuild skipped (it will be used as-is)"

echo "Done. Row count:"
psql "${DATABASE_URL}" -c "SELECT COUNT(*) FROM parcels;" 2>/dev/null \
  || echo "psql not found on PATH; verify count with: SELECT COUNT(*) FROM parcels;"
