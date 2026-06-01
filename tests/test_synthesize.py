"""Unit tests for viability scoring helpers and synthesize_memo node.

No DB or real Anthropic API key required.  The mockable seam for the LLM call
is app.nodes.synthesize._get_client.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import (
    UNABLE_TO_VERIFY,
    _transmission_deduction,
    _queue_deduction,
    _flood_deduction,
    _slope_deduction,
    _stars_and_label,
    _build_hard_disqualifiers,
    _build_viability,
    _build_top_3_constraints,
)
from app.nodes.synthesize import synthesize_memo


# ---------------------------------------------------------------------------
# Deduction band helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("miles,expected", [
    (0.5, 0),
    (1.0, 0),
    (1.1, -10),
    (5.0, -10),
    (5.1, -20),
    (10.0, -20),
    (10.1, -35),
    (25.0, -35),
])
def test_transmission_deduction_bands(miles, expected):
    assert _transmission_deduction(miles) == expected


@pytest.mark.parametrize("mw,expected", [
    (None, 0),
    (0, 0),
    (499, 0),
    (500, -10),
    (1500, -10),
    (1501, -20),
    (3000, -20),
])
def test_queue_deduction_bands(mw, expected):
    assert _queue_deduction(mw) == expected


@pytest.mark.parametrize("zone,expected", [
    (None, 0),
    ("", 0),
    ("X", 0),
    ("X (Unshaded)", 0),
    ("none", 0),
    ("X (shaded)", -10),
    ("X (Shaded)", -10),
    ("AE", -20),
    ("AH", -20),
    ("AO", -20),
    ("VE", -20),
    ("AE/AH/AO/VE", -20),
])
def test_flood_deduction_bands(zone, expected):
    assert _flood_deduction(zone) == expected


@pytest.mark.parametrize("pct,expected", [
    (None, 0),
    (0.0, 0),
    (5.0, 0),
    (5.1, -8),
    (15.0, -8),
    (15.1, -15),
    (30.0, -15),
])
def test_slope_deduction_bands(pct, expected):
    assert _slope_deduction(pct) == expected


@pytest.mark.parametrize("score,stars,label", [
    (0, 0, "Hard Disqualified"),
    (1, 1, "Very Low"),
    (25, 1, "Very Low"),
    (26, 2, "Low"),
    (50, 2, "Low"),
    (51, 3, "Moderate"),
    (70, 3, "Moderate"),
    (71, 4, "Good"),
    (85, 4, "Good"),
    (86, 5, "Strong"),
    (100, 5, "Strong"),
])
def test_stars_and_label_all_bands(score, stars, label):
    s, l = _stars_and_label(score)
    assert s == stars
    assert l == label


# ---------------------------------------------------------------------------
# Hard disqualifiers — individual triggers
# ---------------------------------------------------------------------------

def _clean_env_state(**overrides):
    """Minimal state with environmental data available and nothing overlapping."""
    return {
        "environmental_data_available": True,
        "nwi_overlap": False,
        "nwi_wetland_type": None,
        "padus_overlap": False,
        "padus_unit_name": None,
        "ordinance_found": False,
        "ordinance_moratorium_active": False,
        "ordinance_moratorium_section": None,
        "ordinance_source": None,
        "ordinance_retrieval_date": None,
        **overrides,
    }


def test_hard_disqualifiers_nwi_triggers():
    state = _clean_env_state(nwi_overlap=True, nwi_wetland_type="Freshwater Emergent Wetland")
    result = _build_hard_disqualifiers(state)
    assert isinstance(result, list)
    assert len(result) == 1
    assert "NWI" in result[0].constraint
    assert "Freshwater Emergent Wetland" in result[0].constraint
    assert result[0].citation.source == "USFWS National Wetlands Inventory"


def test_hard_disqualifiers_padus_triggers():
    state = _clean_env_state(padus_overlap=True, padus_unit_name="Adirondack Park")
    result = _build_hard_disqualifiers(state)
    assert isinstance(result, list)
    assert len(result) == 1
    assert "PAD-US" in result[0].constraint
    assert "Adirondack Park" in result[0].constraint
    assert result[0].citation.source == "USGS Protected Areas Database (PAD-US)"


def test_hard_disqualifiers_moratorium_triggers():
    state = {
        "environmental_data_available": False,
        "ordinance_found": True,
        "ordinance_moratorium_active": True,
        "ordinance_moratorium_section": "Local Law No. 3, § 1",
        "ordinance_source": "eCode360",
        "ordinance_retrieval_date": "2026-06-01",
        "nwi_overlap": False,
        "padus_overlap": False,
    }
    result = _build_hard_disqualifiers(state)
    assert isinstance(result, list)
    assert len(result) == 1
    assert "moratorium" in result[0].constraint.lower()
    assert "Local Law No. 3, § 1" in result[0].constraint
    assert result[0].citation.source == "eCode360"


def test_hard_disqualifiers_moratorium_plus_env_available():
    """When both env data and moratorium are present, all three can fire."""
    state = _clean_env_state(
        nwi_overlap=True,
        nwi_wetland_type="Freshwater Forested/Shrub Wetland",
        ordinance_found=True,
        ordinance_moratorium_active=True,
        ordinance_moratorium_section="§ 5",
        ordinance_source="Municode",
        ordinance_retrieval_date="2026-06-01",
    )
    result = _build_hard_disqualifiers(state)
    assert isinstance(result, list)
    assert len(result) == 2
    sources = [d.citation.source for d in result]
    assert "USFWS National Wetlands Inventory" in sources
    assert "Municode" in sources


def test_hard_disqualifiers_empty_when_no_triggers():
    state = _clean_env_state()
    result = _build_hard_disqualifiers(state)
    assert result == []


def test_hard_disqualifiers_unable_to_verify_when_no_data():
    state = {
        "environmental_data_available": False,
        "ordinance_found": False,
        "ordinance_moratorium_active": False,
    }
    assert _build_hard_disqualifiers(state) == UNABLE_TO_VERIFY


# ---------------------------------------------------------------------------
# Viability score — hard disqualified path
# ---------------------------------------------------------------------------

def test_viability_nwi_disqualified():
    state = _clean_env_state(nwi_overlap=True, nwi_wetland_type="Freshwater Emergent Wetland")
    v = _build_viability(state)
    assert v.score == 0
    assert v.stars == 0
    assert v.label == "Hard Disqualified"
    assert v.hard_disqualified is True
    assert len(v.breakdown) > 0
    assert v.breakdown[0].note == "hard disqualifier"


def test_viability_padus_disqualified():
    state = _clean_env_state(padus_overlap=True, padus_unit_name="State Park")
    v = _build_viability(state)
    assert v.score == 0
    assert v.hard_disqualified is True


def test_viability_moratorium_disqualified():
    state = {
        "environmental_data_available": False,
        "ordinance_found": True,
        "ordinance_moratorium_active": True,
        "ordinance_moratorium_section": "§ 2",
        "ordinance_source": "eCode360",
        "ordinance_retrieval_date": "2026-06-01",
        "nwi_overlap": False,
        "padus_overlap": False,
        "grid_data_available": False,
        "hosting_capacity_available": False,
        "terrain_data_available": False,
        "ordinance_deduction": 0,
        "ordinance_summary_text": None,
    }
    v = _build_viability(state)
    assert v.score == 0
    assert v.stars == 0
    assert v.hard_disqualified is True


# ---------------------------------------------------------------------------
# Viability score — weighted scoring path
# ---------------------------------------------------------------------------

def _all_available_state(**overrides):
    """State with all signals available and clean values (full score = 100)."""
    return {
        "grid_data_available": True,
        "nearest_transmission_miles": 0.5,
        "hosting_capacity_available": True,
        "interconnection_capacity_proxy_mw": 200.0,
        "nyiso_snapshot_date": "2025-01-15",
        "nyiso_retrieval_date": "2026-06-01",
        "environmental_data_available": True,
        "flood_zone": "none",
        "nwi_overlap": False,
        "nwi_wetland_type": None,
        "padus_overlap": False,
        "padus_unit_name": None,
        "terrain_data_available": True,
        "mean_slope_percent": 3.0,
        "ordinance_found": True,
        "ordinance_moratorium_active": False,
        "ordinance_moratorium_section": None,
        "ordinance_source": "eCode360",
        "ordinance_retrieval_date": "2026-06-01",
        "ordinance_deduction": 0,
        "ordinance_summary_text": "Permissive ordinance",
        **overrides,
    }


def test_viability_clean_site_scores_100():
    state = _all_available_state()
    v = _build_viability(state)
    assert v.score == 100
    assert v.stars == 5
    assert v.label == "Strong"
    assert v.hard_disqualified is False


def test_viability_known_deductions_compute_correctly():
    # transmission 7 miles → -20, queue 800 MW → -10, flood AE → -20, slope 8% → -8, ord -5
    state = _all_available_state(
        nearest_transmission_miles=7.0,
        interconnection_capacity_proxy_mw=800.0,
        flood_zone="AE",
        mean_slope_percent=8.0,
        ordinance_deduction=-5,
    )
    v = _build_viability(state)
    expected = 100 - 20 - 10 - 20 - 8 - 5  # = 37
    assert v.score == expected
    assert v.stars == 2
    assert v.label == "Low"


def test_viability_clamped_to_1_minimum():
    state = _all_available_state(
        nearest_transmission_miles=15.0,   # -35
        interconnection_capacity_proxy_mw=2000.0,  # -20
        flood_zone="AE",   # -20
        mean_slope_percent=20.0,   # -15
        ordinance_deduction=-10,   # -10
    )
    v = _build_viability(state)
    # 100 - 35 - 20 - 20 - 15 - 10 = 0, but clamped to 1
    assert v.score == 1


def test_viability_unavailable_dimension_contributes_zero():
    state = {
        "grid_data_available": False,
        "hosting_capacity_available": False,
        "environmental_data_available": False,
        "terrain_data_available": False,
        "ordinance_found": False,
        "ordinance_moratorium_active": False,
        "nwi_overlap": False,
        "padus_overlap": False,
    }
    v = _build_viability(state)
    # No signals: all deductions are 0, score stays at 100 clamped → 100
    assert v.score == 100
    # All breakdown components have "unable to verify" note
    for comp in v.breakdown:
        assert comp.deduction == 0
        assert comp.note == "unable to verify"


# ---------------------------------------------------------------------------
# Top 3 constraints
# ---------------------------------------------------------------------------

def test_top_3_constraints_unable_to_verify_when_no_signals():
    state = {
        "grid_data_available": False,
        "hosting_capacity_available": False,
        "environmental_data_available": False,
        "terrain_data_available": False,
        "ordinance_found": False,
        "ordinance_moratorium_active": False,
        "nwi_overlap": False,
        "padus_overlap": False,
    }
    assert _build_top_3_constraints(state) == UNABLE_TO_VERIFY


def test_top_3_constraints_disqualified_returns_disqualifiers():
    state = _clean_env_state(nwi_overlap=True, nwi_wetland_type="Freshwater Emergent Wetland")
    result = _build_top_3_constraints(state)
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].impact == 100
    assert "NWI" in result[0].constraint


def test_top_3_constraints_sorted_by_impact_descending():
    # flood -20, transmission -35, slope -8 → order: transmission, flood, slope
    state = _all_available_state(
        nearest_transmission_miles=12.0,   # -35
        flood_zone="AE",                   # -20
        mean_slope_percent=8.0,            # -8
        interconnection_capacity_proxy_mw=200.0,  # 0
        ordinance_deduction=0,
    )
    result = _build_top_3_constraints(state)
    assert isinstance(result, list)
    assert len(result) == 3
    assert result[0].impact == 35
    assert result[1].impact == 20
    assert result[2].impact == 8


def test_top_3_constraints_max_three():
    # All four deducting dimensions
    state = _all_available_state(
        nearest_transmission_miles=12.0,   # -35
        interconnection_capacity_proxy_mw=2000.0,  # -20
        flood_zone="AE",                   # -20
        mean_slope_percent=8.0,            # -8
        ordinance_deduction=-5,            # -5
    )
    result = _build_top_3_constraints(state)
    assert len(result) <= 3


def test_top_3_constraints_empty_list_when_no_deductions():
    state = _all_available_state(
        nearest_transmission_miles=0.5,    # 0
        interconnection_capacity_proxy_mw=200.0,  # 0
        flood_zone="none",                 # 0
        mean_slope_percent=3.0,            # 0
        ordinance_deduction=0,             # 0
    )
    result = _build_top_3_constraints(state)
    assert result == []


# ---------------------------------------------------------------------------
# synthesize_memo node
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_synthesize_memo_returns_zero_when_ordinance_not_found():
    result = await synthesize_memo({"ordinance_found": False})
    assert result == {"ordinance_deduction": 0}


@pytest.mark.asyncio
async def test_synthesize_memo_returns_zero_when_no_api_key():
    state = {
        "ordinance_found": True,
        "ordinance_summary_text": "Some ordinance",
        "ordinance_setbacks": "50 ft",
        "ordinance_sup": "Required",
    }
    with patch("app.nodes.synthesize._get_client", side_effect=RuntimeError("ANTHROPIC_API_KEY not set")):
        result = await synthesize_memo(state)
    assert result == {"ordinance_deduction": 0}


@pytest.mark.asyncio
async def test_synthesize_memo_returns_negative_from_llm_score():
    state = {
        "ordinance_found": True,
        "ordinance_summary_text": "Very restrictive",
        "ordinance_setbacks": "200 ft from all boundaries",
        "ordinance_sup": "Full SUP with public hearing required",
    }

    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "score_ordinance"
    mock_block.input = {"deduction": 7}

    mock_response = MagicMock()
    mock_response.content = [mock_block]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("app.nodes.synthesize._get_client", return_value=mock_client):
        result = await synthesize_memo(state)

    assert result == {"ordinance_deduction": -7}


@pytest.mark.asyncio
async def test_synthesize_memo_clamps_deduction_to_10():
    state = {
        "ordinance_found": True,
        "ordinance_summary_text": "Extreme restrictions",
        "ordinance_setbacks": None,
        "ordinance_sup": None,
    }

    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "score_ordinance"
    mock_block.input = {"deduction": 99}

    mock_response = MagicMock()
    mock_response.content = [mock_block]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("app.nodes.synthesize._get_client", return_value=mock_client):
        result = await synthesize_memo(state)

    assert result == {"ordinance_deduction": -10}


@pytest.mark.asyncio
async def test_synthesize_memo_returns_zero_on_api_exception():
    state = {
        "ordinance_found": True,
        "ordinance_summary_text": "Test",
        "ordinance_setbacks": None,
        "ordinance_sup": None,
    }

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=Exception("API error"))

    with patch("app.nodes.synthesize._get_client", return_value=mock_client):
        result = await synthesize_memo(state)

    assert result == {"ordinance_deduction": 0}
