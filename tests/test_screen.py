from unittest.mock import AsyncMock, patch

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
