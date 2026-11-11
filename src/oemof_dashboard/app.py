"""Dash layout and callbacks of the Explorer."""

import base64
import math
import uuid
from collections import Counter
from pathlib import Path

import dash_cytoscape as cyto
import pandas as pd
from dash import ALL, MATCH, Dash, Input, Output, Patch, State, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate

from oemof_dashboard import datapackage
from oemof_dashboard.charts import (
    CHART_TYPES,
    HEX_COLOUR,
    PALETTE,
    Chart,
    auto_title,
    chart_figure,
    chart_nodes,
    series_item,
    series_key,
    series_label,
    webgl_warning,
)
from oemof_dashboard.cli import discover_datapackages, discover_results
from oemof_dashboard.dashboard import from_json, to_json
from oemof_dashboard.matching import Matching, match
from oemof_dashboard.result import Result, read, scalar_outcomes, sequence_outcomes

MIN_MATCH_RATIO = 0.5  # below it, the selected Datapackage likely belongs to another Result
ACCENT_COLOUR = "#2563eb"
# Cytoscape rounds the zoom up to a power of 2 before applying "min-zoomed-font-size", so Component labels
# (8 px, at least 10 px zoomed) show above zoom 1 only.
MIN_READABLE_ZOOM = 1.25
GRAPH_STYLESHEET = [
    {"selector": "node", "style": {"label": "data(id)", "font-size": 8, "width": 12, "height": 12}},
    {"selector": ".component", "style": {"background-color": "#8a9bb0", "min-zoomed-font-size": 10}},
    {
        "selector": ".bus",
        "style": {
            "shape": "round-rectangle",
            "background-color": "#d9822b",
            "width": 40,
            "height": 24,
            "font-size": 12,
            "font-weight": "bold",
            "z-index": 10,  # Bus labels on top of Component labels
        },
    },
    {"selector": "edge", "style": {"width": 1, "line-color": "#bbb"}},
    {
        "selector": ".flow",
        "style": {
            "curve-style": "bezier",  # keeps the two Flows of one Connection apart
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#888",
            "line-color": "#888",
            "font-size": 7,
            "text-rotation": "autorotate",
        },
    },
    {
        "selector": ".foreign",
        "style": {
            "line-color": "#e34948",
            "target-arrow-color": "#e34948",
            "line-style": "dashed",
            "label": "data(label)",
        },
    },
    # "neighbour" and "connected" are set on selection by a clientside callback; nothing is faded.
    {"selector": ".neighbour", "style": {"border-width": 2, "border-color": ACCENT_COLOUR}},
    {
        "selector": "node:selected",
        "style": {"border-width": 4, "border-color": ACCENT_COLOUR, "width": 18, "height": 18},
    },
    {"selector": ".bus:selected", "style": {"width": 48, "height": 30}},
    {"selector": ".connected", "style": {"width": 3, "line-color": ACCENT_COLOUR, "target-arrow-color": ACCENT_COLOUR}},
    {"selector": ".flow.connected", "style": {"label": "data(label)"}},
]


def graph_elements(package: datapackage.Datapackage, result: Result | None) -> list[dict]:
    """Cytoscape nodes for all Buses and Components, an arrow per Flow of the Result, and an edge per Connection
    without Flows.

    Args:
        package: Datapackage to draw.
        result: First Result of the Result Selection, or None.

    Returns:
        Cytoscape elements; Flows are labelled with the sum of their `flow` (trailing NaN dropped), Flows without
        a Connection are drawn with class `foreign` and labelled "not in Datapackage".
    """
    nodes = [{"data": {"id": name}, "classes": "bus"} for name in package.buses]
    nodes += [{"data": {"id": name}, "classes": "component"} for name in package.components]
    matching = match(result, package) if result is not None else Matching()
    flows = []
    for entry, (source, target) in matching.matched.items():
        if target is None:
            continue
        data = {"source": source, "target": target}
        sequences = result.entries[entry].sequences
        if entry in matching.unmatched:
            flows.append({"data": data | {"label": "not in Datapackage"}, "classes": "flow foreign"})
            continue
        if "flow" in sequences.columns:
            data["label"] = f"Σ {sequences['flow'].sum():,.0f}"  # pandas skips the trailing NaN
        flows.append({"data": data, "classes": "flow"})
    flowing = {frozenset((flow["data"]["source"], flow["data"]["target"])) for flow in flows}
    connections = [
        {"data": {"source": component, "target": bus}}
        for component, bus in package.connections
        if frozenset((component, bus)) not in flowing
    ]
    return nodes + flows + connections


