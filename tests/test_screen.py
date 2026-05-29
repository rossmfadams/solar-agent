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
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "123 Main St, Albany, NY"})

    assert resp.status_code == 200
    data = resp.json()
    assert "header" in data
    for section in MEMO_SECTIONS:
        assert section in data, f"missing section: {section}"
        assert data[section] == "unable to verify"


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
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"lat": 42.6526, "lng": -73.7562})

    assert resp.status_code == 200
    data = resp.json()
    assert "header" in data
    for section in MEMO_SECTIONS:
        assert section in data


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


def test_screen_all_sections_present_even_without_parcel():
    final = _mock_graph(
        {
            "address": "100 State St, Albany, NY",
            "resolved_lat": 42.6526,
            "resolved_lng": -73.7562,
        }
    )
    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=final)
        resp = client.post("/screen", json={"address": "100 State St, Albany, NY"})

    assert resp.status_code == 200
    data = resp.json()
    for section in MEMO_SECTIONS:
        assert section in data
        assert data[section] == "unable to verify"


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
