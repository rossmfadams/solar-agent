import json

import folium

from app.db import get_pool

_TRANS_QUERY = """
SELECT ST_AsGeoJSON(geom) AS geojson
FROM transmission_lines
ORDER BY geom <-> $1
LIMIT 1
"""

_SUB_QUERY = """
SELECT ST_AsGeoJSON(geom) AS geojson, name
FROM substations
ORDER BY geom <-> $1
LIMIT 3
"""

_FLOOD_QUERY = """
SELECT ST_AsGeoJSON(geom) AS geojson
FROM flood_zones
WHERE ST_Intersects(geom, $1)
"""

_NWI_QUERY = """
SELECT ST_AsGeoJSON(geom) AS geojson
FROM wetlands
WHERE ST_Intersects(geom, $1)
"""

_PADUS_QUERY = """
SELECT ST_AsGeoJSON(geom) AS geojson
FROM protected_areas
WHERE ST_Intersects(geom, $1)
"""


async def fetch_map_layers(parcel_geojson, lat: float | None, lng: float | None) -> dict:
    try:
        pool = await get_pool()
    except RuntimeError:
        return _empty_layers(lat, lng, parcel_geojson)

    try:
        async with pool.acquire() as conn:
            if parcel_geojson is not None:
                geojson_str = (
                    parcel_geojson
                    if isinstance(parcel_geojson, str)
                    else json.dumps(parcel_geojson)
                )
                query_geom = await conn.fetchval(
                    "SELECT ST_GeomFromGeoJSON($1)", geojson_str
                )
                center = await conn.fetchrow(
                    "SELECT ST_Y(ST_Centroid(ST_GeomFromGeoJSON($1))) AS lat,"
                    "       ST_X(ST_Centroid(ST_GeomFromGeoJSON($1))) AS lng",
                    geojson_str,
                )
                center_lat = center["lat"] if center else lat
                center_lng = center["lng"] if center else lng
            else:
                query_geom = await conn.fetchval(
                    "SELECT ST_SetSRID(ST_MakePoint($1, $2), 4326)", lng, lat
                )
                center_lat, center_lng = lat, lng

            if query_geom is None:
                return _empty_layers(lat, lng, parcel_geojson)

            trans_row = await conn.fetchrow(_TRANS_QUERY, query_geom)
            sub_rows = await conn.fetch(_SUB_QUERY, query_geom)
            flood_rows = await conn.fetch(_FLOOD_QUERY, query_geom)
            nwi_rows = await conn.fetch(_NWI_QUERY, query_geom)
            padus_rows = await conn.fetch(_PADUS_QUERY, query_geom)

    except Exception:
        return _empty_layers(lat, lng, parcel_geojson)

    def _parse(rows):
        return [json.loads(r["geojson"]) for r in rows if r and r["geojson"]]

    return {
        "center_lat": center_lat,
        "center_lng": center_lng,
        "parcel": parcel_geojson,
        "transmission": _parse([trans_row] if trans_row else []),
        "substations": _parse(sub_rows),
        "flood": _parse(flood_rows),
        "nwi": _parse(nwi_rows),
        "padus": _parse(padus_rows),
    }


def _empty_layers(lat, lng, parcel_geojson) -> dict:
    return {
        "center_lat": lat or 42.65,
        "center_lng": lng or -73.75,
        "parcel": parcel_geojson,
        "transmission": [],
        "substations": [],
        "flood": [],
        "nwi": [],
        "padus": [],
    }


def render_map(layers: dict, parcel_fallback: bool) -> str:
    center_lat = layers.get("center_lat") or 42.65
    center_lng = layers.get("center_lng") or -73.75

    m = folium.Map(location=[center_lat, center_lng], zoom_start=15)

    # Parcel boundary
    parcel_group = folium.FeatureGroup(name="Parcel Boundary")
    parcel_geojson = layers.get("parcel")
    if parcel_geojson is not None:
        if parcel_fallback:
            tooltip = "Estimated 500m buffer — no parcel polygon"
            style_fn = lambda x: {"color": "#ff7800", "weight": 2, "fillOpacity": 0.1, "dashArray": "6,4"}
        else:
            tooltip = "Parcel boundary"
            style_fn = lambda x: {"color": "#3388ff", "weight": 2, "fillOpacity": 0.1}
        folium.GeoJson(parcel_geojson, style_function=style_fn, tooltip=tooltip).add_to(parcel_group)
    parcel_group.add_to(m)

    # Transmission lines
    trans_group = folium.FeatureGroup(name="HIFLD — Electric Power Transmission Lines")
    for feat in layers.get("transmission", []):
        folium.GeoJson(
            feat,
            style_function=lambda x: {"color": "red", "weight": 2},
            tooltip="HIFLD — Electric Power Transmission Lines",
        ).add_to(trans_group)
    trans_group.add_to(m)

    # Substations
    sub_group = folium.FeatureGroup(name="HIFLD — Electric Substations")
    for feat in layers.get("substations", []):
        folium.GeoJson(
            feat,
            tooltip="HIFLD — Electric Substations",
        ).add_to(sub_group)
    sub_group.add_to(m)

    # FEMA flood zones
    flood_group = folium.FeatureGroup(name="FEMA National Flood Hazard Layer")
    for feat in layers.get("flood", []):
        folium.GeoJson(
            feat,
            style_function=lambda x: {"color": "purple", "fillOpacity": 0.3},
            tooltip="FEMA National Flood Hazard Layer",
        ).add_to(flood_group)
    flood_group.add_to(m)

    # NWI wetlands
    nwi_group = folium.FeatureGroup(name="USFWS National Wetlands Inventory")
    for feat in layers.get("nwi", []):
        folium.GeoJson(
            feat,
            style_function=lambda x: {"color": "green", "fillOpacity": 0.3},
            tooltip="USFWS National Wetlands Inventory",
        ).add_to(nwi_group)
    nwi_group.add_to(m)

    # PAD-US protected areas
    padus_group = folium.FeatureGroup(name="USGS Protected Areas Database (PAD-US)")
    for feat in layers.get("padus", []):
        folium.GeoJson(
            feat,
            style_function=lambda x: {"color": "darkgreen", "fillOpacity": 0.3},
            tooltip="USGS Protected Areas Database (PAD-US)",
        ).add_to(padus_group)
    padus_group.add_to(m)

    folium.LayerControl().add_to(m)

    return m.get_root().render()
