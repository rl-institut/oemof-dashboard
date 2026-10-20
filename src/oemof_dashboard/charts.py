"""Pure figure builders: Outcomes × Result Selection → plotly figure plus notices. No Dash imports."""

import re
from collections.abc import Iterator
from typing import Literal, NotRequired, TypedDict

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from oemof_dashboard.datapackage import Datapackage
from oemof_dashboard.matching import Matching, match
from oemof_dashboard.result import Result, ResultEntry

# Validated categorical palette (light mode), fixed order; colour encodes Entry×variable / Input Sequence, never
# the Result.
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{6}")  # form of a colour override
# The Result is encoded by dash style; the first four stay distinguishable.
DASHES = ["solid", "dash", "dot", "dashdot", "longdash", "longdashdot"]
MAX_DISTINCT_RESULTS = 4
# Chart types per kind; a chart's kind is fixed at creation, its type switches within the kind.
CHART_TYPES = {
    "sequences": ("line", "stacked_area", "duration_curve"),
    "scalars": ("bar",),
    "system": ("sankey", "bus_balance"),
}
SYSTEM_NAMES = {"sankey": "Sankey", "bus_balance": "Bus balance"}
MAX_TITLE_SERIES = 3
# Browsers cap live WebGL contexts (~8–16); beyond that charts go blank.
WEBGL_TYPES = {"line", "duration_curve"}
MAX_WEBGL_CHARTS = 8
# Prefix of an Input Sequence's series key; Outcome keys are "<Result Entry>/<variable>".
INPUT_PREFIX = "input:"
# Sankey colour of a Flow without a Bus end, or a Component without a Connection.
NO_BUS_COLOUR = "#8a9bb0"
LINK_OPACITY = "80"  # hex alpha appended to a link's colour
SANKEY_GAP = 0.02  # paper width between side-by-side Sankeys
# A Bus balance draws its residual only beyond this share of its largest Flow value: solvers leave rounding noise.
RESIDUAL_TOLERANCE = 1e-6
RESIDUAL_COLOUR = "#1f1f1f"


class Chart(TypedDict):
    """Chart config as kept in the charts store (JSON).

    `series` holds Outcomes as [Result Entry, variable] and, in sequence charts only, Input Sequences as
    [Datapackage, resource, column]; system charts have none but a `bus` instead: an optional filter of a Sankey,
    the balanced Bus of a Bus balance; `colours` maps a series key (see `series_key`) to a hex colour overriding the
    palette; `title` None means auto.
    """

    id: str
    kind: Literal["sequences", "scalars", "system"]
    type: Literal["line", "stacked_area", "duration_curve", "bar", "sankey", "bus_balance"]
    title: str | None
    series: list[list[str]]
    colours: dict[str, str]
    width: Literal["half", "full"]
    bus: NotRequired[str | None]


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


def auto_title(chart: Chart) -> str:
    """Auto title of a chart from its first series items, or its Bus filter.

    Args:
        chart: Chart config.

    Returns:
        Title such as "bhkw-electricity · flow, wind-electricity · flow +2", or "Empty chart" without series;
        "Sankey" or "Sankey · <Bus>" for a Sankey, "Bus balance · <Bus>" for a Bus balance.
    """
    if chart["kind"] == "system":
        return " · ".join(filter(None, (SYSTEM_NAMES[chart["type"]], chart.get("bus"))))
    series = chart["series"]
    if not series:
        return "Empty chart"
    title = ", ".join(map(series_label, series[:MAX_TITLE_SERIES]))
    hidden = len(series) - MAX_TITLE_SERIES
    return f"{title} +{hidden}" if hidden > 0 else title


