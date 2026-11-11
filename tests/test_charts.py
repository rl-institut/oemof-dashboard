from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pytest
from conftest import package_of, result_of

from oemof_dashboard import datapackage
from oemof_dashboard.charts import (
    CHART_TYPES,
    PALETTE,
    Chart,
    auto_title,
    bus_balance,
    chart_figure,
    chart_nodes,
    line_chart,
    sankey,
    webgl_warning,
)
from oemof_dashboard.result import Result, ResultEntry, read

BHKW_FLOW = ("bhkw-electricity", "flow")
BATTERY_CONTENT = ("battery_large-None", "storage_content")
PV_INVEST = ("pv-electricity", "invest")
PV_TOTAL = ("pv-electricity", "total")
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


@pytest.mark.parametrize("chart_type", ["line", "stacked_area", "duration_curve"])
def test_input_sequence_is_a_step_line_result_sequences_are_not(adlershof: Result, chart_type: str) -> None:
    series = [list(BHKW_FLOW), list(HEAT_DEMAND)]

    figure, _ = chart_figure(chart(type=chart_type, series=series), {"base": adlershof}, {HEAT_DEMAND: HEAT_PROFILE})

    assert [(trace.name, trace.line.shape) for trace in figure.data] == [
        ("bhkw-electricity · flow · base", None),
        ("adlershof · demands_profile · heat_central-residential", "hv"),
    ]


@pytest.mark.parametrize("chart_type", ["line", "duration_curve"])
def test_datapackage_and_result_values_get_their_own_titled_axis(adlershof: Result, chart_type: str) -> None:
    series = [list(BHKW_FLOW), list(HEAT_DEMAND)]

    figure, _ = chart_figure(chart(type=chart_type, series=series), {"base": adlershof}, {HEAT_DEMAND: HEAT_PROFILE})

    assert [trace.yaxis or "y" for trace in figure.data] == ["y2", "y"]
    assert (figure.layout.yaxis.title.text, figure.layout.yaxis.side) == ("Datapackage", None)
    assert (figure.layout.yaxis2.title.text, figure.layout.yaxis2.side, figure.layout.yaxis2.overlaying) == (
        "Result",
        "right",
        "y",
    )


@pytest.mark.parametrize("chart_type", ["line", "stacked_area", "duration_curve"])
def test_legend_is_split_into_datapackage_and_result_sections(adlershof: Result, chart_type: str) -> None:
    series = [list(BHKW_FLOW), list(HEAT_DEMAND)]

    figure, _ = chart_figure(chart(type=chart_type, series=series), {"base": adlershof}, {HEAT_DEMAND: HEAT_PROFILE})

    assert [(trace.name, trace.legend or "legend") for trace in figure.data] == [
        ("bhkw-electricity · flow · base", "legend2"),
        ("adlershof · demands_profile · heat_central-residential", "legend"),
    ]
    assert (figure.layout.legend.title.text, figure.layout.legend2.title.text) == ("Datapackage", "Result")


def test_stacked_area_splits_axes_per_subplot_and_keeps_results_comparable(adlershof: Result) -> None:
    series = [list(BHKW_FLOW), list(HEAT_DEMAND)]

    figure, _ = chart_figure(
        chart(type="stacked_area", series=series),
        {"base": adlershof, "variant": adlershof},
        {HEAT_DEMAND: HEAT_PROFILE},
    )

    def axis_of(trace: go.Scatter) -> go.layout.YAxis:
        return figure.layout["yaxis" + (trace.yaxis or "y").removeprefix("y")]

    titles = [(trace.name, axis_of(trace).title.text, axis_of(trace).side) for trace in figure.data]
    assert titles == [
        ("bhkw-electricity · flow · base", "Result", "right"),
        ("bhkw-electricity · flow · variant", "Result", "right"),
        ("adlershof · demands_profile · heat_central-residential", "Datapackage", None),
        ("adlershof · demands_profile · heat_central-residential", "Datapackage", None),
    ]
    base, variant = (axis_of(trace) for trace in figure.data[:2])
    assert base.matches == variant.matches is not None  # Result axes still shared across subplots


