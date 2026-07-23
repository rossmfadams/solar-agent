import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


async def _updates(events):
    for event in events:
        yield event


def _parse_sse(text: str) -> list[dict]:
    frames = [f for f in text.split("\n\n") if f.strip()]
    return [json.loads(f[len("data: "):]) for f in frames]


def test_screen_stream_emits_node_events_and_final_memo():
    events = [
        {"geocode_address": {"resolved_lat": 42.6526, "resolved_lng": -73.7562}},
        {"resolve_parcel": {"parcel_id": "1", "county": "Albany", "muni": "Albany", "parcel_geojson": {}, "parcel_fallback": False}},
        {"check_grid_proximity": {"grid_data_available": False}},
        {"check_environmental_constraints": {"environmental_data_available": False}},
        {"check_terrain": {"terrain_data_available": False}},
        {"research_local_ordinance": {"ordinance_available": False, "ordinance_found": False}},
        {"check_hosting_capacity": {"hosting_capacity_available": False}},
        {"synthesize_memo": {"ordinance_deduction": 0}},
    ]

    with (
        patch("app.main.compiled_graph") as mock_graph,
        patch("app.main.save_screen", new=AsyncMock(return_value=True)),
    ):
        mock_graph.astream = lambda *a, **k: _updates(events)
        resp = client.post("/screen/stream", json={"address": "1 Main St, Albany, NY"})

    assert resp.status_code == 200
    parsed = _parse_sse(resp.text)

    node_events = [p for p in parsed if p["type"] == "node"]
    assert [e["node"] for e in node_events] == [
        "geocode_address",
        "resolve_parcel",
        "check_grid_proximity",
        "check_environmental_constraints",
        "check_terrain",
        "research_local_ordinance",
        "check_hosting_capacity",
    ]
    # synthesize_memo's completion is implied by the final memo event, not a
    # dedicated node event (LangGraph fires it once per converging edge).
    assert "synthesize_memo" not in [e["node"] for e in node_events]
    assert all(e["status"] == "done" if e["node"] == "geocode_address" else True for e in node_events)
    # Nodes reporting an unavailable data flag surface as "warning", not error.
    warning_nodes = {e["node"] for e in node_events if e["status"] == "warning"}
    assert warning_nodes == {
        "check_grid_proximity",
        "check_environmental_constraints",
        "check_terrain",
        "research_local_ordinance",  # available but ordinance_found is False
        "check_hosting_capacity",
    }


def test_screen_stream_ordinance_found_is_done_not_warning():
    events = [
        {"geocode_address": {"resolved_lat": 42.6526, "resolved_lng": -73.7562}},
        {
            "research_local_ordinance": {
                "ordinance_available": True,
                "ordinance_found": True,
                "ordinance_source": "eCode360",
            }
        },
    ]

    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.astream = lambda *a, **k: _updates(events)
        resp = client.post("/screen/stream", json={"address": "1 Main St, Albany, NY"})

    parsed = _parse_sse(resp.text)
    ordinance_event = next(p for p in parsed if p.get("node") == "research_local_ordinance")
    assert ordinance_event["status"] == "done"

    memo_events = [p for p in parsed if p["type"] == "memo"]
    assert len(memo_events) == 1
    assert "site_id" in memo_events[0]["memo"]
    assert memo_events[0]["memo"]["header"]["address"] == "1 Main St, Albany, NY"


def test_screen_stream_emits_error_when_geocode_resolves_nothing():
    events = [
        {"geocode_address": {"resolved_lat": None, "resolved_lng": None}},
    ]

    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.astream = lambda *a, **k: _updates(events)
        resp = client.post("/screen/stream", json={"address": "Nowhere At All"})

    assert resp.status_code == 200
    parsed = _parse_sse(resp.text)

    assert len(parsed) == 1
    assert parsed[0]["type"] == "error"
    assert parsed[0]["node"] == "geocode_address"


def test_screen_stream_emits_error_when_out_of_ny_bounds():
    events = [
        {"geocode_address": {"resolved_lat": 39.9612, "resolved_lng": -82.9988}},
        {"validate_ny_bounds": {"out_of_ny_bounds": True}},
    ]

    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.astream = lambda *a, **k: _updates(events)
        resp = client.post("/screen/stream", json={"address": "123 Main St, Columbus, OH"})

    assert resp.status_code == 200
    parsed = _parse_sse(resp.text)

    error_events = [p for p in parsed if p["type"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["node"] == "validate_ny_bounds"
    assert "New York" in error_events[0]["message"]


def test_screen_stream_missing_input_returns_422():
    resp = client.post("/screen/stream", json={})
    assert resp.status_code == 422
