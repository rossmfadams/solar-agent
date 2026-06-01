"""Unit tests for research_local_ordinance.

All tests run without a real DB or real Anthropic API key.  The two mockable
seams are:
  - app.nodes.ordinance.get_pool  (DB / cache layer)
  - app.nodes.ordinance._research_tier  (LLM / web-search call per tier)

The nested sub-graph (_ordinance_subgraph) is exercised indirectly through
the parent node so the conditional-edge loop is covered by real LangGraph
execution rather than mock-only assertions.
"""
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.nodes.ordinance import research_local_ordinance, TIERS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_state(**overrides):
    return {
        "address": None,
        "lat": None,
        "lng": None,
        "resolved_lat": 43.1,
        "resolved_lng": -76.2,
        "parcel_id": "100.00-1-1",
        "county": "Niagara",
        "muni": "Cambria",
        "parcel_geojson": None,
        "parcel_fallback": False,
        **overrides,
    }


def _make_pool(fetchrow_result=None):
    """Build a mock asyncpg pool for cache read (fetchrow) and write (execute)."""
    conn = MagicMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    conn.fetchrow = AsyncMock(return_value=fetchrow_result)
    conn.execute = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)
    return pool, conn


def _cache_row(
    found: bool = True,
    moratorium_active: bool = False,
    days_old: int = 5,
):
    """Build a mock DB row as returned by _read_cache."""
    row = MagicMock()
    retrieval = date.today() - timedelta(days=days_old)

    def getitem(self, k):  # noqa: ANN001
        values = {
            "found": found,
            "source_name": "eCode360",
            "source_url": "https://ecode360.com/CA1234",
            "document_section": "Chapter 216, § 216-4",
            "setbacks": "300 ft from property lines",
            "sup_requirements": "SUP required",
            "moratorium_active": moratorium_active,
            "moratorium_section": "Local Law No. 2, § 1" if moratorium_active else None,
            "moratorium_quote": "No solar applications shall be accepted." if moratorium_active else None,
            "summary": "Test summary",
            "retrieved_at": retrieval,
        }
        return values[k]

    row.__getitem__ = getitem
    return row


def _live_result(moratorium_active: bool = False) -> dict:
    return {
        "found": True,
        "source": "Municode",
        "url": "https://library.municode.com/ny/barton",
        "section": "§ 215-102",
        "setbacks": "150 ft from property lines",
        "sup_requirements": "SUP required for systems > 25 kW",
        "moratorium_active": moratorium_active,
        "moratorium_section": "§ 1 Local Law" if moratorium_active else None,
        "moratorium_quote": "No applications shall be accepted." if moratorium_active else None,
        "summary": "Barton solar ordinance",
    }


# ---------------------------------------------------------------------------
# Cache hit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fresh_cache_hit_returns_without_live_call():
    """A fresh cache row is returned immediately; _research_tier is never called."""
    pool, conn = _make_pool(fetchrow_result=_cache_row(days_old=3))

    with (
        patch("app.nodes.ordinance.get_pool", AsyncMock(return_value=pool)),
        patch("app.nodes.ordinance._research_tier", AsyncMock()) as mock_tier,
    ):
        result = await research_local_ordinance(_base_state())

    mock_tier.assert_not_called()
    assert result["ordinance_available"] is True
    assert result["ordinance_found"] is True
    assert result["ordinance_source"] == "eCode360"
    assert result["ordinance_moratorium_active"] is False


@pytest.mark.asyncio
async def test_fresh_cache_hit_with_moratorium():
    pool, _ = _make_pool(fetchrow_result=_cache_row(moratorium_active=True, days_old=1))

    with (
        patch("app.nodes.ordinance.get_pool", AsyncMock(return_value=pool)),
        patch("app.nodes.ordinance._research_tier", AsyncMock()),
    ):
        result = await research_local_ordinance(_base_state())

    assert result["ordinance_moratorium_active"] is True
    assert result["ordinance_moratorium_section"] is not None
    assert result["ordinance_moratorium_quote"] is not None


