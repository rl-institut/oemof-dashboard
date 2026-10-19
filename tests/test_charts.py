from pathlib import Path

import pandas as pd
import pytest

from oemof_dashboard.charts import CHART_TYPES, Chart, auto_title, chart_figure, line_chart, webgl_warning
from oemof_dashboard.result import Result, ResultEntry, read

BHKW_FLOW = ("bhkw-electricity", "flow")
BATTERY_CONTENT = ("battery_large-None", "storage_content")
HEAT_DEMAND = ("adlershof", "demands_profile", "heat_central-residential")
HEAT_PROFILE = pd.Series(
    [0.2, float("nan"), 0.5], index=pd.date_range("2050-01-01", periods=3, freq="h"), name=HEAT_DEMAND[2]
)


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


def chart(**overrides: object) -> Chart:
    """Sequence line chart of BHKW_FLOW with defaults, overridden per test."""
    return {
        "id": "c1",
        "kind": "sequences",
        "type": "line",
        "title": None,
        "series": [list(BHKW_FLOW)],
        "colours": {},
        "width": "half",
    } | overrides


@pytest.mark.parametrize(
    ("series", "title", "expected"),
    [
        ([list(BHKW_FLOW)], None, "bhkw-electricity · flow"),
        (
            [list(BHKW_FLOW), list(BATTERY_CONTENT)],
            None,
            "bhkw-electricity · flow, battery_large-None · storage_content",
        ),
        ([list(BHKW_FLOW)] * 4, None, "bhkw-electricity · flow, bhkw-electricity · flow, bhkw-electricity · flow +1"),
        ([], None, "Empty chart"),
        ([list(BHKW_FLOW)], "CHP output", "CHP output"),
    ],
)
def test_title_defaults_to_series_unless_set(adlershof: Result, series: list, title: str | None, expected: str) -> None:
    figure, _ = chart_figure(chart(series=series, title=title), {"adlershof": adlershof})

    assert figure.layout.title.text == expected


def test_emptied_chart_is_empty_figure(adlershof: Result) -> None:
    figure, _ = chart_figure(chart(series=[]), {"adlershof": adlershof})

    assert figure.data == ()


def test_type_must_belong_to_kind(adlershof: Result) -> None:
    assert "bar" not in CHART_TYPES["sequences"]
    with pytest.raises(ValueError, match="bar"):
        chart_figure(chart(type="bar"), {"adlershof": adlershof})


def test_colour_override_replaces_palette_for_that_outcome_only(adlershof: Result) -> None:
    series = [list(BHKW_FLOW), list(BATTERY_CONTENT)]

    figure, _ = chart_figure(
        chart(series=series, colours={"battery_large-None/storage_content": "#123456"}),
        {"base": adlershof, "variant": adlershof},
    )

    assert [(trace.line.color, trace.line.dash) for trace in figure.data] == [
        ("#2a78d6", "solid"),
        ("#2a78d6", "dash"),
        ("#123456", "solid"),
        ("#123456", "dash"),
    ]


@pytest.mark.parametrize(("chart_count", "warned"), [(8, False), (9, True)])
def test_more_than_eight_webgl_charts_warns(chart_count: int, warned: bool) -> None:
    warning = webgl_warning([chart(id=str(index)) for index in range(chart_count)])

    assert (warning is not None) is warned


@pytest.mark.parametrize("names", [["base"], ["base", "variant"]])
def test_stacked_area_stacks_outcomes_in_one_subplot_per_result_on_shared_axes(
    adlershof: Result, names: list[str]
) -> None:
    series = [list(BHKW_FLOW), list(BATTERY_CONTENT)]

    figure, _ = chart_figure(chart(type="stacked_area", series=series), dict.fromkeys(names, adlershof))

    assert [annotation.text for annotation in figure.layout.annotations] == names  # subplot titles
    for row, name in enumerate(names, start=1):
        axis = "x" if row == 1 else f"x{row}"
        traces = [trace for trace in figure.data if trace.xaxis == axis]
        assert [trace.name for trace in traces] == [
            f"bhkw-electricity · flow · {name}",
            f"battery_large-None · storage_content · {name}",
        ]
        assert {trace.stackgroup for trace in traces} == {str(row)}
        assert [trace.line.color for trace in traces] == ["#2a78d6", "#eb6834"]
    for axis in ("x", "y"):
        layouts = [figure.layout[f"{axis}axis{row if row > 1 else ''}"] for row in range(1, len(names) + 1)]
        linked = {layout.matches or f"{axis}{row if row > 1 else ''}" for row, layout in enumerate(layouts, start=1)}
        assert len(linked) == 1, f"{axis} axes not shared"


