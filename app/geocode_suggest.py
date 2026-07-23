import os
from urllib.parse import quote

import httpx

from app.nodes.bounds import NY_MAX_LAT, NY_MAX_LNG, NY_MIN_LAT, NY_MIN_LNG

MAPBOX_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json"


def _mapbox_token() -> str | None:
    return os.environ.get("MAPBOX_TOKEN") or None


async def suggest_addresses(query: str) -> dict:
    token = _mapbox_token()
    if not token:
        return {"enabled": False, "suggestions": []}

    params = {
        "access_token": token,
        "bbox": f"{NY_MIN_LNG},{NY_MIN_LAT},{NY_MAX_LNG},{NY_MAX_LAT}",
        "country": "us",
        "types": "address",
        "limit": "5",
        "autocomplete": "true",
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = MAPBOX_URL.format(query=quote(query, safe=""))
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError):
        return {"enabled": True, "suggestions": []}

    suggestions = [
        {
            "label": feature.get("place_name", ""),
            "lng": feature.get("center", [None, None])[0],
            "lat": feature.get("center", [None, None])[1],
        }
        for feature in data.get("features", [])
    ]
    return {"enabled": True, "suggestions": suggestions}