def chart_figure(
    chart: Chart,
    results: dict[str, Result],
    inputs: dict[tuple[str, str, str], pd.Series] | None = None,
    package: Datapackage | None = None,
) -> tuple[go.Figure, list[str]]:
    """Build the figure of one chart for the Result Selection.

    Args:
        chart: Chart config.
        results: Result Selection as Result name → Result.
        inputs: Loaded Input Sequences by (Datapackage, resource, column); series not in it show as missing.
        package: Selected Datapackage, needed by system charts; None if none is selected.

    Returns:
        Figure titled with the chart's title, or the auto title if unset. Notices to show with it.

    Raises:
        ValueError: If the chart's type doesn't belong to its kind.
    """
    if chart["type"] not in CHART_TYPES.get(chart["kind"], ()):
        raise ValueError(f"Chart type {chart['type']!r} isn't of kind {chart['kind']!r}")
    series = [tuple(item) for item in chart["series"]]
    if chart["kind"] == "system" and not package:
        figure, notices = go.Figure(), [f"{SYSTEM_NAMES[chart['type']]} needs a selected Datapackage."]
    elif chart["type"] == "sankey":
        figure, notices = sankey(results, package, chart.get("bus"))
    elif chart["type"] == "bus_balance":
        figure, notices = bus_balance(results, package, chart.get("bus"))
    elif chart["type"] == "bar":
        figure, notices = bar_chart(series, results, chart["colours"])
    else:
        builder = {"line": line_chart, "stacked_area": stacked_area, "duration_curve": duration_curve}[chart["type"]]
        figure, notices = builder(series, results, chart["colours"], inputs)
    figure.update_layout(title_text=chart["title"] or auto_title(chart), margin_t=30)
    return figure, notices


def chart_nodes(chart: Chart, results: dict[str, Result], package: Datapackage | None) -> list[str]:
    """Nodes a chart's series belong to, shown as its chips.

    Args:
        chart: Chart config.
        results: Result Selection as Result name → Result; a Result Entry counts if matched in any of them.
        package: Selected Datapackage; None if none is selected.

    Returns:
        Nodes of the chart's Outcomes' matched Result Entries, in series order and source before target, or the Bus
        of a system chart; unmatched Result Entries, Input Sequences and a Bus not in the Datapackage give none.
        Empty without a Datapackage.
    """
    if package is None:
        return []
    if chart["kind"] == "system":
        return [chart["bus"]] if chart.get("bus") in package.buses else []
    matched = {entry: pair for result in results.values() for entry, pair in match(result, package).matched.items()}
    pairs = [matched.get(item[0], ()) for item in chart["series"] if len(item) == 2]
    return list(dict.fromkeys(name for pair in pairs for name in pair if name is not None))


def _colour(index: int, item: tuple[str, ...], colours: dict[str, str] | None) -> str:
    # ponytail: palette wraps after 8 series; a colour override is the way out
    return (colours or {}).get(series_key(item), PALETTE[index % len(PALETTE)])


def _traces(
    series: list[tuple[str, ...]],
    results: dict[str, Result],
    colours: dict[str, str] | None,
    inputs: dict[tuple[str, str, str], pd.Series] | None,
) -> Iterator[tuple[str, int | None, str, pd.Series | None]]:
    # (colour, Result index, trace name, data or None if missing) per Outcome × Result and once per Input Sequence
    # (Result index None), in series order.
    for index, item in enumerate(series):
        colour = _colour(index, item, colours)
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


def bar_chart(
    series: list[tuple[str, ...]], results: dict[str, Result], colours: dict[str, str] | None = None
) -> tuple[go.Figure, list[str]]:
    """Build a grouped bar chart of Result Scalars across the Result Selection.

    Args:
        series: Outcomes as (Result Entry, variable), in palette and bar order within a group.
        results: Result Selection as Result name → Result, one group of bars each, left to right.
        colours: Hex colours by series key, overriding the palette for those series.

    Returns:
        Figure with one `Bar` trace per Outcome over the Results; an Outcome missing from a Result has no bar there
        and a legend entry "<Outcome> · <Result> (missing)" instead. No notices.
    """
    # Category axis: Result names such as "2045" would otherwise make a numeric axis.
    layout = {"barmode": "group", "xaxis": {"type": "category"}, "margin": {"l": 40, "r": 10, "t": 10, "b": 30}}
    figure = go.Figure(layout=layout)
    for index, item in enumerate(series):
        entry, variable = item
        label = series_label(item)
        style = {"marker": {"color": _colour(index, item, colours)}, "legendgroup": label}
        values = {
            name: result.entries.get(entry, ResultEntry()).scalars.get(variable) for name, result in results.items()
        }
        figure.add_trace(go.Bar(x=list(values), y=list(values.values()), name=label, **style))
        for name in (name for name, value in values.items() if value is None):
            figure.add_trace(go.Bar(x=[None], y=[None], name=f"{label} · {name} (missing)", showlegend=True, **style))
    return figure, []


