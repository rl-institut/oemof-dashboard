"""Pure reader turning an oemof-tabular Datapackage folder into Buses, Components and Connections."""

import csv
import functools
import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

DEFAULT_DELIMITER = ";"  # oemof-tabular writes `;` without declaring a dialect
# Decoding and pandas parser errors are ValueErrors; KeyError covers a resource without `path`.
RESOURCE_ERRORS = (OSError, ValueError, KeyError, csv.Error)


@dataclass(frozen=True)
class Refused:
    """Refused input: a Datapackage or Result that can't be used at all."""

    reason: str


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
        rows = list(csv.DictReader(file, delimiter=_delimiter(resource)))
    for line, row in enumerate(rows, start=2):
        if None in row:  # DictReader files surplus cells under None
            raise csv.Error(f"line {line} has more cells than the header")
    return rows


def _skipped(name: str, error: Exception) -> str:
    """Input Warning for a resource whose CSV can't be read."""
    reason = "missing" if isinstance(error, FileNotFoundError) else f"unparseable ({error})"
    return f"{name}: resource CSV {reason}, skipped"


def _read_header(folder: Path, resource: dict) -> list[str]:
    with (folder / resource["path"]).open(newline="") as file:
        return next(csv.reader(file, delimiter=_delimiter(resource)), [])