def input_sequence_items(
    name: str, package: datapackage.Datapackage, nodes: set[str] | None = None
) -> set[tuple[str, str, str]]:
    """Input Sequences referenced by a Datapackage's Parameters, broken references left out.

    Args:
        name: Name of the Datapackage.
        package: The Datapackage.
        nodes: Only Input Sequences of these Buses or Components; all if None.

    Returns:
        Input Sequences as (Datapackage, resource, column).
    """
    return {
        (name, value.resource, value.column)
        for node in (package.buses | package.components).values()
        if nodes is None or node.name in nodes
        for value in node.parameters.values()
        if isinstance(value, datapackage.InputSequence) and not value.broken
    }


def input_scalar_items(
    name: str, package: datapackage.Datapackage, nodes: set[str] | None = None
) -> set[tuple[str, str, str]]:
    """Input Scalars of a Datapackage: its Components' finite numeric Parameters; NaN and inf can't be drawn.

    Args:
        name: Name of the Datapackage.
        package: The Datapackage.
        nodes: Only Input Scalars of these Components; all if None.

    Returns:
        Input Scalars as (Datapackage, Component, Parameter).
    """
    return {
        (name, component.name, parameter)
        for component in package.components.values()
        if nodes is None or component.name in nodes
        for parameter, value in component.parameters.items()
        if isinstance(value, float) and math.isfinite(value)
    }


def input_option(name: str, parsed: datapackage.Datapackage | Result | datapackage.Refused) -> dict:
    """Selector option for a Datapackage or Result: Refused input marked ✖ with the reason as tooltip and not
    selectable, input with Input Warnings marked ⚠ n.

    Args:
        name: Name of the input.
        parsed: The input as read.

    Returns:
        Dropdown option.
    """
    if isinstance(parsed, datapackage.Refused):
        return {"label": f"✖ {name}", "value": name, "disabled": True, "title": parsed.reason}
    return {"label": f"{name} ⚠ {len(parsed.warnings)}" if parsed.warnings else name, "value": name}


def warning_list(label: str, warnings: list[str]) -> list[html.Details]:
    """Input Warnings of one input for the inspector summary.

    Args:
        label: Input the warnings belong to.
        warnings: Its Input Warnings.

    Returns:
        A collapsible list, or nothing without warnings.
    """
    if not warnings:
        return []
    return [
        html.Details(
            open=True,
            children=[
                html.Summary(f"{label}: {len(warnings)} Input Warnings"),
                html.Ul([html.Li(warning) for warning in warnings]),
            ],
        )
    ]


def node_link(name: str) -> html.Button:
    """Button that selects a node in the inspector.

    Args:
        name: Bus or Component name.

    Returns:
        Button with a pattern-matching `node-link` id.
    """
    return html.Button(name, id={"type": "node-link", "node": name}, className="node-link")


def outcome_rows(package: datapackage.Datapackage, name: str, results: dict[str, Result]) -> list:
    """Outcomes of a node's Result Entries per Result Entry × variable, each with "+ chart".

    Args:
        package: Datapackage holding the node.
        name: Bus or Component name.
        results: Result Selection as Result name → Result.

    Returns:
        Dash children: a table of Outcomes with "in n/m Results", and a line per Result without Outcomes.
    """
    counts: Counter[tuple[str, str]] = Counter()
    without = []
    for result_name, result in results.items():
        entries = match(result, package).entries_of({name})
        if not entries:
            without.append(html.Div(f"{result_name}: no Outcomes in this Result"))
        for entry in entries:
            found = result.entries[entry]
            counts.update((entry, variable) for variable in {*found.scalars, *found.sequences.columns})
    rows = [
        html.Tr(
            [
                html.Td(f"{entry} · {variable}"),
                html.Td(f"in {count}/{len(results)} Results"),
                html.Td(add_series_button((entry, variable))),
            ]
        )
        for (entry, variable), count in sorted(counts.items())
    ]
    return [html.Table(rows), *without]


def add_series_button(item: tuple[str, ...]) -> html.Button:
    """Button adding a series as a new chart of its kind.

    Args:
        item: Outcome as (Result Entry, variable), Input Scalar as (Datapackage, Component, Parameter) or Input
            Sequence as (Datapackage, resource, column).

    Returns:
        "+ chart" button whose id carries the series key.
    """
    return html.Button("+ chart", id={"type": "outcome-chart", "outcome": series_key(item)})


