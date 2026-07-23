# Coarse bounding box covering New York State, used to reject out-of-state
# sites before any paid/downstream API calls run. This is a bbox, not the
# state polygon, so it admits slivers of neighboring states near the border —
# acceptable for an early, cheap guard; the parcel lookup (NY-only data) is
# the real precision check downstream.
NY_MIN_LAT = 40.4
NY_MAX_LAT = 45.02
NY_MIN_LNG = -79.77
NY_MAX_LNG = -71.75


def is_within_ny(lat: float | None, lng: float | None) -> bool:
    if lat is None or lng is None:
        return False
    return NY_MIN_LAT <= lat <= NY_MAX_LAT and NY_MIN_LNG <= lng <= NY_MAX_LNG


async def validate_ny_bounds(state: dict) -> dict:
    lat = state.get("resolved_lat")
    lng = state.get("resolved_lng")
    return {"out_of_ny_bounds": not is_within_ny(lat, lng)}
