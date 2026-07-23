import pytest

from app.rate_limit import reset_limits


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    reset_limits()
    yield
    reset_limits()