@pytest.mark.parametrize("chart_type", ["line", "stacked_area", "duration_curve"])
@pytest.mark.parametrize("item", [BHKW_FLOW, HEAT_DEMAND])
def test_chart_of_one_kind_keeps_one_untitled_axis(adlershof: Result, chart_type: str, item: tuple) -> None:
    figure, _ = chart_figure(
        chart(type=chart_type, series=[list(item)]), {"base": adlershof}, {HEAT_DEMAND: HEAT_PROFILE}
    )

    assert {trace.yaxis or "y" for trace in figure.data} == {"y"}
    assert figure.layout.yaxis.title.text is None
    assert "yaxis2" not in figure.to_dict()["layout"]
    assert {trace.legend or "legend" for trace in figure.data} == {"legend"}
    assert figure.layout.legend.title.text is None


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
    assert auto_title(chart(series=[list(HEAT_DEMAND)])) == "adlershof · demands_profile · heat_central-residential"


def scalars_result(**scalars: float) -> Result:
    """Result with one Result Entry pv-electricity holding these Result Scalars."""
    return Result({"pv-electricity": ResultEntry(scalars=scalars)})


def bar(**overrides: object) -> Chart:
    """Scalar bar chart of PV_INVEST and PV_TOTAL, overridden per test."""
    return chart(kind="scalars", type="bar", series=[list(PV_INVEST), list(PV_TOTAL)]) | overrides


def test_bar_chart_of_one_result_has_one_bar_per_outcome_coloured_by_outcome() -> None:
    figure, notices = chart_figure(bar(), {"base": scalars_result(invest=3.0, total=5.0)})

    assert [(trace.type, trace.name, list(trace.x), list(trace.y), trace.marker.color) for trace in figure.data] == [
        ("bar", "pv-electricity · invest", ["base"], [3.0], "#2a78d6"),
        ("bar", "pv-electricity · total", ["base"], [5.0], "#eb6834"),
    ]
    assert figure.layout.barmode == "group"
    assert figure.layout.title.text == "pv-electricity · invest, pv-electricity · total"
    assert notices == []


def test_bar_chart_groups_bars_by_result_even_with_numeric_names() -> None:
    results = {"base": scalars_result(invest=3.0, total=5.0), "2045": scalars_result(invest=4.0, total=6.0)}

    figure, _ = chart_figure(bar(), results)

    assert figure.layout.xaxis.type == "category"

    assert [(list(trace.x), list(trace.y)) for trace in figure.data] == [
        (["base", "2045"], [3.0, 4.0]),
        (["base", "2045"], [5.0, 6.0]),
    ]


def test_scalar_missing_from_a_result_is_legend_entry_without_bar() -> None:
    results = {"base": scalars_result(invest=3.0, total=5.0), "other": Result({})}

    figure, _ = chart_figure(bar(series=[list(PV_INVEST)]), results)

    invest, missing = figure.data
    assert list(invest.y) == [3.0, None]
    assert missing.name == "pv-electricity · invest · other (missing)"
    assert missing.showlegend is True
    assert missing.marker.color == "#2a78d6"
    assert missing.legendgroup == invest.legendgroup is not None  # toggled together
    assert all(value is None for value in missing.y)


def test_colour_override_applies_to_bar_outcome_only() -> None:
    figure, _ = chart_figure(
        bar(colours={"pv-electricity/total": "#123456"}), {"base": scalars_result(invest=3.0, total=5.0)}
    )

    assert [trace.marker.color for trace in figure.data] == ["#2a78d6", "#123456"]


PV_CAPACITY = ("adlershof", "pv", "capacity")


