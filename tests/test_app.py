import base64
import json
import math
import socket
import threading
import time
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path

import pandas as pd
import pytest
from conftest import package_of, result_of
from dash import Dash, html
from plotly.utils import PlotlyJSONEncoder

from oemof_dashboard import datapackage
from oemof_dashboard.app import create_app, graph_elements, input_scalar_items, inspector
from oemof_dashboard.charts import PALETTE
from oemof_dashboard.result import Result, read

# The pattern-matching inputs of the card edit callbacks, none matched.
NO_EDIT_INPUTS = {"chart-field": [], "chart-colour": [], "chart-colour-reset": []}
WIND_PROFILE = "input:adlershof/volatile_profile/wind-profile"
BHKW_EFFICIENCY = "input:adlershof/bhkw/electric_efficiency"
EXPLORER_IDS = [
    "datapackage",
    "result-selection",
    "outcome-picker",
    "add-chart",
    "sankey-bus",
    "add-sankey",
    "add-bus-balance",
    "graph",
    "charts",
    "charts-store",
    "webgl-warning",
    "save-dashboard",
    "dashboard-download",
    "dashboard-upload",
    "dashboard-notice",
    "inspector",
    "toggle-left-pane",
    "toggle-inspector",
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


@pytest.fixture
def faulty_inputs(tmp_path: Path) -> Path:
    """Inputs with defects: Datapackages `broken` (refused) and `warned` (row without type); Results `empty`
    (refused) and `partial` (one unparseable file)."""
    (tmp_path / "datapackages" / "broken").mkdir(parents=True)
    (tmp_path / "datapackages" / "broken" / "datapackage.json").write_text("")
    warned = tmp_path / "datapackages" / "warned"
    warned.mkdir()
    (warned / "bus.csv").write_text("name;type\nel;bus\npv;\n")
    schema = {"fields": [{"name": "name"}, {"name": "type"}]}
    (warned / "datapackage.json").write_text(
        json.dumps({"resources": [{"name": "bus", "path": "bus.csv", "schema": schema}]})
    )
    (tmp_path / "results" / "empty").mkdir(parents=True)
    (tmp_path / "results" / "empty" / "bhkw-electricity-sequences.csv").write_text("")
    (tmp_path / "results" / "partial").mkdir()
    (tmp_path / "results" / "partial" / "bhkw-electricity-sequences.csv").write_text("")
    (tmp_path / "results" / "partial" / "bhkw-electricity-scalars.csv").write_text("variable_name;2050\ninvest;1\n")
    return tmp_path


def test_selectors_mark_refused_inputs_and_count_warnings(faulty_inputs: Path) -> None:
    components = components_by_id(create_app(faulty_inputs / "datapackages", faulty_inputs / "results"))

    broken, warned = components["datapackage"]["options"]
    assert broken["label"] == "✖ broken"
    assert broken["disabled"] is True
    assert "datapackage.json" in broken["title"]
    assert warned == {"label": "warned ⚠ 2", "value": "warned"}  # row without type, no Bus foreignKeys
    empty, partial = components["result-selection"]["options"]
    assert empty == {
        "label": "✖ empty",
        "value": "empty",
        "disabled": True,
        "title": "no usable Result file; bhkw-electricity-sequences.csv: unparseable (No columns to parse from file), "
        "skipped",
    }
    assert partial == {"label": "partial ⚠ 1", "value": "partial"}


def test_inspector_summary_lists_input_warnings_per_input(faulty_inputs: Path) -> None:
    app = create_app(faulty_inputs / "datapackages", faulty_inputs / "results")

    inputs = inspect_inputs("warned") | {"result-selection.value": ["partial"]}
    text = rendered(fire(app, inputs, changed=["result-selection.value"])["inspector"]["children"])

    assert "Datapackage warned: 2 Input Warnings" in text
    assert "bus line 3: pv has no type, kept as unknown" in text
    assert "partial: 1 Input Warnings" in text
    assert "bhkw-electricity-sequences.csv: unparseable" in text
    assert "refused" not in text


def test_selected_refused_input_shows_banner(faulty_inputs: Path) -> None:
    app = create_app(faulty_inputs / "datapackages", faulty_inputs / "results")

    inputs = inspect_inputs("broken") | {"result-selection.value": ["empty", "partial"]}
    children = fire(app, inputs, changed=["datapackage.value"])["inspector"]["children"]

    assert "Datapackage broken refused: datapackage.json missing or invalid" in rendered(children[0])
    assert "Result empty refused: no usable Result file" in rendered(children[1])
    assert "partial: 1 Result Entries" in rendered(children)


def test_layout_rescans_folders_on_every_load(tmp_path: Path) -> None:
    app = create_app(tmp_path / "datapackages", tmp_path / "results")
    assert components_by_id(app)["result-selection"]["options"] == []

    (tmp_path / "results" / "late_result").mkdir(parents=True)
    (tmp_path / "results" / "late_result" / "bhkw-electricity-scalars.csv").write_text("variable_name;2050\ninvest;1\n")

    assert components_by_id(app)["result-selection"]["options"] == [{"label": "late_result", "value": "late_result"}]


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
    An empty `changed` is what the browser sends when the last component matching a pattern-matching input is gone.
    Returns output props by id, or {} when the callback prevents the update.
    """

    def props(values: dict[str, object]) -> list[dict]:
        return [
            {"id": key.split(".")[0], "property": key.split(".")[1], "value": value} if "." in key else value
            for key, value in values.items()
        ]

    states = states or {}
    changed = list(inputs) if changed is None else changed
    key = next(
        key
        for key, callback in app.callback_map.items()
        if "callback" in callback  # server-side, not a clientside callback on the same inputs
        and [input_name(spec) for spec in callback["inputs"] + callback["state"]] == [*inputs, *states]
    )
    outputs = [
        {"id": concrete(output.rsplit(".", 1)[0], changed), "property": output.rsplit(".", 1)[1]}
        for output in key.strip(".").split("...")
    ]
    payload = {
        "output": key,
        "outputs": outputs if key.startswith("..") else outputs[0],
        "inputs": props(inputs),
        "state": props(states),
        "changedPropIds": changed,
    }
    response = app.server.test_client().post("/_dash-update-component", json=payload)
    assert response.status_code in (200, 204), response.get_data(as_text=True)
    return response.get_json()["response"] if response.status_code == 200 else {}


def concrete(output_id: str, changed: list[str]) -> str | dict:
    """Output id as the browser sends it: a MATCH wildcard takes its value from the triggering input."""
    if not output_id.startswith("{"):
        return output_id
    trigger = json.loads(changed[0].rsplit(".", 1)[0])
    return {key: trigger[key] if value == ["MATCH"] else value for key, value in json.loads(output_id).items()}


def components(tree: object) -> Iterator[dict]:
    """Props of every component in a rendered component tree."""
    if isinstance(tree, list):
        for item in tree:
            yield from components(item)
    elif isinstance(tree, dict) and "props" in tree:
        yield tree["props"]
        yield from components(tree["props"].get("children"))


def set_props(tree: object, component_id: dict, props: dict) -> None:
    """Update the props of the component with this id in a rendered component tree, as the browser does."""
    for found in components(tree):
        if found.get("id") == component_id:
            found.update(props)


def props_of(tree: object, component_id: dict) -> dict:
    """Props of the one component with this id in a rendered component tree."""
    (props,) = [found for found in components(tree) if found.get("id") == component_id]
    return props


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
            case "Extend":
                value.extend(params["value"])
            case "Assign":
                value[location[0]] = params["value"]
            case "Delete":
                del value[location[0]]
    return value


def test_inspector_summary_lists_result_entries_without_datapackage(adlershof_app: Dash) -> None:
    inspector = fire(
        adlershof_app,
        inspect_inputs(None) | {"result-selection.value": ["adlershof"]},
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
        self.datapackage: str | None = "adlershof"
        self.added: str | None = None  # id of the last added chart, for the browser to scroll to

    def apply(self, response: dict) -> None:
        """Apply a callback response to the charts store, the cards and props of single cards' components."""
        for output, props in response.items():
            if output == "charts-store":
                self.charts = patched(self.charts, props["data"])
            elif output == "charts":
                self.cards = patched(self.cards, props["children"])
            elif output == "added-chart":
                self.added = props["data"]
            elif output.startswith("{"):
                set_props(self.cards, json.loads(output), props)

    def states(self) -> dict[str, object]:
        """States the chart callbacks read: the charts store, a Result Selection of adlershof and the Datapackage."""
        return {
            "charts-store.data": self.charts,
            "result-selection.value": ["adlershof"],
            "datapackage.value": self.datapackage,
        }

    def rerender(self) -> None:
        """Re-render all cards, as on a change of the Result Selection or Datapackage."""
        inputs = {"result-selection.value": ["adlershof"], "datapackage.value": self.datapackage}
        self.cards = fire(self.app, inputs, {"charts-store.data": self.charts})["charts"]["children"]

    def trigger(self, inputs: dict[str, list], component_id: dict, prop: str, value: object) -> None:
        """Click one card button, passing the other pattern-matching inputs of the callback empty."""
        inputs[component_id["type"]] = [{"id": component_id, "property": prop, "value": value}]
        self.apply(fire(self.app, inputs, self.states(), changed=[f"{pattern(component_id)}.{prop}"]))

    def add(self, *picked: str) -> None:
        """Pick Outcomes as "<Result Entry>/<variable>" and click "Add chart"."""
        self.apply(
            fire(
                self.app,
                {"add-chart.n_clicks": 1, "outcome-chart": []},
                {"outcome-picker.value": list(picked), **self.states()},
            )
        )

    def add_system(self, button: str, bus: str | None = None, inspector_bus: str | None = None) -> None:
        """Pick a Bus in the left pane and click "Add Sankey" or "Add Bus balance" there, or click "Add Bus balance"
        in the inspector of `inspector_bus` (`button` "bus-balance")."""
        inputs: dict[str, object] = {"add-sankey.n_clicks": None, "add-bus-balance.n_clicks": None, "bus-balance": []}
        changed = [f"{button}.n_clicks"]
        if inspector_bus:
            component_id = {"type": "bus-balance", "bus": inspector_bus}
            inputs["bus-balance"] = [{"id": component_id, "property": "n_clicks", "value": 1}]
            changed = [f"{pattern(component_id)}.n_clicks"]
        else:
            inputs[f"{button}.n_clicks"] = 1
        self.apply(fire(self.app, inputs, {"sankey-bus.value": bus, **self.states()}, changed))

    def add_sankey(self, bus: str | None = None) -> None:
        """Pick a Bus filter, or none for the whole system, and click "Add Sankey"."""
        self.add_system("add-sankey", bus)

    def change(self, component_id: dict, value: object, prop: str = "value") -> set[str]:
        """Change a prop of one card control: both edit callbacks (store and card) fire on the same state.

        Returns the ids of the updated outputs."""
        set_props(self.cards, component_id, {prop: value})
        inputs: dict[str, object] = dict(NO_EDIT_INPUTS)
        inputs[component_id["type"]] = [{"id": component_id, "property": prop, "value": value}]
        changed = [f"{pattern(component_id)}.{prop}"]
        responses = [
            fire(self.app, inputs, {"charts-store.data": self.charts}, changed),
            fire(self.app, inputs, self.states(), changed),
        ]
        for response in responses:
            self.apply(response)
        return {output for response in responses for output in response}

    def edit(self, field: str, chart: int, value: object) -> set[str]:
        """Set a card's title, type, width, series or Bus control; return the ids of the updated outputs."""
        return self.change({"type": "chart-field", "field": field, "chart": self.charts[chart]["id"]}, value)

    def colour(self, chart: int, series: str, value: str) -> set[str]:
        """Type a colour override for one series of a card; return the ids of the updated outputs."""
        return self.change({"type": "chart-colour", "chart": self.charts[chart]["id"], "series": series}, value)

    def reset_colour(self, chart: int, series: str, clicks: int | None = 1) -> set[str]:
        """Click the reset button of a series' colour override; return the ids of the updated outputs."""
        component_id = {"type": "chart-colour-reset", "chart": self.charts[chart]["id"], "series": series}
        return self.change(component_id, clicks, "n_clicks")

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


@pytest.mark.parametrize(
    "add",
    [
        lambda page: page.add("bhkw-electricity/flow"),
        lambda page: page.add_sankey(),
        lambda page: page.add_system("add-bus-balance", "gas"),
        lambda page: page.add_system("bus-balance", inspector_bus="gas"),
    ],
    ids=["add chart", "add Sankey", "add Bus balance", "inspector add Bus balance"],
)
def test_every_add_path_names_the_added_chart_to_scroll_to(page: Page, add: Callable[[Page], None]) -> None:
    page.add("wind-electricity/flow")

    add(page)

    assert page.added == page.charts[-1]["id"]


def test_result_selection_change_rerenders_stored_charts(page: Page) -> None:
    page.add("bhkw-electricity/flow")
    page.cards = []

    page.rerender()

    assert "bhkw-electricity · flow · adlershof" in json.dumps(page.cards, ensure_ascii=False)


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


def test_editing_a_card_updates_only_that_card(page: Page) -> None:
    page.add("bhkw-electricity/flow")
    page.add("wind-electricity/flow")
    other = json.dumps(page.cards[1])

    updated = page.edit("width", 0, "full") | page.edit(
        "series", 0, ["bhkw-electricity/flow", "battery_large-None/storage_content"]
    )

    assert "charts" not in updated  # the chart grid isn't re-rendered
    card = json.dumps(page.cards[0], ensure_ascii=False)
    assert "chart-card full" in card
    assert "battery_large-None · storage_content · adlershof" in card  # figure
    assert '"placeholder": "bhkw-electricity · flow, battery_large-None · storage_content"' in card
    assert json.dumps(page.cards[1]) == other


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


def test_colour_override_is_set_and_reset(page: Page) -> None:
    page.add("bhkw-electricity/flow")

    page.colour(0, "bhkw-electricity/flow", "#123456")
    assert page.charts[0]["colours"] == {"bhkw-electricity/flow": "#123456"}

    page.reset_colour(0, "bhkw-electricity/flow")
    assert page.charts[0]["colours"] == {}


def test_colour_field_is_a_native_colour_input_showing_the_effective_colour(page: Page) -> None:
    page.add("bhkw-electricity/flow", "wind-electricity/flow")
    page.colour(0, "wind-electricity/flow", "#123456")

    def field(series: str) -> dict:
        return props_of(page.cards, {"type": "chart-colour", "chart": page.charts[0]["id"], "series": series})

    bhkw = field("bhkw-electricity/flow")
    assert bhkw["type"] == "color"
    assert bhkw["value"] == PALETTE[0]
    assert field("wind-electricity/flow")["value"] == "#123456"


def test_picking_the_palette_colour_clears_the_override(page: Page) -> None:
    page.add("bhkw-electricity/flow")
    page.colour(0, "bhkw-electricity/flow", "#123456")

    page.colour(0, "bhkw-electricity/flow", PALETTE[0])

    assert page.charts[0]["colours"] == {}


def test_rendered_reset_button_resets_nothing(page: Page) -> None:
    page.add("bhkw-electricity/flow")
    page.colour(0, "bhkw-electricity/flow", "#123456")

    # The card update renders the reset button, which fires the edit callbacks unclicked.
    assert page.reset_colour(0, "bhkw-electricity/flow", clicks=None) == set()


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


def test_removing_the_last_card_raises_no_error(page: Page) -> None:
    page.add("bhkw-electricity/flow")
    page.click("remove", 0)

    # The removed card's controls were the last ones matching the edit callback's inputs.
    response = fire(
        page.app,
        NO_EDIT_INPUTS,
        {"charts-store.data": page.charts},
        changed=[],
    )

    assert response == {}


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
        NO_EDIT_INPUTS | {"chart-field": fields},
        page.states(),
        changed=[f"{pattern(field['id'])}.value" for field in fields],
    )

    assert response == {}


