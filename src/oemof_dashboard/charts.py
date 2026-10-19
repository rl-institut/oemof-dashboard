"""Pure figure builders: Outcomes × Result Selection → plotly figure plus notices. No Dash imports."""

import plotly.graph_objects as go

from oemof_dashboard.result import Result, ResultEntry

# Validated categorical palette (light mode), fixed order; colour encodes Entry×variable, never the Result.
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
# The Result is encoded by dash style; the first four stay distinguishable.
DASHES = ["solid", "dash", "dot", "dashdot", "longdash", "longdashdot"]
MAX_DISTINCT_RESULTS = 4


def line_chart(series: list[tuple[str, str]], results: dict[str, Result]) -> tuple[go.Figure, list[str]]:
    """Build a line chart of Result Sequences for every Result in the Result Selection.

    Args:
        series: Outcomes as (Result Entry, variable), in palette order.
        results: Result Selection as Result name → Result, in dash style order.

    Returns:
        Figure with one `Scattergl` trace per Outcome × Result on a shared datetime x-axis; an Outcome
        missing from a Result is a legend entry suffixed "(missing)" without data. Notices to show with it.
    """
    figure = go.Figure(layout={"xaxis": {"type": "date"}, "margin": {"l": 40, "r": 10, "t": 10, "b": 30}})
    for index, (entry, variable) in enumerate(series):
        # ponytail: palette wraps after 8 Outcomes, per-series colour overrides arrive with chart card editing
        colour = PALETTE[index % len(PALETTE)]
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