def _flows(
    result: Result, matching: Matching, bus: str | None
) -> tuple[dict[str, tuple[str, str, pd.Series]], list[str]]:
    # (source, target, `flow`) by Result Entry per Flow from or to `bus` (any if None), and the Result Entries of
    # Flows without `flow`.
    found, without = {}, []
    for entry, (source, target) in matching.matched.items():
        if target is None or (bus is not None and bus not in (source, target)):
            continue
        sequences = result.entries[entry].sequences
        if "flow" not in sequences.columns:
            without.append(entry)
            continue
        found[entry] = (source, target, sequences["flow"])
    return found, without


def sankey(results: dict[str, Result], package: Datapackage, bus: str | None = None) -> tuple[go.Figure, list[str]]:
    """Build one Sankey of the energy flows per Result in the Result Selection, side by side.

    Args:
        results: Result Selection as Result name → Result, one Sankey each, left to right.
        package: Datapackage the Result Entries are matched against.
        bus: Only Flows from or to this Bus; all Flows if None.

    Returns:
        Figure with one `Sankey` trace per Result, titled with the Result: nodes are Buses and Components, links
        are Flows valued with their summed `flow` (NaN dropped). Buses are coloured by palette in Datapackage
        order; a link takes the colour of its Bus, a Component that of its first Connection's Bus. Notices list a
        Bus filter not in the Datapackage and, per Result, the Flows without `flow`, which get no link.
    """
    figure = go.Figure(layout={"margin": {"l": 10, "r": 10, "t": 10, "b": 10}})
    bus_colours = {name: PALETTE[index % len(PALETTE)] for index, name in enumerate(package.buses)}
    component_buses: dict[str, str] = {}
    for component, connected in package.connections:
        component_buses.setdefault(component, connected)
    width = 1 / max(len(results), 1)
    notices = [f"Bus {bus} (missing): not in the Datapackage."] if bus is not None and bus not in package.buses else []
    for result_index, (result_name, result) in enumerate(results.items()):
        found, without = _flows(result, match(result, package), bus)
        # pandas skips NaN, e.g. the trailing row
        sums = [(source, target, float(flow.sum())) for source, target, flow in found.values()]
        if without:
            notices.append(f"{result_name}: no flow for {', '.join(sorted(without))}")
        nodes = list(dict.fromkeys(name for source, target, _ in sums for name in (source, target)))
        positions = {name: position for position, name in enumerate(nodes)}
        node_colours = [
            bus_colours.get(name) or bus_colours.get(component_buses.get(name), NO_BUS_COLOUR) for name in nodes
        ]
        link_colours = [bus_colours.get(source) or bus_colours.get(target, NO_BUS_COLOUR) for source, target, _ in sums]
        left = result_index * width
        figure.add_trace(
            go.Sankey(
                domain={"x": [left, left + width - SANKEY_GAP]},
                node={"label": nodes, "color": node_colours},
                link={
                    "color": [colour + LINK_OPACITY for colour in link_colours],
                    "source": [positions[source] for source, _, _ in sums],
                    "target": [positions[target] for _, target, _ in sums],
                    "value": [value for _, _, value in sums],
                    "hovertemplate": "%{source.label} → %{target.label}<br>Σ flow: %{value:,.0f}<extra></extra>",
                },
            )
        )
        figure.add_annotation(
            text=result_name, x=left + width / 2, y=1, xref="paper", yref="paper", yanchor="bottom", showarrow=False
        )
    return figure, notices