def test_duration_curve_sorts_descending_drops_nan_on_hour_ranks() -> None:
    index = pd.date_range("2050-01-01", periods=5, freq="h")
    sequences = pd.DataFrame({"flow": [2.0, 5.0, float("nan"), 1.0, 3.0]}, index=index)
    result = Result({"bhkw-electricity": ResultEntry(sequences=sequences)})

    figure, _ = chart_figure(chart(type="duration_curve"), {"base": result})

    (trace,) = figure.data
    assert trace.type == "scattergl"
    assert list(trace.x) == [0, 1, 2, 3]
    assert list(trace.y) == [5.0, 3.0, 2.0, 1.0]
    assert figure.layout.xaxis.type != "date"


def test_duration_curve_dashes_results_and_warns_beyond_four(adlershof: Result) -> None:
    results = {f"r{index}": adlershof for index in range(5)}

    figure, notices = chart_figure(chart(type="duration_curve"), results)

    assert [(trace.name, trace.line.dash) for trace in figure.data[:2]] == [
        ("bhkw-electricity · flow · r0", "solid"),
        ("bhkw-electricity · flow · r1", "dash"),
    ]
    assert len(figure.data[0].y) == 8760  # trailing NaN of the 8761st row dropped
    assert len(notices) == 1


@pytest.mark.parametrize("chart_type", ["line", "duration_curve"])
def test_input_sequence_appears_once_in_palette_order_next_to_outcomes(adlershof: Result, chart_type: str) -> None:
    series = [list(BHKW_FLOW), list(HEAT_DEMAND)]

    figure, _ = chart_figure(
        chart(type=chart_type, series=series), {"base": adlershof, "variant": adlershof}, {HEAT_DEMAND: HEAT_PROFILE}
    )

    assert [(trace.name, trace.line.color) for trace in figure.data] == [
        ("bhkw-electricity · flow · base", "#2a78d6"),
        ("bhkw-electricity · flow · variant", "#2a78d6"),
        ("adlershof · demands_profile · heat_central-residential", "#eb6834"),
    ]


def test_input_sequence_duration_curve_drops_nan() -> None:
    figure, _ = chart_figure(chart(type="duration_curve", series=[list(HEAT_DEMAND)]), {}, {HEAT_DEMAND: HEAT_PROFILE})

    (trace,) = figure.data
    assert list(trace.y) == [0.5, 0.2]


def test_input_sequence_overlays_every_stacked_subplot_with_one_legend_entry(adlershof: Result) -> None:
    series = [list(BHKW_FLOW), list(HEAT_DEMAND)]

    figure, _ = chart_figure(
        chart(type="stacked_area", series=series),
        {"base": adlershof, "variant": adlershof},
        {HEAT_DEMAND: HEAT_PROFILE},
    )

    profiles = [
        trace for trace in figure.data if trace.name == "adlershof · demands_profile · heat_central-residential"
    ]
    assert [trace.xaxis for trace in profiles] == ["x", "x2"]
    assert [trace.showlegend is not False for trace in profiles] == [True, False]
    assert all(trace.stackgroup is None for trace in profiles)  # drawn as a line over the stack


@pytest.mark.parametrize("chart_type", ["line", "stacked_area", "duration_curve"])
def test_input_sequence_not_loaded_is_missing(adlershof: Result, chart_type: str) -> None:
    figure, _ = chart_figure(chart(type=chart_type, series=[list(HEAT_DEMAND)]), {"base": adlershof}, {})

    (trace,) = figure.data
    assert trace.name == "adlershof · demands_profile · heat_central-residential (missing)"
    assert trace.showlegend is True


def test_colour_override_applies_to_input_sequence(adlershof: Result) -> None:
    figure, _ = chart_figure(
        chart(
            series=[list(HEAT_DEMAND)], colours={"input:adlershof/demands_profile/heat_central-residential": "#123456"}
        ),
        {"base": adlershof},
        {HEAT_DEMAND: HEAT_PROFILE},
    )

    assert figure.data[0].line.color == "#123456"


def test_auto_title_names_input_sequences() -> None:
    assert auto_title([list(HEAT_DEMAND)]) == "adlershof · demands_profile · heat_central-residential"
