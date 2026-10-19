"""Pure figure builders: Outcomes × Result Selection → plotly figure plus notices. No Dash imports."""

from collections.abc import Iterator
from typing import Literal, TypedDict

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from oemof_dashboard.result import Result, ResultEntry

# Validated categorical palette (light mode), fixed order; colour encodes Entry×variable / Input Sequence, never
# the Result.
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
# The Result is encoded by dash style; the first four stay distinguishable.
DASHES = ["solid", "dash", "dot", "dashdot", "longdash", "longdashdot"]
MAX_DISTINCT_RESULTS = 4
# Chart types per kind; a chart's kind is fixed at creation, its type switches within the kind.
CHART_TYPES = {"sequences": ("line", "stacked_area", "duration_curve")}
MAX_TITLE_SERIES = 3
# Browsers cap live WebGL contexts (~8–16); beyond that charts go blank.
WEBGL_TYPES = {"line", "duration_curve"}
MAX_WEBGL_CHARTS = 8
# Prefix of an Input Sequence's series key; Outcome keys are "<Result Entry>/<variable>".
INPUT_PREFIX = "input:"


class Chart(TypedDict):
    """Chart config as kept in the charts store (JSON).

    `series` holds Outcomes as [Result Entry, variable] and Input Sequences as [Datapackage, resource, column];
    `colours` maps a series key (see `series_key`) to a hex colour overriding the palette; `title` None means auto.
    """

    id: str
    kind: Literal["sequences"]
    type: Literal["line", "stacked_area", "duration_curve"]
    title: str | None
    series: list[list[str]]
    colours: dict[str, str]
    width: Literal["half", "full"]


def series_key(item: list[str] | tuple[str, ...]) -> str:
    """Key of a series item, as used for dropdown values and colour overrides.

    Args:
        item: Outcome as [Result Entry, variable] or Input Sequence as [Datapackage, resource, column].

    Returns:
        "<Result Entry>/<variable>" or "input:<Datapackage>/<resource>/<column>".
    """
    return INPUT_PREFIX + "/".join(item) if len(item) == 3 else "/".join(item)


def series_item(key: str) -> list[str]:
    """Series item of a key made by `series_key`.

    Args:
        key: Series key.

    Returns:
        [Result Entry, variable] or [Datapackage, resource, column].
    """
    # Result Entry, Datapackage and resource names come from file and folder names, so they never contain "/".
    if key.startswith(INPUT_PREFIX):
        return key.removeprefix(INPUT_PREFIX).split("/", 2)
    return key.split("/", 1)


def series_label(item: list[str] | tuple[str, ...]) -> str:
    """Label of a series item.

    Args:
        item: Outcome as [Result Entry, variable] or Input Sequence as [Datapackage, resource, column].

    Returns:
        Its parts joined, e.g. "bhkw-electricity · flow" or "adlershof · demands_profile · wind-profile".
    """
    return " · ".join(item)


def auto_title(series: list[list[str]]) -> str:
    """Auto title of a chart from its first series items.

    Args:
        series: Outcomes and Input Sequences as stored in a chart.

    Returns:
        Title such as "bhkw-electricity · flow, wind-electricity · flow +2", or "Empty chart" without series.
    """
    if not series:
        return "Empty chart"
    title = ", ".join(map(series_label, series[:MAX_TITLE_SERIES]))
    hidden = len(series) - MAX_TITLE_SERIES
    return f"{title} +{hidden}" if hidden > 0 else title


def chart_figure(
    chart: Chart, results: dict[str, Result], inputs: dict[tuple[str, str, str], pd.Series] | None = None
) -> tuple[go.Figure, list[str]]:
    """Build the figure of one chart for the Result Selection.

    Args:
        chart: Chart config.
        results: Result Selection as Result name → Result.
        inputs: Loaded Input Sequences by (Datapackage, resource, column); series not in it show as missing.

    Returns:
        Figure titled with the chart's title, or the auto title if unset. Notices to show with it.

    Raises:
        ValueError: If the chart's type doesn't belong to its kind.
    """
    if chart["type"] not in CHART_TYPES.get(chart["kind"], ()):
        raise ValueError(f"Chart type {chart['type']!r} isn't of kind {chart['kind']!r}")
    builder = {"line": line_chart, "stacked_area": stacked_area, "duration_curve": duration_curve}[chart["type"]]
    figure, notices = builder([tuple(item) for item in chart["series"]], results, chart["colours"], inputs)
    figure.update_layout(title_text=chart["title"] or auto_title(chart["series"]), margin_t=30)
    return figure, notices


def _traces(
    series: list[tuple[str, ...]],
    results: dict[str, Result],
    colours: dict[str, str] | None,
    inputs: dict[tuple[str, str, str], pd.Series] | None,
) -> Iterator[tuple[str, int | None, str, pd.Series | None]]:
    # (colour, Result index, trace name, data or None if missing) per Outcome × Result and once per Input Sequence
    # (Result index None), in series order.
    for index, item in enumerate(series):
        # ponytail: palette wraps after 8 series; a colour override is the way out
        colour = (colours or {}).get(series_key(item), PALETTE[index % len(PALETTE)])
        if len(item) == 3:
            yield colour, None, series_label(item), (inputs or {}).get(item)
            continue
        entry, variable = item
        for result_index, (result_name, result) in enumerate(results.items()):
            sequences = result.entries.get(entry, ResultEntry()).sequences
            yield colour, result_index, f"{series_label(item)} · {result_name}", sequences.get(variable)


