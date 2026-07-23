from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_FAKE_SITE_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

_FAKE_MEMO = {
    "header": {"address": "123 Main St, Albany, NY"},
    "viability": {"score": 82},
    "site_id": _FAKE_SITE_ID,
}

_FAKE_ROW = {
    "site_id": _FAKE_SITE_ID,
    "memo": _FAKE_MEMO,
}


def test_get_screen_memo_returns_stored_memo():
    with patch("app.main.get_screen", new=AsyncMock(return_value=_FAKE_ROW)):
        resp = client.get(f"/screen/{_FAKE_SITE_ID}/memo")

    assert resp.status_code == 200
    assert resp.json() == _FAKE_MEMO


def test_get_screen_memo_unknown_id_returns_404():
    with patch("app.main.get_screen", new=AsyncMock(return_value=None)):
        resp = client.get("/screen/00000000-0000-0000-0000-000000000000/memo")

    assert resp.status_code == 404
