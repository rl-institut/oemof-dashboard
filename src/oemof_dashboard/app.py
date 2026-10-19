"""Dash layout and callbacks of the Explorer."""

import re
import uuid
from pathlib import Path

import dash_cytoscape as cyto
from dash import ALL, Dash, Input, Output, Patch, State, ctx, dcc, html
from dash.exceptions import PreventUpdate

from oemof_dashboard import datapackage
from oemof_dashboard.charts import CHART_TYPES, PALETTE, Chart, auto_title, chart_figure, webgl_warning
from oemof_dashboard.cli import discover_datapackages, discover_results
from oemof_dashboard.result import Result, read, sequence_outcomes

HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{6}")
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
]


def graph_elements(package: datapackage.Datapackage) -> list[dict]:
    """Cytoscape nodes for all Buses and Components, and one edge per Connection.

    Args:
        package: Datapackage to draw.

    Returns:
        Cytoscape elements.
    """
    nodes = [{"data": {"id": name}, "classes": "bus"} for name in package.buses]
    nodes += [{"data": {"id": name}, "classes": "component"} for name in package.components]
    edges = [{"data": {"source": component, "target": bus}} for component, bus in package.connections]
    return nodes + edges


def node_link(name: str) -> html.Button:
    """Button that selects a node in the inspector.

    Args:
        name: Bus or Component name.

    Returns:
        Button with a pattern-matching `node-link` id.
    """
    return html.Button(name, id={"type": "node-link", "node": name}, className="node-link")