def test_rerendered_colour_field_updates_nothing(page: Page) -> None:
    page.add("bhkw-electricity/flow")

    # A card update re-renders its colour fields, which fire the edit callbacks with their unchanged values.
    assert page.colour(0, "bhkw-electricity/flow", PALETTE[0]) == set()


def test_dropping_a_series_drops_its_colour_override(page: Page) -> None:
    page.add("bhkw-electricity/flow", "wind-electricity/flow")
    page.colour(0, "bhkw-electricity/flow", "#123456")
    page.colour(0, "wind-electricity/flow", "#abcdef")

    page.edit("series", 0, ["wind-electricity/flow"])

    assert page.charts[0]["colours"] == {"wind-electricity/flow": "#abcdef"}


def edges(elements: list[dict]) -> dict[tuple[str, str], dict]:
    """Graph edges by (source, target)."""
    return {(edge["data"]["source"], edge["data"]["target"]): edge for edge in elements if "source" in edge["data"]}


def test_graph_draws_flows_of_result_as_arrows_with_sum(shipped_data: Path) -> None:
    package = datapackage.read(shipped_data / "datapackages" / "adlershof")

    drawn = edges(graph_elements(package, read(shipped_data / "results" / "adlershof")))

    absorption = drawn[("cool_process-absorption", "cool_process")]
    assert absorption["classes"] == "flow"
    assert absorption["data"]["label"] == "Σ 88,661"
    assert drawn[("electricity", "cool_process-absorption")]["classes"] == "flow"


