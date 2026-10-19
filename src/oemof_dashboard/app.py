"""Dash layout and callbacks of the Explorer."""

from pathlib import Path

import dash_cytoscape as cyto
from dash import Dash, dcc, html

from oemof_dashboard.cli import discover_datapackages, discover_results


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
    return app