def inspector(package: datapackage.Datapackage, name: str) -> list:
    """Inspector content for one Bus or Component: type/resource, Connections, Parameters, Input Sequences.

    Args:
        package: Datapackage holding the node.
        name: Bus or Component name.

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
    ]


def chart_card(chart: Chart, results: dict[str, Result]) -> html.Div:
    """Chart card: controls for title, type, width, order and removal; series multi-select; colour overrides; figure.

    Args:
        chart: Chart config.
        results: Result Selection as Result name → Result.

    Returns:
        Card whose controls carry pattern-matching ids keyed by the chart id.
    """
    chart_id = chart["id"]
    picked = [f"{entry}/{variable}" for entry, variable in chart["series"]]
    # ponytail: sequence kind only until scalar charts arrive; then pick the outcomes by chart["kind"]
    outcomes = {f"{entry}/{variable}" for result in results.values() for entry, variable in sequence_outcomes(result)}
    options = [{"label": item.replace("/", " · ", 1), "value": item} for item in sorted(outcomes | set(picked))]
    figure, notices = chart_figure(chart, results)

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
                        placeholder=auto_title(chart["series"]),
                        debounce=True,
                        className="chart-title",
                    ),
                    dcc.Dropdown(
                        id=field("type"),
                        options=CHART_TYPES[chart["kind"]],
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
            dcc.Dropdown(id=field("series"), options=options, value=picked, multi=True),
            html.Div(
                className="chart-colours",
                children=[
                    html.Label(
                        [
                            item.replace("/", " · ", 1),
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
                            options=discover_datapackages(datapackages),
                            placeholder="(no Datapackage)",
                        ),
                        html.Label("Result Selection", htmlFor="result-selection"),
                        dcc.Dropdown(id="result-selection", options=discover_results(results), multi=True),
                        html.Hr(),
                        html.Label("Outcome", htmlFor="outcome-picker"),
                        dcc.Dropdown(
                            id="outcome-picker", options=[], multi=True, placeholder="Outcome / Input Sequence…"
                        ),
                        html.Button("Add chart", id="add-chart"),
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

    def read_selection(selection: list[str] | None) -> dict[str, Result]:
        # Parsed lazily on selection; `read` re-uses the parse until a Result file changes.
        return {name: read(results / name) for name in selection or []}

    @app.callback(Output("graph", "elements"), Input("datapackage", "value"))
    def draw_graph(name: str | None) -> list[dict]:
        return graph_elements(datapackage.read(datapackages / name)) if name else []

    @app.callback(Output("outcome-picker", "options"), Input("result-selection", "value"))
    def list_outcomes(selection: list[str] | None) -> list[dict[str, str]]:
        # ponytail: Result Sequences only while the line chart is the only chart; scalars arrive with the bar chart
        outcomes = set().union(*map(sequence_outcomes, read_selection(selection).values()))
        # Result Entry names come from file names, so they never contain "/".
        return [
            {"label": f"{entry} · {variable}", "value": f"{entry}/{variable}"} for entry, variable in sorted(outcomes)
        ]

    @app.callback(
        Output("inspector", "children"),
        Input("graph", "tapNode"),  # not tapNodeData: that doesn't change when the same node is tapped again
        Input({"type": "node-link", "node": ALL}, "n_clicks"),
        Input("datapackage", "value"),
        Input("result-selection", "value"),
    )
    def inspect(tapped: dict | None, _clicks: list[int | None], name: str | None, selection: list[str] | None) -> list:
        link_clicked = isinstance(ctx.triggered_id, dict)
        if link_clicked and not ctx.triggered[0]["value"]:
            raise PreventUpdate  # new links rendered, not clicked
        package = datapackage.read(datapackages / name) if name else None
        if package and link_clicked:
            return inspector(package, ctx.triggered_id["node"])
        if package and ctx.triggered_id == "graph":
            return inspector(package, tapped["data"]["id"])
        # Nothing selected: summarise the inputs.
        warnings = [html.Div(warning, className="warning") for warning in package.warnings] if package else []
        return warnings + [
            html.Details(
                open=True,
                children=[
                    html.Summary(f"{result_name}: {len(result.entries)} Result Entries"),
                    html.Ul([html.Li(entry) for entry in result.entries]),
                ],
            )
            for result_name, result in read_selection(selection).items()
        ]

    # Chart callbacks keep "charts-store" and the cards in "charts" in step by patching both at the same index,
    # so editing one chart re-renders only its card.
    @app.callback(
        Output("charts-store", "data"),
        Output("charts", "children", allow_duplicate=True),
        Input("add-chart", "n_clicks"),
        State("outcome-picker", "value"),
        State("charts-store", "data"),
        State("result-selection", "value"),
        prevent_initial_call=True,
    )
    def add_chart(_clicks: int, picked: list[str] | None, _charts: list[Chart], selection: list[str] | None) -> tuple:
        if not picked:
            raise PreventUpdate
        chart: Chart = {
            "id": uuid.uuid4().hex,
            "kind": "sequences",
            "type": "line",
            "title": None,
            "series": [value.split("/", 1) for value in picked],
            "colours": {},
            "width": "half",
        }
        charts, cards = Patch(), Patch()
        charts.append(chart)
        cards.append(chart_card(chart, read_selection(selection)))
        return charts, cards

    @app.callback(
        Output("charts-store", "data", allow_duplicate=True),
        Output("charts", "children", allow_duplicate=True),
        Input({"type": "chart-field", "field": ALL, "chart": ALL}, "value"),
        Input({"type": "chart-colour", "chart": ALL, "series": ALL}, "value"),
        State("charts-store", "data"),
        State("result-selection", "value"),
        prevent_initial_call=True,
    )
    def edit_chart(_fields: list, _colours: list, charts: list[Chart], selection: list[str] | None) -> tuple:
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
            chart["series"] = [item.split("/", 1) for item in value or []]
            chart["colours"] = {item: colour for item, colour in chart["colours"].items() if item in (value or [])}
        elif trigger["field"] == "title":
            chart["title"] = (value or "").strip() or None
        else:
            chart[trigger["field"]] = value  # type or width, offered by the card's dropdowns
        patched_charts, cards = Patch(), Patch()
        patched_charts[index] = chart
        cards[index] = chart_card(chart, read_selection(selection))
        return patched_charts, cards

    @app.callback(
        Output("charts-store", "data", allow_duplicate=True),
        Output("charts", "children", allow_duplicate=True),
        Input({"type": "chart-action", "action": ALL, "chart": ALL}, "n_clicks"),
        State("charts-store", "data"),
        State("result-selection", "value"),
        prevent_initial_call=True,
    )
    def arrange_chart(_clicks: list[int | None], charts: list[Chart], selection: list[str] | None) -> tuple:
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
        selected = read_selection(selection)
        for position, chart in ((index, charts[other]), (other, charts[index])):
            patched_charts[position] = chart
            cards[position] = chart_card(chart, selected)
        return patched_charts, cards

    @app.callback(
        Output("charts", "children"),
        Input("result-selection", "value"),
        State("charts-store", "data"),
    )
    def render_charts(selection: list[str] | None, charts: list[Chart]) -> list[html.Div]:
        selected = read_selection(selection)
        return [chart_card(chart, selected) for chart in charts]

    @app.callback(Output("webgl-warning", "children"), Input("charts-store", "data"))
    def warn_webgl(charts: list[Chart]) -> list[html.Div]:
        warning = webgl_warning(charts)
        return [html.Div(warning, className="notice")] if warning else []

    return app
