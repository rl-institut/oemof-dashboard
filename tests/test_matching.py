from pathlib import Path

import pytest
from conftest import package_of, result_of

from oemof_dashboard import datapackage, result
from oemof_dashboard.matching import match


def test_all_adlershof_result_entries_split_uniquely(shipped_data: Path) -> None:
    matching = match(
        result.read(shipped_data / "results" / "adlershof"),
        datapackage.read(shipped_data / "datapackages" / "adlershof"),
    )

    assert matching.unmatched == {}
    assert len(matching.matched) == 85
    assert matching.matched["bhkw-electricity"] == ("bhkw", "electricity")
    assert matching.matched["battery_large-None"] == ("battery_large", None)
    assert matching.matched["electricity-import-electricity"] == ("electricity-import", "electricity")
    assert matching.matched["heat_central-gas_boiler-heat_central"] == ("heat_central-gas_boiler", "heat_central")


def test_entry_without_valid_split_is_unmatched() -> None:
    matching = match(result_of("pv-el", "wind-el", "pv"), package_of(["el"], [("pv", "el")]))

    assert matching.unmatched == {
        "wind-el": "no split into two Datapackage names",
        "pv": "no split into two Datapackage names",
    }
    assert "wind-el" not in matching.matched


def test_entry_with_several_valid_splits_is_unmatched_not_guessed() -> None:
    package = package_of(["c", "a"], [("a-b", "c"), ("b-c", "a")])

    matching = match(result_of("a-b-c"), package)

    assert matching.unmatched == {"a-b-c": "ambiguous: a → b-c, a-b → c"}
    assert matching.matched == {}


def test_split_flow_without_connection_is_kept_and_listed_as_not_in_datapackage() -> None:
    package = package_of(["el", "heat"], [("pv", "el"), ("boiler", "heat")])

    matching = match(result_of("pv-el", "el-pv", "pv-heat"), package)

    assert matching.matched == {"pv-el": ("pv", "el"), "el-pv": ("el", "pv"), "pv-heat": ("pv", "heat")}
    assert matching.unmatched == {"pv-heat": "not in Datapackage: no Connection between pv and heat"}


@pytest.mark.parametrize(
    ("entries", "ratio"),
    [(("pv-el", "pv-None"), 1.0), (("pv-el", "x-el", "y"), 1 / 3), (("pv-heat", "pv-el"), 0.5), ((), 1.0)],
)
def test_match_ratio_counts_entries_not_unmatched(entries: tuple[str, ...], ratio: float) -> None:
    package = package_of(["el", "heat"], [("pv", "el")])

    assert match(result_of(*entries), package).ratio == pytest.approx(ratio)