# ---------------------------------------------------------------------------
# Cache miss → live research
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_miss_triggers_live_research_and_write_through():
    """On a cache miss the live sub-graph runs and the result is written back."""
    pool, conn = _make_pool(fetchrow_result=None)

    with (
        patch("app.nodes.ordinance.get_pool", AsyncMock(return_value=pool)),
        patch("app.nodes.ordinance._research_tier", AsyncMock(return_value=_live_result())) as mock_tier,
    ):
        result = await research_local_ordinance(_base_state(muni="Barton", county="Tioga"))

    # _research_tier called at least once (for tier 0 — eCode360)
    mock_tier.assert_called()
    # Write-through executed
    conn.execute.assert_called_once()
    assert result["ordinance_available"] is True
    assert result["ordinance_found"] is True
    assert result["ordinance_source"] == "Municode"
    assert result["ordinance_retrieval_date"] == date.today().isoformat()


@pytest.mark.asyncio
async def test_live_result_with_moratorium_propagated_to_state():
    pool, _ = _make_pool(fetchrow_result=None)

    with (
        patch("app.nodes.ordinance.get_pool", AsyncMock(return_value=pool)),
        patch("app.nodes.ordinance._research_tier", AsyncMock(return_value=_live_result(moratorium_active=True))),
    ):
        result = await research_local_ordinance(_base_state())

    assert result["ordinance_moratorium_active"] is True
    assert result["ordinance_moratorium_section"] is not None
    assert result["ordinance_moratorium_quote"] is not None


# ---------------------------------------------------------------------------
# Tier fallthrough — conditional-edge loop in the nested sub-graph
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tier_fallthrough_stops_at_first_hit():
    """Tier 0 miss, tier 1 hit → result uses tier-1 source; sub-graph stops there."""
    pool, _ = _make_pool(fetchrow_result=None)

    # Side-effects: tier 0 (eCode360) returns None, tier 1 (Municode) returns a hit
    tier_side_effects = [None, _live_result()]

    with (
        patch("app.nodes.ordinance.get_pool", AsyncMock(return_value=pool)),
        patch(
            "app.nodes.ordinance._research_tier",
            AsyncMock(side_effect=tier_side_effects),
        ) as mock_tier,
    ):
        result = await research_local_ordinance(_base_state())

    # Called exactly twice (tier 0 miss, tier 1 hit)
    assert mock_tier.call_count == 2
    # Tier 1 is Municode — verify the tier argument
    _, kwargs_tier1 = mock_tier.call_args_list[1]
    assert mock_tier.call_args_list[1].args[2].name == "Municode"
    assert result["ordinance_found"] is True


@pytest.mark.asyncio
async def test_all_tiers_exhausted_returns_available_but_not_found():
    """When every tier returns None the node signals 'searched but not found'."""
    pool, conn = _make_pool(fetchrow_result=None)

    with (
        patch("app.nodes.ordinance.get_pool", AsyncMock(return_value=pool)),
        patch(
            "app.nodes.ordinance._research_tier",
            AsyncMock(return_value=None),
        ) as mock_tier,
    ):
        result = await research_local_ordinance(_base_state())

    assert mock_tier.call_count == len(TIERS)
    assert result["ordinance_available"] is True
    assert result["ordinance_found"] is False
    # Negative result is also written to cache
    conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_tiers_found_false_treated_as_miss_and_falls_through():
    """Claude returning found=False triggers the next tier, not a found result."""
    pool, _ = _make_pool(fetchrow_result=None)

    not_found = {"found": False, "moratorium_active": False}
    side_effects = [not_found, not_found, _live_result(), None]

    with (
        patch("app.nodes.ordinance.get_pool", AsyncMock(return_value=pool)),
        patch(
            "app.nodes.ordinance._research_tier",
            AsyncMock(side_effect=side_effects),
        ) as mock_tier,
    ):
        result = await research_local_ordinance(_base_state())

    # Stopped at tier 2 (Town website) which returned a result
    assert mock_tier.call_count == 3
    assert result["ordinance_found"] is True


