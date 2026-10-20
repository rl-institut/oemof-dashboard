"""Dash layout and callbacks of the Explorer."""

import re
import uuid
from collections import Counter
from pathlib import Path

import dash_cytoscape as cyto
import pandas as pd
from dash import ALL, Dash, Input, Output, Patch, State, ctx, dcc, html
from dash.exceptions import PreventUpdate

from oemof_dashboard import datapackage
from oemof_dashboard.charts import (
    CHART_TYPES,
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
from oemof_dashboard.matching import Matching, match
from oemof_dashboard.result import Result, read, scalar_outcomes, sequence_outcomes

HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{6}")
MIN_MATCH_RATIO = 0.5  # below it, the selected Datapackage likely belongs to another Result
GRAPH_STYLESHEET = [
    {"selector": "node", "style": {"label": "data(id)", "font-size": 8, "width": 12, "height": 12}},
    {"selector": ".component", "style": {"background-color": "#8a9bb0"}},
    {
        "selector": ".bus",
        "style": {
            "shape": "round-rectangle",
            "background-color": "#d9822b",
            "width": 30,
            "height": 18,
            "font-size": 11,
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
            "label": "data(label)",
            "font-size": 7,
            "text-rotation": "autorotate",
        },
    },
    {
        "selector": ".foreign",
        "style": {"line-color": "#e34948", "target-arrow-color": "#e34948", "line-style": "dashed"},
    },
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
                html.Td(html.Button("+ chart", id={"type": "outcome-chart", "outcome": f"{entry}/{variable}"})),
            ]
        )
        for (entry, variable), count in sorted(counts.items())
    ]
    return [html.Table(rows), *without]


def inspector(package: datapackage.Datapackage, name: str, results: dict[str, Result]) -> list:
    """Inspector content for one Bus or Component: type/resource, Connections, Parameters, Input Sequences, and
    its Outcomes in the Result Selection.

    Args:
        package: Datapackage holding the node.
        name: Bus or Component name.
        results: Result Selection as Result name → Result.

    Returns:
        Dash children for the inspector pane.
    """
    node = package.buses.get(name) or package.components[name]
    neighbours = [
        bus if component == name else component for component, bus in package.connections if name in (component, bus)
    ]
    scalars = {key: value for key, value in node.parameters.items() if not isinstance(value, datapackage.InputSequence)}
    sequences = {key: value for key, value in node.parameters.items() if isinstance(value, datapackage.InputSequence)}
    return [
        html.H4(name),
        html.Div(f"type: {node.type} · resource: {node.resource}"),
        *([html.Button("Add Bus balance", id={"type": "bus-balance", "bus": name})] if name in package.buses else []),
        html.Label("Connections"),
        html.Div([node_link(neighbour) for neighbour in neighbours] or "–"),
        html.Label("Parameters"),
        html.Table([html.Tr([html.Td(key), html.Td(str(value).removesuffix(".0"))]) for key, value in scalars.items()]),
        html.Label("Input Sequences"),
        html.Ul(
            [
                html.Li(f"{key}: {ref.resource} × {ref.column}" + (" (broken: column missing)" if ref.broken else ""))
                for key, ref in sequences.items()
            ]
        ),
        *([html.Label("Outcomes"), *outcome_rows(package, name, results)] if results else []),
    ]


