"""Dash layout and callbacks of the Explorer."""

from pathlib import Path

import dash_cytoscape as cyto
from dash import Dash, Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate

from oemof_dashboard.charts import line_chart
from oemof_dashboard.cli import discover_datapackages, discover_results
from oemof_dashboard.result import Result, read, sequence_outcomes


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
                        # Each chart is its Outcome list as [Result Entry, variable] pairs.
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

    @app.callback(Output("outcome-picker", "options"), Input("result-selection", "value"))
    def list_outcomes(selection: list[str] | None) -> list[dict[str, str]]:
        # ponytail: Result Sequences only while the line chart is the only chart; scalars arrive with the bar chart
        outcomes = set().union(*map(sequence_outcomes, read_selection(selection).values()))
        # Result Entry names come from file names, so they never contain "/".
        return [
            {"label": f"{entry} · {variable}", "value": f"{entry}/{variable}"} for entry, variable in sorted(outcomes)
        ]

    @app.callback(Output("inspector", "children"), Input("result-selection", "value"))
    def summarise(selection: list[str] | None) -> list[html.Details]:
        return [
            html.Details(
                open=True,
                children=[
                    html.Summary(f"{name}: {len(result.entries)} Result Entries"),
                    html.Ul([html.Li(entry) for entry in result.entries]),
                ],
            )
            for name, result in read_selection(selection).items()
        ]

    @app.callback(
        Output("charts-store", "data"),
        Input("add-chart", "n_clicks"),
        State("outcome-picker", "value"),
        State("charts-store", "data"),
        prevent_initial_call=True,
    )
    def add_chart(_clicks: int, picked: list[str] | None, charts: list[list[list[str]]]) -> list[list[list[str]]]:
        if not picked:
            raise PreventUpdate
        return [*charts, [value.split("/", 1) for value in picked]]

    @app.callback(Output("charts", "children"), Input("charts-store", "data"), Input("result-selection", "value"))
    def render_charts(charts: list[list[list[str]]], selection: list[str] | None) -> list[html.Div]:
        selected = read_selection(selection)
        cards = []
        for series in charts:
            figure, notices = line_chart([tuple(item) for item in series], selected)
            cards.append(
                html.Div(
                    className="chart-card",
                    children=[*(html.Div(notice, className="notice") for notice in notices), dcc.Graph(figure=figure)],
                )
            )
        return cards

    return app