def line_chart(
    series: list[tuple[str, ...]],
    results: dict[str, Result],
    colours: dict[str, str] | None = None,
    inputs: dict[tuple[str, str, str], pd.Series] | None = None,
) -> tuple[go.Figure, list[str]]:
    """Build a line chart of Result Sequences for every Result in the Result Selection, plus Input Sequences.

    Args:
        series: Outcomes as (Result Entry, variable) and Input Sequences as (Datapackage, resource, column), in
            palette order.
        results: Result Selection as Result name → Result, in dash style order.
        colours: Hex colours by series key, overriding the palette for those series.
        inputs: Loaded Input Sequences by (Datapackage, resource, column).

    Returns:
        Figure with one `Scattergl` trace per Outcome × Result and one solid trace per Input Sequence on a shared
        datetime x-axis; a series missing from a Result or from `inputs` is a legend entry suffixed "(missing)"
        without data. Notices to show with it.
    """
    return _dashed_chart(series, results, colours, inputs, duration=False)


def duration_curve(
    series: list[tuple[str, ...]],
    results: dict[str, Result],
    colours: dict[str, str] | None = None,
    inputs: dict[tuple[str, str, str], pd.Series] | None = None,
) -> tuple[go.Figure, list[str]]:
    """Build duration curves of Result Sequences for every Result in the Result Selection, plus Input Sequences.

    Args:
        series: As for `line_chart`.
        results: Result Selection as Result name → Result, in dash style order.
        colours: Hex colours by series key, overriding the palette for those series.
        inputs: Loaded Input Sequences by (Datapackage, resource, column).

    Returns:
        Figure with traces as in `line_chart`, but values sorted descending with NaN dropped, against their rank in
        hours (0…n−1). Notices to show with it.
    """
    return _dashed_chart(series, results, colours, inputs, duration=True)


def _dashed_chart(
    series: list[tuple[str, ...]],
    results: dict[str, Result],
    colours: dict[str, str] | None,
    inputs: dict[tuple[str, str, str], pd.Series] | None,
    duration: bool,
) -> tuple[go.Figure, list[str]]:
    # Line chart or duration curve: the Result is encoded by dash style, Input Sequences are solid.
    xaxis = {"title": {"text": "hours (rank)"}} if duration else {"type": "date"}
    figure = go.Figure(layout={"xaxis": xaxis, "margin": {"l": 40, "r": 10, "t": 10, "b": 30}})
    for colour, result_index, name, column in _traces(series, results, colours, inputs):
        line = {"color": colour, "dash": DASHES[(result_index or 0) % len(DASHES)]}
        if column is None:
            figure.add_trace(
                go.Scattergl(x=[None], y=[None], name=f"{name} (missing)", mode="lines", line=line, showlegend=True)
            )
            continue
        if duration:
            values = column.dropna().sort_values(ascending=False).to_numpy()
            x = np.arange(len(values))
        else:
            values, x = column.to_numpy(), column.index
        figure.add_trace(go.Scattergl(x=x, y=values, name=name, mode="lines", line=line))
    notices = []
    if len(results) > MAX_DISTINCT_RESULTS:
        notices.append(f"More than {MAX_DISTINCT_RESULTS} Results: dash styles get hard to tell apart.")
    return figure, notices


def stacked_area(
    series: list[tuple[str, ...]],
    results: dict[str, Result],
    colours: dict[str, str] | None = None,
    inputs: dict[tuple[str, str, str], pd.Series] | None = None,
) -> tuple[go.Figure, list[str]]:
    """Build a stacked area chart of Result Sequences with one subplot per Result in the Result Selection.

    Args:
        series: As for `line_chart`, in palette and stack order.
        results: Result Selection as Result name → Result, one subplot each, top to bottom.
        colours: Hex colours by series key, overriding the palette for those series.
        inputs: Loaded Input Sequences by (Datapackage, resource, column).

    Returns:
        Figure with one stacked `Scatter` trace per Outcome × Result; subplots share both axes and are titled
        with the Result. Input Sequences are drawn unstacked over every subplot with one legend entry. A missing
        series is a legend entry suffixed "(missing)". No notices.
    """
    rows = max(len(results), 1)
    figure = make_subplots(rows=rows, cols=1, shared_xaxes=True, subplot_titles=list(results))
    figure.update_yaxes(matches="y")
    figure.update_layout(margin={"l": 40, "r": 10, "t": 10, "b": 30})
    for colour, result_index, name, column in _traces(series, results, colours, inputs):
        line = {"color": colour}
        if column is None:
            trace = go.Scatter(x=[None], y=[None], name=f"{name} (missing)", mode="lines", line=line, showlegend=True)
            figure.add_trace(trace, row=(result_index or 0) + 1, col=1)
            continue
        data = {"x": column.index, "y": column.to_numpy(), "name": name, "mode": "lines", "line": line}
        if result_index is None:  # Input Sequence: unstacked over every subplot, one legend entry
            for row in range(1, rows + 1):
                figure.add_trace(go.Scatter(**data, legendgroup=name, showlegend=row == 1), row=row, col=1)
        else:
            figure.add_trace(go.Scatter(**data, stackgroup=str(result_index + 1)), row=result_index + 1, col=1)
    return figure, []


def webgl_warning(charts: list[Chart]) -> str | None:
    """Warn when more charts draw with WebGL (`Scattergl`) than browsers reliably keep alive; no cap.

    Args:
        charts: Charts on the page.

    Returns:
        Warning text, or None when within the limit.
    """
    count = sum(chart["type"] in WEBGL_TYPES for chart in charts)
    if count <= MAX_WEBGL_CHARTS:
        return None
    return f"{count} WebGL charts: browsers may blank some beyond {MAX_WEBGL_CHARTS}; remove charts if any go empty."
