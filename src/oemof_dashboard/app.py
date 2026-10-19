"""Dash layout and callbacks of the Explorer."""

from pathlib import Path

import dash_cytoscape as cyto
from dash import ALL, Dash, Input, Output, ctx, dcc, html
from dash.exceptions import PreventUpdate

from oemof_dashboard import datapackage
from oemof_dashboard.cli import discover_datapackages, discover_results

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
                        html.Div(id="charts", className="chart-grid"),
                    ],
                ),
                html.Div(id="inspector", className="pane"),
            ],
        )

    app.layout = layout

    @app.callback(Output("graph", "elements"), Input("datapackage", "value"))
    def draw_graph(name: str | None) -> list[dict]:
        return graph_elements(datapackage.read(datapackages / name)) if name else []

    @app.callback(
        Output("inspector", "children"),
        Input("graph", "tapNode"),  # not tapNodeData: that doesn't change when the same node is tapped again
        Input({"type": "node-link", "node": ALL}, "n_clicks"),
        Input("datapackage", "value"),
    )
    def inspect(tapped: dict | None, _clicks: list[int | None], name: str | None) -> list:
        if not name:
            return []
        link_clicked = isinstance(ctx.triggered_id, dict)
        if link_clicked and not ctx.triggered[0]["value"]:
            raise PreventUpdate  # new links rendered, not clicked
        package = datapackage.read(datapackages / name)
        if link_clicked:
            return inspector(package, ctx.triggered_id["node"])
        if ctx.triggered_id == "graph":
            return inspector(package, tapped["data"]["id"])
        return [html.Div(warning, className="warning") for warning in package.warnings]

    return app