def test_graph_without_result_draws_connections_undirected(shipped_data: Path) -> None:
    package = package_of(["el"], [("pv", "el")])

    assert edges(graph_elements(package, None)) == {("pv", "el"): {"data": {"source": "pv", "target": "el"}}}


def test_graph_sums_flow_dropping_trailing_nan_and_marks_flows_not_in_datapackage() -> None:
    package = package_of(["el", "heat"], [("pv", "el"), ("boiler", "heat")])
    result = result_of("pv-el", "pv-heat")
    index = pd.date_range("2050-01-01", periods=3, freq="h")
    result.entries["pv-el"].sequences = pd.DataFrame({"flow": [1.5, 2.0, math.nan]}, index=index)

    drawn = edges(graph_elements(package, result))

    assert drawn[("pv", "el")]["data"]["label"] == "Σ 4"
    assert drawn[("pv", "heat")]["classes"] == "flow foreign"
    assert drawn[("pv", "heat")]["data"]["label"] == "not in Datapackage"
    assert drawn[("boiler", "heat")] == {"data": {"source": "boiler", "target": "heat"}}  # no Flow in Result


def test_graph_callback_draws_flows_of_first_result(adlershof_app: Dash) -> None:
    elements = fire(adlershof_app, {"datapackage.value": "adlershof", "result-selection.value": ["adlershof"]})

    drawn = edges(elements["graph"]["elements"])
    assert drawn[("cool_process-absorption", "cool_process")]["classes"] == "flow"