def bus_balance(results: dict[str, Result], package: Datapackage, bus: str) -> tuple[go.Figure, list[str]]:
    """Build the balance of one Bus with one subplot per Result in the Result Selection.

    Args:
        results: Result Selection as Result name → Result, one subplot each, top to bottom.
        package: Datapackage the Result Entries are matched against.
        bus: Bus to balance.

    Returns:
        Figure with one stacked `Scatter` trace of `flow` per Flow to the Bus (positive, stacked above zero) and
        from it (negative, stacked below), labelled with the other node, also if the Flow isn't in the Datapackage.
        Flows are coloured and stacked by Σ flow over the Result Selection, descending, alike in every subplot;
        subplots share both axes and are titled with the Result. A dotted residual Σin − Σout is drawn where its
        max |value| exceeds `RESIDUAL_TOLERANCE` × the largest Flow value of that Result. Notices list a Bus not in the Datapackage
        (no traces then) and, per Result, Flows without `flow`, unmatched Result Entries and a Bus without Flows.
    """
    figure = make_subplots(rows=max(len(results), 1), cols=1, shared_xaxes=True, subplot_titles=list(results))
    figure.update_yaxes(matches="y")
    figure.update_layout(margin={"l": 40, "r": 10, "t": 10, "b": 30})
    if bus not in package.buses:
        return figure, [f"Bus {bus} (missing): not in the Datapackage."]
    flows_by_result, notices = _bus_flows(results, package, bus)
    totals: dict[str, float] = {}
    for flows in flows_by_result.values():
        for entry, (_, _, flow) in flows.items():
            totals[entry] = totals.get(entry, 0.0) + flow.sum()
    order = sorted(totals, key=totals.__getitem__, reverse=True)
    shown = set()
    for row, flows in enumerate(flows_by_result.values(), start=1):
        signed = []
        for index, entry in enumerate(order):
            if entry not in flows:
                continue
            source, target, flow = flows[entry]
            incoming = target == bus
            signed_flow = flow if incoming else -flow
            signed.append(signed_flow)
            figure.add_trace(
                go.Scatter(
                    x=flow.index,
                    y=signed_flow.to_numpy(),
                    name=source if incoming else target,
                    mode="lines",
                    line={"color": PALETTE[index % len(PALETTE)]},
                    stackgroup=f"{'in' if incoming else 'out'}{row}",
                    legendgroup=entry,
                    showlegend=entry not in shown,
                ),
                row=row,
                col=1,
            )
            shown.add(entry)
        if not signed:
            continue
        residual = pd.concat(signed, axis=1).sum(axis=1)  # Σin − Σout; pandas skips NaN
        if residual.abs().max() > RESIDUAL_TOLERANCE * max(flow.abs().max() for flow in signed):
            figure.add_trace(
                go.Scatter(
                    x=residual.index,
                    y=residual.to_numpy(),
                    name="residual",
                    mode="lines",
                    line={"color": RESIDUAL_COLOUR, "dash": "dot"},
                    legendgroup="residual",
                    showlegend="residual" not in shown,
                ),
                row=row,
                col=1,
            )
            shown.add("residual")
    return figure, notices


def _bus_flows(
    results: dict[str, Result], package: Datapackage, bus: str
) -> tuple[dict[str, dict[str, tuple[str, str, pd.Series]]], list[str]]:
    # Flows from or to `bus` by Result name as `_flows` gives them, and the notices of a Bus balance on them.
    flows_by_result, notices = {}, []
    for name, result in results.items():
        matching = match(result, package)
        flows, without = _flows(result, matching, bus)
        flows_by_result[name] = flows
        # A Flow not in the Datapackage is matched and counted, though also listed as unmatched.
        unmatched = sorted(matching.unmatched.keys() - matching.matched.keys())
        notices += [f"{name}: no flow for {', '.join(sorted(without))}"] if without else []
        notices += [f"{name}: unmatched, left out: {', '.join(unmatched)}"] if unmatched else []
        notices += [] if flows or without else [f"{name}: no Flows of {bus} (missing)"]
    return flows_by_result, notices


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