def test_input_scalar_is_one_hatched_bar_left_of_the_results_on_its_own_axis_and_legend() -> None:
    results = {"base": scalars_result(invest=3.0), "variant": scalars_result(invest=4.0)}

    figure, _ = chart_figure(bar(series=[list(PV_INVEST), list(PV_CAPACITY)]), results, {PV_CAPACITY: 10.0})

    invest, capacity = figure.data
    assert (list(invest.x), list(invest.y), invest.yaxis, invest.legend) == (
        ["base", "variant"],
        [3.0, 4.0],
        "y2",
        "legend2",
    )
    assert (capacity.name, list(capacity.x), list(capacity.y), capacity.marker.color) == (
        "adlershof · pv · capacity",
        ["adlershof"],
        [10.0],
        "#eb6834",
    )
    assert capacity.marker.pattern.shape == "/"
    assert invest.marker.pattern.shape is None
    assert (capacity.yaxis or "y", capacity.legend or "legend") == ("y", "legend")
    assert list(figure.layout.xaxis.categoryarray) == ["adlershof", "base", "variant"]
    assert (figure.layout.yaxis.title.text, figure.layout.yaxis2.title.text) == ("Datapackage", "Result")
    assert (figure.layout.legend.title.text, figure.layout.legend2.title.text) == ("Datapackage", "Result")


def test_input_scalar_not_loaded_is_hatched_legend_entry_without_bar() -> None:
    figure, _ = chart_figure(bar(series=[list(PV_CAPACITY)]), {"base": scalars_result()}, {})

    (missing,) = figure.data
    assert missing.name == "adlershof · pv · capacity (missing)"
    assert missing.showlegend is True
    assert missing.marker.pattern.shape == "/"
    assert all(value is None for value in missing.y)
    assert "yaxis2" not in figure.to_dict()["layout"]


def test_input_scalar_of_datapackage_without_loaded_values_gets_no_category() -> None:
    figure, _ = chart_figure(bar(series=[list(PV_INVEST), list(PV_CAPACITY)]), {"base": scalars_result(invest=3.0)}, {})

    assert list(figure.layout.xaxis.categoryarray) == ["base"]


@pytest.mark.parametrize(("series", "inputs"), [([PV_INVEST], {}), ([PV_CAPACITY], {PV_CAPACITY: 10.0})])
def test_bar_chart_of_one_kind_keeps_one_untitled_axis_and_legend(series: list, inputs: dict) -> None:
    figure, _ = chart_figure(bar(series=[list(item) for item in series]), {"base": scalars_result(invest=3.0)}, inputs)

    assert {trace.yaxis or "y" for trace in figure.data} == {"y"}
    assert {trace.legend or "legend" for trace in figure.data} == {"legend"}
    assert figure.layout.yaxis.title.text is None
    assert "yaxis2" not in figure.to_dict()["layout"]


def test_bar_is_the_only_type_of_scalar_kind() -> None:
    assert CHART_TYPES["scalars"] == ("bar",)


@pytest.mark.parametrize(("kind", "chart_type"), [("sequences", "bar"), ("scalars", "line")])
def test_type_must_belong_to_kind(kind: str, chart_type: str) -> None:
    with pytest.raises(ValueError, match=chart_type):
        chart_figure(chart(kind=kind, type=chart_type), {})


def test_bar_charts_are_not_webgl() -> None:
    assert webgl_warning([bar(id=str(index)) for index in range(9)]) is None


@pytest.fixture
def adlershof_package(shipped_data: Path) -> datapackage.Datapackage:
    return datapackage.read(shipped_data / "datapackages" / "adlershof")


def sankey_links(trace: go.Sankey) -> dict[tuple[str, str], float]:
    """Links of a Sankey trace as (source, target) node label → value."""
    labels = trace.node.label
    return {
        (labels[source], labels[target]): value
        for source, target, value in zip(trace.link.source, trace.link.target, trace.link.value, strict=True)
    }


def test_sankey_links_every_flow_of_the_system_with_its_summed_flow(
    adlershof: Result, adlershof_package: datapackage.Datapackage
) -> None:
    figure, notices = sankey({"adlershof": adlershof}, adlershof_package)

    (trace,) = figure.data
    assert trace.type == "sankey"
    links = sankey_links(trace)
    assert len(links) == 80  # every Flow file of the shipped Result
    assert links[("gas-import", "gas")] == pytest.approx(83725062.81)
    assert links[("gas", "heat_decentral-gas_boiler")] == pytest.approx(83725062.81)
    assert links[("bhkw", "electricity")] == 0.0
    assert "Σ flow" in trace.link.hovertemplate
    assert notices == []


