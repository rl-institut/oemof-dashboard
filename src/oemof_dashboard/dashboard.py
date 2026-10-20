"""Dashboard file: the charts in grid order with an optional Result Selection and Datapackage, as versioned JSON."""

import json
import uuid
from typing import Literal

from pydantic import BaseModel, model_validator

from oemof_dashboard.charts import CHART_TYPES, HEX_COLOUR, Chart

VERSION = 1
# Series item lengths a chart kind can draw: Outcomes (2) everywhere but in system charts, Input Sequences (3) in
# sequence charts only.
SERIES_LENGTHS = {"sequences": (2, 3), "scalars": (2,), "system": ()}


class DashboardChart(BaseModel):
    """A chart config as stored: a `Chart` without its id, `bus` set for system charts only."""

    kind: str
    type: str
    title: str | None
    series: list[list[str]]
    colours: dict[str, str]
    width: Literal["half", "full"]
    bus: str | None = None

    @model_validator(mode="after")
    def refuse_undrawable(self) -> "DashboardChart":
        """Refuse a chart the charts module couldn't draw, or the Dashboard couldn't have made.

        Returns:
            The chart, unchanged.

        Raises:
            ValueError: If its type isn't of its kind, a series item or colour doesn't fit, or its Bus is set on a
                chart other than a system chart or missing from a Bus balance.
        """
        if self.type not in CHART_TYPES.get(self.kind, ()):
            raise ValueError(f"chart type {self.type!r} isn't of kind {self.kind!r}")
        if (self.bus is not None and self.kind != "system") or (self.type == "bus_balance" and self.bus is None):
            raise ValueError(f"a {self.type} chart can't have Bus {self.bus!r}")
        if any(len(item) not in SERIES_LENGTHS[self.kind] for item in self.series):
            raise ValueError(f"series {self.series} can't be drawn in a {self.type} chart")
        if not all(HEX_COLOUR.fullmatch(colour) for colour in self.colours.values()):
            raise ValueError(f"colours {self.colours} aren't all hex colours like #2a78d6")
        return self


class Dashboard(BaseModel):
    """A Dashboard file. Result Selection and Datapackage are non-binding defaults; None if not stored."""

    version: Literal[1]
    result_selection: list[str] | None = None
    datapackage: str | None = None
    charts: list[DashboardChart]

    def chart_configs(self) -> list[Chart]:
        """Charts for the charts store.

        Returns:
            Chart configs in grid order, each with a fresh id.
        """
        return [chart.model_dump(exclude_unset=True) | {"id": uuid.uuid4().hex} for chart in self.charts]


def to_json(charts: list[Chart], selection: list[str] | None, datapackage: str | None) -> str:
    """Dashboard file of the current page.

    Args:
        charts: Charts store content, in grid order.
        selection: Result Selection; None if none is made.
        datapackage: Selected Datapackage; None if none is selected.

    Returns:
        JSON text of the Dashboard file.
    """
    dashboard = Dashboard(
        version=VERSION,
        result_selection=selection or None,
        datapackage=datapackage,
        charts=[DashboardChart.model_validate(chart) for chart in charts],  # drops the id
    )
    return dashboard.model_dump_json(exclude_unset=True, indent=2)


def from_json(text: str) -> Dashboard:
    """Read a Dashboard file.

    Args:
        text: JSON text of the file.

    Returns:
        The Dashboard.

    Raises:
        ValueError: With the reason, if the text isn't JSON, has an unknown version or fails the schema.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON: {error}") from error
    if isinstance(data, dict) and data.get("version", VERSION) != VERSION:
        raise ValueError(f"unknown version {data['version']!r}")
    return Dashboard.model_validate(data)  # pydantic's ValidationError is a ValueError
