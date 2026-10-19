import json
import socket
import threading
import time
import urllib.request
from pathlib import Path

import pytest
from dash import Dash

from oemof_dashboard.app import create_app

EXPLORER_IDS = [
    "datapackage",
    "result-selection",
    "outcome-picker",
    "add-chart",
    "graph",
    "charts",
    "charts-store",
    "webgl-warning",
    "inspector",
]


@pytest.fixture
def adlershof_app(shipped_data: Path) -> Dash:
    """App over the shipped test data: one Datapackage and one Result, both named adlershof."""
    return create_app(shipped_data / "datapackages", shipped_data / "results")


def components_by_id(app: Dash) -> dict[str, dict]:
    """Fetch the layout as a browser would on page load and index its components' props by id."""
    response = app.server.test_client().get("/_dash-layout")
    assert response.status_code == 200
    found: dict[str, dict] = {}
    pending = [response.get_json()]
    while pending:
        node = pending.pop()
        if isinstance(node, list):
            pending.extend(node)
        elif isinstance(node, dict) and "props" in node:
            props = node["props"]
            if "id" in props:
                found[props["id"]] = props
            pending.append(props.get("children"))
    return found


def free_port() -> int:
    """Ask the OS for a currently unused local port."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_server_starts_and_serves_page(adlershof_app: Dash) -> None:
    port = free_port()
    threading.Thread(target=adlershof_app.run, kwargs={"host": "127.0.0.1", "port": port}, daemon=True).start()

    deadline = time.monotonic() + 10
    while True:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1) as response:
                assert response.status == 200
                return
        except OSError:
            if time.monotonic() > deadline:
                raise


def test_layout_has_explorer_panes(adlershof_app: Dash) -> None:
    assert set(EXPLORER_IDS) <= components_by_id(adlershof_app).keys()


def test_selectors_list_discovered_inputs(tmp_path: Path) -> None:
    (tmp_path / "datapackages" / "dp_only").mkdir(parents=True)
    (tmp_path / "datapackages" / "dp_only" / "datapackage.json").write_text("")
    (tmp_path / "results" / "result_only").mkdir(parents=True)
    (tmp_path / "results" / "result_only" / "bhkw-electricity-sequences.csv").write_text("")

    components = components_by_id(create_app(tmp_path / "datapackages", tmp_path / "results"))

    assert components["datapackage"]["options"] == ["dp_only"]
    assert components["result-selection"]["options"] == ["result_only"]


def test_layout_rescans_folders_on_every_load(tmp_path: Path) -> None:
    app = create_app(tmp_path / "datapackages", tmp_path / "results")
    assert components_by_id(app)["result-selection"]["options"] == []

    (tmp_path / "results" / "late_result").mkdir(parents=True)
    (tmp_path / "results" / "late_result" / "bhkw-electricity-sequences.csv").write_text("")

    assert components_by_id(app)["result-selection"]["options"] == ["late_result"]


def input_name(spec: dict) -> str:
    """Name of a callback input as `fire` takes it: `id.prop`, or the `type` of a pattern-matching id."""
    if spec["id"].startswith("{"):
        return json.loads(spec["id"])["type"]
    return f"{spec['id']}.{spec['property']}"


def pattern(component_id: dict) -> str:
    """Stringify a pattern-matching id as the browser does in `changedPropIds`."""
    return json.dumps(component_id, sort_keys=True, separators=(",", ":"))


def fire(
    app: Dash,
    inputs: dict[str, object],
    states: dict[str, object] | None = None,
    changed: list[str] | None = None,
) -> dict:
    """POST to the callback with exactly these inputs and states, in order, as the browser would; return its outputs.

    A key without "." names a pattern-matching input by its `type` and passes its value through raw, i.e. the
    list of matched `{"id", "property", "value"}` entries. `changed` names the triggering inputs; default all.
    Returns output props by id, or {} when the callback prevents the update.
    """

    def props(values: dict[str, object]) -> list[dict]:
        return [
            {"id": key.split(".")[0], "property": key.split(".")[1], "value": value} if "." in key else value
            for key, value in values.items()
        ]

    states = states or {}
    key = next(
        key
        for key, callback in app.callback_map.items()
        if [input_name(spec) for spec in callback["inputs"] + callback["state"]] == [*inputs, *states]
    )
    outputs = [{"id": output.split(".")[0], "property": output.split(".")[1]} for output in key.strip(".").split("...")]
    payload = {
        "output": key,
        "outputs": outputs if key.startswith("..") else outputs[0],
        "inputs": props(inputs),
        "state": props(states),
        "changedPropIds": changed or list(inputs),
    }
    response = app.server.test_client().post("/_dash-update-component", json=payload)
    assert response.status_code in (200, 204), response.get_data(as_text=True)
    return response.get_json()["response"] if response.status_code == 200 else {}


def patched(value: list, update: object) -> list:
    """Apply a Dash `Patch` response to a list as the browser does; a plain value replaces it."""
    if not (isinstance(update, dict) and "__dash_patch_update" in update):
        return update
    value = list(value)
    for operation in update["operations"]:
        location, params = operation["location"], operation["params"]
        match operation["operation"]:
            case "Append":
                value.append(params["value"])
            case "Assign":
                value[location[0]] = params["value"]
            case "Delete":
                del value[location[0]]
    return value


def test_inspector_summary_lists_result_entries_without_datapackage(adlershof_app: Dash) -> None:
    inspector = fire(
        adlershof_app,
        {"graph.tapNode": None, "node-link": [], "datapackage.value": None, "result-selection.value": ["adlershof"]},
        changed=["result-selection.value"],
    )["inspector"]

    (summary,) = inspector["children"]
    heading, entries = summary["props"]["children"]
    assert heading["props"]["children"] == "adlershof: 85 Result Entries"
    assert {"props": {"children": "bhkw-electricity"}, "type": "Li", "namespace": "dash_html_components"} in entries[
        "props"
    ]["children"]


class Page:
    """Charts store and rendered chart cards of one browser page, driven through the chart callbacks."""

    def __init__(self, app: Dash) -> None:
        self.app = app
        self.charts: list[dict] = []
        self.cards: list = []

    def apply(self, response: dict) -> None:
        """Apply a callback response to the charts store and cards, unless the update was prevented."""
        if response:
            self.charts = patched(self.charts, response["charts-store"]["data"])
            self.cards = patched(self.cards, response["charts"]["children"])

    def states(self) -> dict[str, object]:
        """States the chart callbacks read: the charts store and a Result Selection of adlershof."""
        return {"charts-store.data": self.charts, "result-selection.value": ["adlershof"]}

    def trigger(self, inputs: dict[str, list], component_id: dict, prop: str, value: object) -> None:
        """Change one prop of one card control, passing the other pattern-matching inputs of the callback empty."""
        inputs[component_id["type"]] = [{"id": component_id, "property": prop, "value": value}]
        self.apply(fire(self.app, inputs, self.states(), changed=[f"{pattern(component_id)}.{prop}"]))

    def add(self, *picked: str) -> None:
        """Pick Outcomes as "<Result Entry>/<variable>" and click "Add chart"."""
        self.apply(fire(self.app, {"add-chart.n_clicks": 1}, {"outcome-picker.value": list(picked), **self.states()}))

    def edit(self, field: str, chart: int, value: object) -> None:
        """Set a card's title, type, width or series control."""
        component_id = {"type": "chart-field", "field": field, "chart": self.charts[chart]["id"]}
        self.trigger({"chart-field": [], "chart-colour": []}, component_id, "value", value)

    def colour(self, chart: int, series: str, value: str) -> None:
        """Type a colour override for one series of a card."""
        component_id = {"type": "chart-colour", "chart": self.charts[chart]["id"], "series": series}
        self.trigger({"chart-field": [], "chart-colour": []}, component_id, "value", value)

    def click(self, action: str, chart: int) -> None:
        """Click a card's up, down or remove button."""
        component_id = {"type": "chart-action", "action": action, "chart": self.charts[chart]["id"]}
        self.trigger({"chart-action": []}, component_id, "n_clicks", 1)

    def series(self) -> list[list[list[str]]]:
        """Series of every chart, in grid order."""
        return [chart["series"] for chart in self.charts]


