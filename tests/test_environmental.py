from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.nodes.environmental import check_environmental_constraints

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
    "environmental_data_available": False,
}


def _state(**overrides):
    return {**_BASE_STATE, **overrides}


def _make_pool(flood_rows, nwi_row, padus_row):
    """Build a mock asyncpg pool returning the given environmental query results."""
    conn = MagicMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)

    # fetchval is used to build the parcel geometry
    conn.fetchval = AsyncMock(return_value="mock-geom")

    # fetch → flood rows; fetchrow alternates NWI then PAD-US
    conn.fetch = AsyncMock(return_value=flood_rows)
    conn.fetchrow = AsyncMock(side_effect=[nwi_row, padus_row])

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)
    return pool


def _flood_row(fld_zone, zone_subty=""):
    row = MagicMock()
    row.__getitem__ = lambda self, k: {"fld_zone": fld_zone, "zone_subty": zone_subty}[k]
    return row


def _nwi_row(wetland_type="Freshwater Emergent Wetland"):
    row = MagicMock()
    row.__getitem__ = lambda self, k: wetland_type if k == "wetland_type" else None
    return row


def _padus_row(unit_nm="Adirondack Park"):
    row = MagicMock()
    row.__getitem__ = lambda self, k: unit_nm if k == "unit_nm" else None
    return row


# ---------------------------------------------------------------------------
# Flood zone classification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_flood_zone_ae_classified_severe():
    pool = _make_pool([_flood_row("AE")], None, None)
    with patch("app.nodes.environmental.get_pool", AsyncMock(return_value=pool)):
        result = await check_environmental_constraints(_state())
    assert result["environmental_data_available"] is True
    assert result["flood_zone"] == "AE/AH/AO/VE"


@pytest.mark.asyncio
async def test_flood_zone_ve_classified_severe():
    pool = _make_pool([_flood_row("VE")], None, None)
    with patch("app.nodes.environmental.get_pool", AsyncMock(return_value=pool)):
        result = await check_environmental_constraints(_state())
    assert result["flood_zone"] == "AE/AH/AO/VE"


@pytest.mark.asyncio
async def test_flood_zone_x_shaded_classified_moderate():
    pool = _make_pool([_flood_row("X", "0.2 PCT ANNUAL CHANCE FLOOD HAZARD")], None, None)
    with patch("app.nodes.environmental.get_pool", AsyncMock(return_value=pool)):
        result = await check_environmental_constraints(_state())
    assert result["flood_zone"] == "X (shaded)"


@pytest.mark.asyncio
async def test_flood_zone_x_unshaded_classified_minimal():
    pool = _make_pool([_flood_row("X", "")], None, None)
    with patch("app.nodes.environmental.get_pool", AsyncMock(return_value=pool)):
        result = await check_environmental_constraints(_state())
    assert result["flood_zone"] == "X (unshaded)"


@pytest.mark.asyncio
async def test_flood_zone_none_when_no_overlap():
    pool = _make_pool([], None, None)
    with patch("app.nodes.environmental.get_pool", AsyncMock(return_value=pool)):
        result = await check_environmental_constraints(_state())
    assert result["flood_zone"] == "none"


@pytest.mark.asyncio
async def test_flood_zone_worst_wins_ae_over_x():
    """When a parcel overlaps both AE and X zones, AE/AH/AO/VE is returned."""
    pool = _make_pool([_flood_row("X", ""), _flood_row("AE")], None, None)
    with patch("app.nodes.environmental.get_pool", AsyncMock(return_value=pool)):
        result = await check_environmental_constraints(_state())
    assert result["flood_zone"] == "AE/AH/AO/VE"


# ---------------------------------------------------------------------------
# NWI wetlands overlap
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nwi_overlap_true_when_wetland_found():
    pool = _make_pool([], _nwi_row("Freshwater Emergent Wetland"), None)
    with patch("app.nodes.environmental.get_pool", AsyncMock(return_value=pool)):
        result = await check_environmental_constraints(_state())
    assert result["nwi_overlap"] is True
    assert result["nwi_wetland_type"] == "Freshwater Emergent Wetland"


@pytest.mark.asyncio
async def test_nwi_overlap_false_when_no_wetland():
    pool = _make_pool([], None, None)
    with patch("app.nodes.environmental.get_pool", AsyncMock(return_value=pool)):
        result = await check_environmental_constraints(_state())
    assert result["nwi_overlap"] is False
    assert result["nwi_wetland_type"] is None


# ---------------------------------------------------------------------------
# PAD-US protected lands overlap
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_padus_overlap_true_when_protected_area_found():
    pool = _make_pool([], None, _padus_row("Adirondack Park"))
    with patch("app.nodes.environmental.get_pool", AsyncMock(return_value=pool)):
        result = await check_environmental_constraints(_state())
    assert result["padus_overlap"] is True
    assert result["padus_unit_name"] == "Adirondack Park"


@pytest.mark.asyncio
async def test_padus_overlap_false_when_no_protected_area():
    pool = _make_pool([], None, None)
    with patch("app.nodes.environmental.get_pool", AsyncMock(return_value=pool)):
        result = await check_environmental_constraints(_state())
    assert result["padus_overlap"] is False
    assert result["padus_unit_name"] is None


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_degrades_when_get_pool_raises():
    with patch("app.nodes.environmental.get_pool", AsyncMock(side_effect=RuntimeError("no db"))):
        result = await check_environmental_constraints(_state())
    assert result["environmental_data_available"] is False
    assert result["flood_zone"] is None
    assert result["nwi_overlap"] is None
    assert result["padus_overlap"] is None


@pytest.mark.asyncio
async def test_degrades_when_no_resolved_coords():
    s = _state(resolved_lat=None, resolved_lng=None, parcel_geojson=None)
    with patch("app.nodes.environmental.get_pool", AsyncMock(side_effect=AssertionError("should not reach db"))):
        result = await check_environmental_constraints(s)
    assert result["environmental_data_available"] is False


@pytest.mark.asyncio
async def test_degrades_on_db_exception():
    conn = MagicMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    conn.fetchval = AsyncMock(side_effect=Exception("table does not exist"))
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)

    with patch("app.nodes.environmental.get_pool", AsyncMock(return_value=pool)):
        result = await check_environmental_constraints(_state())

    assert result["environmental_data_available"] is False


@pytest.mark.asyncio
async def test_degrades_when_parcel_geom_is_null():
    conn = MagicMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    conn.fetchval = AsyncMock(return_value=None)  # geometry returns NULL
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)

    with patch("app.nodes.environmental.get_pool", AsyncMock(return_value=pool)):
        result = await check_environmental_constraints(_state())

    assert result["environmental_data_available"] is False


@pytest.mark.asyncio
async def test_uses_parcel_geojson_when_present():
    """Node should call ST_GeomFromGeoJSON when parcel_geojson is available."""
    conn = MagicMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    conn.fetchval = AsyncMock(return_value="mock-geom")
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(side_effect=[None, None])
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)

    geojson = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}
    s = _state(parcel_geojson=geojson)

    with patch("app.nodes.environmental.get_pool", AsyncMock(return_value=pool)):
        result = await check_environmental_constraints(s)

    assert result["environmental_data_available"] is True
    # Confirm ST_GeomFromGeoJSON was called (not the point fallback)
    call_sql = conn.fetchval.call_args[0][0]
    assert "ST_GeomFromGeoJSON" in call_sql
