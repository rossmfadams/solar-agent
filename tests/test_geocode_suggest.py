from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_suggest_disabled_when_token_unset(monkeypatch):
    monkeypatch.delenv("MAPBOX_TOKEN", raising=False)

    response = client.get("/geocode/suggest", params={"q": "123 County Rd"})

    assert response.status_code == 200
    assert response.json() == {"enabled": False, "suggestions": []}


def test_suggest_short_query_skips_call(monkeypatch):
    monkeypatch.setenv("MAPBOX_TOKEN", "test-token")

    with patch("app.geocode_suggest.httpx.AsyncClient") as mock_client_cls:
        response = client.get("/geocode/suggest", params={"q": "1"})

    assert response.status_code == 200
    assert response.json() == {"enabled": True, "suggestions": []}
    mock_client_cls.assert_not_called()


def test_suggest_returns_mapbox_features(monkeypatch):
    monkeypatch.setenv("MAPBOX_TOKEN", "test-token")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "features": [
            {"place_name": "123 County Rd, Madison County, NY", "center": [-75.6, 42.9]},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False

    with patch("app.geocode_suggest.httpx.AsyncClient", return_value=mock_client):
        response = client.get("/geocode/suggest", params={"q": "123 County Rd"})

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["suggestions"] == [
        {"label": "123 County Rd, Madison County, NY", "lng": -75.6, "lat": 42.9},
    ]


def test_suggest_degrades_on_mapbox_error(monkeypatch):
    monkeypatch.setenv("MAPBOX_TOKEN", "test-token")

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("boom"))
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False

    with patch("app.geocode_suggest.httpx.AsyncClient", return_value=mock_client):
        response = client.get("/geocode/suggest", params={"q": "123 County Rd"})

    assert response.status_code == 200
    assert response.json() == {"enabled": True, "suggestions": []}