def graph_styles(app: Dash) -> dict[str, dict]:
    """Styles of the graph's stylesheet by selector."""
    return {rule["selector"]: rule["style"] for rule in components_by_id(app)["graph"]["stylesheet"]}


def test_graph_layout_is_deterministic_cose_bilkent(adlershof_app: Dash) -> None:
    layout = components_by_id(adlershof_app)["graph"]["layout"]

    assert layout["name"] == "cose-bilkent"
    assert layout["randomize"] is False


def test_graph_zoom_is_limited_and_has_fit_button(adlershof_app: Dash) -> None:
    components = components_by_id(adlershof_app)
    graph = components["graph"]

    assert graph["minZoom"] == pytest.approx(0.2)
    assert graph["maxZoom"] == pytest.approx(3)
    assert graph["wheelSensitivity"] < 1
    assert components["graph-fit"]["children"] == "Fit"


def test_graph_buses_stand_out_and_component_labels_hide_when_zoomed_out(adlershof_app: Dash) -> None:
    styles = graph_styles(adlershof_app)

    assert styles[".bus"]["font-weight"] == "bold"
    assert styles[".bus"]["width"] > styles["node"]["width"]
    assert styles[".bus"]["shape"] != styles["node"].get("shape", "ellipse")
    assert styles[".component"]["min-zoomed-font-size"] > 0
    assert "min-zoomed-font-size" not in styles[".bus"]


def test_graph_shows_flow_sums_only_on_edges_of_selected_node(adlershof_app: Dash) -> None:
    styles = graph_styles(adlershof_app)

    assert "label" not in styles[".flow"]
    assert styles[".flow.connected"]["label"] == "data(label)"
    assert styles[".foreign"]["label"] == "data(label)"  # a warning, not a sum: always shown


def test_graph_highlights_selected_node_neighbours_and_edges_without_fading(adlershof_app: Dash) -> None:
    styles = graph_styles(adlershof_app)

    selected = styles["node:selected"]
    neighbour = styles[".neighbour"]
    assert selected["border-width"] > neighbour["border-width"] > 0
    assert selected["border-color"] == neighbour["border-color"]
    assert selected["width"] > styles["node"]["width"]
    assert styles[".connected"]["width"] > styles["edge"]["width"]
    assert not any("opacity" in style for style in styles.values())


def rendered(children: list) -> str:
    """Dash children as the JSON sent to the browser."""
    return json.dumps(children, cls=PlotlyJSONEncoder, ensure_ascii=False)


@pytest.fixture
def two_results() -> tuple[datapackage.Datapackage, dict[str, Result]]:
    """pv and wind feeding Bus el; Result r1 has pv-el (flow sequence, invest scalar), r2 has wind-el only."""
    package = package_of(["el"], [("pv", "el"), ("wind", "el")])
    first, second = result_of("pv-el"), result_of("wind-el")
    index = pd.date_range("2050-01-01", periods=2, freq="h")
    first.entries["pv-el"].sequences = pd.DataFrame({"flow": [1.0, 2.0]}, index=index)
    first.entries["pv-el"].scalars = {"invest": 3.0}
    second.entries["wind-el"].sequences = pd.DataFrame({"flow": [1.0, 2.0]}, index=index)
    return package, {"r1": first, "r2": second}


def test_inspector_lists_outcomes_per_entry_and_variable_with_add_chart(two_results: tuple) -> None:
    package, results = two_results

    text = rendered(inspector(package, "pv", results, "dp"))

    assert "pv-el · flow" in text
    assert "pv-el · invest" in text
    outcomes = inspector(package, "pv", results, "dp")[-2]
    assert {len(row.children) for row in outcomes.children} == {2}  # name and "+ chart", no "in n/m Results"
    assert json.dumps({"type": "outcome-chart", "outcome": "pv-el/flow"}) in text
    assert json.dumps({"type": "outcome-chart", "outcome": "pv-el/invest"}) in text


def test_inspector_shows_results_without_outcomes_for_node(two_results: tuple) -> None:
    package, results = two_results

    text = rendered(inspector(package, "wind", results, "dp"))

    assert "r1: no Outcomes in this Result" in text
    assert "r2: no Outcomes" not in text


def test_inspector_shows_dash_for_empty_sections(two_results: tuple) -> None:
    package, _ = two_results

    children = inspector(package, "pv", {}, "dp")

    labels = [index for index, child in enumerate(children) if isinstance(child, html.Label)]
    sections = {children[index].children: children[index + 1] for index in labels}
    assert sections["Parameters"] == "–"
    assert sections["Input Sequences"] == "–"


@pytest.mark.parametrize(
    ("value", "shown", "tooltip"),
    [
        (123456.789, "123500", "123456.789"),
        (0.123456, "0.1235", "0.123456"),
        (1.0, "1", "1.0"),
        (1e-10, "1e-10", "1e-10"),
        (1e300, "1e+300", "1e+300"),
        ("{}", "–", None),
        ("text", "text", None),
    ],
)
def test_inspector_rounds_numeric_parameters_with_full_value_as_tooltip(
    two_results: tuple, value: float | str, shown: str, tooltip: str | None
) -> None:
    package, _ = two_results
    package.components["pv"].parameters["capacity"] = value

    children = inspector(package, "pv", {}, "dp")

    table = children[[getattr(child, "children", None) for child in children].index("Parameters") + 1]
    (row,) = table.children
    cell = row.children[1]
    assert cell.children == shown
    assert getattr(cell, "title", None) == tooltip


