import pytest

from app.nodes.bounds import is_within_ny, validate_ny_bounds


@pytest.mark.parametrize(
    "lat,lng,expected",
    [
        (42.6526, -73.7562, True),  # Albany, NY
        (40.7128, -74.0060, True),  # NYC
        (39.9612, -82.9988, False),  # Columbus, OH
        (42.3601, -71.0589, False),  # Boston, MA
        (None, -73.7562, False),
        (42.6526, None, False),
    ],
)
def test_is_within_ny(lat, lng, expected):
    assert is_within_ny(lat, lng) is expected


async def test_validate_ny_bounds_node_flags_out_of_state():
    result = await validate_ny_bounds({"resolved_lat": 39.9612, "resolved_lng": -82.9988})
    assert result == {"out_of_ny_bounds": True}


async def test_validate_ny_bounds_node_passes_ny_site():
    result = await validate_ny_bounds({"resolved_lat": 42.6526, "resolved_lng": -73.7562})
    assert result == {"out_of_ny_bounds": False}
