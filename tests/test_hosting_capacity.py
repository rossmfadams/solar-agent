from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.nodes.hosting_capacity import check_hosting_capacity

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
    "nearest_transmission_miles": 0.8,
    "transmission_band": "strong positive",
    "nearest_substation_miles": 1.5,
    "nearest_substations": [
        {"id": 1, "name": "Albany Sub A", "miles": 1.5},
        {"id": 2, "name": "Albany Sub B", "miles": 2.3},
        {"id": 3, "name": "Albany Sub C", "miles": 4.1},
    ],
    "grid_data_available": True,
    "interconnection_capacity_proxy_mw": None,
    "queue_match_rate": None,
    "nyiso_snapshot_date": None,
    "nyiso_retrieval_date": None,
    "hosting_capacity_available": False,
}


def _state(**overrides):
    return {**_BASE_STATE, **overrides}


def _make_pool(queue_row, meta_row):
    """Build a mock asyncpg pool returning the given rows."""
    conn = MagicMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    conn.fetchrow = AsyncMock(side_effect=[queue_row, meta_row])
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)
    return pool


def _queue_row(total_mw: float, county_mw: float = 0.0, n: int = 3):
    row = MagicMock()

    def getitem(self, k):
        return {"total_mw": total_mw, "county_mw": county_mw, "n_projects": n}[k]

    row.__getitem__ = getitem
    return row


def _meta_row(snapshot: str = "2025-01-15", retrieved: str = "2025-05-01"):
    from datetime import date

    row = MagicMock()

    def getitem(self, k):
        mapping = {
            "snapshot_date": date.fromisoformat(snapshot),
            "retrieved_at": date.fromisoformat(retrieved),
        }
        return mapping[k]

    row.__getitem__ = getitem
    return row


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_all_name_matched():
    """All MW matched by substation name → match_rate == 1.0."""
    pool = _make_pool(_queue_row(800.0, county_mw=0.0), _meta_row())

    with patch("app.nodes.hosting_capacity.get_pool", AsyncMock(return_value=pool)):
        result = await check_hosting_capacity(_state())

    assert result["hosting_capacity_available"] is True
    assert result["interconnection_capacity_proxy_mw"] == 800
    assert result["queue_match_rate"] == 1.0
    assert result["nyiso_snapshot_date"] == "2025-01-15"
    assert result["nyiso_retrieval_date"] == "2025-05-01"


@pytest.mark.asyncio
async def test_happy_path_partial_county_match():
    """Some MW via county fallback → match_rate reflects the split."""
    pool = _make_pool(_queue_row(1000.0, county_mw=200.0), _meta_row())

    with patch("app.nodes.hosting_capacity.get_pool", AsyncMock(return_value=pool)):
        result = await check_hosting_capacity(_state())

    assert result["hosting_capacity_available"] is True
    assert result["queue_match_rate"] == pytest.approx(0.8, rel=1e-3)


@pytest.mark.asyncio
async def test_zero_mw_in_radius():
    """No queued projects in 10-mile radius → 0 MW, hosting_capacity_available True."""
    pool = _make_pool(_queue_row(0.0, county_mw=0.0, n=0), _meta_row())

    with patch("app.nodes.hosting_capacity.get_pool", AsyncMock(return_value=pool)):
        result = await check_hosting_capacity(_state())

    assert result["hosting_capacity_available"] is True
    assert result["interconnection_capacity_proxy_mw"] == 0
    assert result["queue_match_rate"] == 1.0  # no MW → sentinel value


# ---------------------------------------------------------------------------
# MW band boundaries (values the synthesis slice will threshold on)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mw,expected_band_label",
    [
        (499, "<500 MW"),
        (500, "500-1500 MW"),
        (1500, "500-1500 MW"),
        (1501, ">1500 MW"),
    ],
)
async def test_mw_band_boundaries_return_correct_value(mw, expected_band_label):
    """Verify the raw MW value is returned correctly at each scoring threshold."""
    pool = _make_pool(_queue_row(float(mw)), _meta_row())

    with patch("app.nodes.hosting_capacity.get_pool", AsyncMock(return_value=pool)):
        result = await check_hosting_capacity(_state())

    assert result["hosting_capacity_available"] is True
    assert result["interconnection_capacity_proxy_mw"] == mw, (
        f"Expected {mw} MW for band {expected_band_label}, "
        f"got {result['interconnection_capacity_proxy_mw']}"
    )


# ---------------------------------------------------------------------------
# Degradation paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_degrades_when_grid_data_unavailable():
    s = _state(grid_data_available=False)
    with patch(
        "app.nodes.hosting_capacity.get_pool",
        AsyncMock(side_effect=AssertionError("should not reach db")),
    ):
        result = await check_hosting_capacity(s)

    assert result["hosting_capacity_available"] is False
    assert result["interconnection_capacity_proxy_mw"] is None


@pytest.mark.asyncio
async def test_degrades_when_nearest_substations_empty():
    s = _state(nearest_substations=[])
    with patch(
        "app.nodes.hosting_capacity.get_pool",
        AsyncMock(side_effect=AssertionError("should not reach db")),
    ):
        result = await check_hosting_capacity(s)

    assert result["hosting_capacity_available"] is False


@pytest.mark.asyncio
async def test_degrades_when_get_pool_raises():
    with patch(
        "app.nodes.hosting_capacity.get_pool",
        AsyncMock(side_effect=RuntimeError("DATABASE_URL not set")),
    ):
        result = await check_hosting_capacity(_state())

    assert result["hosting_capacity_available"] is False
    assert result["interconnection_capacity_proxy_mw"] is None


@pytest.mark.asyncio
async def test_degrades_when_nyiso_table_empty():
    """meta_row is None → nyiso_queue table is empty (not loaded yet)."""
    pool = _make_pool(_queue_row(500.0), None)

    with patch("app.nodes.hosting_capacity.get_pool", AsyncMock(return_value=pool)):
        result = await check_hosting_capacity(_state())

    assert result["hosting_capacity_available"] is False


@pytest.mark.asyncio
async def test_degrades_on_db_exception():
    conn = MagicMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    conn.fetchrow = AsyncMock(side_effect=Exception("relation nyiso_queue does not exist"))
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)

    with patch("app.nodes.hosting_capacity.get_pool", AsyncMock(return_value=pool)):
        result = await check_hosting_capacity(_state())

    assert result["hosting_capacity_available"] is False
