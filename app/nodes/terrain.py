import json

from app.db import get_pool

# Compute mean slope (percent rise) over all DEM tiles that intersect the parcel.
# ST_Union merges overlapping tiles; ST_Slope converts elevation to percent slope;
# ST_Clip clips the result to the parcel boundary; ST_SummaryStats extracts the mean.
_SLOPE_QUERY = """
SELECT (ST_SummaryStats(
    ST_Slope(
        ST_Clip(ST_Union(d.rast), $1::geometry),
        1,
        '32BF',
        'PERCENT'
    )
)).mean AS mean_slope
FROM dem d
WHERE ST_Intersects(d.rast, $1::geometry)
"""

_DEGRADED = {
    "mean_slope_percent": None,
    "terrain_data_available": False,
}


async def check_terrain(state: dict) -> dict:
    """Compute mean slope across the parcel polygon from the 3DEP DEM."""
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
            # Build query geometry: prefer parcel polygon, fall back to point
            if parcel_geojson is not None:
                geojson_str = (
                    parcel_geojson
                    if isinstance(parcel_geojson, str)
                    else json.dumps(parcel_geojson)
                )
                parcel_geom = await conn.fetchval(
                    "SELECT ST_GeomFromGeoJSON($1)", geojson_str
                )
            else:
                # For a point with no parcel polygon, use a small buffer (approx 1 acre)
                parcel_geom = await conn.fetchval(
                    "SELECT ST_Buffer(ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography, 63)::geometry",
                    lng,
                    lat,
                )

            if parcel_geom is None:
                return _DEGRADED

            row = await conn.fetchrow(_SLOPE_QUERY, parcel_geom)

    except Exception:
        return _DEGRADED

    if row is None or row["mean_slope"] is None:
        return _DEGRADED

    return {
        "mean_slope_percent": round(float(row["mean_slope"]), 2),
        "terrain_data_available": True,
    }
