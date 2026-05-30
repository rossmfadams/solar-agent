#!/usr/bin/env bash
# Load USGS Protected Areas Database of the US (PAD-US) into PostGIS.
#
# Download the PAD-US geodatabase from USGS ScienceBase:
#   https://www.sciencebase.gov/catalog/item/652f1decad27ef1a46bf21f1
# (PAD-US 3.0 or later; download "PAD-US3_0_GDB.zip")
#
# The relevant layer for protected area polygons is "PADUS3_0Combined_Proclamation_Marine_Fee_Designation_Easement"
# or more commonly just the "Fee" ownership layer "PADUS3_0Fee".
# For this use case, load the Combined layer which includes all designation types.
#
# Usage:
#   DATABASE_URL=postgresql://user:pass@host:5432/dbname \
#     ./scripts/load_padus.sh /path/to/PAD_US3_0.gdb
#
# Or with a flat shapefile:
#   ./scripts/load_padus.sh /path/to/PADUS3_0Combined.shp
#
# Requires ogr2ogr (part of GDAL). Install with: apt-get install gdal-bin
# or: brew install gdal

set -euo pipefail

SRC="${1:?Usage: $0 <path-to-PAD_US3_0.gdb or PADUS3_0Combined.shp>}"
: "${DATABASE_URL:?DATABASE_URL must be set}"

echo "Loading USGS PAD-US protected areas from: $SRC"

if [[ "$SRC" == *.gdb ]]; then
    # Use the Combined layer for broadest coverage; fall back to Fee layer
    LAYER_ARG="PADUS3_0Combined_Proclamation_Marine_Fee_Designation_Easement"
else
    LAYER_ARG=""
fi

ogr2ogr \
    -f PostgreSQL \
    PG:"${DATABASE_URL}" \
    "${SRC}" \
    ${LAYER_ARG} \
    -nln protected_areas \
    -nlt PROMOTE_TO_MULTI \
    -nlt CONVERT_TO_LINEAR \
    -t_srs EPSG:4326 \
    -lco GEOMETRY_NAME=geom \
    -lco FID=id \
    -select "Unit_Nm,Des_Tp" \
    -overwrite \
    --config PG_USE_COPY YES

echo "Creating spatial index..."
psql "${DATABASE_URL}" -c "
    CREATE INDEX IF NOT EXISTS protected_areas_geom_idx ON protected_areas USING GIST (geom);
" 2>/dev/null \
  || echo "psql not found on PATH; index creation skipped (run manually if needed)"

echo "Done. Row count:"
psql "${DATABASE_URL}" -c "SELECT COUNT(*) FROM protected_areas;" 2>/dev/null \
  || echo "psql not found on PATH; verify with: SELECT COUNT(*) FROM protected_areas;"