def inspector(package: datapackage.Datapackage, name: str, results: dict[str, Result], package_name: str) -> list:
    """Inspector content for one Bus or Component: type/resource, Connections, Parameters, Input Sequences, and
    its Outcomes in the Result Selection; Input Scalars and unbroken Input Sequences each with "+ chart".

    Args:
        package: Datapackage holding the node.
        name: Bus or Component name.
        results: Result Selection as Result name → Result.
        package_name: Name of the Datapackage.

    Returns:
        Dash children for the inspector pane.
    """
    node = package.buses.get(name) or package.components[name]
    neighbours = [
        bus if component == name else component for component, bus in package.connections if name in (component, bus)
    ]
    scalars = {key: value for key, value in node.parameters.items() if not isinstance(value, datapackage.InputSequence)}
    sequences = {key: value for key, value in node.parameters.items() if isinstance(value, datapackage.InputSequence)}
    input_scalars = input_scalar_items(package_name, package, {name})
    return [
        html.H4(name),
        html.Div(f"type: {node.type} · resource: {node.resource}"),
        *([html.Button("Add Bus balance", id={"type": "bus-balance", "bus": name})] if name in package.buses else []),
        html.Label("Connections"),
        html.Div([node_link(neighbour) for neighbour in neighbours] or "–"),
        html.Label("Parameters"),
        html.Table(
            [
                html.Tr(
                    [
                        html.Td(key),
                        html.Td(str(value).removesuffix(".0")),
                        html.Td(
                            add_series_button((package_name, name, key))
                            if (package_name, name, key) in input_scalars
                            else []
                        ),
                    ]
                )
                for key, value in scalars.items()
            ]
        ),
        html.Label("Input Sequences"),
        html.Ul(
            [
                html.Li(
                    [
                        f"{key}: {ref.resource} × {ref.column}",
                        " (broken: column missing)"
                        if ref.broken
                        else add_series_button((package_name, ref.resource, ref.column)),
                    ]
                )
                for key, ref in sequences.items()
            ]
        ),
        *([html.Label("Outcomes"), *outcome_rows(package, name, results)] if results else []),
    ]


def chart_card(
    chart: Chart,
    results: dict[str, Result],
    input_items: set[tuple[str, str, str]],
    inputs: dict[tuple[str, str, str], pd.Series | float],
    package: datapackage.Datapackage | None,
) -> html.Div:
    """Chart card: controls for title, type, width, order and removal; series multi-select and colour overrides, or
    a Bus filter for system charts; figure.

    Args:
        chart: Chart config.
        results: Result Selection as Result name → Result.
        input_items: Input Sequences (sequence charts) or Input Scalars (bar charts) of the selected Datapackage,
            offered as series.
        inputs: Loaded Input Sequences and Input Scalars by (Datapackage, resource or Component, column or
            Parameter).
        package: Selected Datapackage, offering its Buses as filter of system charts; None if none is selected.

    Returns:
        Card whose controls carry pattern-matching ids keyed by the chart id.
    """
    chart_id = chart["id"]
    picked = [series_key(item) for item in chart["series"]]
    if chart["kind"] == "scalars":
        offered = {series_key(item) for result in results.values() for item in scalar_outcomes(result)}
    else:
        offered = {series_key(item) for result in results.values() for item in sequence_outcomes(result)}
    offered |= {series_key(item) for item in input_items} | set(picked)
    options = [{"label": series_label(series_item(key)), "value": key} for key in sorted(offered)]
    figure, notices = chart_figure(chart, results, inputs, package)

    def field(name: str) -> dict:
        return {"type": "chart-field", "field": name, "chart": chart_id}

    def action(name: str, label: str) -> html.Button:
        return html.Button(label, id={"type": "chart-action", "action": name, "chart": chart_id}, title=name)

    def part(name: str) -> dict:
        return {"type": name, "chart": chart_id}

    return html.Div(
        id=part("chart-card"),
        className=f"chart-card {chart['width']}",
        children=[
            html.Div(
                className="chart-controls",
                children=[
                    dcc.Input(
                        id=field("title"),
                        value=chart["title"] or "",
                        placeholder=auto_title(chart),
                        debounce=True,
                        className="chart-title",
                    ),
                    dcc.Dropdown(
                        id=field("type"),
                        # A Sankey and a Bus balance read `bus` differently, so system charts keep their type.
                        options=[chart["type"]] if chart["kind"] == "system" else CHART_TYPES[chart["kind"]],
                        value=chart["type"],
                        clearable=False,
                        className="chart-select",
                    ),
                    dcc.Dropdown(
                        id=field("width"),
                        options=["half", "full"],
                        value=chart["width"],
                        clearable=False,
                        className="chart-select",
                    ),
                    action("up", "↑"),
                    action("down", "↓"),
                    action("remove", "×"),
                ],
            ),
            html.Div(
                id=part("chart-chips"),
                children=[
                    html.Button(node, id={"type": "chart-chip", "chart": chart_id, "node": node}, className="node-link")
                    for node in chart_nodes(chart, results, package)
                ],
            ),
            *(
                [
                    dcc.Dropdown(
                        id=field("bus"),
                        options=list(package.buses) if package else [],
                        value=chart.get("bus"),
                        placeholder="(whole system)",
                        clearable=chart["type"] == "sankey",  # a Bus balance needs its Bus
                    )
                ]
                if chart["kind"] == "system"
                else [dcc.Dropdown(id=field("series"), options=options, value=picked, multi=True)]
            ),
            html.Div(  # also on system charts, empty, so the card update always has its target
                id=part("chart-colours"),
                className="chart-colours",
                children=[
                    html.Label(
                        [
                            series_label(series_item(item)),
                            dcc.Input(
                                id={"type": "chart-colour", "chart": chart_id, "series": item},
                                value=chart["colours"].get(item, ""),
                                placeholder=PALETTE[index % len(PALETTE)],
                                debounce=True,
                                className="chart-colour",
                            ),
                        ]
                    )
                    for index, item in enumerate(picked)
                ],
            ),
            html.Div(id=part("chart-notices"), children=[html.Div(notice, className="notice") for notice in notices]),
            dcc.Graph(id=part("chart-graph"), figure=figure),
        ],
    )


