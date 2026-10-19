"""Pure reader turning an oemof-tabular Datapackage folder into Buses, Components and Connections."""

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DELIMITER = ";"  # oemof-tabular writes `;` without declaring a dialect


@dataclass(frozen=True)
class InputSequence:
    """Reference from a Parameter to one column of a sequence resource; `broken` if that column is missing."""

    resource: str
    column: str
    broken: bool


@dataclass
class Node:
    """A Bus or Component: one element row of the Datapackage."""

    name: str
    type: str
    resource: str
    parameters: dict[str, float | str | InputSequence] = field(default_factory=dict)


@dataclass
class Datapackage:
    """Energy system of one Datapackage."""

    buses: dict[str, Node] = field(default_factory=dict)
    components: dict[str, Node] = field(default_factory=dict)
    connections: list[tuple[str, str]] = field(default_factory=list)  # (Component, Bus), undirected
    warnings: list[str] = field(default_factory=list)


def _delimiter(resource: dict) -> str:
    return resource.get("dialect", {}).get("delimiter", DEFAULT_DELIMITER)


def _read_rows(folder: Path, resource: dict) -> list[dict[str, str]]:
    with (folder / resource["path"]).open(newline="") as file:
        return list(csv.DictReader(file, delimiter=_delimiter(resource)))


def _read_header(folder: Path, resource: dict) -> set[str]:
    with (folder / resource["path"]).open(newline="") as file:
        return set(next(csv.reader(file, delimiter=_delimiter(resource)), []))


def _key_fields(foreign_key: dict) -> list[str]:
    fields = foreign_key["fields"]
    return [fields] if isinstance(fields, str) else fields


def _scalar(value: str) -> float | str:
    try:
        return float(value)
    except ValueError:
        return value


def read(folder: Path) -> Datapackage:
    """Read a Datapackage folder.

    Element resources are those whose schema has a `name` field; rows with `type == "bus"` become Buses,
    all other rows Components. A `foreignKeys` entry referencing a resource that holds Buses gives
    Connections (skipped with a warning if the Bus doesn't exist), and its fields are not Parameters; without any, Components stay unconnected and a warning
    is recorded. A `foreignKeys` entry referencing any other non-element resource turns the cell into an
    InputSequence (resource, column). Empty cells give no Parameter; other non-numeric values stay text.

    Args:
        folder: Folder holding `datapackage.json`.

    Returns:
        The Datapackage's energy system.
    """
    with (folder / "datapackage.json").open() as file:
        resources = json.load(file)["resources"]
    elements = {
        resource["name"]: (resource, _read_rows(folder, resource))
        for resource in resources
        if any(column["name"] == "name" for column in resource.get("schema", {}).get("fields", []))
    }
    sequence_columns = {
        resource["name"]: _read_header(folder, resource) for resource in resources if resource["name"] not in elements
    }
    bus_names = {row["name"]: name for name, (_, rows) in elements.items() for row in rows if row["type"] == "bus"}
    bus_resources = set(bus_names.values())

    package = Datapackage()
    has_bus_keys = False
    for name, (resource, rows) in elements.items():
        bus_fields: list[str] = []
        sequence_fields: dict[str, str] = {}
        for foreign_key in resource["schema"].get("foreignKeys", []):
            referenced = foreign_key["reference"]["resource"]
            if referenced in bus_resources:
                bus_fields.extend(_key_fields(foreign_key))
            elif referenced not in elements:
                sequence_fields.update(dict.fromkeys(_key_fields(foreign_key), referenced))
        has_bus_keys = has_bus_keys or bool(bus_fields)

        for row in rows:
            parameters: dict[str, float | str | InputSequence] = {}
            for column, value in row.items():
                if not value or column in bus_fields or column in ("name", "type"):
                    continue
                if column in sequence_fields:
                    sequence = sequence_fields[column]
                    broken = value not in sequence_columns.get(sequence, set())
                    parameters[column] = InputSequence(resource=sequence, column=value, broken=broken)
                else:
                    parameters[column] = _scalar(value)
            node = Node(name=row["name"], type=row["type"], resource=name, parameters=parameters)
            (package.buses if node.type == "bus" else package.components)[node.name] = node
            for bus in filter(None, (row[bus_field] for bus_field in bus_fields)):
                if bus in bus_names:
                    package.connections.append((node.name, bus))
                else:
                    package.warnings.append(f"Connection from {node.name} to unknown Bus {bus} skipped")

    if package.components and not has_bus_keys:
        package.warnings.append("No foreignKeys reference a Bus resource; Components are shown unconnected")
    return package
