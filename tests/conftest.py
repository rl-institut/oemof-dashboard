from pathlib import Path

import pytest

TEST_DATA = Path(__file__).parent / "test_data"


@pytest.fixture
def shipped_data() -> Path:
    """Root of the shipped adlershof test data, laid out as `datapackages/` and `results/`."""
    return TEST_DATA
