from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

MEMO_SECTIONS = [
    "hard_disqualifiers",
    "top_3_constraints",
    "interconnection",
    "environmental",
    "terrain",
    "ordinance_summary",
    "interactive_map",
]

client = TestClient(app)


def _mock_graph(state_overrides: dict):
    base = {
        "address": None,
        "lat": None,
        "lng": None,
        "resolved_lat": None,
        "resolved_lng": None,
        "parcel_id": None,
        "county": None,
        "muni": None,
        "parcel_geojson": None,
        "parcel_fallback": False,
        "nearest_transmission_miles": None,
        "transmission_band": None,
        "nearest_substation_miles": None,
        "nearest_substations": [],
        "grid_data_available": False,
        "interconnection_capacity_proxy_mw": None,
        "queue_match_rate": None,
        "nyiso_snapshot_date": None,
        "nyiso_retrieval_date": None,
        "hosting_capacity_available": False,
        # Environmental
        "flood_zone": None,
        "nwi_overlap": None,
        "nwi_wetland_type": None,
        "padus_overlap": None,
        "padus_unit_name": None,
        "environmental_data_available": False,
        # Terrain
        "mean_slope_percent": None,
        "terrain_data_available": False,
        # Ordinance
        "ordinance_available": False,
        "ordinance_found": False,
        "ordinance_source": None,
        "ordinance_source_url": None,
        "ordinance_section": None,
        "ordinance_setbacks": None,
        "ordinance_sup": None,
        "ordinance_summary_text": None,
        "ordinance_moratorium_active": False,
        "ordinance_moratorium_section": None,
        "ordinance_moratorium_quote": None,
        "ordinance_retrieval_date": None,
        # Synthesis
        "ordinance_deduction": None,
    }
    return {**base, **state_overrides}


def test_screen_address_returns_200_with_all_sections():
    final = _mock_graph(
        {
            "address": "123 Main St, Albany, NY",
            "resolved_lat": 42.6526,
            "resolved_lng": -73.7562,
            "parcel_id": "110.00-3-15",
            "county": "Albany",
            "muni": "Albany",
        }
    )
    with (
        patch("app.main.compiled_graph") as mock_graph,
        patch("app.main.save_screen", new=AsyncMock(return_value=True)),
    ):
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "123 Main St, Albany, NY"})

    assert resp.status_code == 200
    data = resp.json()
    assert "header" in data
    assert "site_id" in data
    for section in MEMO_SECTIONS:
        assert section in data, f"missing section: {section}"
    # interactive_map is now populated; all other sections still "unable to verify"
    assert isinstance(data["interactive_map"], dict)
    assert "site_id" in data["interactive_map"]
    assert data["interactive_map"]["url"].startswith("/screen/")
    non_map_sections = [s for s in MEMO_SECTIONS if s != "interactive_map"]
    for section in non_map_sections:
        assert data[section] == "unable to verify", f"{section} should be unable to verify"


def test_screen_lat_lng_returns_200_with_all_sections():
    final = _mock_graph(
        {
            "lat": 42.6526,
            "lng": -73.7562,
            "resolved_lat": 42.6526,
            "resolved_lng": -73.7562,
            "parcel_id": "110.00-3-15",
            "county": "Albany",
            "muni": "Albany",
        }
    )
    with (
        patch("app.main.compiled_graph") as mock_graph,
        patch("app.main.save_screen", new=AsyncMock(return_value=True)),
    ):
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"lat": 42.6526, "lng": -73.7562})

    assert resp.status_code == 200
    data = resp.json()
    assert "header" in data
    assert "site_id" in data
    for section in MEMO_SECTIONS:
        assert section in data
    assert isinstance(data["interactive_map"], dict)