def chart_index(charts: list[Chart], chart_id: str) -> int:
    """Position of a chart in the charts store.

    Args:
        charts: Charts store content.
        chart_id: Id of the chart.

    Returns:
        Index of the chart.

    Raises:
        PreventUpdate: If the chart is gone, so the calling callback stops.
    """
    for index, chart in enumerate(charts):
        if chart["id"] == chart_id:
            return index
    raise PreventUpdate


def edited_chart(charts: list[Chart]) -> tuple[int, Chart]:
    """Apply the card control change that triggered the running callback (read from `ctx`) to its chart.

    Args:
        charts: Charts store content before the change.

    Returns:
        Index of the chart in the store and the changed chart.

    Raises:
        PreventUpdate: If no single control was changed by the user, the colour is invalid or nothing changed.
    """
    if not ctx.triggered or len(ctx.triggered) != 1:
        # A rendered card fires with all its inputs at once (at least title, type, width, series), a removed last
        # card with none; a user edit changes one.
        raise PreventUpdate
    trigger, value = ctx.triggered_id, ctx.triggered[0]["value"]
    index = chart_index(charts, trigger["chart"])
    chart = dict(charts[index])
    if trigger["type"] == "chart-colour":
        if value and not HEX_COLOUR.fullmatch(value):
            raise PreventUpdate
        colours = {item: colour for item, colour in chart["colours"].items() if item != trigger["series"]}
        chart["colours"] = colours | ({trigger["series"]: value} if value else {})
    elif trigger["field"] == "series":
        chart["series"] = [series_item(item) for item in value or []]
        chart["colours"] = {item: colour for item, colour in chart["colours"].items() if item in (value or [])}
    elif trigger["field"] == "title":
        chart["title"] = (value or "").strip() or None
    else:
        chart[trigger["field"]] = value  # type, width or Bus, offered by the card's dropdowns
    if chart == charts[index]:
        raise PreventUpdate  # e.g. re-rendered colour fields: no store write, and no card update loop
    return index, chart