def to_numbers(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Convert a frame read from CSV to numbers.

    Args:
        frame: Values as read; empty cells and pandas' NA markers (`n/a`, `NaN`, …) are gaps already.

    Returns:
        The frame with non-numeric values as NaN, and how many values that turned into gaps.
    """
    converted = frame.apply(pd.to_numeric, errors="coerce")
    return converted, int((converted.isna() & frame.notna()).to_numpy().sum())


def _key_fields(foreign_key: dict) -> list[str]:
    fields = foreign_key["fields"]
    return [fields] if isinstance(fields, str) else fields


def _scalar(value: str) -> float | str:
    try:
        return float(value)
    except ValueError:
        return value


def read(folder: Path) -> Datapackage | Refused:
    """Read a Datapackage folder.

    Element resources are those whose schema has a `name` field; rows with `type == "bus"` become Buses,
    all other rows Components. A `foreignKeys` entry referencing a resource that holds Buses gives
    Connections (skipped with a warning if the Bus doesn't exist), and its fields are not Parameters; without
    any, Components stay unconnected and a warning is recorded. A `foreignKeys` entry referencing any other
    non-element resource turns the cell into an InputSequence (resource, column). Empty cells give no
    Parameter; other non-numeric values stay text.

    A resource whose CSV is missing or unparseable is skipped with a warning (references into it are broken),
    as is a row without `name`; a row without `type` is kept as type "unknown" with a warning. Non-numeric
    Input Sequence values give one warning per resource with their count.

    Skipped items become Input Warnings; they and a refusal are logged once per parse, i.e. until a file
    in the folder changes.

    Args:
        folder: Folder holding `datapackage.json`.

    Returns:
        The Datapackage's energy system, or Refused if `datapackage.json` is missing or invalid, names are
        duplicated or no element row is usable.
    """
    files = sorted(file for file in folder.rglob("*") if file.is_file())
    return _read(folder, tuple((str(file.relative_to(folder)), file.stat().st_mtime_ns) for file in files))


@functools.lru_cache(maxsize=32)
def _read(folder: Path, stamps: tuple[tuple[str, int], ...]) -> Datapackage | Refused:
    # `stamps` (file, mtime) only keys the cache: any added, removed or edited file forces a re-parse.
    try:
        package = _parse(folder)
    except (KeyError, TypeError, AttributeError) as error:  # descriptor not shaped like a Datapackage
        package = Refused(f"datapackage.json invalid: {error!r}")
    if isinstance(package, Refused):
        log.warning("Datapackage %s refused: %s", folder, package.reason)
        return package
    for warning in package.warnings:
        log.warning("Datapackage %s: %s", folder, warning)
    return package


def _parse(folder: Path) -> Datapackage | Refused:
    try:
        with (folder / "datapackage.json").open() as file:
            resources = json.load(file)["resources"]
    except (OSError, ValueError, KeyError, TypeError) as error:  # JSON and decoding errors are ValueErrors
        return Refused(f"datapackage.json missing or invalid: {error}")
    package = Datapackage()
    elements: dict[str, tuple[dict, list[dict[str, str]]]] = {}
    unread: set[str] = set()
    for resource in resources:
        if not any(column["name"] == "name" for column in resource.get("schema", {}).get("fields", [])):
            continue
        rows = []
        try:
            csv_rows = _read_rows(folder, resource)
        except RESOURCE_ERRORS as error:
            package.warnings.append(_skipped(resource["name"], error))
            unread.add(resource["name"])
            csv_rows = []
        for line, row in enumerate(csv_rows, start=2):  # line 1 is the header
            if not row.get("name"):
                package.warnings.append(f"{resource['name']} line {line}: row without name skipped")
                continue
            if not row.get("type"):
                package.warnings.append(f"{resource['name']} line {line}: {row['name']} has no type, kept as unknown")
                row["type"] = "unknown"
            rows.append(row)
        elements[resource["name"]] = (resource, rows)
    names = Counter(row["name"] for _, rows in elements.values() for row in rows)
    if duplicates := sorted(name for name, count in names.items() if count > 1):
        return Refused(f"duplicate names: {', '.join(duplicates)}")
    if not names:
        return Refused("; ".join(["no usable element row", *package.warnings]))
    sequence_columns: dict[str, list[str]] = {}
    for resource in resources:
        if resource["name"] in elements:
            continue
        try:
            frame = pd.read_csv(folder / resource["path"], sep=_delimiter(resource), index_col=0)
        except RESOURCE_ERRORS as error:
            package.warnings.append(_skipped(resource["name"], error))
            continue
        sequence_columns[resource["name"]] = list(frame.columns)
        _, dropped = to_numbers(frame)
        if dropped:
            package.warnings.append(f"{resource['name']}: {dropped} non-numeric values read as gaps")
    bus_names = {row["name"]: name for name, (_, rows) in elements.items() for row in rows if row["type"] == "bus"}
    bus_resources = set(bus_names.values())

    has_bus_keys = False
    for name, (resource, rows) in elements.items():
        bus_fields: list[str] = []
        unread_fields: list[str] = []  # into element resources skipped above, e.g. a missing bus resource
        sequence_fields: dict[str, str] = {}
        for foreign_key in resource["schema"].get("foreignKeys", []):
            referenced = foreign_key["reference"]["resource"]
            if referenced in bus_resources:
                bus_fields.extend(_key_fields(foreign_key))
            elif referenced in unread:
                unread_fields.extend(_key_fields(foreign_key))
            elif referenced not in elements:
                sequence_fields.update(dict.fromkeys(_key_fields(foreign_key), referenced))
        has_bus_keys = has_bus_keys or bool(bus_fields)

        for row in rows:
            parameters: dict[str, float | str | InputSequence] = {}
            for column, value in row.items():
                if not value or column in bus_fields or column in unread_fields or column in ("name", "type"):
                    continue
                if column in sequence_fields:
                    sequence = sequence_fields[column]
                    broken = value not in sequence_columns.get(sequence, [])
                    parameters[column] = InputSequence(resource=sequence, column=value, broken=broken)
                else:
                    parameters[column] = _scalar(value)
            node = Node(name=row["name"], type=row["type"], resource=name, parameters=parameters)
            (package.buses if node.type == "bus" else package.components)[node.name] = node
            for bus in filter(None, (row.get(bus_field) for bus_field in bus_fields)):
                if bus in bus_names:
                    package.connections.append((node.name, bus))
                else:
                    package.warnings.append(f"Connection from {node.name} to unknown Bus {bus} skipped")

    if package.components and not has_bus_keys:
        package.warnings.append("No foreignKeys reference a Bus resource; Components are shown unconnected")
    return package


def input_sequence(folder: Path, resource: str, column: str) -> pd.Series | None:
    """Read the values of one Input Sequence.

    Args:
        folder: Folder holding `datapackage.json`.
        resource: Name of the sequence resource.
        column: Column of that resource.

    Returns:
        Values on the resource's datetime index, non-numeric values as NaN; None if the resource or column is missing.
    """
    # ponytail: re-reads the column on every call; cache like `result.read` if chart rendering gets slow
    with (folder / "datapackage.json").open() as file:
        found = [item for item in json.load(file)["resources"] if item["name"] == resource]
    if not found:
        return None
    header = _read_header(folder, found[0])
    if column not in header[1:]:
        return None
    frame = pd.read_csv(
        folder / found[0]["path"], sep=_delimiter(found[0]), usecols=[header[0], column], index_col=0, parse_dates=True
    )
    return pd.to_numeric(frame[column], errors="coerce")
