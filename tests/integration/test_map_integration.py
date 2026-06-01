import os

import asyncpg
import httpx
import pytest

import app.db as _db
from app.main import app

pytestmark = pytest.mark.integration

_DB_URL = os.environ.get("DATABASE_URL")

if not _DB_URL:
    pytest.skip("DATABASE_URL not set — skipping integration tests", allow_module_level=True)


async def _db_reachable() -> bool:
    try:
        conn = await asyncpg.connect(_DB_URL)
        await conn.close()
        return True
    except Exception:
        return False


@pytest.fixture(autouse=True)
async def reset_pool():
    """Close any existing pool before each test so each test gets its own pool
    created in the current event loop — avoids asyncpg cross-loop errors."""
    await _db.close_pool()
    _db._pool = None
    yield
    await _db.close_pool()
    _db._pool = None


@pytest.fixture(scope="module", autouse=True)
def check_db_reachable():
    import asyncio
    if not asyncio.run(_db_reachable()):
        pytest.skip("DB unreachable — skipping integration tests")


_NY_PAYLOAD = {"lat": 42.6526, "lng": -73.7562}

_LAYER_SOURCES = [
    "HIFLD",
    "Electric Power Transmission Lines",
    "Electric Substations",
    "FEMA National Flood Hazard Layer",
    "USFWS National Wetlands Inventory",
    "USGS Protected Areas Database (PAD-US)",
]


async def test_post_screen_returns_site_id():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/screen", json=_NY_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert "site_id" in data
    assert isinstance(data["site_id"], str)
    assert len(data["site_id"]) == 36
    assert isinstance(data["interactive_map"], dict)
    assert data["interactive_map"]["url"].startswith("/screen/")


async def test_get_screen_returns_html_with_layer_sources():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        post_resp = await client.post("/screen", json=_NY_PAYLOAD)
        assert post_resp.status_code == 200
        site_id = post_resp.json()["site_id"]

        get_resp = await client.get(f"/screen/{site_id}")

    assert get_resp.status_code == 200
    assert "text/html" in get_resp.headers["content-type"]

    html = get_resp.text
    for source in _LAYER_SOURCES:
        assert source in html, f"Expected layer source not found in map HTML: {source}"


async def test_get_screen_unknown_id_returns_404():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/screen/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