def create_app(datapackages: Path, results: Path) -> Dash:
    """Build the Explorer app.

    Args:
        datapackages: Datapackage folder, rescanned on every page load.
        results: Result folder, rescanned on every page load.

    Returns:
        Dash app; call `run` to serve it.
    """
    cyto.load_extra_layouts()  # for "cose-bilkent"
    app = Dash(__name__, title="oemof Dashboard")

    def layout() -> html.Div:
        # Dash calls a layout function on every page load, so a refresh rescans both folders.
        return html.Div(
            className="explorer",
            children=[
                html.Div(
                    className="pane",
                    children=[
                        html.H3("oemof Dashboard"),
                        html.Label("Datapackage", htmlFor="datapackage"),
                        dcc.Dropdown(
                            id="datapackage",
                            options=[
                                input_option(name, datapackage.read(datapackages / name))
                                for name in discover_datapackages(datapackages)
                            ],
                            placeholder="(no Datapackage)",
                        ),
                        html.Label("Result Selection", htmlFor="result-selection"),
                        dcc.Dropdown(
                            id="result-selection",
                            options=[input_option(name, read(results / name)) for name in discover_results(results)],
                            multi=True,
                        ),
                        html.Hr(),
                        html.Label("Outcome", htmlFor="outcome-picker"),
                        dcc.Dropdown(
                            id="outcome-picker", options=[], multi=True, placeholder="Outcome / Input Sequence…"
                        ),
                        html.Button("Add chart", id="add-chart"),
                        html.Hr(),
                        html.Label("Sankey / Bus balance", htmlFor="sankey-bus"),
                        dcc.Dropdown(id="sankey-bus", options=[], placeholder="(whole system)", disabled=True),
                        html.Button("Add Sankey", id="add-sankey", disabled=True),
                        html.Button("Add Bus balance", id="add-bus-balance", disabled=True),
                        html.Hr(),
                        html.Button("Save Dashboard", id="save-dashboard"),
                        dcc.Download(id="dashboard-download"),
                        dcc.Upload(html.Button("Load Dashboard"), id="dashboard-upload", accept=".json"),
                    ],
                ),
                html.Div(
                    className="center",
                    children=[
                        html.Div(
                            className="graph-pane",
                            children=[
                                cyto.Cytoscape(
                                    id="graph",
                                    elements=[],
                                    layout={"name": "cose-bilkent", "randomize": False},  # same input, same layout
                                    stylesheet=GRAPH_STYLESHEET,
                                    minZoom=0.2,
                                    maxZoom=3,
                                    wheelSensitivity=0.2,
                                    style={"width": "100%", "height": "100%"},
                                ),
                                html.Button("Fit", id="graph-fit", className="graph-fit"),
                            ],
                        ),
                        html.Div(id="dashboard-notice"),
                        html.Div(id="webgl-warning"),
                        html.Div(id="charts", className="chart-grid"),
                        # Chart configs in grid order; the cards in "charts" follow it one to one.
                        dcc.Store(id="charts-store", data=[]),
                    ],
                ),
                html.Div(id="inspector", className="pane"),
            ],
        )

    app.layout = layout

    # Refused input isn't selectable, but may still be selected from before it broke: treat it as not selected.
    def read_selection(selection: list[str] | None) -> dict[str, Result]:
        # `read` re-uses the parse until a Result file changes.
        parsed = {name: read(results / name) for name in selection or []}
        return {name: result for name, result in parsed.items() if isinstance(result, Result)}

    def read_package(name: str | None) -> datapackage.Datapackage | None:
        package = datapackage.read(datapackages / name) if name else None
        return package if isinstance(package, datapackage.Datapackage) else None

    def refusal_banners(name: str | None, selection: list[str] | None) -> list[html.Div]:
        parsed = [(f"Datapackage {name}", datapackage.read(datapackages / name))] if name else []
        parsed += [(f"Result {result}", read(results / result)) for result in selection or []]
        return [
            html.Div(f"{label} refused: {input_.reason}", className="warning")
            for label, input_ in parsed
            if isinstance(input_, datapackage.Refused)
        ]

    def chart_cards(charts: list[Chart], selection: list[str] | None, name: str | None) -> list[html.Div]:
        # Only Input Sequences referenced (unbroken) in, and Input Scalars of, the selected Datapackage are loaded;
        # any other, e.g. of another Datapackage, shows as missing.
        selected = read_selection(selection)
        package = read_package(name)
        sequence_items = input_sequence_items(name, package) if package else set()
        scalar_items = input_scalar_items(name, package) if package else set()
        wanted = {tuple(item) for chart in charts for item in chart["series"] if tuple(item) in sequence_items}
        loaded = {item: datapackage.input_sequence(datapackages / name, *item[1:]) for item in wanted}
        inputs: dict[tuple[str, str, str], pd.Series | float] = {
            item: values for item, values in loaded.items() if values is not None
        }
        inputs |= {item: package.components[item[1]].parameters[item[2]] for item in scalar_items}
        return [
            chart_card(chart, selected, scalar_items if chart["kind"] == "scalars" else sequence_items, inputs, package)
            for chart in charts
        ]

    def selected_node(name: str | None, selected_nodes: list[dict] | None) -> str | None:
        # Cytoscape may keep a selection from the previous Datapackage; drop names it doesn't have.
        # ponytail: a box selection counts as its alphabetically first node.
        package = read_package(name)
        if not package or not selected_nodes:
            return None
        known = {node["id"] for node in selected_nodes} & (package.buses.keys() | package.components.keys())
        return min(known, default=None)

    @app.callback(Output("graph", "elements"), Input("datapackage", "value"), Input("result-selection", "value"))
    def draw_graph(name: str | None, selection: list[str] | None) -> list[dict]:
        package = read_package(name)
        if not package:
            return []
        # Flows of the first Result only: one graph can't show several Results' sums.
        first = next(iter(read_selection(selection).values()), None)
        return graph_elements(package, first)

    @app.callback(
        Output("outcome-picker", "options"),
        Input("result-selection", "value"),
        Input("datapackage", "value"),
        Input("graph", "selectedNodeData"),  # emptied by tapping the graph background
    )
    def list_outcomes(
        selection: list[str] | None, name: str | None, selected_nodes: list[dict] | None
    ) -> list[dict[str, str]]:
        selected = read_selection(selection)
        outcomes = set().union(*map(sequence_outcomes, selected.values()), *map(scalar_outcomes, selected.values()))
        node = selected_node(name, selected_nodes)
        nodes = {node} if node else set()
        package = read_package(name)
        inputs = (
            (input_sequence_items(name, package, nodes or None) | input_scalar_items(name, package, nodes or None))
            if package
            else set()
        )
        if nodes:
            entries = set().union(*(match(result, package).entries_of(nodes) for result in selected.values()))
            outcomes = {(entry, variable) for entry, variable in outcomes if entry in entries}
        return [
            {"label": series_label(item), "value": series_key(item)} for item in [*sorted(outcomes), *sorted(inputs)]
        ]

    # The graph's node selection is the one selection state (node or none, see `selected_node`): a tap, a node
    # link or a chart chip selects a node, tapping empty space deselects it; the inspector, like the Outcome
    # picker, follows it. Server callbacks can't write "selectedNodeData", so every (de)select path is clientside.
    @app.callback(
        Output("inspector", "children"),
        Input("graph", "selectedNodeData"),
        Input("datapackage", "value"),
        Input("result-selection", "value"),
    )
    def inspect(selected_nodes: list[dict] | None, name: str | None, selection: list[str] | None) -> list:
        package = read_package(name)
        selected = read_selection(selection)
        if node := selected_node(name, selected_nodes):
            return inspector(package, node, selected, name)
        # Nothing selected: summarise the inputs.
        summary = refusal_banners(name, selection)
        summary += warning_list(f"Datapackage {name}", package.warnings) if package else []
        for result_name, result in selected.items():
            summary.append(
                html.Details(
                    open=True,
                    children=[
                        html.Summary(f"{result_name}: {len(result.entries)} Result Entries"),
                        html.Ul([html.Li(entry) for entry in result.entries]),
                    ],
                )
            )
            summary += warning_list(result_name, result.warnings)
            if not package:
                continue
            matching = match(result, package)
            if matching.ratio < MIN_MATCH_RATIO:
                banner = (
                    f"{result_name}: Datapackage likely doesn't belong to this Result ({matching.ratio:.0%} matched)"
                )
                summary.insert(0, html.Div(banner, className="warning"))
            summary.append(
                html.Details(
                    open=bool(matching.unmatched),
                    children=[
                        html.Summary(f"{result_name}: {len(matching.unmatched)} unmatched"),
                        html.Ul([html.Li(f"{entry}: {reason}") for entry, reason in matching.unmatched.items()]),
                    ],
                )
            )
        return summary

    # Re-rendered inspector content starts at its top, e.g. the name of a newly selected node.
    app.clientside_callback(
        """() => { document.getElementById("inspector").scrollTop = 0; }""",
        Input("inspector", "children"),
        prevent_initial_call=True,
    )

    # A clicked node link or chart chip selects its node in the graph, which updates "selectedNodeData".
    # Selecting via `elements` instead would miss a node re-selected after a tap: elements only patch on change.
    app.clientside_callback(
        """(_links, _chips) => {
            const context = window.dash_clientside.callback_context;
            const cy = document.getElementById("graph")?._cyreg?.cy;
            if (!cy || !context.triggered[0]?.value) return;  // new links or chips rendered, not clicked
            const node = cy.getElementById(context.triggered_id.node);
            if (node.empty()) return;  // not in the graph: keep the selection
            cy.$(":selected").unselect();
            node.select();
            // Graph taps don't pass here, so a tapped node doesn't jump away.
            cy.animate({center: {eles: node}, zoom: Math.max(cy.zoom(), MIN_READABLE_ZOOM)}, {duration: 400});
        }""".replace("MIN_READABLE_ZOOM", str(MIN_READABLE_ZOOM)),
        Input({"type": "node-link", "node": ALL}, "n_clicks"),
        Input({"type": "chart-chip", "chart": ALL, "node": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )

    # Cytoscape has no selector for a selected node's neighbourhood, so mark it with classes for the stylesheet.
    app.clientside_callback(
        """(_selected, _elements) => {
            const cy = document.getElementById("graph")?._cyreg?.cy;
            if (!cy) return;
            cy.elements().removeClass("neighbour connected");
            const selected = cy.nodes(":selected");
            selected.neighborhood("node").addClass("neighbour");
            selected.connectedEdges().addClass("connected");
        }""",
        Input("graph", "selectedNodeData"),
        Input("graph", "elements"),  # new elements reset their classes
    )

    app.clientside_callback(
        """(_clicks) => { document.getElementById("graph")?._cyreg?.cy?.fit(); }""",
        Input("graph-fit", "n_clicks"),
        prevent_initial_call=True,
    )

    # Adding and arranging charts keep "charts-store" and the cards in "charts" in step by patching both at the same
    # index; an edit patches the store and its own card's components only.
    @app.callback(
        Output("charts-store", "data"),
        Output("charts", "children", allow_duplicate=True),
        Input("add-chart", "n_clicks"),
        Input({"type": "outcome-chart", "outcome": ALL}, "n_clicks"),
        State("outcome-picker", "value"),
        State("charts-store", "data"),
        State("result-selection", "value"),
        State("datapackage", "value"),
        prevent_initial_call=True,
    )
    def add_chart(
        _clicks: int | None,
        _outcome_clicks: list[int | None],
        picked: list[str] | None,
        _charts: list[Chart],
        selection: list[str] | None,
        name: str | None,
    ) -> tuple:
        if not ctx.triggered[0]["value"]:
            raise PreventUpdate  # "+ chart" buttons rendered or removed, not clicked
        if isinstance(ctx.triggered_id, dict):
            picked = [ctx.triggered_id["outcome"]]
        if not picked:
            raise PreventUpdate
        # Sequence and scalar items never mix in one chart: a mixed pick adds one chart per kind.
        # ponytail: an Outcome counts as scalar if it is a Result Scalar in any selected Result; an Input Scalar if
        # it is one of the selected Datapackage, whose key would win over an Input Sequence spelled the same.
        scalars = {
            series_key(item) for result in read_selection(selection).values() for item in scalar_outcomes(result)
        }
        package = read_package(name)
        scalars |= {series_key(item) for item in input_scalar_items(name, package)} if package else set()
        by_kind = {
            "sequences": [value for value in picked if value not in scalars],
            "scalars": [value for value in picked if value in scalars],
        }
        new: list[Chart] = [
            {
                "id": uuid.uuid4().hex,
                "kind": kind,
                "type": CHART_TYPES[kind][0],
                "title": None,
                "series": [series_item(value) for value in values],
                "colours": {},
                "width": "half",
            }
            for kind, values in by_kind.items()
            if values
        ]
        charts, cards = Patch(), Patch()
        charts.extend(new)
        cards.extend(chart_cards(new, selection, name))
        return charts, cards

    @app.callback(
        Output("sankey-bus", "options"),
        Output("sankey-bus", "value"),
        Output("sankey-bus", "disabled"),
        Output("add-sankey", "disabled"),
        Input("datapackage", "value"),
    )
    def offer_sankey(name: str | None) -> tuple[list[str], None, bool, bool]:
        package = read_package(name)
        buses = list(package.buses) if package else []
        return buses, None, not package, not package

    @app.callback(Output("add-bus-balance", "disabled"), Input("sankey-bus", "value"))
    def offer_bus_balance(bus: str | None) -> bool:
        return not bus

    @app.callback(
        Output("charts-store", "data", allow_duplicate=True),
        Output("charts", "children", allow_duplicate=True),
        Input("add-sankey", "n_clicks"),
        Input("add-bus-balance", "n_clicks"),
        Input({"type": "bus-balance", "bus": ALL}, "n_clicks"),
        State("sankey-bus", "value"),
        State("charts-store", "data"),
        State("result-selection", "value"),
        State("datapackage", "value"),
        prevent_initial_call=True,
    )
    def add_system_chart(
        _sankey_clicks: int | None,
        _balance_clicks: int | None,
        _inspector_clicks: list[int | None],
        bus: str | None,
        _charts: list[Chart],
        selection: list[str] | None,
        name: str | None,
    ) -> tuple:
        if not ctx.triggered[0]["value"]:
            raise PreventUpdate  # "Add Bus balance" button rendered or removed, not clicked
        if isinstance(ctx.triggered_id, dict):
            bus = ctx.triggered_id["bus"]
        new: Chart = {
            "id": uuid.uuid4().hex,
            "kind": "system",
            "type": "sankey" if ctx.triggered_id == "add-sankey" else "bus_balance",
            "title": None,
            "series": [],
            "colours": {},
            "width": "half",
            "bus": bus,
        }
        charts, cards = Patch(), Patch()
        charts.append(new)
        cards.extend(chart_cards([new], selection, name))
        return charts, cards

    # An edit changes the store and its own card only: re-rendering the chart grid would reset the page's scroll.
    @app.callback(
        Output("charts-store", "data", allow_duplicate=True),
        Input({"type": "chart-field", "field": ALL, "chart": ALL}, "value"),
        Input({"type": "chart-colour", "chart": ALL, "series": ALL}, "value"),
        State("charts-store", "data"),
        prevent_initial_call=True,
    )
    def edit_chart(_fields: list, _colours: list, charts: list[Chart]) -> Patch:
        index, chart = edited_chart(charts)
        patched_charts = Patch()
        patched_charts[index] = chart
        return patched_charts

    @app.callback(
        Output({"type": "chart-card", "chart": MATCH}, "className"),
        Output({"type": "chart-field", "field": "title", "chart": MATCH}, "placeholder"),
        Output({"type": "chart-chips", "chart": MATCH}, "children"),
        Output({"type": "chart-colours", "chart": MATCH}, "children"),
        Output({"type": "chart-notices", "chart": MATCH}, "children"),
        Output({"type": "chart-graph", "chart": MATCH}, "figure"),
        Input({"type": "chart-field", "field": ALL, "chart": MATCH}, "value"),
        Input({"type": "chart-colour", "chart": MATCH, "series": ALL}, "value"),
        # Before the edit: "edit_chart" fires on the same change. ponytail: a second edit sent before the first
        # one's store patch returns draws the card without the first; trigger on the store if that bites.
        State("charts-store", "data"),
        State("result-selection", "value"),
        State("datapackage", "value"),
        prevent_initial_call=True,
    )
    def update_card(
        _fields: list, _colours: list, charts: list[Chart], selection: list[str] | None, name: str | None
    ) -> tuple:
        _, chart = edited_chart(charts)
        (card,) = chart_cards([chart], selection, name)
        chart_id = chart["id"]
        return (
            card.className,
            card[{"type": "chart-field", "field": "title", "chart": chart_id}].placeholder,
            card[{"type": "chart-chips", "chart": chart_id}].children,
            card[{"type": "chart-colours", "chart": chart_id}].children,
            card[{"type": "chart-notices", "chart": chart_id}].children,
            card[{"type": "chart-graph", "chart": chart_id}].figure,
        )

    @app.callback(
        Output("charts-store", "data", allow_duplicate=True),
        Output("charts", "children", allow_duplicate=True),
        Input({"type": "chart-action", "action": ALL, "chart": ALL}, "n_clicks"),
        State("charts-store", "data"),
        State("result-selection", "value"),
        State("datapackage", "value"),
        prevent_initial_call=True,
    )
    def arrange_chart(
        _clicks: list[int | None], charts: list[Chart], selection: list[str] | None, name: str | None
    ) -> tuple:
        if len(ctx.triggered) != 1 or not ctx.triggered[0]["value"]:
            raise PreventUpdate  # new buttons rendered, not clicked
        index = chart_index(charts, ctx.triggered_id["chart"])
        patched_charts, cards = Patch(), Patch()
        if ctx.triggered_id["action"] == "remove":
            del patched_charts[index]
            del cards[index]
            return patched_charts, cards
        other = index - 1 if ctx.triggered_id["action"] == "up" else index + 1
        if not 0 <= other < len(charts):
            raise PreventUpdate
        cards[index], cards[other] = chart_cards([charts[other], charts[index]], selection, name)
        patched_charts[index], patched_charts[other] = charts[other], charts[index]
        return patched_charts, cards

    @app.callback(
        Output("charts", "children"),
        Input("result-selection", "value"),
        Input("datapackage", "value"),
        State("charts-store", "data"),
    )
    def render_charts(selection: list[str] | None, name: str | None, charts: list[Chart]) -> list[html.Div]:
        return chart_cards(charts, selection, name)

    @app.callback(
        Output("dashboard-download", "data"),
        Input("save-dashboard", "n_clicks"),
        State("charts-store", "data"),
        State("result-selection", "value"),
        State("datapackage", "value"),
        prevent_initial_call=True,
    )
    def save_dashboard(
        _clicks: int | None, charts: list[Chart], selection: list[str] | None, name: str | None
    ) -> dict[str, str]:
        return {"content": to_json(charts, selection, name), "filename": "dashboard.json"}

    @app.callback(
        Output("charts-store", "data", allow_duplicate=True),
        Output("charts", "children", allow_duplicate=True),
        Output("result-selection", "value"),
        Output("datapackage", "value"),
        Output("dashboard-notice", "children"),
        # Cleared, so uploading the same file again fires once more.
        Output("dashboard-upload", "contents"),
        Input("dashboard-upload", "contents"),
        State("result-selection", "value"),
        State("datapackage", "value"),
        prevent_initial_call=True,
    )
    def load_dashboard(contents: str | None, selection: list[str] | None, name: str | None) -> tuple:
        if not contents:
            raise PreventUpdate
        try:
            # `contents` is a data URL: "data:<type>;base64,<data>"
            loaded = from_json(base64.b64decode(contents.partition(",")[2]).decode())
        except ValueError as error:  # also undecodable bytes
            banner = html.Div(f"Dashboard file refused: {error}", className="warning")
            return no_update, no_update, no_update, no_update, [banner], None
        # Stored inputs are non-binding defaults: those present are applied, the current ones stay otherwise.
        missing, selection_out, name_out = [], no_update, no_update
        if loaded.result_selection is not None:
            available = set(discover_results(results))
            usable = list(read_selection([result for result in loaded.result_selection if result in available]))
            missing += [f"Result {result}" for result in loaded.result_selection if result not in usable]
            if usable:
                selection = selection_out = usable
        if loaded.datapackage is not None:
            if loaded.datapackage in discover_datapackages(datapackages) and read_package(loaded.datapackage):
                name = name_out = loaded.datapackage
            else:
                missing.append(f"Datapackage {loaded.datapackage}")
        notices = [
            html.Div(f"{label} (missing): stored in the Dashboard, but not available or refused.", className="notice")
            for label in missing
        ]
        charts = loaded.chart_configs()
        return charts, chart_cards(charts, selection, name), selection_out, name_out, notices, None

    @app.callback(Output("webgl-warning", "children"), Input("charts-store", "data"))
    def warn_webgl(charts: list[Chart]) -> list[html.Div]:
        warning = webgl_warning(charts)
        return [html.Div(warning, className="notice")] if warning else []

    return app