def inspect_inputs(datapackage_name: str | None, selected: str | None = None) -> dict[str, object]:
    """Inspector callback inputs before the Result Selection: the node selected in the graph, if any, and a
    Datapackage."""
    return {
        "graph.selectedNodeData": [{"id": selected}] if selected else None,
        "datapackage.value": datapackage_name,
    }


def test_inspector_summary_lists_unmatched_and_warns_on_low_match_ratio(shipped_data: Path, tmp_path: Path) -> None:
    (tmp_path / "mixed").mkdir()
    for entry in ("bhkw-electricity", "foo-bar", "baz"):
        (tmp_path / "mixed" / f"{entry}-scalars.csv").write_text("variable_name;2050-01-01\ninvest;1.0\n")
    app = create_app(shipped_data / "datapackages", tmp_path)

    inputs = inspect_inputs("adlershof") | {"result-selection.value": ["mixed"]}
    text = rendered(fire(app, inputs, changed=["result-selection.value"])["inspector"]["children"])

    assert "Datapackage likely doesn't belong to this Result" in text
    assert "mixed: 2 unmatched" in text
    assert "foo-bar: no split into two Datapackage names" in text


def test_inspector_summary_without_banner_when_result_matches(adlershof_app: Dash) -> None:
    inputs = inspect_inputs("adlershof") | {"result-selection.value": ["adlershof"]}
    text = rendered(fire(adlershof_app, inputs, changed=["result-selection.value"])["inspector"]["children"])

    assert "doesn't belong" not in text
    assert "adlershof: 0 unmatched" in text


def test_tapping_node_shows_its_outcomes(adlershof_app: Dash) -> None:
    inputs = inspect_inputs("adlershof", selected="bhkw") | {"result-selection.value": ["adlershof"]}
    text = rendered(fire(adlershof_app, inputs, changed=["graph.selectedNodeData"])["inspector"]["children"])

    assert "bhkw-electricity · flow" in text


@pytest.mark.parametrize(
    ("node", "offered", "not_offered"),
    [("bhkw", BHKW_EFFICIENCY, "input:adlershof/bhkw/expandable"), ("wind", WIND_PROFILE, None)],
)
def test_inspector_offers_add_chart_for_numeric_parameters_and_input_sequences(
    adlershof_app: Dash, node: str, offered: str, not_offered: str | None
) -> None:
    inputs = inspect_inputs("adlershof", selected=node) | {"result-selection.value": ["adlershof"]}
    text = rendered(fire(adlershof_app, inputs, changed=["graph.selectedNodeData"])["inspector"]["children"])

    assert json.dumps({"type": "outcome-chart", "outcome": offered}) in text
    assert not_offered is None or not_offered not in text


@pytest.mark.parametrize(
    ("selected", "wind_listed"), [([{"id": "bhkw"}], False), ([], True), (None, True), ([{"id": "gone"}], True)]
)
def test_selected_graph_node_prefilters_outcome_picker(
    adlershof_app: Dash, selected: list | None, wind_listed: bool
) -> None:
    inputs = {
        "result-selection.value": ["adlershof"],
        "datapackage.value": "adlershof",
        "graph.selectedNodeData": selected,
    }

    values = [option["value"] for option in fire(adlershof_app, inputs)["outcome-picker"]["options"]]

    assert {"bhkw-electricity/flow", "gas-bhkw/flow"} <= set(values)
    assert ("wind-electricity/flow" in values) is wind_listed


@pytest.mark.parametrize(
    ("selected", "chip"), [([{"id": "wind"}], "Only wind"), ([], None), (None, None), ([{"id": "gone"}], None)]
)
def test_filter_chip_names_selected_node_above_outcome_picker(
    adlershof_app: Dash, selected: list | None, chip: str | None
) -> None:
    inputs = {"graph.selectedNodeData": selected, "datapackage.value": "adlershof"}

    response = fire(adlershof_app, inputs)

    assert response["outcome-filter"]["hidden"] is (chip is None)
    assert chip is None or response["outcome-filter-node"]["children"] == chip


def test_filter_chip_has_clear_button_and_starts_hidden(adlershof_app: Dash) -> None:
    components = components_by_id(adlershof_app)

    assert components["outcome-filter"]["hidden"] is True
    assert components["outcome-filter-clear"]["children"] == "×"


def test_add_chart_button_in_inspector_adds_line_chart(page: Page) -> None:
    button = {"type": "outcome-chart", "outcome": "bhkw-electricity/flow"}
    inputs = {"add-chart.n_clicks": None, "outcome-chart": [{"id": button, "property": "n_clicks", "value": 1}]}

    page.apply(fire(page.app, inputs, {"outcome-picker.value": None, **page.states()}, [f"{pattern(button)}.n_clicks"]))

    assert page.series() == [[["bhkw-electricity", "flow"]]]


def test_rendering_add_chart_buttons_adds_no_chart(page: Page) -> None:
    button = {"type": "outcome-chart", "outcome": "bhkw-electricity/flow"}
    inputs = {"add-chart.n_clicks": None, "outcome-chart": [{"id": button, "property": "n_clicks", "value": None}]}

    response = fire(page.app, inputs, {"outcome-picker.value": None, **page.states()}, [f"{pattern(button)}.n_clicks"])

    assert response == {}


def test_chart_card_shows_chips_of_its_nodes(page: Page) -> None:
    page.add("bhkw-electricity/flow")

    chart_id = page.charts[0]["id"]
    text = rendered(page.cards)

    for node in ("bhkw", "electricity"):
        assert rendered({"type": "chart-chip", "chart": chart_id, "node": node}) in text


