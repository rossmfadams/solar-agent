import os

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.integration

_DB_URL = os.environ.get("DATABASE_URL")

# Skip entire module when DATABASE_URL is absent
if not _DB_URL:
    pytest.skip("DATABASE_URL not set — skipping integration tests", allow_module_level=True)


def _db_reachable() -> bool:
    import asyncio

    async def _check():
        try:
            conn = await asyncpg.connect(_DB_URL)
            await conn.close()
            return True
        except Exception:
            return False

    return asyncio.run(_check())


if not _db_reachable():
    pytest.skip("DB unreachable — skipping integration tests", allow_module_level=True)

client = TestClient(app)

_NY_PAYLOAD = {"lat": 42.6526, "lng": -73.7562}

_LAYER_SOURCES = [
    "HIFLD",
    "Electric Power Transmission Lines",
    "Electric Substations",
    "FEMA National Flood Hazard Layer",
    "USFWS National Wetlands Inventory",
    "USGS Protected Areas Database (PAD-US)",
]


def test_post_screen_returns_site_id():
    resp = client.post("/screen", json=_NY_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert "site_id" in data
    assert isinstance(data["site_id"], str)
    assert len(data["site_id"]) == 36  # UUID length
    assert isinstance(data["interactive_map"], dict)
    assert data["interactive_map"]["url"].startswith("/screen/")


def test_get_screen_returns_html_with_layer_sources():
    post_resp = client.post("/screen", json=_NY_PAYLOAD)
    assert post_resp.status_code == 200
    site_id = post_resp.json()["site_id"]

    get_resp = client.get(f"/screen/{site_id}")
    assert get_resp.status_code == 200
    assert "text/html" in get_resp.headers["content-type"]

    html = get_resp.text
    for source in _LAYER_SOURCES:
        assert source in html, f"Expected layer source not found in map HTML: {source}"


def test_get_screen_unknown_id_returns_404():
    resp = client.get("/screen/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