def test_screen_no_parcel_found_notes_fallback():
    final = _mock_graph(
        {
            "address": "1 Nowhere Rd, Albany, NY",
            "resolved_lat": 42.5,
            "resolved_lng": -73.5,
            "parcel_fallback": True,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "1 Nowhere Rd, Albany, NY"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["header"]["parcel_fallback"] is True
    assert data["header"]["fallback_note"] is not None


def test_screen_missing_input_returns_422():
    resp = client.post("/screen", json={})
    assert resp.status_code == 422


def test_screen_out_of_ny_bounds_returns_422_friendly_message():
    final = _mock_graph(
        {
            "address": "123 Main St, Columbus, OH",
            "resolved_lat": 39.9612,
            "resolved_lng": -82.9988,
            "out_of_ny_bounds": True,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "123 Main St, Columbus, OH"})

    assert resp.status_code == 422
    assert "New York" in resp.json()["detail"]


def test_screen_all_sections_present_even_without_parcel():
    final = _mock_graph(
        {
            "address": "100 State St, Albany, NY",
            "resolved_lat": 42.6526,
            "resolved_lng": -73.7562,
        }
    )
    with (
        patch("app.main.compiled_graph") as mock_graph,
        patch("app.main.save_screen", new=AsyncMock(return_value=True)),
    ):
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "100 State St, Albany, NY"})

    assert resp.status_code == 200
    data = resp.json()
    for section in MEMO_SECTIONS:
        assert section in data
    non_map_sections = [s for s in MEMO_SECTIONS if s != "interactive_map"]
    for section in non_map_sections:
        assert data[section] == "unable to verify"
    assert isinstance(data["interactive_map"], dict)


