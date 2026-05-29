import asyncio

from geopy.geocoders import Nominatim

_geolocator = Nominatim(user_agent="helios-solar-agent/1.0")


async def geocode_address(state: dict) -> dict:
    if state.get("lat") is not None and state.get("lng") is not None:
        return {"resolved_lat": state["lat"], "resolved_lng": state["lng"]}

    address = state.get("address")
    if not address:
        return {"resolved_lat": None, "resolved_lng": None}

    location = await asyncio.to_thread(_geolocator.geocode, address)
    if location is None:
        return {"resolved_lat": None, "resolved_lng": None}

    return {"resolved_lat": location.latitude, "resolved_lng": location.longitude}