def flows(**flow_values: list[float]) -> Result:
    """Result with these Result Entries, each holding a `flow` Result Sequence; an empty list gives no `flow`."""
    return Result(
        {
            entry: ResultEntry(
                sequences=pd.DataFrame(
                    {"flow": values}, index=pd.date_range("2050-01-01", periods=len(values), freq="h")
                )
                if values
                else pd.DataFrame()
            )
            for entry, values in flow_values.items()
        }
    )


TWO_BUSES = package_of(["el", "heat"], [("pv", "el"), ("demand", "el"), ("hp", "el"), ("hp", "heat")])


def test_sankey_drops_trailing_nan_and_lists_flows_without_flow_in_a_notice() -> None:
    result = flows(**{"pv-el": [1.0, 2.0, float("nan")], "el-demand": [], "el-hp": []})

    figure, notices = sankey({"base": result}, TWO_BUSES)

    assert sankey_links(figure.data[0]) == {("pv", "el"): 3.0}
    assert notices == ["base: no flow for el-demand, el-hp"]


def test_sankey_bus_filter_keeps_flows_from_or_to_that_bus(
    adlershof: Result, adlershof_package: datapackage.Datapackage
) -> None:
    figure, _ = sankey({"adlershof": adlershof}, adlershof_package, bus="gas")

    assert set(sankey_links(figure.data[0])) == {
        ("gas", "bhkw"),
        ("gas", "gas-excess"),
        ("gas", "heat_central-gas_boiler"),
        ("gas", "heat_decentral-gas_boiler"),
        ("gas-import", "gas"),
        ("gas-shortage", "gas"),
    }


def test_sankey_bus_filter_lists_only_that_bus_flows_without_flow() -> None:
    result = flows(**{"pv-el": [1.0], "el-hp": [], "hp-heat": []})

    _, notices = sankey({"base": result}, TWO_BUSES, bus="heat")

    assert notices == ["base: no flow for hp-heat"]


def test_sankey_per_result_side_by_side_titled_with_the_result() -> None:
    results = {"base": flows(**{"pv-el": [1.0]}), "variant": flows(**{"pv-el": [2.0]})}

    figure, _ = sankey(results, TWO_BUSES)

    assert [sankey_links(trace) for trace in figure.data] == [{("pv", "el"): 1.0}, {("pv", "el"): 2.0}]
    (left, middle), (start, right) = (trace.domain.x for trace in figure.data)
    assert 0 <= left < middle <= start < right <= 1
    assert [annotation.text for annotation in figure.layout.annotations] == ["base", "variant"]


def test_sankey_colours_buses_by_datapackage_order_links_by_their_bus_components_by_first_connection() -> None:
    result = flows(**{"hp-heat": [1.0], "el-hp": [1.0], "pv-el": [1.0]})

    (trace,) = sankey({"base": result}, TWO_BUSES)[0].data

    colours = dict(zip(trace.node.label, trace.node.color, strict=True))
    assert colours["el"] == PALETTE[0]
    assert colours["heat"] == PALETTE[1]
    assert colours["pv"] == PALETTE[0]
    assert colours["hp"] == PALETTE[0]  # first Connection is to el, though its first link is to heat
    assert list(trace.link.color) == [f"{PALETTE[1]}80", f"{PALETTE[0]}80", f"{PALETTE[0]}80"]


def system(**overrides: object) -> Chart:
    """Sankey chart of the whole system, overridden per test."""
    return chart(kind="system", type="sankey", series=[]) | overrides


@pytest.mark.parametrize(("bus", "title", "link_count"), [(None, "Sankey", 3), ("heat", "Sankey · heat", 1)])
def test_sankey_chart_filters_by_its_bus_and_is_titled_after_it(bus: str | None, title: str, link_count: int) -> None:
    result = flows(**{"hp-heat": [1.0], "el-hp": [1.0], "pv-el": [1.0]})

    figure, _ = chart_figure(system(bus=bus), {"base": result}, package=TWO_BUSES)

    assert len(sankey_links(figure.data[0])) == link_count
    assert figure.layout.title.text == title


