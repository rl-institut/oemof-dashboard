from pathlib import Path

import pytest

from oemof_dashboard import datapackage, result

TEST_DATA = Path(__file__).parent / "test_data"


@pytest.fixture
def shipped_data() -> Path:
    """Root of the shipped adlershof test data, laid out as `datapackages/` and `results/`."""
    return TEST_DATA


def package_of(buses: list[str], connections: list[tuple[str, str]]) -> datapackage.Datapackage:
    """Datapackage with these Buses, and a Component for every other name in `connections`."""
    package = datapackage.Datapackage(connections=connections)
    for name in buses:
        package.buses[name] = datapackage.Node(name=name, type="bus", resource="bus")
    for component, _ in connections:
        package.components[component] = datapackage.Node(name=component, type="load", resource="loads")
    return package


def result_of(*entries: str) -> result.Result:
    """Result with these Result Entries, all empty."""
    return result.Result({entry: result.ResultEntry() for entry in entries})
