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


def fire(app: Dash, output: str, inputs: dict[str, object], states: dict[str, object] | None = None) -> dict:
    """POST to the callback behind `output` (`id.prop`) as the browser would; return the new output props."""

    def props(values: dict[str, object]) -> list[dict]:
        return [
            {"id": key.split(".")[0], "property": key.split(".")[1], "value": value} for key, value in values.items()
        ]

    output_id, output_prop = output.split(".")
    payload = {
        "output": output,
        "outputs": {"id": output_id, "property": output_prop},
        "inputs": props(inputs),
        "state": props(states or {}),
        "changedPropIds": list(inputs),
    }
    response = app.server.test_client().post("/_dash-update-component", json=payload)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["response"][output_id]


def test_inspector_summary_lists_result_entries_without_datapackage(adlershof_app: Dash) -> None:
    inspector = fire(adlershof_app, "inspector.children", {"result-selection.value": ["adlershof"]})

    (summary,) = inspector["children"]
    heading, entries = summary["props"]["children"]
    assert heading["props"]["children"] == "adlershof: 85 Result Entries"
    assert {"props": {"children": "bhkw-electricity"}, "type": "Li", "namespace": "dash_html_components"} in entries[
        "props"
    ]["children"]


def test_added_chart_renders_for_result_selection(adlershof_app: Dash) -> None:
    charts = fire(
        adlershof_app,
        "charts-store.data",
        {"add-chart.n_clicks": 1},
        {"outcome-picker.value": ["bhkw-electricity/flow"], "charts-store.data": []},
    )["data"]
    assert charts == [[["bhkw-electricity", "flow"]]]

    cards = fire(
        adlershof_app, "charts.children", {"charts-store.data": charts, "result-selection.value": ["adlershof"]}
    )

    assert "bhkw-electricity · flow · adlershof" in json.dumps(cards, ensure_ascii=False)
