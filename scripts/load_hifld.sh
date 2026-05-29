#!/usr/bin/env bash
# Load HIFLD Electric Power Transmission Lines and Electric Substations into PostGIS.
#
# Data sources (public, no auth required):
#   Transmission Lines:
#     https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Electric_Power_Transmission_Lines/FeatureServer/0
#   Substations (national HIFLD, 77k records):
#     https://services6.arcgis.com/OO2s4OoyCZkYJ6oE/arcgis/rest/services/Substations/FeatureServer/0
#
# Requires: ogr2ogr (gdal-bin), python3
#   apt-get install gdal-bin   OR   brew install gdal
#
# Usage:
#   DATABASE_URL=postgresql://user:pass@host:5432/dbname ./scripts/load_hifld.sh

set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL must be set}"

TRANS_URL="https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Electric_Power_Transmission_Lines/FeatureServer/0"
SUBS_URL="https://services6.arcgis.com/OO2s4OoyCZkYJ6oE/arcgis/rest/services/Substations/FeatureServer/0"

# New York State bounding box (WGS84)
NY_BBOX="-79.76,40.49,-71.78,45.02"
PAGE_SIZE=1000

TMPDIR_HIFLD=$(mktemp -d)
trap 'rm -rf "$TMPDIR_HIFLD"' EXIT

# Download a FeatureServer layer as GeoJSON (paginated via ESRI JSON + resultOffset).
# Uses the ESRI JSON format (not GeoJSON) because it reliably returns exceededTransferLimit.
# Converts to GeoJSON for ogr2ogr compatibility.
download_layer_py() {
    local url="$1"
    local fields="$2"
    local outfile="$3"

    python3 << PYEOF
import urllib.request, urllib.parse, json, sys

url = "${url}/query"
bbox = "${NY_BBOX}"
page_size = ${PAGE_SIZE}
fields = "${fields}"
outfile = "${outfile}"

all_features = []
offset = 0

while True:
    params = urllib.parse.urlencode({
        "where": "1=1",
        "geometry": bbox,
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": fields,
        "outSR": "4326",
        "resultOffset": offset,
        "resultRecordCount": page_size,
        "f": "json",  # ESRI JSON includes exceededTransferLimit
    })
    with urllib.request.urlopen(url + "?" + params) as resp:
        data = json.loads(resp.read())

    if "error" in data:
        print(f"  API error: {data['error']}", file=sys.stderr)
        sys.exit(1)

    esri_features = data.get("features", [])

    # Convert ESRI JSON features to GeoJSON
    for feat in esri_features:
        geom = feat.get("geometry", {})
        attrs = feat.get("attributes", {})

        if "paths" in geom:
            geo = {"type": "MultiLineString", "coordinates": geom["paths"]}
        elif "rings" in geom:
            geo = {"type": "MultiPolygon", "coordinates": [geom["rings"]]}
        elif "x" in geom:
            geo = {"type": "Point", "coordinates": [geom["x"], geom["y"]]}
        else:
            geo = None

        if geo:
            all_features.append({"type": "Feature", "geometry": geo, "properties": attrs})

    print(f"  fetched {len(esri_features)} features (total {len(all_features)})", flush=True)

    if not data.get("exceededTransferLimit", False) or len(esri_features) == 0:
        break
    offset += page_size

with open(outfile, "w") as f:
    json.dump({"type": "FeatureCollection", "features": all_features}, f)

print(f"  wrote {len(all_features)} features to {outfile}")
PYEOF
}

echo "=== Downloading transmission lines (NY extent) ==="
TRANS_FILE="${TMPDIR_HIFLD}/transmission_lines.geojson"
download_layer_py "$TRANS_URL" "OBJECTID,VOLTAGE,VOLT_CLASS" "$TRANS_FILE"

echo "=== Loading transmission lines into PostGIS ==="
ogr2ogr \
    -f PostgreSQL \
    PG:"${DATABASE_URL}" \
    "$TRANS_FILE" \
    -nln transmission_lines \
    -nlt PROMOTE_TO_MULTI \
    -nlt CONVERT_TO_LINEAR \
    -t_srs EPSG:4326 \
    -lco GEOMETRY_NAME=geom \
    -lco FID=id \
    -overwrite \
    --config PG_USE_COPY YES

echo "=== Downloading substations (NY extent) ==="
SUBS_FILE="${TMPDIR_HIFLD}/substations.geojson"
download_layer_py "$SUBS_URL" "OBJECTID,NAME,TYPE,STATUS,COUNTY,STATE,MAX_VOLT" "$SUBS_FILE"

echo "=== Loading substations into PostGIS ==="
ogr2ogr \
    -f PostgreSQL \
    PG:"${DATABASE_URL}" \
    "$SUBS_FILE" \
    -nln substations \
    -nlt POINT \
    -t_srs EPSG:4326 \
    -lco GEOMETRY_NAME=geom \
    -lco FID=id \
    -overwrite \
    --config PG_USE_COPY YES

echo "=== Rebuilding spatial indexes ==="
psql "${DATABASE_URL}" -c "
CREATE INDEX IF NOT EXISTS transmission_lines_geom_idx ON transmission_lines USING GIST (geom);
CREATE INDEX IF NOT EXISTS substations_geom_idx ON substations USING GIST (geom);
" 2>/dev/null || echo "(psql not on PATH — indexes created on first query)"

echo "=== Row counts ==="
psql "${DATABASE_URL}" -c "
SELECT 'transmission_lines' AS tbl, COUNT(*) FROM transmission_lines
UNION ALL
SELECT 'substations', COUNT(*) FROM substations;
" 2>/dev/null || echo "(psql not on PATH — verify counts manually)"

echo "Done."