def chart_card(
    chart: Chart,
    results: dict[str, Result],
    input_items: set[tuple[str, str, str]],
    inputs: dict[tuple[str, str, str], pd.Series],
    package: datapackage.Datapackage | None,
) -> html.Div:
    """Chart card: controls for title, type, width, order and removal; series multi-select and colour overrides, or
    a Bus filter for system charts; figure.

    Args:
        chart: Chart config.
        results: Result Selection as Result name → Result.
        input_items: Input Sequences of the selected Datapackage, offered as series of sequence charts.
        inputs: Loaded Input Sequences of the chart by (Datapackage, resource, column).
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
        offered |= {series_key(item) for item in input_items}
    offered |= set(picked)
    options = [{"label": series_label(series_item(key)), "value": key} for key in sorted(offered)]
    figure, notices = chart_figure(chart, results, inputs, package)

    def field(name: str) -> dict:
        return {"type": "chart-field", "field": name, "chart": chart_id}

    def action(name: str, label: str) -> html.Button:
        return html.Button(label, id={"type": "chart-action", "action": name, "chart": chart_id}, title=name)

    return html.Div(
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
                [
                    html.Button(node, id={"type": "chart-chip", "chart": chart_id, "node": node}, className="node-link")
                    for node in chart_nodes(chart, results, package)
                ]
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
                else [
                    dcc.Dropdown(id=field("series"), options=options, value=picked, multi=True),
                    html.Div(
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
                ]
            ),
            *(html.Div(notice, className="notice") for notice in notices),
            dcc.Graph(figure=figure),
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


def create_app(datapackages: Path, results: Path) -> Dash:
    """Build the Explorer app.

    Args:
        datapackages: Datapackage folder, rescanned on every page load.
        results: Result folder, rescanned on every page load.

    Returns:
        Dash app; call `run` to serve it.
    """
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
                    ],
                ),
                html.Div(
                    className="center",
                    children=[
                        html.Div(
                            className="graph-pane",
                            children=cyto.Cytoscape(
                                id="graph",
                                elements=[],
                                layout={"name": "cose"},
                                stylesheet=GRAPH_STYLESHEET,
                                style={"width": "100%", "height": "100%"},
                            ),
                        ),
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
        # Only Input Sequences referenced (unbroken) in the selected Datapackage are loaded; any other, e.g. of
        # another Datapackage, shows as missing.
        selected = read_selection(selection)
        package = read_package(name)
        input_items = input_sequence_items(name, package) if package else set()
        wanted = {tuple(item) for chart in charts for item in chart["series"] if tuple(item) in input_items}
        loaded = {item: datapackage.input_sequence(datapackages / name, *item[1:]) for item in wanted}
        inputs = {item: values for item, values in loaded.items() if values is not None}
        return [chart_card(chart, selected, input_items, inputs, package) for chart in charts]

    def selected_node_names(name: str | None, selected_nodes: list[dict] | None) -> set[str]:
        # Cytoscape may keep a selection from the previous Datapackage; drop names it doesn't have.
        package = read_package(name)
        if not package or not selected_nodes:
            return set()
        return {node["id"] for node in selected_nodes} & (package.buses.keys() | package.components.keys())

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
        nodes = selected_node_names(name, selected_nodes)
        package = read_package(name)
        inputs = input_sequence_items(name, package, nodes or None) if package else set()
        if nodes:
            entries = set().union(*(match(result, package).entries_of(nodes) for result in selected.values()))
            outcomes = {(entry, variable) for entry, variable in outcomes if entry in entries}
        return [
            {"label": series_label(item), "value": series_key(item)} for item in [*sorted(outcomes), *sorted(inputs)]
        ]

    @app.callback(
        Output("inspector", "children"),
        Input("graph", "tapNode"),  # not tapNodeData: that doesn't change when the same node is tapped again
        Input({"type": "node-link", "node": ALL}, "n_clicks"),
        Input({"type": "chart-chip", "chart": ALL, "node": ALL}, "n_clicks"),
        Input("datapackage", "value"),
        Input("result-selection", "value"),
        State("graph", "selectedNodeData"),
    )
    def inspect(
        tapped: dict | None,
        _clicks: list[int | None],
        _chip_clicks: list[int | None],
        name: str | None,
        selection: list[str] | None,
        selected_nodes: list[dict] | None,
    ) -> list:
        link_clicked = isinstance(ctx.triggered_id, dict)
        if link_clicked and not ctx.triggered[0]["value"]:
            raise PreventUpdate  # new links or chips rendered, not clicked
        package = read_package(name)
        selected = read_selection(selection)
        if package and link_clicked:
            return inspector(package, ctx.triggered_id["node"], selected)
        if package and ctx.triggered_id == "graph":
            return inspector(package, tapped["data"]["id"], selected)
        kept = selected_node_names(name, selected_nodes)
        if kept and ctx.triggered_id == "result-selection":
            return inspector(package, min(kept), selected)
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

    # A clicked node link or chart chip also selects its node in the graph, which updates "selectedNodeData".
    # Selecting via `elements` instead would miss a node re-selected after a tap: elements only patch on change.
    app.clientside_callback(
        """(_links, _chips) => {
            const context = window.dash_clientside.callback_context;
            const cy = document.getElementById("graph")?._cyreg?.cy;
            if (!cy || !context.triggered[0]?.value) return;  // new links or chips rendered, not clicked
            cy.$(":selected").unselect();
            cy.getElementById(context.triggered_id.node).select();
        }""",
        Input({"type": "node-link", "node": ALL}, "n_clicks"),
        Input({"type": "chart-chip", "chart": ALL, "node": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )

    # Chart callbacks keep "charts-store" and the cards in "charts" in step by patching both at the same index,
    # so editing one chart re-renders only its card.
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
        if isinstance(ctx.triggered_id, dict):
            if not ctx.triggered[0]["value"]:
                raise PreventUpdate  # new "+ chart" buttons rendered, not clicked
            picked = [ctx.triggered_id["outcome"]]
        if not picked:
            raise PreventUpdate
        # Sequence and scalar items never mix in one chart: a mixed pick adds one chart per kind.
        # ponytail: an Outcome counts as scalar if it is a Result Scalar in any selected Result
        scalars = {
            series_key(item) for result in read_selection(selection).values() for item in scalar_outcomes(result)
        }
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
        if isinstance(ctx.triggered_id, dict):
            if not ctx.triggered[0]["value"]:
                raise PreventUpdate  # new "Add Bus balance" button rendered, not clicked
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

    @app.callback(
        Output("charts-store", "data", allow_duplicate=True),
        Output("charts", "children", allow_duplicate=True),
        Input({"type": "chart-field", "field": ALL, "chart": ALL}, "value"),
        Input({"type": "chart-colour", "chart": ALL, "series": ALL}, "value"),
        State("charts-store", "data"),
        State("result-selection", "value"),
        State("datapackage", "value"),
        prevent_initial_call=True,
    )
    def edit_chart(
        _fields: list, _colours: list, charts: list[Chart], selection: list[str] | None, name: str | None
    ) -> tuple:
        if len(ctx.triggered) != 1:
            # A rendered card fires with all its inputs at once (at least title, type, width, series); a user
            # edit changes one.
            raise PreventUpdate
        trigger, value = ctx.triggered_id, ctx.triggered[0]["value"]
        index = chart_index(charts, trigger["chart"])
        chart = charts[index]
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
        patched_charts, cards = Patch(), Patch()
        patched_charts[index] = chart
        (cards[index],) = chart_cards([chart], selection, name)
        return patched_charts, cards

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

    @app.callback(Output("webgl-warning", "children"), Input("charts-store", "data"))
    def warn_webgl(charts: list[Chart]) -> list[html.Div]:
        warning = webgl_warning(charts)
        return [html.Div(warning, className="notice")] if warning else []

    return app