def test_inspector_keeps_selected_node_when_result_selection_changes(adlershof_app: Dash) -> None:
    inputs = inspect_inputs("adlershof", selected="bhkw") | {"result-selection.value": ["adlershof"]}

    text = rendered(fire(adlershof_app, inputs, changed=["result-selection.value"])["inspector"]["children"])

    assert "bhkw-electricity · flow" in text


@pytest.mark.parametrize("selected", [[], [{"id": "gone"}]])
def test_deselecting_in_graph_returns_inspector_to_overview(adlershof_app: Dash, selected: list) -> None:
    # Tapping empty space empties the selection; a node of another Datapackage counts as none.
    inputs = inspect_inputs("adlershof") | {"graph.selectedNodeData": selected, "result-selection.value": ["adlershof"]}

    text = rendered(fire(adlershof_app, inputs, changed=["graph.selectedNodeData"])["inspector"]["children"])

    assert "adlershof: 85 Result Entries" in text


@pytest.mark.parametrize(
    ("name", "selected", "wind_listed"),
    [
        ("adlershof", None, True),
        ("adlershof", [{"id": "wind"}], True),
        ("adlershof", [{"id": "bhkw"}], False),
        (None, None, False),
    ],
)
def test_outcome_picker_offers_input_sequences_of_datapackage_and_selected_nodes(
    adlershof_app: Dash, name: str | None, selected: list | None, wind_listed: bool
) -> None:
    inputs = {"result-selection.value": ["adlershof"], "datapackage.value": name, "graph.selectedNodeData": selected}

    options = fire(adlershof_app, inputs)["outcome-picker"]["options"]

    by_value = {option["value"]: option["label"] for option in options}
    assert (WIND_PROFILE in by_value) is wind_listed
    if wind_listed:
        assert by_value[WIND_PROFILE] == "adlershof · volatile_profile · wind-profile"


def test_input_sequence_is_added_and_drawn_next_to_result_sequences(page: Page) -> None:
    page.add("bhkw-electricity/flow", WIND_PROFILE)

    assert page.series() == [[["bhkw-electricity", "flow"], ["adlershof", "volatile_profile", "wind-profile"]]]
    card = json.dumps(page.cards, ensure_ascii=False)
    assert '"name": "adlershof · volatile_profile · wind-profile"' in card
    assert "(missing)" not in card
    assert WIND_PROFILE in card  # offered and picked in the series multi-select


@pytest.mark.parametrize("other", [None, "copy"])
def test_input_sequence_of_another_datapackage_is_missing(
    shipped_data: Path, tmp_path: Path, other: str | None
) -> None:
    (tmp_path / "datapackages").mkdir()
    for name in ("adlershof", "copy"):  # same content, different Datapackage
        (tmp_path / "datapackages" / name).symlink_to(shipped_data / "datapackages" / "adlershof")
    page = Page(create_app(tmp_path / "datapackages", shipped_data / "results"))
    page.add(WIND_PROFILE)

    page.datapackage = other
    page.rerender()

    assert "adlershof · volatile_profile · wind-profile (missing)" in json.dumps(page.cards, ensure_ascii=False)


@pytest.mark.parametrize("chart_type", ["stacked_area", "duration_curve"])
def test_type_switches_within_sequence_kind_keeping_series(page: Page, chart_type: str) -> None:
    page.add("bhkw-electricity/flow", WIND_PROFILE)

    page.edit("type", 0, chart_type)

    assert page.charts[0]["type"] == chart_type
    assert len(page.series()[0]) == 2
    card = json.dumps(page.cards, ensure_ascii=False)
    assert all(option in card for option in ('"line"', '"stacked_area"', '"duration_curve"'))


@pytest.mark.parametrize(
    ("button", "picked", "options"),
    [
        (
            "add-chart",
            "bhkw-electricity/flow",
            {"line": "Line", "stacked_area": "Stacked area", "duration_curve": "Duration curve"},
        ),
        ("add-chart", "bhkw-electricity/invest", {"bar": "Bar"}),
        ("add-sankey", None, {"sankey": "Sankey"}),
        ("add-bus-balance", "gas", {"bus_balance": "Bus balance"}),  # can't switch to Sankey
    ],
)
def test_type_dropdown_shows_readable_type_names(
    page: Page, button: str, picked: str | None, options: dict[str, str]
) -> None:
    if button == "add-chart":
        page.add(picked)
    else:
        page.add_system(button, picked)

    dropdown = props_of(page.cards, {"type": "chart-field", "field": "type", "chart": page.charts[0]["id"]})

    assert dropdown["options"] == options


def test_outcome_picker_offers_result_scalars(adlershof_app: Dash) -> None:
    inputs = {"result-selection.value": ["adlershof"], "datapackage.value": None, "graph.selectedNodeData": None}

    options = fire(adlershof_app, inputs)["outcome-picker"]["options"]

    assert {"label": "bhkw-electricity · invest", "value": "bhkw-electricity/invest"} in options


@pytest.mark.parametrize(
    ("selected", "bhkw_listed"), [(None, True), ([{"id": "bhkw"}], True), ([{"id": "wind"}], False)]
)
def test_outcome_picker_offers_numeric_input_scalars_of_datapackage_and_selected_nodes(
    adlershof_app: Dash, selected: list | None, bhkw_listed: bool
) -> None:
    inputs = {
        "result-selection.value": ["adlershof"],
        "datapackage.value": "adlershof",
        "graph.selectedNodeData": selected,
    }

    options = fire(adlershof_app, inputs)["outcome-picker"]["options"]

    by_value = {option["value"]: option["label"] for option in options}
    assert (by_value.get(BHKW_EFFICIENCY) == "adlershof · bhkw · electric_efficiency") is bhkw_listed
    assert "input:adlershof/bhkw/expandable" not in by_value  # text Parameter


def test_input_scalars_are_finite_numeric_parameters_of_components() -> None:
    package = package_of(["el"], [("pv", "el")])
    package.buses["el"].parameters = {"balanced": 1.0}
    package.components["pv"].parameters = {
        "capacity": 5.0,
        "potential": float("inf"),
        "cost": float("nan"),
        "tech": "pv",
    }

    assert input_scalar_items("dp", package) == {("dp", "pv", "capacity")}


