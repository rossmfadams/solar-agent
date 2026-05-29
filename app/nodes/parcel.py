from app.db import get_pool

_POINT_QUERY = """
SELECT print_key, county_nam AS county, muni_name AS muni,
       ST_AsGeoJSON(geom)::json AS geojson
FROM parcels
WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint($1, $2), 4326))
LIMIT 1
"""

_BUFFER_QUERY = """
SELECT print_key, county_nam AS county, muni_name AS muni,
       ST_AsGeoJSON(geom)::json AS geojson
FROM parcels
WHERE ST_DWithin(
    geom::geography,
    ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography,
    500
)
ORDER BY ST_Distance(
    geom::geography,
    ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography
)
LIMIT 1
"""


async def resolve_parcel(state: dict) -> dict:
    lat = state.get("resolved_lat")
    lng = state.get("resolved_lng")

    if lat is None or lng is None:
        return {
            "parcel_id": None,
            "county": None,
            "muni": None,
            "parcel_geojson": None,
            "parcel_fallback": False,
        }

    try:
        pool = await get_pool()
    except RuntimeError:
        return {
            "parcel_id": None,
            "county": None,
            "muni": None,
            "parcel_geojson": None,
            "parcel_fallback": False,
        }

    async with pool.acquire() as conn:
        # ST_MakePoint takes (longitude, latitude)
        row = await conn.fetchrow(_POINT_QUERY, lng, lat)

        fallback = False
        if row is None:
            row = await conn.fetchrow(_BUFFER_QUERY, lng, lat)
            fallback = True

    if row is None:
        return {
            "parcel_id": None,
            "county": None,
            "muni": None,
            "parcel_geojson": None,
            "parcel_fallback": fallback,
        }

    return {
        "parcel_id": row["print_key"],
        "county": row["county"],
        "muni": row["muni"],
        "parcel_geojson": row["geojson"],
        "parcel_fallback": fallback,
    }
