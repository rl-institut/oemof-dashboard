"""Pure Result reader: Result Entries with their Result Scalars and Result Sequences."""

import functools
import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from oemof_dashboard.datapackage import Refused, to_numbers

log = logging.getLogger(__name__)

KINDS = ("scalars", "sequences")


@dataclass
class ResultEntry:
    """Result Scalars by `variable_name` and Result Sequences by column, both as written."""

    scalars: dict[str, float] = field(default_factory=dict)
    sequences: pd.DataFrame = field(default_factory=pd.DataFrame)


@dataclass
class Result:
    """Result Entries by name, i.e. file name minus `-scalars.csv` / `-sequences.csv` (e.g. `bhkw-electricity`)."""

    entries: dict[str, ResultEntry]
    warnings: list[str] = field(default_factory=list)


def read(path: Path) -> Result | Refused:
    """Read a Result folder, re-using the last parse while no Result file changed.

    A file that can't be used is skipped with an Input Warning; files not named `<entry>-scalars.csv` /
    `<entry>-sequences.csv` are ignored with a log line. Warnings and a refusal are logged once per parse.

    Args:
        path: Result folder holding `<entry>-scalars.csv` / `<entry>-sequences.csv` files.

    Returns:
        Result with one Result Entry per name; sequences keep every row as read on a datetime index, non-numeric
        values as NaN. Refused if no file is usable.
    """
    files = sorted(file for kind in KINDS for file in path.glob(f"*-{kind}.csv"))
    return _read(path, tuple((file.name, file.stat().st_mtime_ns) for file in files))


def _read_file(file: Path, kind: str) -> pd.DataFrame | str:
    # Values as read, or the reason to skip the file.
    try:
        frame = pd.read_csv(file, sep=";", index_col=0, parse_dates=kind == "sequences")
    except (OSError, ValueError) as error:  # pandas parser errors are ValueErrors
        return f"unparseable ({error})"
    if frame.empty:
        return "header only"
    if kind == "sequences" and not isinstance(frame.index, pd.DatetimeIndex):
        return "index not datetime"
    if kind == "scalars" and (frame.index.name != "variable_name" or len(frame.columns) != 1):
        columns = ", ".join(map(str, [frame.index.name, *frame.columns]))
        return f"not variable_name + one value column (multi-period Results are unsupported): {columns}"
    return frame


@functools.lru_cache(maxsize=32)
def _read(path: Path, stamps: tuple[tuple[str, int], ...]) -> Result | Refused:
    # `stamps` (file name, mtime) only keys the cache: any added, removed or edited file forces a re-parse.
    result_files = {name for name, _ in stamps}
    for ignored in sorted(file.name for file in path.iterdir() if file.name not in result_files):
        log.info("Result %s: ignoring %s, not <entry>-scalars.csv / <entry>-sequences.csv", path, ignored)
    result = Result({})
    for name, _ in stamps:
        entry_name, kind = name.removesuffix(".csv").rsplit("-", 1)
        frame = _read_file(path / name, kind)
        if isinstance(frame, str):
            result.warnings.append(f"{name}: {frame}, skipped")
            continue
        frame, dropped = to_numbers(frame)
        if dropped:
            result.warnings.append(f"{name}: {dropped} non-numeric values read as gaps")
        entry = result.entries.setdefault(entry_name, ResultEntry())
        if kind == "scalars":
            entry.scalars = frame.iloc[:, 0].to_dict()
        else:
            entry.sequences = frame
    if not result.entries:
        refused = Refused("; ".join(["no usable Result file", *result.warnings]))
        log.warning("Result %s refused: %s", path, refused.reason)
        return refused
    for warning in result.warnings:
        log.warning("Result %s: %s", path, warning)
    return result


def sequence_outcomes(result: Result) -> set[tuple[str, str]]:
    """List the Result Sequences of a Result as (Result Entry, variable) Outcomes."""
    return {(name, variable) for name, entry in result.entries.items() for variable in entry.sequences.columns}


def scalar_outcomes(result: Result) -> set[tuple[str, str]]:
    """List the Result Scalars of a Result as Outcomes.

    Args:
        result: Result to list.

    Returns:
        Outcomes as (Result Entry, variable).
    """
    return {(name, variable) for name, entry in result.entries.items() for variable in entry.scalars}