@pytest.fixture
def page(adlershof_app: Dash) -> Page:
    """Fresh page over the adlershof app without charts."""
    return Page(adlershof_app)


def test_added_chart_is_a_half_width_line_chart_rendered_for_result_selection(page: Page) -> None:
    page.add("bhkw-electricity/flow")

    (chart,) = page.charts
    assert chart | {"id": None} == {
        "id": None,
        "kind": "sequences",
        "type": "line",
        "title": None,
        "series": [["bhkw-electricity", "flow"]],
        "colours": {},
        "width": "half",
    }
    assert "bhkw-electricity · flow · adlershof" in json.dumps(page.cards, ensure_ascii=False)


def test_result_selection_change_rerenders_stored_charts(page: Page) -> None:
    page.add("bhkw-electricity/flow")

    cards = fire(page.app, {"result-selection.value": ["adlershof"]}, {"charts-store.data": page.charts})["charts"][
        "children"
    ]

    assert "bhkw-electricity · flow · adlershof" in json.dumps(cards, ensure_ascii=False)


def test_editing_title_width_and_series_updates_chart_and_card(page: Page) -> None:
    page.add("bhkw-electricity/flow")

    page.edit("title", 0, "CHP output")
    page.edit("width", 0, "full")
    page.edit("series", 0, ["bhkw-electricity/flow", "battery_large-None/storage_content"])

    (chart,) = page.charts
    assert (chart["title"], chart["width"]) == ("CHP output", "full")
    assert chart["series"] == [["bhkw-electricity", "flow"], ["battery_large-None", "storage_content"]]
    card = json.dumps(page.cards, ensure_ascii=False)
    assert "CHP output" in card
    assert "battery_large-None · storage_content · adlershof" in card
    assert "chart-card full" in card


