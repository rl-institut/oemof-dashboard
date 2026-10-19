from pathlib import Path

import pandas as pd
import pytest

from oemof_dashboard.charts import line_chart
from oemof_dashboard.result import Result, ResultEntry, read

BHKW_FLOW = ("bhkw-electricity", "flow")
BATTERY_CONTENT = ("battery_large-None", "storage_content")


@pytest.fixture
def adlershof(shipped_data: Path) -> Result:
    return read(shipped_data / "results" / "adlershof")


def test_one_result_one_outcome_is_one_webgl_line_on_real_timestamps(adlershof: Result) -> None:
    figure, notices = line_chart([BHKW_FLOW], {"adlershof": adlershof})

    (trace,) = figure.data
    assert trace.type == "scattergl"
    assert trace.name == "bhkw-electricity · flow · adlershof"
    assert pd.Timestamp(trace.x[0]) == pd.Timestamp("2050-01-01 00:00")
    assert len(trace.x) == len(trace.y) == 8761
    assert trace.line.color == "#2a78d6"
    assert trace.line.dash == "solid"
    assert notices == []


def test_series_are_outcomes_times_results_coloured_by_outcome_dashed_by_result(adlershof: Result) -> None:
    figure, _ = line_chart([BHKW_FLOW, BATTERY_CONTENT], {"base": adlershof, "variant": adlershof})

    assert [(trace.name, trace.line.color, trace.line.dash) for trace in figure.data] == [
        ("bhkw-electricity · flow · base", "#2a78d6", "solid"),
        ("bhkw-electricity · flow · variant", "#2a78d6", "dash"),
        ("battery_large-None · storage_content · base", "#eb6834", "solid"),
        ("battery_large-None · storage_content · variant", "#eb6834", "dash"),
    ]


def test_outcome_missing_from_a_result_is_legend_entry_without_data(adlershof: Result) -> None:
    other = Result({"bhkw-electricity": ResultEntry()})

    figure, _ = line_chart([BHKW_FLOW, BATTERY_CONTENT], {"base": adlershof, "other": other})

    by_name = {trace.name: trace for trace in figure.data}
    assert len(by_name["bhkw-electricity · flow · base"].y) == 8761
    for missing in (
        "bhkw-electricity · flow · other (missing)",
        "battery_large-None · storage_content · other (missing)",
    ):
        assert by_name[missing].showlegend is True
        assert all(value is None for value in by_name[missing].y)  # legend-only entry


@pytest.mark.parametrize(("result_count", "notice_count"), [(4, 0), (5, 1)])
def test_more_than_four_results_warns(adlershof: Result, result_count: int, notice_count: int) -> None:
    results = {f"r{index}": adlershof for index in range(result_count)}

    figure, notices = line_chart([BHKW_FLOW], results)

    assert len(figure.data) == result_count
    assert len(notices) == notice_count
    assert all("4 Results" in notice for notice in notices)


def test_empty_series_gives_empty_figure(adlershof: Result) -> None:
    figure, notices = line_chart([], {"adlershof": adlershof})

    assert figure.data == ()
    assert notices == []
