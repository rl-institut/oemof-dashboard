"""Pure Result reader: Result Entries with their Result Scalars and Result Sequences."""

import functools
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

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


def read(path: Path) -> Result:
    """Read a Result folder, re-using the last parse while no Result file changed.

    Args:
        path: Result folder holding `<entry>-scalars.csv` / `<entry>-sequences.csv` files.

    Returns:
        Result with one Result Entry per name; sequences keep every row as read on a datetime index.
    """
    files = sorted(file for kind in KINDS for file in path.glob(f"*-{kind}.csv"))
    return _read(path, tuple((file.name, file.stat().st_mtime_ns) for file in files))


@functools.lru_cache(maxsize=32)
def _read(path: Path, stamps: tuple[tuple[str, int], ...]) -> Result:
    # `stamps` (file name, mtime) only keys the cache: any added, removed or edited file forces a re-parse.
    entries: dict[str, ResultEntry] = {}
    for name, _ in stamps:
        entry_name, kind = name.removesuffix(".csv").rsplit("-", 1)
        entry = entries.setdefault(entry_name, ResultEntry())
        if kind == "scalars":
            entry.scalars = pd.read_csv(path / name, sep=";", index_col=0).iloc[:, 0].to_dict()
        else:
            entry.sequences = pd.read_csv(path / name, sep=";", index_col=0, parse_dates=True)
    return Result(entries)


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