def test_sankey_chart_without_datapackage_is_empty_with_notice() -> None:
    figure, notices = chart_figure(system(), {"base": flows(**{"pv-el": [1.0]})})

    assert figure.data == ()
    assert notices == ["Sankey needs a selected Datapackage."]


def test_sankey_and_bus_balance_are_the_types_of_system_kind() -> None:
    assert CHART_TYPES["system"] == ("sankey", "bus_balance")


def test_sankey_bus_filter_not_in_datapackage_is_noticed() -> None:
    figure, notices = sankey({"base": flows(**{"pv-el": [1.0]})}, TWO_BUSES, bus="gas")

    assert sankey_links(figure.data[0]) == {}
    assert notices == ["Bus gas (missing): not in the Datapackage."]


def stacks(figure: go.Figure) -> list[tuple[str, list[float]]]:
    """Stacked traces of a Bus balance as (name, values), in drawing order."""
    return [(trace.name, list(trace.y)) for trace in figure.data if trace.stackgroup]


def test_bus_balance_stacks_incoming_flows_above_zero_and_outgoing_below_labelled_by_other_node() -> None:
    result = flows(**{"pv-el": [3.0, 1.0], "el-demand": [2.0, 0.5], "el-hp": [1.0, 0.5]})

    figure, notices = bus_balance({"base": result}, TWO_BUSES, "el")

    assert stacks(figure) == [("pv", [3.0, 1.0]), ("demand", [-2.0, -0.5]), ("hp", [-1.0, -0.5])]
    assert len({trace.stackgroup for trace in figure.data}) == 2  # in and out stack apart
    assert notices == []


WIND_PV_BUS = package_of(["el"], [("wind", "el"), ("pv", "el"), ("demand", "el")])


def test_bus_balance_stacks_by_flow_sum_over_the_result_selection_in_one_subplot_per_result() -> None:
    results = {
        "base": flows(**{"wind-el": [2.0], "pv-el": [1.0], "el-demand": [3.0]}),
        "variant": flows(**{"wind-el": [1.0], "pv-el": [5.0], "el-demand": [6.0]}),
    }

    figure, _ = bus_balance(results, WIND_PV_BUS, "el")

    # Σ over both Results: demand 9, pv 6, wind 3, though wind is larger than pv in base
    assert [name for name, _ in stacks(figure)] == ["demand", "pv", "wind"] * 2
    assert [trace.yaxis for trace in figure.data] == ["y"] * 3 + ["y2"] * 3
    assert [annotation.text for annotation in figure.layout.annotations] == ["base", "variant"]
    colours = [trace.line.color for trace in figure.data]
    assert colours == PALETTE[:3] * 2
    assert [trace.showlegend is not False for trace in figure.data] == [True] * 3 + [False] * 3


def test_balanced_bus_has_no_residual(adlershof: Result, adlershof_package: datapackage.Datapackage) -> None:
    figure, notices = bus_balance({"adlershof": adlershof}, adlershof_package, "electricity")

    assert len(figure.data) == 27  # every Flow from or to electricity
    assert all(trace.stackgroup for trace in figure.data)
    assert notices == []


@pytest.mark.parametrize(("demand", "residual"), [(999_999.5, None), (999_998.0, [2.0, 0.0])])
def test_residual_is_drawn_only_above_a_millionth_of_the_largest_flow(demand: float, residual: list | None) -> None:
    result = flows(**{"pv-el": [1_000_000.0, 1.0], "el-demand": [demand, 1.0]})

    figure, _ = bus_balance({"base": result}, TWO_BUSES, "el")

    lines = [list(trace.y) for trace in figure.data if trace.name == "residual" and not trace.stackgroup]
    assert lines == ([residual] if residual else [])


