import json

from app.db import get_pool

# Flood zone classes, worst-first ordering for overlap resolution.
# FEMA zone codes that trigger the -20 deduction.
_SEVERE_ZONES = {"AE", "AH", "AO", "VE", "A", "V"}

_FLOOD_QUERY = """
SELECT fld_zone, zone_subty
FROM flood_zones
WHERE ST_Intersects(geom, $1::geometry)
"""

_NWI_QUERY = """
SELECT wetland_type
FROM wetlands
WHERE ST_Intersects(geom, $1::geometry)
LIMIT 1
"""

_PADUS_QUERY = """
SELECT unit_nm
FROM protected_areas
WHERE ST_Intersects(geom, $1::geometry)
LIMIT 1
"""

_DEGRADED = {
    "flood_zone": None,
    "nwi_overlap": None,
    "nwi_wetland_type": None,
    "padus_overlap": None,
    "padus_unit_name": None,
    "environmental_data_available": False,
}


def _classify_flood(rows) -> str:
    """Return the worst flood zone classification from a list of FEMA zone rows."""
    if not rows:
        return "none"
    zones = {r["fld_zone"].strip().upper() for r in rows if r["fld_zone"]}
    subtypes = {(r["zone_subty"] or "").upper() for r in rows}

    # Severe: AE, AH, AO, VE (also plain A / V)
    if zones & _SEVERE_ZONES:
        return "AE/AH/AO/VE"

    # Zone X shaded = 0.2 PCT annual chance (moderate risk)
    for subty in subtypes:
        if "0.2 PCT" in subty or "SHADED" in subty:
            return "X (shaded)"

    # Any remaining X zones are unshaded (minimal risk)
    if any(z.startswith("X") for z in zones):
        return "X (unshaded)"

    return "none"


async def check_environmental_constraints(state: dict) -> dict:
    """Query flood zones, NWI wetlands, and PAD-US protected areas for the parcel."""
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
                parcel_geom = await conn.fetchval(
                    "SELECT ST_SetSRID(ST_MakePoint($1, $2), 4326)", lng, lat
                )

            if parcel_geom is None:
                return _DEGRADED

            flood_rows = await conn.fetch(_FLOOD_QUERY, parcel_geom)
            nwi_row = await conn.fetchrow(_NWI_QUERY, parcel_geom)
            padus_row = await conn.fetchrow(_PADUS_QUERY, parcel_geom)

    except Exception:
        return _DEGRADED

    return {
        "flood_zone": _classify_flood(flood_rows),
        "nwi_overlap": nwi_row is not None,
        "nwi_wetland_type": nwi_row["wetland_type"] if nwi_row else None,
        "padus_overlap": padus_row is not None,
        "padus_unit_name": padus_row["unit_nm"] if padus_row else None,
        "environmental_data_available": True,
    }
