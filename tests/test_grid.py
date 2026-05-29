from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.nodes.grid import check_grid_proximity

_BASE_STATE = {
    "address": None,
    "lat": None,
    "lng": None,
    "resolved_lat": 42.6526,
    "resolved_lng": -73.7562,
    "parcel_id": "110.00-3-15",
    "county": "Albany",
    "muni": "Albany",
    "parcel_geojson": None,
    "parcel_fallback": False,
    "nearest_transmission_miles": None,
    "transmission_band": None,
    "nearest_substation_miles": None,
    "nearest_substations": [],
    "grid_data_available": False,
}


def _state(**overrides):
    return {**_BASE_STATE, **overrides}


def _make_pool(trans_row, sub_rows):
    """Build a mock asyncpg pool that returns the given rows."""
    conn = MagicMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)

    conn.fetchval = AsyncMock(return_value="POINT(-73.7562 42.6526)")
    conn.fetchrow = AsyncMock(return_value=trans_row)
    conn.fetch = AsyncMock(return_value=sub_rows)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)
    return pool


def _trans_row(meters: float):
    row = MagicMock()
    row.__getitem__ = lambda self, k: meters / 1609.344 if k == "miles" else None
    return row


def _sub_row(sub_id, name, meters):
    row = MagicMock()

    def getitem(self, k):
        return {"id": sub_id, "name": name, "miles": meters / 1609.344}[k]

    row.__getitem__ = getitem
    return row


@pytest.mark.asyncio
async def test_happy_path_returns_distances_and_substations():
    trans = _trans_row(1609.344)  # exactly 1 mile
    subs = [
        _sub_row(1, "Albany Sub A", 3218.688),   # 2 miles
        _sub_row(2, "Albany Sub B", 4828.032),   # 3 miles
        _sub_row(3, "Albany Sub C", 8046.720),   # 5 miles
    ]
    pool = _make_pool(trans, subs)

    with patch("app.nodes.grid.get_pool", AsyncMock(return_value=pool)):
        result = await check_grid_proximity(_state())

    assert result["grid_data_available"] is True
    assert result["nearest_transmission_miles"] == pytest.approx(1.0, rel=1e-3)
    assert result["transmission_band"] == "strong positive"
    assert result["nearest_substation_miles"] == pytest.approx(2.0, rel=1e-3)
    assert len(result["nearest_substations"]) == 3
    assert result["nearest_substations"][0]["name"] == "Albany Sub A"
    assert result["nearest_substations"][0]["miles"] == pytest.approx(2.0, rel=1e-3)


@pytest.mark.asyncio
async def test_transmission_band_thresholds():
    bands = [
        (1609.0, "strong positive"),   # just under 1 mile
        (8046.720, "neutral"),          # 5 miles
        (16093.440, "mild negative"),   # 10 miles
        (20000.0, "strong negative"),   # > 10 miles
    ]
    subs = [_sub_row(1, "S", 1000), _sub_row(2, "S", 2000), _sub_row(3, "S", 3000)]

    for meters, expected_band in bands:
        pool = _make_pool(_trans_row(meters), subs)
        with patch("app.nodes.grid.get_pool", AsyncMock(return_value=pool)):
            result = await check_grid_proximity(_state())
        assert result["transmission_band"] == expected_band, f"failed at {meters}m"


@pytest.mark.asyncio
async def test_degrades_when_get_pool_raises():
    with patch("app.nodes.grid.get_pool", AsyncMock(side_effect=RuntimeError("no db"))):
        result = await check_grid_proximity(_state())

    assert result["grid_data_available"] is False
    assert result["nearest_transmission_miles"] is None
    assert result["nearest_substations"] == []


@pytest.mark.asyncio
async def test_degrades_when_no_transmission_rows():
    pool = _make_pool(None, [])
    with patch("app.nodes.grid.get_pool", AsyncMock(return_value=pool)):
        result = await check_grid_proximity(_state())

    assert result["grid_data_available"] is False


@pytest.mark.asyncio
async def test_degrades_when_no_resolved_coords():
    s = _state(resolved_lat=None, resolved_lng=None, parcel_geojson=None)
    with patch("app.nodes.grid.get_pool", AsyncMock(side_effect=AssertionError("should not reach db"))):
        result = await check_grid_proximity(s)

    assert result["grid_data_available"] is False


@pytest.mark.asyncio
async def test_degrades_on_db_exception():
    conn = MagicMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    conn.fetchval = AsyncMock(side_effect=Exception("table does not exist"))
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)

    with patch("app.nodes.grid.get_pool", AsyncMock(return_value=pool)):
        result = await check_grid_proximity(_state())

    assert result["grid_data_available"] is False
