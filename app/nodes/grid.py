from app.db import get_pool

_METERS_PER_MILE = 1609.344

_TRANSMISSION_QUERY = """
SELECT ST_Distance(geom::geography, $1::geography) / $2 AS miles
FROM transmission_lines
ORDER BY geom <-> $1
LIMIT 1
"""

_SUBSTATIONS_QUERY = """
SELECT id, name, ST_Distance(geom::geography, $1::geography) / $2 AS miles
FROM substations
ORDER BY geom <-> $1
LIMIT 3
"""

_DEGRADED = {
    "nearest_transmission_miles": None,
    "nearest_substation_miles": None,
    "nearest_substations": [],
    "grid_data_available": False,
}


def _transmission_band(miles: float) -> str:
    if miles <= 1.0:
        return "strong positive"
    if miles <= 5.0:
        return "neutral"
    if miles <= 10.0:
        return "mild negative"
    return "strong negative"


async def check_grid_proximity(state: dict) -> dict:
    # Determine query point: prefer parcel centroid, fall back to resolved point.
    parcel_geojson = state.get("parcel_geojson")
    lat = state.get("resolved_lat")
    lng = state.get("resolved_lng")

    if parcel_geojson is None and (lat is None or lng is None):
        return _DEGRADED

    try:
        pool = await get_pool()
    except RuntimeError:
        return _DEGRADED

    try:
        async with pool.acquire() as conn:
            if parcel_geojson is not None:
                import json
                # asyncpg returns json columns as raw strings; dicts must be serialised
                geojson_str = (
                    parcel_geojson
                    if isinstance(parcel_geojson, str)
                    else json.dumps(parcel_geojson)
                )
                point_wkt = await conn.fetchval(
                    "SELECT ST_AsText(ST_Centroid(ST_GeomFromGeoJSON($1)))",
                    geojson_str,
                )
            else:
                point_wkt = await conn.fetchval(
                    "SELECT ST_AsText(ST_SetSRID(ST_MakePoint($1, $2), 4326))",
                    lng,
                    lat,
                )

            if point_wkt is None:
                return _DEGRADED

            point_geom = f"SRID=4326;{point_wkt}"

            trans_row = await conn.fetchrow(
                _TRANSMISSION_QUERY, point_geom, _METERS_PER_MILE
            )
            sub_rows = await conn.fetch(
                _SUBSTATIONS_QUERY, point_geom, _METERS_PER_MILE
            )
    except Exception:
        return _DEGRADED

    if trans_row is None or not sub_rows:
        return _DEGRADED

    nearest_trans = round(trans_row["miles"], 3)
    nearest_subs = [
        {"id": r["id"], "name": r["name"], "miles": round(r["miles"], 3)}
        for r in sub_rows
    ]

    return {
        "nearest_transmission_miles": nearest_trans,
        "transmission_band": _transmission_band(nearest_trans),
        "nearest_substation_miles": round(sub_rows[0]["miles"], 3),
        "nearest_substations": nearest_subs,
        "grid_data_available": True,
    }