@pytest.mark.parametrize("cleared", ["", "   "])
def test_cleared_title_falls_back_to_auto(page: Page, cleared: str) -> None:
    page.add("bhkw-electricity/flow")
    page.edit("title", 0, "CHP output")

    page.edit("title", 0, cleared)

    assert page.charts[0]["title"] is None


def test_emptied_chart_stays(page: Page) -> None:
    page.add("bhkw-electricity/flow")

    page.edit("series", 0, [])

    assert page.series() == [[]]
    assert len(page.cards) == 1


def test_series_options_offer_result_sequences_only(page: Page) -> None:
    page.add("bhkw-electricity/flow")

    options = json.dumps(page.cards)

    assert "battery_large-None/storage_content" in options
    assert "invest" not in options  # a Result Scalar


@pytest.mark.parametrize(("value", "colours"), [("#123456", {"bhkw-electricity/flow": "#123456"}), ("", {})])
def test_colour_override_is_set_or_cleared(page: Page, value: str, colours: dict) -> None:
    page.add("bhkw-electricity/flow")
    page.colour(0, "bhkw-electricity/flow", "#abcdef")

    page.colour(0, "bhkw-electricity/flow", value)

    assert page.charts[0]["colours"] == colours


def test_invalid_colour_is_ignored(page: Page) -> None:
    page.add("bhkw-electricity/flow")

    page.colour(0, "bhkw-electricity/flow", "red; drop")

    assert page.charts[0]["colours"] == {}


def test_charts_move_up_and_down_and_are_removed(page: Page) -> None:
    page.add("bhkw-electricity/flow")
    page.add("battery_large-None/storage_content")
    page.add("wind-electricity/flow")
    first, second, third = page.series()

    page.click("up", 1)
    assert page.series() == [second, first, third]
    page.click("down", 1)
    assert page.series() == [second, third, first]
    page.click("down", 2)  # already last
    assert page.series() == [second, third, first]
    page.click("remove", 0)
    assert page.series() == [third, first]
    assert len(page.cards) == 2
    assert "wind-electricity · flow" in json.dumps(page.cards[0], ensure_ascii=False)


def test_more_than_eight_webgl_charts_show_warning(adlershof_app: Dash) -> None:
    charts = [{"id": str(index), "kind": "sequences", "type": "line"} for index in range(9)]

    warning = fire(adlershof_app, {"charts-store.data": charts})["webgl-warning"]["children"]

    assert "9 WebGL charts" in json.dumps(warning)


def test_rendering_a_card_does_not_count_as_editing_it(page: Page) -> None:
    page.add("bhkw-electricity/flow")
    page.edit("title", 0, "CHP output")
    chart_id = page.charts[0]["id"]
    # A newly rendered card fires the edit callback with all of its inputs at once.
    fields = [
        {"id": {"type": "chart-field", "field": field, "chart": chart_id}, "property": "value", "value": value}
        for field, value in [("title", ""), ("type", "line"), ("width", "half")]
    ]

    response = fire(
        page.app,
        {"chart-field": fields, "chart-colour": []},
        {"charts-store.data": page.charts, "result-selection.value": ["adlershof"]},
        changed=[f"{pattern(field['id'])}.value" for field in fields],
    )

    assert response == {}


def test_dropping_a_series_drops_its_colour_override(page: Page) -> None:
    page.add("bhkw-electricity/flow", "wind-electricity/flow")
    page.colour(0, "bhkw-electricity/flow", "#123456")
    page.colour(0, "wind-electricity/flow", "#abcdef")

    page.edit("series", 0, ["wind-electricity/flow"])

    assert page.charts[0]["colours"] == {"wind-electricity/flow": "#abcdef"}
