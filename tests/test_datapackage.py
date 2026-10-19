import json
import math
from pathlib import Path

import pandas as pd
import pytest

from oemof_dashboard import datapackage

ADLERSHOF_BUSES = {
    "electricity",
    "heat_central",
    "heat_decentral",
    "aquifer",
    "heat_lt_central",
    "gas",
    "cool_process",
    "cool_space",
}
BUS_CSV = "name;type\nel;bus\nheat;bus\n"


@pytest.fixture(scope="module")
def adlershof() -> datapackage.Datapackage:
    return datapackage.read(Path(__file__).parent / "test_data" / "datapackages" / "adlershof")


def test_bus_rows_become_buses_all_others_components(adlershof: datapackage.Datapackage) -> None:
    assert set(adlershof.buses) == ADLERSHOF_BUSES
    assert len(adlershof.components) == 58
    assert adlershof.components["bhkw"].type == "backpressure"
    assert adlershof.components["bhkw"].resource == "backpressures"
    assert adlershof.buses["gas"].resource == "bus"


def write_datapackage(folder: Path, resources: dict[str, tuple[str, list[dict]]]) -> Path:
    """Write a Datapackage with one `;`-separated CSV per resource.

    Args:
        folder: Datapackage folder to write into.
        resources: Resource name → (CSV text, foreignKeys).

    Returns:
        `folder`, for reading.
    """
    descriptors = []
    for name, (text, foreign_keys) in resources.items():
        (folder / f"{name}.csv").write_text(text)
        columns = text.splitlines()[0].split(";")
        schema = {"fields": [{"name": column} for column in columns], "foreignKeys": foreign_keys}
        descriptors.append({"name": name, "path": f"{name}.csv", "schema": schema})
    (folder / "datapackage.json").write_text(json.dumps({"resources": descriptors}))
    return folder


def bus_key(fields: str | list[str]) -> dict:
    """foreignKeys entry linking `fields` to the `bus` resource."""
    return {"fields": fields, "reference": {"resource": "bus", "fields": "name"}}


def test_connections_from_bus_foreign_keys(adlershof: datapackage.Datapackage) -> None:
    assert {bus for component, bus in adlershof.connections if component == "bhkw"} == {
        "gas",
        "electricity",
        "heat_central",
    }
    assert ("battery_small", "electricity") in adlershof.connections


def test_connections_from_foreign_key_with_field_list(tmp_path: Path) -> None:
    write_datapackage(
        tmp_path,
        {
            "bus": (BUS_CSV, []),
            "chp": ("name;type;el_bus;heat_bus\nchp1;chp;el;heat\n", [bus_key(["el_bus", "heat_bus"])]),
        },
    )

    assert set(datapackage.read(tmp_path).connections) == {("chp1", "el"), ("chp1", "heat")}


def test_parameters_numeric_or_text_without_bus_fields(adlershof: datapackage.Datapackage) -> None:
    parameters = adlershof.components["bhkw"].parameters

    assert parameters["electric_efficiency"] == 0.38
    assert parameters["expandable"] == "true"
    assert not {"name", "type", "fuel_bus", "electricity_bus", "heat_bus"} & parameters.keys()
    assert "carrier" not in parameters  # empty cell
    assert adlershof.components["battery_small"].parameters["input_parameters"] == "{}"


def test_without_bus_foreign_keys_components_unconnected_with_warning(tmp_path: Path) -> None:
    write_datapackage(tmp_path, {"bus": (BUS_CSV, []), "demand": ("name;type;bus\nload;load;el\n", [])})

    package = datapackage.read(tmp_path)

    assert set(package.components) == {"load"}
    assert package.connections == []
    assert len(package.warnings) == 1
    assert "foreignKeys" in package.warnings[0]


def test_adlershof_has_no_warnings(adlershof: datapackage.Datapackage) -> None:
    assert adlershof.warnings == []


def test_input_sequence_references_from_sequence_foreign_keys(adlershof: datapackage.Datapackage) -> None:
    assert adlershof.components["heatpump_mt"].parameters["efficiency"] == datapackage.InputSequence(
        resource="heatpumps_profile", column="heatpump_mt-efficiency", broken=False
    )
    assert adlershof.components["wind"].parameters["profile"] == datapackage.InputSequence(
        resource="volatile_profile", column="wind-profile", broken=False
    )
    assert "capacity_potential" not in adlershof.components["heatpump_aquifer"].parameters  # empty cell


def test_reference_to_missing_sequence_column_is_broken(tmp_path: Path) -> None:
    profile_key = {"fields": "profile", "reference": {"resource": "profiles", "fields": ""}}
    write_datapackage(
        tmp_path,
        {
            "bus": (BUS_CSV, []),
            "demand": ("name;type;bus;profile\nload;load;el;load-profil\n", [bus_key("bus"), profile_key]),
            "profiles": ("timeindex;load-profile\n2050-01-01 00:00:00;1.0\n", []),
        },
    )

    assert datapackage.read(tmp_path).components["load"].parameters["profile"] == datapackage.InputSequence(
        resource="profiles", column="load-profil", broken=True
    )


def test_connection_to_unknown_bus_skipped_with_warning(tmp_path: Path) -> None:
    write_datapackage(tmp_path, {"bus": (BUS_CSV, []), "demand": ("name;type;bus\nload;load;gas\n", [bus_key("bus")])})

    package = datapackage.read(tmp_path)

    assert package.connections == []
    assert len(package.warnings) == 1
    assert "gas" in package.warnings[0]


def test_input_sequence_values_on_real_timestamps() -> None:
    folder = Path(__file__).parent / "test_data" / "datapackages" / "adlershof"

    values = datapackage.input_sequence(folder, "volatile_profile", "wind-profile")

    assert len(values) == 8760
    assert values.index[0] == pd.Timestamp("2050-01-01 00:00")
    assert values.iloc[:2].tolist() == [0.0076691, 0.0484804]


def test_non_numeric_input_sequence_values_become_gaps(tmp_path: Path) -> None:
    write_datapackage(tmp_path, {"profiles": ("timeindex;load\n2050-01-01 00:00;1.5\n2050-01-01 01:00;n/a\n", [])})

    values = datapackage.input_sequence(tmp_path, "profiles", "load")

    assert values.iloc[0] == 1.5
    assert math.isnan(values.iloc[1])


@pytest.mark.parametrize(("resource", "column"), [("profiles", "gone"), ("gone", "load")])
def test_missing_input_sequence_is_none(tmp_path: Path, resource: str, column: str) -> None:
    write_datapackage(tmp_path, {"profiles": ("timeindex;load\n2050-01-01 00:00;1.5\n", [])})

    assert datapackage.input_sequence(tmp_path, resource, column) is None
