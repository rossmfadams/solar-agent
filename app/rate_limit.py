import time
from collections import defaultdict, deque

# Generous per-IP limit: stops one actor scripting large volumes of sequential
# requests without biting a small group demo behind a shared/NAT'd IP.
RATE_LIMIT_MAX_RUNS = 20
RATE_LIMIT_WINDOW_SECONDS = 3600

# Real backstop on simultaneous spend, independent of how many people share an IP.
MAX_CONCURRENT_RUNS = 5

FRIENDLY_LIMIT_MESSAGE = "Helios demo is popular right now — try again in a few minutes."

_ip_hits: dict[str, deque] = defaultdict(deque)
_in_flight = 0


class RateLimitExceeded(Exception):
    pass


class ConcurrencyLimitExceeded(Exception):
    pass


def check_rate_limit(ip: str) -> None:
    now = time.monotonic()
    hits = _ip_hits[ip]
    while hits and now - hits[0] > RATE_LIMIT_WINDOW_SECONDS:
        hits.popleft()
    if len(hits) >= RATE_LIMIT_MAX_RUNS:
        raise RateLimitExceeded()
    hits.append(now)


def acquire_concurrency_slot() -> None:
    global _in_flight
    if _in_flight >= MAX_CONCURRENT_RUNS:
        raise ConcurrencyLimitExceeded()
    _in_flight += 1


def release_concurrency_slot() -> None:
    global _in_flight
    _in_flight = max(0, _in_flight - 1)


def reset_limits() -> None:
    """Test-only: clear all in-memory limiter state."""
    global _in_flight
    _ip_hits.clear()
    _in_flight = 0
