#!/usr/bin/env bash
# Load NY GIS statewide parcel shapefile into PostGIS.
#
# Download the statewide parcel dataset from:
#   https://gis.ny.gov/parcels  (NYS Office of Information Technology Services)
#
# The dataset is a ZIP containing a shapefile. Extract it, then run:
#   DATABASE_URL=postgresql://user:pass@host:5432/dbname ./scripts/load_parcels.sh /path/to/parcels.shp
#
# Requires ogr2ogr (part of GDAL). Install with: apt-get install gdal-bin
# or: brew install gdal

set -euo pipefail

SHP="${1:?Usage: $0 <path-to-parcels.shp>}"
: "${DATABASE_URL:?DATABASE_URL must be set}"

echo "Loading parcels from: $SHP"

ogr2ogr \
    -f PostgreSQL \
    PG:"${DATABASE_URL}" \
    "${SHP}" \
    -nln parcels \
    -nlt PROMOTE_TO_MULTI \
    -t_srs EPSG:4326 \
    -lco GEOMETRY_NAME=geom \
    -lco FID=id \
    -select "PRINT_KEY,COUNTY_NAM,MUNI_NAME" \
    -overwrite \
    --config PG_USE_COPY YES

echo "Rebuilding spatial index..."
psql "${DATABASE_URL}" -c "REINDEX INDEX parcels_geom_idx;"

echo "Done. Row count:"
psql "${DATABASE_URL}" -c "SELECT COUNT(*) FROM parcels;"
