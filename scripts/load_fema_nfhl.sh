#!/usr/bin/env bash
# Load FEMA National Flood Hazard Layer (NFHL) into PostGIS.
#
# Download the statewide NFHL from FEMA's Map Service Center:
#   https://msc.fema.gov/portal/advanceSearch  (select "NFHL Data" → New York)
# or via the FEMA NFHL REST API bulk export:
#   https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer
#
# The download is a ZIP containing File Geodatabase (.gdb) layers.
# The relevant layer for flood zone polygons is S_Fld_Haz_Ar.
# Extract the .gdb, then run:
#   DATABASE_URL=postgresql://user:pass@host:5432/dbname \
#     ./scripts/load_fema_nfhl.sh /path/to/NFHL.gdb
#
# Or supply a .shp directly:
#   ./scripts/load_fema_nfhl.sh /path/to/S_Fld_Haz_Ar.shp
#
# Requires ogr2ogr (part of GDAL). Install with: apt-get install gdal-bin
# or: brew install gdal

set -euo pipefail

SRC="${1:?Usage: $0 <path-to-NFHL.gdb or S_Fld_Haz_Ar.shp>}"
: "${DATABASE_URL:?DATABASE_URL must be set}"

echo "Loading FEMA NFHL flood zones from: $SRC"

# Detect whether source is a .gdb (need to name the layer) or a flat file
if [[ "$SRC" == *.gdb ]]; then
    LAYER_ARG="S_Fld_Haz_Ar"
else
    LAYER_ARG=""
fi

ogr2ogr \
    -f PostgreSQL \
    PG:"${DATABASE_URL}" \
    "${SRC}" \
    ${LAYER_ARG} \
    -nln flood_zones \
    -nlt PROMOTE_TO_MULTI \
    -nlt CONVERT_TO_LINEAR \
    -t_srs EPSG:4326 \
    -lco GEOMETRY_NAME=geom \
    -lco FID=id \
    -select "FLD_ZONE,ZONE_SUBTY" \
    -overwrite \
    --config PG_USE_COPY YES

echo "Creating spatial index..."
psql "${DATABASE_URL}" -c "
    CREATE INDEX IF NOT EXISTS flood_zones_geom_idx ON flood_zones USING GIST (geom);
" 2>/dev/null \
  || echo "psql not found on PATH; index creation skipped (run manually if needed)"

echo "Done. Row count:"
psql "${DATABASE_URL}" -c "SELECT COUNT(*) FROM flood_zones;" 2>/dev/null \
  || echo "psql not found on PATH; verify with: SELECT COUNT(*) FROM flood_zones;"
