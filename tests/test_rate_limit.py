from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rate_limit import (
    MAX_CONCURRENT_RUNS,
    RATE_LIMIT_MAX_RUNS,
    ConcurrencyLimitExceeded,
    RateLimitExceeded,
    acquire_concurrency_slot,
    check_rate_limit,
    release_concurrency_slot,
)

client = TestClient(app)


def _mock_final_state():
    return {
        "address": "1 Main St, Albany, NY",
        "resolved_lat": 42.6526,
        "resolved_lng": -73.7562,
        "out_of_ny_bounds": False,
        "parcel_id": None,
        "county": None,
        "muni": None,
        "parcel_fallback": False,
        "grid_data_available": False,
        "hosting_capacity_available": False,
        "environmental_data_available": False,
        "terrain_data_available": False,
        "ordinance_available": False,
        "ordinance_found": False,
    }


# ---------------------------------------------------------------------------
# Unit tests on the limiter module
# ---------------------------------------------------------------------------


def test_check_rate_limit_allows_up_to_threshold():
    for _ in range(RATE_LIMIT_MAX_RUNS):
        check_rate_limit("1.2.3.4")


def test_check_rate_limit_rejects_over_threshold():
    for _ in range(RATE_LIMIT_MAX_RUNS):
        check_rate_limit("1.2.3.4")
    with pytest.raises(RateLimitExceeded):
        check_rate_limit("1.2.3.4")


def test_check_rate_limit_is_per_ip():
    for _ in range(RATE_LIMIT_MAX_RUNS):
        check_rate_limit("1.2.3.4")
    # A different IP (e.g. another visitor sharing an office NAT) is unaffected.
    check_rate_limit("5.6.7.8")


def test_concurrency_slot_rejects_beyond_cap():
    for _ in range(MAX_CONCURRENT_RUNS):
        acquire_concurrency_slot()
    with pytest.raises(ConcurrencyLimitExceeded):
        acquire_concurrency_slot()
    for _ in range(MAX_CONCURRENT_RUNS):
        release_concurrency_slot()


def test_concurrency_slot_allows_after_release():
    for _ in range(MAX_CONCURRENT_RUNS):
        acquire_concurrency_slot()
    release_concurrency_slot()
    acquire_concurrency_slot()  # should not raise
    for _ in range(MAX_CONCURRENT_RUNS):
        release_concurrency_slot()


# ---------------------------------------------------------------------------
# Integration tests through /screen
# ---------------------------------------------------------------------------


def test_screen_returns_429_friendly_message_when_rate_limited():
    for _ in range(RATE_LIMIT_MAX_RUNS):
        check_rate_limit("testclient")

    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=_mock_final_state())
        resp = client.post("/screen", json={"address": "1 Main St, Albany, NY"})

    assert resp.status_code == 429
    assert "try again" in resp.json()["detail"].lower()


def test_screen_returns_429_friendly_message_when_concurrency_capped():
    for _ in range(MAX_CONCURRENT_RUNS):
        acquire_concurrency_slot()

    with patch("app.main.compiled_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=_mock_final_state())
        resp = client.post("/screen", json={"address": "1 Main St, Albany, NY"})

    assert resp.status_code == 429
    assert "try again" in resp.json()["detail"].lower()

    for _ in range(MAX_CONCURRENT_RUNS):
        release_concurrency_slot()


def test_screen_releases_concurrency_slot_after_success():
    with (
        patch("app.main.compiled_graph") as mock_graph,
        patch("app.main.save_screen", new=AsyncMock(return_value=True)),
    ):
        mock_graph.ainvoke = AsyncMock(return_value=_mock_final_state())
        resp = client.post("/screen", json={"address": "1 Main St, Albany, NY"})

    assert resp.status_code == 200

    # The slot from the request above should have been released, so the
    # cap can be fully re-acquired without hitting the limit.
    for _ in range(MAX_CONCURRENT_RUNS):
        acquire_concurrency_slot()
    for _ in range(MAX_CONCURRENT_RUNS):
        release_concurrency_slot()


def test_screen_stream_returns_429_friendly_message_when_rate_limited():
    for _ in range(RATE_LIMIT_MAX_RUNS):
        check_rate_limit("testclient")

    resp = client.post("/screen/stream", json={"address": "1 Main St, Albany, NY"})

    assert resp.status_code == 429
    assert "try again" in resp.json()["detail"].lower()


def test_screen_stream_returns_429_friendly_message_when_concurrency_capped():
    for _ in range(MAX_CONCURRENT_RUNS):
        acquire_concurrency_slot()

    resp = client.post("/screen/stream", json={"address": "1 Main St, Albany, NY"})

    assert resp.status_code == 429
    assert "try again" in resp.json()["detail"].lower()

    for _ in range(MAX_CONCURRENT_RUNS):
        release_concurrency_slot()


def test_screen_shared_ip_group_usage_not_blocked_by_per_ip_limit_alone():
    """Several runs from one shared IP, well under the generous threshold, all succeed."""
    with (
        patch("app.main.compiled_graph") as mock_graph,
        patch("app.main.save_screen", new=AsyncMock(return_value=True)),
    ):
        mock_graph.ainvoke = AsyncMock(return_value=_mock_final_state())
        headers = {"Fly-Client-IP": "10.0.0.1"}
        for _ in range(5):
            resp = client.post(
                "/screen",
                json={"address": "1 Main St, Albany, NY"},
                headers=headers,
            )
            assert resp.status_code == 200
