from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.nodes.terrain import check_terrain

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
    "terrain_data_available": False,
}


def _state(**overrides):
    return {**_BASE_STATE, **overrides}


def _make_pool(mean_slope):
    """Build a mock asyncpg pool returning a slope row."""
    conn = MagicMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)

    # fetchval builds the parcel geometry
    conn.fetchval = AsyncMock(return_value="mock-geom")

    # fetchrow returns the slope summary row
    if mean_slope is None:
        slope_row = None
    else:
        slope_row = MagicMock()
        slope_row.__getitem__ = lambda self, k: mean_slope if k == "mean_slope" else None

    conn.fetchrow = AsyncMock(return_value=slope_row)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)
    return pool


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_happy_path_returns_mean_slope():
    pool = _make_pool(3.75)
    with patch("app.nodes.terrain.get_pool", AsyncMock(return_value=pool)):
        result = await check_terrain(_state())
    assert result["terrain_data_available"] is True
    assert result["mean_slope_percent"] == pytest.approx(3.75, rel=1e-3)


@pytest.mark.asyncio
async def test_slope_rounded_to_two_decimal_places():
    pool = _make_pool(12.34567)
    with patch("app.nodes.terrain.get_pool", AsyncMock(return_value=pool)):
        result = await check_terrain(_state())
    assert result["mean_slope_percent"] == pytest.approx(12.35, rel=1e-2)


@pytest.mark.asyncio
async def test_uses_parcel_geojson_when_present():
    """Node calls ST_GeomFromGeoJSON path when parcel_geojson is provided."""
    pool = _make_pool(7.0)
    geojson = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}
    s = _state(parcel_geojson=geojson)
    with patch("app.nodes.terrain.get_pool", AsyncMock(return_value=pool)):
        result = await check_terrain(s)
    assert result["terrain_data_available"] is True
    conn = pool.acquire.return_value.__aenter__.return_value
    call_sql = conn.fetchval.call_args[0][0]
    assert "ST_GeomFromGeoJSON" in call_sql


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_degrades_when_get_pool_raises():
    with patch("app.nodes.terrain.get_pool", AsyncMock(side_effect=RuntimeError("no db"))):
        result = await check_terrain(_state())
    assert result["terrain_data_available"] is False
    assert result["mean_slope_percent"] is None


@pytest.mark.asyncio
async def test_degrades_when_no_resolved_coords():
    s = _state(resolved_lat=None, resolved_lng=None, parcel_geojson=None)
    with patch("app.nodes.terrain.get_pool", AsyncMock(side_effect=AssertionError("should not reach db"))):
        result = await check_terrain(s)
    assert result["terrain_data_available"] is False


@pytest.mark.asyncio
async def test_degrades_when_slope_row_is_none():
    """No DEM tiles intersect the parcel — fetchrow returns None."""
    pool = _make_pool(None)
    with patch("app.nodes.terrain.get_pool", AsyncMock(return_value=pool)):
        result = await check_terrain(_state())
    assert result["terrain_data_available"] is False


@pytest.mark.asyncio
async def test_degrades_when_slope_mean_is_null():
    """DEM tiles found but ST_SummaryStats returns NULL mean (empty raster)."""
    conn = MagicMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    conn.fetchval = AsyncMock(return_value="mock-geom")
    null_row = MagicMock()
    null_row.__getitem__ = lambda self, k: None  # mean_slope is NULL
    conn.fetchrow = AsyncMock(return_value=null_row)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)

    with patch("app.nodes.terrain.get_pool", AsyncMock(return_value=pool)):
        result = await check_terrain(_state())

    assert result["terrain_data_available"] is False


@pytest.mark.asyncio
async def test_degrades_on_db_exception():
    conn = MagicMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    conn.fetchval = AsyncMock(side_effect=Exception("dem table does not exist"))
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)

    with patch("app.nodes.terrain.get_pool", AsyncMock(return_value=pool)):
        result = await check_terrain(_state())

    assert result["terrain_data_available"] is False


@pytest.mark.asyncio
async def test_degrades_when_parcel_geom_is_null():
    conn = MagicMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    conn.fetchval = AsyncMock(return_value=None)  # geometry returns NULL
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)

    with patch("app.nodes.terrain.get_pool", AsyncMock(return_value=pool)):
        result = await check_terrain(_state())

    assert result["terrain_data_available"] is False