def test_screen_interconnection_populated_when_grid_data_available():
    final = _mock_graph(
        {
            "address": "1 Empire State Plaza, Albany, NY",
            "resolved_lat": 42.6526,
            "resolved_lng": -73.7562,
            "parcel_id": "110.00-3-15",
            "county": "Albany",
            "muni": "Albany",
            "nearest_transmission_miles": 0.8,
            "transmission_band": "strong positive",
            "nearest_substation_miles": 1.5,
            "nearest_substations": [
                {"id": 1, "name": "Albany Sub A", "miles": 1.5},
                {"id": 2, "name": "Albany Sub B", "miles": 2.3},
                {"id": 3, "name": "Albany Sub C", "miles": 4.1},
            ],
            "grid_data_available": True,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post(
            "/screen", json={"address": "1 Empire State Plaza, Albany, NY"}
        )

    assert resp.status_code == 200
    data = resp.json()
    ic = data["interconnection"]
    assert ic != "unable to verify"
    assert ic["nearest_transmission_miles"] == 0.8
    assert ic["transmission_band"] == "strong positive"
    assert ic["nearest_substation_miles"] == 1.5
    assert len(ic["nearest_substations"]) == 3
    assert len(ic["citations"]) == 1
    assert ic["citations"][0]["source"] == "HIFLD"


def test_screen_interconnection_unable_to_verify_when_grid_data_unavailable():
    final = _mock_graph(
        {
            "address": "Remote Site, NY",
            "resolved_lat": 44.0,
            "resolved_lng": -75.0,
            "grid_data_available": False,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "Remote Site, NY"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["interconnection"] == "unable to verify"


def test_screen_interconnection_includes_nyiso_citation_when_hosting_capacity_available():
    """Interconnection section carries proxy MW + a NYISO Citation when queue loaded."""
    final = _mock_graph(
        {
            "address": "1 Empire State Plaza, Albany, NY",
            "resolved_lat": 42.6526,
            "resolved_lng": -73.7562,
            "nearest_transmission_miles": 0.8,
            "transmission_band": "strong positive",
            "nearest_substation_miles": 1.5,
            "nearest_substations": [
                {"id": 1, "name": "Albany Sub A", "miles": 1.5},
                {"id": 2, "name": "Albany Sub B", "miles": 2.3},
                {"id": 3, "name": "Albany Sub C", "miles": 4.1},
            ],
            "grid_data_available": True,
            "interconnection_capacity_proxy_mw": 950,
            "queue_match_rate": 0.87,
            "nyiso_snapshot_date": "2025-01-15",
            "nyiso_retrieval_date": "2025-05-01",
            "hosting_capacity_available": True,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post(
            "/screen", json={"address": "1 Empire State Plaza, Albany, NY"}
        )

    assert resp.status_code == 200
    ic = resp.json()["interconnection"]
    assert ic != "unable to verify"
    assert ic["interconnection_capacity_proxy_mw"] == 950
    assert ic["queue_match_rate"] == pytest.approx(0.87, rel=1e-3)
    sources = [c["source"] for c in ic["citations"]]
    assert "HIFLD" in sources
    assert "NYISO Interconnection Queue" in sources
    nyiso_citation = next(c for c in ic["citations"] if c["source"] == "NYISO Interconnection Queue")
    assert "2025-01-15" in nyiso_citation["reference"]
    assert nyiso_citation["retrieval_date"] == "2025-05-01"


def test_screen_interconnection_no_nyiso_citation_when_hosting_capacity_unavailable():
    """When NYISO queue not loaded, Interconnection section has only the HIFLD citation."""
    final = _mock_graph(
        {
            "address": "1 Empire State Plaza, Albany, NY",
            "resolved_lat": 42.6526,
            "resolved_lng": -73.7562,
            "nearest_transmission_miles": 0.8,
            "transmission_band": "strong positive",
            "nearest_substation_miles": 1.5,
            "nearest_substations": [
                {"id": 1, "name": "Albany Sub A", "miles": 1.5},
            ],
            "grid_data_available": True,
            "hosting_capacity_available": False,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post(
            "/screen", json={"address": "1 Empire State Plaza, Albany, NY"}
        )

    assert resp.status_code == 200
    ic = resp.json()["interconnection"]
    assert ic != "unable to verify"
    assert ic["interconnection_capacity_proxy_mw"] is None
    sources = [c["source"] for c in ic["citations"]]
    assert "NYISO Interconnection Queue" not in sources
    assert "HIFLD" in sources


# ---------------------------------------------------------------------------
# Environmental section
# ---------------------------------------------------------------------------

def test_screen_environmental_populated_when_data_available():
    final = _mock_graph(
        {
            "address": "1 Empire State Plaza, Albany, NY",
            "resolved_lat": 42.6526,
            "resolved_lng": -73.7562,
            "flood_zone": "AE/AH/AO/VE",
            "nwi_overlap": False,
            "nwi_wetland_type": None,
            "padus_overlap": False,
            "padus_unit_name": None,
            "environmental_data_available": True,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "1 Empire State Plaza, Albany, NY"})

    assert resp.status_code == 200
    env = resp.json()["environmental"]
    assert env != "unable to verify"
    assert env["flood_zone"] == "AE/AH/AO/VE"
    assert env["nwi_overlap"] is False
    assert env["padus_overlap"] is False
    sources = [c["source"] for c in env["citations"]]
    assert "FEMA National Flood Hazard Layer" in sources
    assert "USFWS National Wetlands Inventory" in sources
    assert "USGS Protected Areas Database (PAD-US)" in sources


def test_screen_environmental_unable_to_verify_when_data_unavailable():
    final = _mock_graph(
        {
            "address": "Remote Site, NY",
            "resolved_lat": 44.0,
            "resolved_lng": -75.0,
            "environmental_data_available": False,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "Remote Site, NY"})

    assert resp.status_code == 200
    assert resp.json()["environmental"] == "unable to verify"


# ---------------------------------------------------------------------------
# Terrain section
# ---------------------------------------------------------------------------

def test_screen_terrain_populated_when_data_available():
    final = _mock_graph(
        {
            "address": "1 Empire State Plaza, Albany, NY",
            "resolved_lat": 42.6526,
            "resolved_lng": -73.7562,
            "mean_slope_percent": 4.5,
            "terrain_data_available": True,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "1 Empire State Plaza, Albany, NY"})

    assert resp.status_code == 200
    terrain = resp.json()["terrain"]
    assert terrain != "unable to verify"
    assert terrain["mean_slope_percent"] == pytest.approx(4.5, rel=1e-3)
    assert len(terrain["citations"]) == 1
    assert "3DEP" in terrain["citations"][0]["source"]


def test_screen_terrain_unable_to_verify_when_data_unavailable():
    final = _mock_graph(
        {
            "address": "Remote Site, NY",
            "resolved_lat": 44.0,
            "resolved_lng": -75.0,
            "terrain_data_available": False,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "Remote Site, NY"})

    assert resp.status_code == 200
    assert resp.json()["terrain"] == "unable to verify"


# ---------------------------------------------------------------------------
# Hard disqualifiers
# ---------------------------------------------------------------------------

def test_screen_hard_disqualifiers_empty_list_when_no_overlaps():
    final = _mock_graph(
        {
            "address": "1 Empire State Plaza, Albany, NY",
            "resolved_lat": 42.6526,
            "resolved_lng": -73.7562,
            "flood_zone": "none",
            "nwi_overlap": False,
            "nwi_wetland_type": None,
            "padus_overlap": False,
            "padus_unit_name": None,
            "environmental_data_available": True,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "1 Empire State Plaza, Albany, NY"})

    assert resp.status_code == 200
    hd = resp.json()["hard_disqualifiers"]
    assert hd == []


def test_screen_hard_disqualifiers_nwi_overlap_triggers_entry():
    final = _mock_graph(
        {
            "address": "Wetland Parcel, NY",
            "resolved_lat": 42.6526,
            "resolved_lng": -73.7562,
            "flood_zone": "none",
            "nwi_overlap": True,
            "nwi_wetland_type": "Freshwater Emergent Wetland",
            "padus_overlap": False,
            "padus_unit_name": None,
            "environmental_data_available": True,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "Wetland Parcel, NY"})

    assert resp.status_code == 200
    hd = resp.json()["hard_disqualifiers"]
    assert len(hd) == 1
    assert "NWI wetland" in hd[0]["constraint"]
    assert "Freshwater Emergent Wetland" in hd[0]["constraint"]
    assert hd[0]["citation"]["source"] == "USFWS National Wetlands Inventory"


def test_screen_hard_disqualifiers_padus_overlap_triggers_entry():
    final = _mock_graph(
        {
            "address": "Protected Land, NY",
            "resolved_lat": 44.0,
            "resolved_lng": -74.0,
            "flood_zone": "none",
            "nwi_overlap": False,
            "nwi_wetland_type": None,
            "padus_overlap": True,
            "padus_unit_name": "Adirondack Park",
            "environmental_data_available": True,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "Protected Land, NY"})

    assert resp.status_code == 200
    hd = resp.json()["hard_disqualifiers"]
    assert len(hd) == 1
    assert "PAD-US" in hd[0]["constraint"]
    assert "Adirondack Park" in hd[0]["constraint"]
    assert hd[0]["citation"]["source"] == "USGS Protected Areas Database (PAD-US)"


def test_screen_hard_disqualifiers_both_nwi_and_padus_overlap():
    final = _mock_graph(
        {
            "address": "Double Disqualified, NY",
            "resolved_lat": 44.0,
            "resolved_lng": -74.0,
            "flood_zone": "none",
            "nwi_overlap": True,
            "nwi_wetland_type": "Freshwater Forested/Shrub Wetland",
            "padus_overlap": True,
            "padus_unit_name": "Adirondack Park",
            "environmental_data_available": True,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "Double Disqualified, NY"})

    assert resp.status_code == 200
    hd = resp.json()["hard_disqualifiers"]
    assert len(hd) == 2
    sources = [entry["citation"]["source"] for entry in hd]
    assert "USFWS National Wetlands Inventory" in sources
    assert "USGS Protected Areas Database (PAD-US)" in sources


def test_screen_hard_disqualifiers_unable_to_verify_when_env_data_unavailable():
    final = _mock_graph(
        {
            "address": "Remote Site, NY",
            "resolved_lat": 44.0,
            "resolved_lng": -75.0,
            "environmental_data_available": False,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "Remote Site, NY"})

    assert resp.status_code == 200
    assert resp.json()["hard_disqualifiers"] == "unable to verify"


# ---------------------------------------------------------------------------
# Ordinance summary section
# ---------------------------------------------------------------------------

def test_screen_ordinance_summary_populated_when_ordinance_found():
    """ordinance_summary is populated with setbacks/SUP/citation when an ordinance is found."""
    final = _mock_graph(
        {
            "address": "1 Empire State Plaza, Albany, NY",
            "resolved_lat": 42.6526,
            "resolved_lng": -73.7562,
            "muni": "Guilderland",
            "county": "Albany",
            "ordinance_available": True,
            "ordinance_found": True,
            "ordinance_source": "eCode360",
            "ordinance_source_url": "https://ecode360.com/GU5678",
            "ordinance_section": "§ 280-74",
            "ordinance_setbacks": "Standard district setbacks apply",
            "ordinance_sup": "Site plan approval for systems over 1 acre",
            "ordinance_summary_text": "Permissive solar ordinance — standard setbacks only",
            "ordinance_moratorium_active": False,
            "ordinance_moratorium_section": None,
            "ordinance_moratorium_quote": None,
            "ordinance_retrieval_date": "2026-06-01",
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "1 Empire State Plaza, Albany, NY"})

    assert resp.status_code == 200
    os_ = resp.json()["ordinance_summary"]
    assert os_ != "unable to verify"
    assert os_["source"] == "eCode360"
    assert os_["section"] == "§ 280-74"
    assert os_["setbacks"] == "Standard district setbacks apply"
    assert os_["moratorium"] is None
    assert os_["citation"]["source"] == "eCode360"
    assert os_["citation"]["retrieval_date"] == "2026-06-01"


def test_screen_ordinance_summary_unable_to_verify_when_not_found():
    """ordinance_summary is 'unable to verify' when ordinance_available is False."""
    final = _mock_graph(
        {
            "address": "Remote Site, NY",
            "resolved_lat": 44.0,
            "resolved_lng": -75.0,
            "muni": "Unknown Town",
            "county": "Unknown County",
            "ordinance_available": False,
            "ordinance_found": False,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "Remote Site, NY"})

    assert resp.status_code == 200
    assert resp.json()["ordinance_summary"] == "unable to verify"


def test_screen_ordinance_summary_unable_to_verify_when_searched_not_found():
    """ordinance_summary is 'unable to verify' when available but ordinance not found."""
    final = _mock_graph(
        {
            "address": "123 Rural Rd, NY",
            "resolved_lat": 43.5,
            "resolved_lng": -74.5,
            "muni": "Smalltown",
            "county": "Hamilton",
            "ordinance_available": True,
            "ordinance_found": False,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "123 Rural Rd, NY"})

    assert resp.status_code == 200
    assert resp.json()["ordinance_summary"] == "unable to verify"


# ---------------------------------------------------------------------------
# Viability section
# ---------------------------------------------------------------------------

def test_screen_viability_present_in_response():
    """viability is a top-level object in every response."""
    final = _mock_graph(
        {
            "address": "123 Main St, Albany, NY",
            "resolved_lat": 42.6526,
            "resolved_lng": -73.7562,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "123 Main St, Albany, NY"})

    assert resp.status_code == 200
    data = resp.json()
    assert "viability" in data
    v = data["viability"]
    assert "score" in v
    assert "stars" in v
    assert "label" in v
    assert "hard_disqualified" in v


def test_screen_viability_scored_when_signals_exist():
    """viability.score is deterministic when known signals are provided."""
    final = _mock_graph(
        {
            "address": "1 Empire State Plaza, Albany, NY",
            "resolved_lat": 42.6526,
            "resolved_lng": -73.7562,
            # Transmission 7 mi → -20, queue 800 MW → -10, flood AE → -20, slope 8% → -8
            "grid_data_available": True,
            "nearest_transmission_miles": 7.0,
            "transmission_band": "moderate negative",
            "nearest_substation_miles": 3.0,
            "nearest_substations": [{"id": 1, "name": "Sub A", "miles": 3.0}],
            "hosting_capacity_available": True,
            "interconnection_capacity_proxy_mw": 800.0,
            "queue_match_rate": 0.8,
            "nyiso_snapshot_date": "2025-01-15",
            "nyiso_retrieval_date": "2026-06-01",
            "environmental_data_available": True,
            "flood_zone": "AE",
            "nwi_overlap": False,
            "padus_overlap": False,
            "terrain_data_available": True,
            "mean_slope_percent": 8.0,
            "ordinance_found": False,
            "ordinance_deduction": None,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "1 Empire State Plaza, Albany, NY"})

    assert resp.status_code == 200
    v = resp.json()["viability"]
    # 100 - 20 - 10 - 20 - 8 = 42
    assert v["score"] == 42
    assert v["stars"] == 2
    assert v["label"] == "Low"
    assert v["hard_disqualified"] is False


def test_screen_top_3_constraints_populated_when_signals_exist():
    """top_3_constraints is a list (not 'unable to verify') when any signal is available."""
    final = _mock_graph(
        {
            "address": "1 Empire State Plaza, Albany, NY",
            "resolved_lat": 42.6526,
            "resolved_lng": -73.7562,
            "grid_data_available": True,
            "nearest_transmission_miles": 7.0,
            "transmission_band": "moderate negative",
            "nearest_substation_miles": 3.0,
            "nearest_substations": [{"id": 1, "name": "Sub A", "miles": 3.0}],
            "hosting_capacity_available": False,
            "environmental_data_available": True,
            "flood_zone": "AE",
            "nwi_overlap": False,
            "padus_overlap": False,
            "terrain_data_available": False,
            "ordinance_found": False,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "1 Empire State Plaza, Albany, NY"})

    assert resp.status_code == 200
    top3 = resp.json()["top_3_constraints"]
    assert isinstance(top3, list)
    # Both transmission (7mi → -20) and flood (AE → -20) should appear
    labels = [c["constraint"] for c in top3]
    assert any("Transmission" in lbl or "transmission" in lbl for lbl in labels)
    assert any("Flood" in lbl or "flood" in lbl or "AE" in lbl for lbl in labels)


def test_screen_moratorium_yields_hard_disqualified_viability():
    """An active moratorium drives viability.score == 0 and hard_disqualified == True."""
    final = _mock_graph(
        {
            "address": "Moratorium Town, NY",
            "resolved_lat": 43.0,
            "resolved_lng": -74.0,
            "ordinance_available": True,
            "ordinance_found": True,
            "ordinance_source": "eCode360",
            "ordinance_section": "Local Law No. 3, § 1",
            "ordinance_moratorium_active": True,
            "ordinance_moratorium_section": "Local Law No. 3, § 1",
            "ordinance_moratorium_quote": "No solar applications shall be accepted.",
            "ordinance_retrieval_date": "2026-06-01",
            "ordinance_deduction": 0,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "Moratorium Town, NY"})

    assert resp.status_code == 200
    data = resp.json()
    v = data["viability"]
    assert v["score"] == 0
    assert v["stars"] == 0
    assert v["label"] == "Hard Disqualified"
    assert v["hard_disqualified"] is True

    # The moratorium should also appear in hard_disqualifiers
    hd = data["hard_disqualifiers"]
    assert isinstance(hd, list)
    assert any("moratorium" in entry["constraint"].lower() for entry in hd)

    # And in top_3_constraints
    top3 = data["top_3_constraints"]
    assert isinstance(top3, list)
    assert any("moratorium" in c["constraint"].lower() for c in top3)
