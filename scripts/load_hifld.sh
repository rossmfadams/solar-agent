#!/usr/bin/env bash
# Load HIFLD Electric Power Transmission Lines and Electric Substations into PostGIS.
#
# Data sources (public, no auth required):
#   Transmission Lines:
#     https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Electric_Power_Transmission_Lines/FeatureServer/0
#   Substations:
#     https://services1.arcgis.com/BSnEnFfEn54YLVeq/arcgis/rest/services/HIFLD_Electric_Substations/FeatureServer/5
#
# Requires: ogr2ogr (gdal-bin), curl, python3
#   apt-get install gdal-bin   OR   brew install gdal
#
# Usage:
#   DATABASE_URL=postgresql://user:pass@host:5432/dbname ./scripts/load_hifld.sh

set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL must be set}"

TRANS_URL="https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Electric_Power_Transmission_Lines/FeatureServer/0"
SUBS_URL="https://services1.arcgis.com/BSnEnFfEn54YLVeq/arcgis/rest/services/HIFLD_Electric_Substations/FeatureServer/5"

# New York State bounding box (WGS84)
NY_BBOX="-79.76,40.49,-71.78,45.02"
PAGE_SIZE=1000

TMPDIR_HIFLD=$(mktemp -d)
trap 'rm -rf "$TMPDIR_HIFLD"' EXIT

# Download a FeatureServer layer as a single GeoJSON file (handles pagination).
download_layer() {
    local url="$1"
    local fields="$2"
    local outfile="$3"

    echo '{"type":"FeatureCollection","features":[' > "$outfile"
    local offset=0
    local first=true

    while true; do
        local page
        page=$(curl -sf "${url}/query" \
            --data-urlencode "where=1=1" \
            --data-urlencode "geometry=${NY_BBOX}" \
            --data-urlencode "geometryType=esriGeometryEnvelope" \
            --data-urlencode "inSR=4326" \
            --data-urlencode "spatialRel=esriSpatialRelIntersects" \
            --data-urlencode "outFields=${fields}" \
            --data-urlencode "outSR=4326" \
            --data-urlencode "resultOffset=${offset}" \
            --data-urlencode "resultRecordCount=${PAGE_SIZE}" \
            --data-urlencode "f=geojson")

        local features exceeded count
        features=$(python3 -c "
import sys, json
d = json.loads('''${page}'''.replace(\"'\", \"'\"))
" 2>/dev/null || python3 << PYEOF
import json
d = json.loads(open('/dev/stdin').read())
feats = d.get('features', [])
print(','.join(json.dumps(f) for f in feats))
PYEOF
        )

        # Use python to safely parse page
        read -r count exceeded < <(python3 - "$page" << 'PYEOF'
import sys, json
raw = sys.argv[1]
d = json.loads(raw)
feats = d.get('features', [])
exceeded = d.get('exceededTransferLimit', False)
print(len(feats), str(exceeded))
PYEOF
        )

        # Extract and write features
        python3 - "$page" "$outfile" "$first" << 'PYEOF'
import sys, json
raw = sys.argv[1]
outfile = sys.argv[2]
first = sys.argv[3] == "true"
d = json.loads(raw)
feats = d.get('features', [])
if feats:
    sep = "" if first else ","
    with open(outfile, 'a') as f:
        f.write(sep + ",".join(json.dumps(feat) for feat in feats))
PYEOF

        first=false

        if [ "$exceeded" != "True" ] || [ "$count" -eq 0 ]; then
            break
        fi
        offset=$((offset + PAGE_SIZE))
        echo "  ... fetched offset ${offset}"
    done

    echo ']}' >> "$outfile"
}

# Simpler paginated download using python directly
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
        "f": "geojson",
    })
    with urllib.request.urlopen(url + "?" + params) as resp:
        data = json.loads(resp.read())

    feats = data.get("features", [])
    all_features.extend(feats)
    print(f"  fetched {len(feats)} features (total {len(all_features)})", flush=True)

    if not data.get("exceededTransferLimit", False) or len(feats) == 0:
        break
    offset += page_size

with open(outfile, "w") as f:
    json.dump({"type": "FeatureCollection", "features": all_features}, f)

print(f"  wrote {len(all_features)} features to {outfile}")
PYEOF
}

echo "=== Downloading transmission lines (NY extent) ==="
TRANS_FILE="${TMPDIR_HIFLD}/transmission_lines.geojson"
download_layer_py "$TRANS_URL" "OBJECTID,ID,VOLTAGE,VOLT_CLASS" "$TRANS_FILE"

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
download_layer_py "$SUBS_URL" "OBJECTID,ID,NAME,TYPE,STATUS" "$SUBS_FILE"

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
" 2>/dev/null || echo "(psql not on PATH — indexes will be created on first query)"

echo "=== Row counts ==="
psql "${DATABASE_URL}" -c "
SELECT 'transmission_lines' AS tbl, COUNT(*) FROM transmission_lines
UNION ALL
SELECT 'substations', COUNT(*) FROM substations;
" 2>/dev/null || echo "(psql not on PATH — verify counts manually)"

echo "Done."
