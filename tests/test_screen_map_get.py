import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_FAKE_SITE_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

_FAKE_ROW = {
    "site_id": _FAKE_SITE_ID,
    "address": "123 Main St, Albany, NY",
    "resolved_lat": 42.6526,
    "resolved_lng": -73.7562,
    "parcel_id": "110.00-3-15",
    "parcel_geojson": {
        "type": "Polygon",
        "coordinates": [[
            [-73.760, 42.650], [-73.750, 42.650],
            [-73.750, 42.660], [-73.760, 42.660], [-73.760, 42.650],
        ]],
    },
    "parcel_fallback": False,
    "memo": {},
}

_FAKE_LAYERS = {
    "center_lat": 42.655,
    "center_lng": -73.755,
    "parcel": _FAKE_ROW["parcel_geojson"],
    "transmission": [],
    "substations": [],
    "flood": [],
    "nwi": [],
    "padus": [],
}


def test_get_screen_map_returns_200_html():
    with (
        patch("app.main.get_screen", new=AsyncMock(return_value=_FAKE_ROW)),
        patch("app.main.fetch_map_layers", new=AsyncMock(return_value=_FAKE_LAYERS)),
    ):
        resp = client.get(f"/screen/{_FAKE_SITE_ID}")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert len(resp.text) > 100


def test_get_screen_map_html_body_present():
    with (
        patch("app.main.get_screen", new=AsyncMock(return_value=_FAKE_ROW)),
        patch("app.main.fetch_map_layers", new=AsyncMock(return_value=_FAKE_LAYERS)),
    ):
        resp = client.get(f"/screen/{_FAKE_SITE_ID}")

    assert "<html" in resp.text.lower() or "<!DOCTYPE" in resp.text


def test_get_screen_map_unknown_id_returns_404():
    with patch("app.main.get_screen", new=AsyncMock(return_value=None)):
        resp = client.get("/screen/00000000-0000-0000-0000-000000000000")

    assert resp.status_code == 404


def test_get_screen_map_passes_parcel_fallback():
    fallback_row = {**_FAKE_ROW, "parcel_fallback": True}
    with (
        patch("app.main.get_screen", new=AsyncMock(return_value=fallback_row)),
        patch("app.main.fetch_map_layers", new=AsyncMock(return_value=_FAKE_LAYERS)),
    ):
        resp = client.get(f"/screen/{_FAKE_SITE_ID}")

    assert resp.status_code == 200
    assert "Estimated 500m buffer" in resp.text


def test_save_screen_returns_false_when_no_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import app.db as _db
    _db._pool = None

    import asyncio
    from app.screens_store import save_screen
    import uuid

    result = asyncio.run(save_screen(uuid.uuid4(), {}, {}))
    assert result is False