# ---------------------------------------------------------------------------
# Moratorium discipline
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_moratorium_false_when_only_restrictive_setbacks():
    """A restrictive ordinance (large setbacks, SUP) must NOT set moratorium_active."""
    pool, _ = _make_pool(fetchrow_result=None)
    restrictive = {
        "found": True,
        "source": "eCode360",
        "url": "https://ecode360.com/PO9999",
        "section": "§ 200-18.1",
        "setbacks": "300 ft from all property lines; 750 ft from dwellings",
        "sup_requirements": "SUP required",
        "moratorium_active": False,  # restrictive ≠ moratorium
        "moratorium_section": None,
        "moratorium_quote": None,
        "summary": "Restrictive but legal ordinance",
    }

    with (
        patch("app.nodes.ordinance.get_pool", AsyncMock(return_value=pool)),
        patch("app.nodes.ordinance._research_tier", AsyncMock(return_value=restrictive)),
    ):
        result = await research_local_ordinance(_base_state())

    assert result["ordinance_moratorium_active"] is False
    assert result["ordinance_setbacks"] == "300 ft from all property lines; 750 ft from dwellings"
    assert result["ordinance_found"] is True


@pytest.mark.asyncio
async def test_moratorium_requires_section_and_quote():
    """moratorium_active=True is propagated only when section+quote are present."""
    pool, _ = _make_pool(fetchrow_result=None)
    with_moratorium = {
        "found": True,
        "source": "eCode360",
        "url": "https://ecode360.com/CA1234",
        "section": "Local Law No. 2 of 2023, § 1",
        "setbacks": "300 ft from property lines",
        "sup_requirements": "SUP required",
        "moratorium_active": True,
        "moratorium_section": "Local Law No. 2 of 2023, § 1",
        "moratorium_quote": (
            "A moratorium is hereby declared on the acceptance of applications "
            "for solar energy systems."
        ),
        "summary": "Active moratorium",
    }

    with (
        patch("app.nodes.ordinance.get_pool", AsyncMock(return_value=pool)),
        patch("app.nodes.ordinance._research_tier", AsyncMock(return_value=with_moratorium)),
    ):
        result = await research_local_ordinance(_base_state())

    assert result["ordinance_moratorium_active"] is True
    assert result["ordinance_moratorium_section"] == "Local Law No. 2 of 2023, § 1"
    assert "moratorium is hereby declared" in result["ordinance_moratorium_quote"]


# ---------------------------------------------------------------------------
# Degradation paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_degrades_when_muni_missing():
    result = await research_local_ordinance(_base_state(muni=None))

    assert result["ordinance_available"] is False
    assert result["ordinance_found"] is False
    assert result["ordinance_retrieval_date"] is None


@pytest.mark.asyncio
async def test_degrades_when_get_pool_raises_runtime_error():
    """DATABASE_URL not set: cache is skipped; live research also degrades gracefully."""
    with (
        patch("app.nodes.ordinance.get_pool", AsyncMock(side_effect=RuntimeError("no db"))),
        patch("app.nodes.ordinance._research_tier", AsyncMock(return_value=_live_result())) as mock_tier,
    ):
        result = await research_local_ordinance(_base_state())

    # Live research still ran (cache failure is non-fatal)
    mock_tier.assert_called()
    assert result["ordinance_available"] is True
    assert result["ordinance_found"] is True


@pytest.mark.asyncio
async def test_degrades_when_research_tier_always_raises():
    """Broad exception in _research_tier returns _DEGRADED from the parent node."""
    pool, _ = _make_pool(fetchrow_result=None)

    with (
        patch("app.nodes.ordinance.get_pool", AsyncMock(return_value=pool)),
        patch(
            "app.nodes.ordinance._research_tier",
            AsyncMock(side_effect=Exception("api down")),
        ),
    ):
        result = await research_local_ordinance(_base_state())

    # All tiers return None (exception → None inside _try_tier_node via _research_tier)
    # so the node returns available=True, found=False (searched, nothing found)
    assert result["ordinance_available"] is True
    assert result["ordinance_found"] is False


@pytest.mark.asyncio
async def test_degrades_gracefully_on_subgraph_exception():
    """If the sub-graph itself raises, the parent node returns _DEGRADED."""
    pool, _ = _make_pool(fetchrow_result=None)

    with (
        patch("app.nodes.ordinance.get_pool", AsyncMock(return_value=pool)),
        patch(
            "app.nodes.ordinance._ordinance_subgraph",
        ) as mock_sg,
    ):
        mock_sg.ainvoke = AsyncMock(side_effect=Exception("graph error"))
        result = await research_local_ordinance(_base_state())

    assert result["ordinance_available"] is False