def test_added_scalar_outcome_is_a_bar_chart_offering_result_scalars_only(page: Page) -> None:
    page.add("bhkw-electricity/invest")

    (chart,) = page.charts
    assert (chart["kind"], chart["type"], chart["series"]) == ("scalars", "bar", [["bhkw-electricity", "invest"]])
    card = json.dumps(page.cards, ensure_ascii=False)
    assert '"type": "bar"' in card
    assert "bhkw-electricity/total" in card  # another Result Scalar offered
    assert "bhkw-electricity/flow" not in card  # a Result Sequence
    assert WIND_PROFILE not in card  # an Input Sequence


def test_mixed_pick_adds_one_chart_per_kind(page: Page) -> None:
    page.add("bhkw-electricity/invest", "bhkw-electricity/flow", WIND_PROFILE, "bhkw-electricity/total")

    assert [(chart["kind"], chart["series"]) for chart in page.charts] == [
        ("sequences", [["bhkw-electricity", "flow"], ["adlershof", "volatile_profile", "wind-profile"]]),
        ("scalars", [["bhkw-electricity", "invest"], ["bhkw-electricity", "total"]]),
    ]
    assert len(page.cards) == 2


def test_input_scalar_is_added_to_a_bar_chart_and_drawn_next_to_result_scalars(page: Page) -> None:
    page.add("bhkw-electricity/invest", BHKW_EFFICIENCY, WIND_PROFILE)

    assert [(chart["kind"], chart["series"]) for chart in page.charts] == [
        ("sequences", [["adlershof", "volatile_profile", "wind-profile"]]),
        ("scalars", [["bhkw-electricity", "invest"], ["adlershof", "bhkw", "electric_efficiency"]]),
    ]
    card = json.dumps(page.cards[1], ensure_ascii=False)
    assert '"name": "adlershof · bhkw · electric_efficiency"' in card
    assert "0.38" in card
    assert "(missing)" not in card
    assert "input:adlershof/bhkw/capacity_cost" in card  # another Input Scalar offered
    assert WIND_PROFILE not in card  # an Input Sequence


@pytest.mark.parametrize("other", [None, "copy"])
def test_input_scalar_of_another_datapackage_is_missing(shipped_data: Path, tmp_path: Path, other: str | None) -> None:
    (tmp_path / "datapackages").mkdir()
    for name in ("adlershof", "copy"):  # same content, different Datapackage
        (tmp_path / "datapackages" / name).symlink_to(shipped_data / "datapackages" / "adlershof")
    page = Page(create_app(tmp_path / "datapackages", shipped_data / "results"))
    page.add(BHKW_EFFICIENCY)

    page.datapackage = other
    page.rerender()

    assert "adlershof · bhkw · electric_efficiency (missing)" in json.dumps(page.cards, ensure_ascii=False)


def test_inspector_add_chart_button_adds_bar_chart_for_scalar(page: Page) -> None:
    button = {"type": "outcome-chart", "outcome": "bhkw-electricity/invest"}
    inputs = {"add-chart.n_clicks": None, "outcome-chart": [{"id": button, "property": "n_clicks", "value": 1}]}

    page.apply(fire(page.app, inputs, {"outcome-picker.value": None, **page.states()}, [f"{pattern(button)}.n_clicks"]))

    assert [(chart["kind"], chart["type"]) for chart in page.charts] == [("scalars", "bar")]


@pytest.mark.parametrize(("name", "disabled"), [(None, True), ("adlershof", False)])
def test_add_sankey_needs_a_selected_datapackage(adlershof_app: Dash, name: str | None, disabled: bool) -> None:
    outputs = fire(adlershof_app, {"datapackage.value": name})

    assert outputs["add-sankey"]["disabled"] is disabled
    assert outputs["sankey-bus"]["disabled"] is disabled


@pytest.mark.parametrize(("name", "buses"), [(None, []), ("adlershof", ["electricity", "heat_central"])])
def test_sankey_bus_picker_offers_buses_of_the_datapackage(adlershof_app: Dash, name: str | None, buses: list) -> None:
    sankey_bus = fire(adlershof_app, {"datapackage.value": name})["sankey-bus"]

    assert sankey_bus["options"][:2] == buses
    assert sankey_bus["value"] is None  # a Bus of the previous Datapackage is dropped


def test_sankey_is_added_with_the_picked_bus(page: Page) -> None:
    page.add_sankey("gas")

    assert page.charts[0]["bus"] == "gas"
    assert "Sankey · gas" in json.dumps(page.cards, ensure_ascii=False)


def test_added_sankey_is_a_full_width_system_chart_offering_a_bus_filter_instead_of_series(page: Page) -> None:
    page.add_sankey()

    (chart,) = page.charts
    assert chart | {"id": None} == {
        "id": None,
        "kind": "system",
        "type": "sankey",
        "title": None,
        "series": [],
        "colours": {},
        "width": "full",
        "bus": None,
    }
    card = json.dumps(page.cards, ensure_ascii=False)
    assert '"type": "sankey"' in card
    assert '"field": "bus"' in card
    assert '"options": ["electricity", "heat_central"' in card  # Buses of the Datapackage
    assert '"field": "series"' not in card


def test_picking_a_bus_filters_the_sankey(page: Page) -> None:
    page.add_sankey()

    page.edit("bus", 0, "gas")

    assert page.charts[0]["bus"] == "gas"
    assert "Sankey · gas" in json.dumps(page.cards, ensure_ascii=False)


def test_sankey_without_datapackage_shows_notice(page: Page) -> None:
    page.add_sankey()

    page.datapackage = None
    page.rerender()

    assert "Sankey needs a selected Datapackage." in json.dumps(page.cards, ensure_ascii=False)


def test_inspector_of_a_bus_offers_add_bus_balance(two_results: tuple) -> None:
    package, results = two_results

    assert json.dumps({"type": "bus-balance", "bus": "el"}) in rendered(inspector(package, "el", results, "dp"))
    assert '"bus-balance"' not in rendered(inspector(package, "pv", results, "dp"))


