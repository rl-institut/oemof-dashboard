import json

import pytest

from oemof_dashboard.dashboard import from_json, to_json

CHARTS = [
    {
        "id": "a",
        "kind": "sequences",
        "type": "line",
        "title": None,
        "series": [["bhkw-electricity", "flow"], ["adlershof", "volatile_profile", "wind-profile"]],
        "colours": {"bhkw-electricity/flow": "#123456"},
        "width": "half",
    },
    {
        "id": "b",
        "kind": "sequences",
        "type": "stacked_area",
        "title": "Heat",
        "series": [],
        "colours": {},
        "width": "full",
    },
    {
        "id": "c",
        "kind": "sequences",
        "type": "duration_curve",
        "title": None,
        "series": [["gas-bhkw", "flow"]],
        "colours": {},
        "width": "half",
    },
    {
        "id": "d",
        "kind": "scalars",
        "type": "bar",
        "title": None,
        "series": [["bhkw-electricity", "invest"]],
        "colours": {},
        "width": "half",
    },
    {
        "id": "e",
        "kind": "system",
        "type": "sankey",
        "title": None,
        "series": [],
        "colours": {},
        "width": "half",
        "bus": None,
    },
    {
        "id": "f",
        "kind": "system",
        "type": "bus_balance",
        "title": None,
        "series": [],
        "colours": {},
        "width": "full",
        "bus": "gas",
    },
]


def without_ids(charts: list[dict]) -> list[dict]:
    """Chart configs with their ids dropped."""
    return [{key: value for key, value in chart.items() if key != "id"} for chart in charts]


def test_round_trip_keeps_every_chart_type_in_order_with_selection_and_datapackage() -> None:
    dashboard = from_json(to_json(CHARTS, ["2045", "2050"], "adlershof"))

    assert dashboard.result_selection == ["2045", "2050"]
    assert dashboard.datapackage == "adlershof"
    assert without_ids(dashboard.chart_configs()) == without_ids(CHARTS)


def test_loaded_charts_get_fresh_ids() -> None:
    first, second = from_json(to_json(CHARTS[:2], None, None)).chart_configs()

    assert first["id"] != second["id"]
    assert {first["id"], second["id"]}.isdisjoint({"a", "b"})


def test_file_holds_version_and_no_chart_ids() -> None:
    stored = json.loads(to_json(CHARTS[:1], None, None))

    assert stored["version"] == 1
    assert (stored["result_selection"], stored["datapackage"]) == (None, None)
    assert "id" not in stored["charts"][0]


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("{not json", "Invalid JSON"),
        ('{"version": 2, "charts": []}', "unknown version 2"),
        ('{"version": 1}', "charts"),
        ('{"version": 1, "charts": [{"kind": "scalars", "type": "line"}]}', "charts.0"),
        ("[]", "Input should be"),
    ],
)
def test_bad_file_is_refused_with_reason(text: str, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        from_json(text)


@pytest.mark.parametrize(
    "chart",
    [
        CHARTS[0] | {"type": "bar"},  # type of another kind
        CHARTS[3] | {"series": [["adlershof", "volatile_profile", "wind-profile"]]},  # Input Sequence in a bar chart
        CHARTS[0] | {"series": [["only-entry"]]},
        CHARTS[0] | {"colours": {"bhkw-electricity/flow": "red"}},
        CHARTS[5] | {"bus": None},  # a Bus balance needs its Bus
        CHARTS[3] | {"bus": "gas"},  # only system charts have a Bus
    ],
)
def test_chart_the_dashboard_could_not_draw_is_refused(chart: dict) -> None:
    with pytest.raises(ValueError):
        from_json(to_json([chart], None, None))