def test_bus_balance_of_bus_not_in_datapackage_is_missing() -> None:
    figure, notices = bus_balance({"base": flows(**{"pv-el": [1.0]})}, TWO_BUSES, "gas")

    assert figure.data == ()
    assert notices == ["Bus gas (missing): not in the Datapackage."]


def test_bus_balance_of_result_without_flows_of_the_bus_is_empty_subplot_with_notice() -> None:
    results = {"base": flows(**{"pv-el": [1.0], "el-demand": [1.0]}), "variant": flows(**{"hp-heat": [1.0]})}

    figure, notices = bus_balance(results, TWO_BUSES, "el")

    assert [trace.yaxis for trace in figure.data] == ["y", "y"]
    assert [annotation.text for annotation in figure.layout.annotations] == ["base", "variant"]
    assert notices == ["variant: no Flows of el (missing)"]


def test_bus_balance_counts_flows_not_in_datapackage_and_lists_unmatched_entries_and_flows_without_flow() -> None:
    # heat-el has no Connection; el-nowhere doesn't split into two Datapackage names; el-demand has no `flow`
    result = flows(**{"pv-el": [3.0], "heat-el": [1.0], "el-nowhere": [2.0], "el-demand": []})

    figure, notices = bus_balance({"base": result}, TWO_BUSES, "el")

    assert stacks(figure) == [("pv", [3.0]), ("heat", [1.0])]
    assert notices == ["base: no flow for el-demand", "base: unmatched, left out: el-nowhere"]


def test_bus_balance_chart_is_titled_after_its_bus() -> None:
    result = flows(**{"pv-el": [1.0], "el-demand": [1.0]})

    figure, _ = chart_figure(system(type="bus_balance", bus="el"), {"base": result}, package=TWO_BUSES)

    assert stacks(figure) == [("pv", [1.0]), ("demand", [-1.0])]
    assert figure.layout.title.text == "Bus balance · el"


def test_bus_balance_chart_without_datapackage_is_empty_with_notice() -> None:
    figure, notices = chart_figure(system(type="bus_balance", bus="el"), {"base": flows(**{"pv-el": [1.0]})})

    assert figure.data == ()
    assert notices == ["Bus balance needs a selected Datapackage."]


@pytest.mark.parametrize(
    ("series", "nodes"),
    [
        ([list(BHKW_FLOW)], ["bhkw", "electricity"]),
        (
            [list(BATTERY_CONTENT), list(BHKW_FLOW), ["gas-bhkw", "flow"]],
            ["battery_large", "bhkw", "electricity", "gas"],
        ),
        ([["no-such-entry", "flow"], list(HEAT_DEMAND)], []),
    ],
)
def test_chart_nodes_are_the_nodes_of_its_matched_result_entries_in_series_order(
    adlershof: Result, adlershof_package: datapackage.Datapackage, series: list, nodes: list[str]
) -> None:
    assert chart_nodes(chart(series=series), {"adlershof": adlershof}, adlershof_package) == nodes


@pytest.mark.parametrize(
    ("overrides", "nodes"),
    [
        ({"type": "bus_balance", "bus": "electricity"}, ["electricity"]),
        ({"bus": "heat_central"}, ["heat_central"]),
        ({"bus": None}, []),
        ({"bus": "no_such_bus"}, []),
    ],
)
def test_system_chart_nodes_are_its_bus(
    adlershof: Result, adlershof_package: datapackage.Datapackage, overrides: dict, nodes: list[str]
) -> None:
    assert chart_nodes(system(**overrides), {"adlershof": adlershof}, adlershof_package) == nodes


def test_chart_nodes_without_datapackage_are_none(adlershof: Result) -> None:
    assert chart_nodes(chart(), {"adlershof": adlershof}, None) == []
    assert chart_nodes(system(bus="electricity"), {"adlershof": adlershof}, None) == []


def test_flow_not_in_datapackage_still_gives_chips_as_the_graph_draws_it() -> None:
    nodes = chart_nodes(
        chart(series=[["pv-heat", "flow"], ["foo-bar", "flow"]]), {"base": result_of("pv-heat")}, TWO_BUSES
    )

    assert nodes == ["pv", "heat"]
