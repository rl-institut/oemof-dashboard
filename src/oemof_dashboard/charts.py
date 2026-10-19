"""Pure figure builders: Outcomes × Result Selection → plotly figure plus notices. No Dash imports."""

from typing import Literal, TypedDict

import plotly.graph_objects as go

from oemof_dashboard.result import Result, ResultEntry

# Validated categorical palette (light mode), fixed order; colour encodes Entry×variable, never the Result.
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
# The Result is encoded by dash style; the first four stay distinguishable.
DASHES = ["solid", "dash", "dot", "dashdot", "longdash", "longdashdot"]
MAX_DISTINCT_RESULTS = 4
# Chart types per kind; a chart's kind is fixed at creation, its type switches within the kind.
CHART_TYPES = {"sequences": ("line",)}
MAX_TITLE_SERIES = 3
# Browsers cap live WebGL contexts (~8–16); beyond that charts go blank.
WEBGL_TYPES = {"line"}
MAX_WEBGL_CHARTS = 8


class Chart(TypedDict):
    """Chart config as kept in the charts store (JSON).

    `series` holds Outcomes as [Result Entry, variable]; `colours` maps "<Result Entry>/<variable>" to a hex
    colour overriding the palette; `title` None means auto.
    """

    id: str
    kind: Literal["sequences"]
    type: Literal["line"]
    title: str | None
    series: list[list[str]]
    colours: dict[str, str]
    width: Literal["half", "full"]


def auto_title(series: list[list[str]]) -> str:
    """Auto title of a chart from its first Outcomes.

    Args:
        series: Outcomes as [Result Entry, variable].

    Returns:
        Title such as "bhkw-electricity · flow, wind-electricity · flow +2", or "Empty chart" without Outcomes.
    """
    if not series:
        return "Empty chart"
    title = ", ".join(f"{entry} · {variable}" for entry, variable in series[:MAX_TITLE_SERIES])
    hidden = len(series) - MAX_TITLE_SERIES
    return f"{title} +{hidden}" if hidden > 0 else title


def chart_figure(chart: Chart, results: dict[str, Result]) -> tuple[go.Figure, list[str]]:
    """Build the figure of one chart for the Result Selection.

    Args:
        chart: Chart config.
        results: Result Selection as Result name → Result.

    Returns:
        Figure titled with the chart's title, or the auto title if unset. Notices to show with it.

    Raises:
        ValueError: If the chart's type doesn't belong to its kind.
    """
    if chart["type"] not in CHART_TYPES.get(chart["kind"], ()):
        raise ValueError(f"Chart type {chart['type']!r} isn't of kind {chart['kind']!r}")
    figure, notices = line_chart([tuple(item) for item in chart["series"]], results, chart["colours"])
    figure.update_layout(title_text=chart["title"] or auto_title(chart["series"]), margin_t=30)
    return figure, notices


def line_chart(
    series: list[tuple[str, str]], results: dict[str, Result], colours: dict[str, str] | None = None
) -> tuple[go.Figure, list[str]]:
    """Build a line chart of Result Sequences for every Result in the Result Selection.

    Args:
        series: Outcomes as (Result Entry, variable), in palette order.
        results: Result Selection as Result name → Result, in dash style order.
        colours: Hex colours by "<Result Entry>/<variable>", overriding the palette for those Outcomes.

    Returns:
        Figure with one `Scattergl` trace per Outcome × Result on a shared datetime x-axis; an Outcome
        missing from a Result is a legend entry suffixed "(missing)" without data. Notices to show with it.
    """
    figure = go.Figure(layout={"xaxis": {"type": "date"}, "margin": {"l": 40, "r": 10, "t": 10, "b": 30}})
    for index, (entry, variable) in enumerate(series):
        # ponytail: palette wraps after 8 Outcomes; a colour override is the way out
        colour = (colours or {}).get(f"{entry}/{variable}", PALETTE[index % len(PALETTE)])
        for result_index, (result_name, result) in enumerate(results.items()):
            line = {"color": colour, "dash": DASHES[result_index % len(DASHES)]}
            name = f"{entry} · {variable} · {result_name}"
            sequences = result.entries.get(entry, ResultEntry()).sequences
            if variable not in sequences.columns:
                missing = go.Scattergl(
                    x=[None], y=[None], name=f"{name} (missing)", mode="lines", line=line, showlegend=True
                )
                figure.add_trace(missing)
                continue
            column = sequences[variable]
            figure.add_trace(go.Scattergl(x=column.index, y=column.to_numpy(), name=name, mode="lines", line=line))
    notices = []
    if len(results) > MAX_DISTINCT_RESULTS:
        notices.append(f"More than {MAX_DISTINCT_RESULTS} Results: dash styles get hard to tell apart.")
    return figure, notices


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