def test_add_bus_balance_in_inspector_adds_a_bus_balance_of_that_bus(page: Page) -> None:
    page.add_system("bus-balance", inspector_bus="gas")

    (chart,) = page.charts
    assert (chart["kind"], chart["type"], chart["bus"], chart["width"]) == ("system", "bus_balance", "gas", "full")
    card = json.dumps(page.cards, ensure_ascii=False)
    assert "Bus balance · gas" in card


def test_rendering_add_bus_balance_buttons_adds_no_chart(page: Page) -> None:
    button = {"type": "bus-balance", "bus": "gas"}
    inputs = {
        "add-sankey.n_clicks": None,
        "add-bus-balance.n_clicks": None,
        "bus-balance": [{"id": button, "property": "n_clicks", "value": None}],
    }

    response = fire(page.app, inputs, {"sankey-bus.value": None, **page.states()}, [f"{pattern(button)}.n_clicks"])

    assert response == {}


@pytest.mark.parametrize(
    ("inputs", "states"),
    [
        (
            {"add-sankey.n_clicks": None, "add-bus-balance.n_clicks": None, "bus-balance": []},
            {"sankey-bus.value": None},
        ),
        ({"add-chart.n_clicks": None, "outcome-chart": []}, {"outcome-picker.value": ["bhkw-electricity/flow"]}),
    ],
)
def test_switching_the_inspector_away_from_add_buttons_adds_no_chart(page: Page, inputs: dict, states: dict) -> None:
    # E.g. clicking a Connection in a Bus's inspector replaces the inspector and its "Add Bus balance" button.
    response = fire(page.app, inputs, states | page.states(), changed=[])

    assert response == {}


def test_add_bus_balance_in_left_pane_adds_a_bus_balance_of_the_picked_bus(page: Page) -> None:
    page.add_system("add-bus-balance", "electricity")

    assert [(chart["type"], chart["bus"]) for chart in page.charts] == [("bus_balance", "electricity")]


@pytest.mark.parametrize(("bus", "disabled"), [(None, True), ("gas", False)])
def test_add_bus_balance_in_left_pane_needs_a_picked_bus(adlershof_app: Dash, bus: str | None, disabled: bool) -> None:
    assert fire(adlershof_app, {"sankey-bus.value": bus})["add-bus-balance"]["disabled"] is disabled


def upload(text: str) -> str:
    """`dcc.Upload` contents of a file with this text."""
    return "data:application/json;base64," + base64.b64encode(text.encode()).decode()


def save(page: Page) -> str:
    """Click "Save Dashboard" and return the downloaded file's text."""
    download = fire(page.app, {"save-dashboard.n_clicks": 1}, page.states())["dashboard-download"]["data"]
    assert download["filename"] == "dashboard.json"
    return download["content"]


def inputs_of(page: Page) -> dict[str, object]:
    """Result Selection and Datapackage of the page, as states."""
    return {key: value for key, value in page.states().items() if key != "charts-store.data"}


def load(page: Page, text: str) -> dict:
    """Upload a Dashboard file with this text; apply the response to the page and return it."""
    response = fire(page.app, {"dashboard-upload.contents": upload(text)}, inputs_of(page))
    page.apply(response)
    return response


def test_saved_dashboard_holds_charts_result_selection_and_datapackage(page: Page) -> None:
    page.add("bhkw-electricity/flow")

    stored = json.loads(save(page))

    assert (stored["version"], stored["result_selection"], stored["datapackage"]) == (1, ["adlershof"], "adlershof")
    assert [chart["series"] for chart in stored["charts"]] == [[["bhkw-electricity", "flow"]]]


def test_loading_replaces_the_charts(page: Page) -> None:
    page.add("bhkw-electricity/flow")
    page.add_system("add-bus-balance", "gas")
    saved = save(page)
    page.click("remove", 0)
    page.add_sankey()

    load(page, saved)

    assert [(chart["type"], chart.get("bus")) for chart in page.charts] == [("line", None), ("bus_balance", "gas")]
    assert len(page.cards) == 2
    assert "Bus balance · gas" in json.dumps(page.cards, ensure_ascii=False)


def test_loading_applies_stored_inputs_and_notices_missing_ones(page: Page) -> None:
    text = json.dumps(
        {
            "version": 1,
            "result_selection": ["adlershof", "gone"],
            "datapackage": "elsewhere",
            "charts": [
                {
                    "kind": "sequences",
                    "type": "line",
                    "title": None,
                    "series": [["nope", "flow"]],
                    "colours": {},
                    "width": "half",
                }
            ],
        }
    )

    response = load(page, text)

    assert response["result-selection"]["value"] == ["adlershof"]
    assert "datapackage" not in response  # stored one missing: the current one stays
    notice = json.dumps(response["dashboard-notice"]["children"])
    assert "Result gone" in notice and "Datapackage elsewhere" in notice
    assert "nope · flow · adlershof (missing)" in json.dumps(page.cards, ensure_ascii=False)


def test_loading_without_stored_inputs_keeps_the_current_ones(page: Page) -> None:
    response = load(page, '{"version": 1, "charts": []}')

    assert "result-selection" not in response and "datapackage" not in response
    assert page.charts == [] and response["dashboard-notice"]["children"] == []


@pytest.mark.parametrize("text", ["{not json", '{"version": 2, "charts": []}', '{"version": 1}'])
def test_bad_dashboard_file_is_refused_with_banner_and_charts_untouched(page: Page, text: str) -> None:
    page.add("bhkw-electricity/flow")

    response = fire(page.app, {"dashboard-upload.contents": upload(text)}, inputs_of(page))

    assert response.keys() == {"dashboard-notice", "dashboard-upload"}
    (banner,) = response["dashboard-notice"]["children"]
    assert banner["props"]["className"] == "warning"
    assert banner["props"]["children"].startswith("Dashboard file refused: ")


def test_upload_is_cleared_so_the_same_file_can_be_loaded_again(page: Page) -> None:
    response = load(page, '{"version": 1, "charts": []}')

    assert response["dashboard-upload"]["contents"] is None
    assert fire(page.app, {"dashboard-upload.contents": None}, inputs_of(page)) == {}
