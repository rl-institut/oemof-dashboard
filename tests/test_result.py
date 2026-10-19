import math
import os
from pathlib import Path

import pandas as pd

from oemof_dashboard.result import read, sequence_outcomes


def test_reads_adlershof_result_entries_as_written(shipped_data: Path) -> None:
    result = read(shipped_data / "results" / "adlershof")

    bhkw = result.entries["bhkw-electricity"]
    assert bhkw.scalars == {"invest": 0.0, "total": 0.0}
    assert list(bhkw.sequences.columns) == ["flow"]
    assert result.entries["battery_large-None"].scalars["init_content"] == 0.0
    assert list(result.entries["battery_large-None"].sequences.columns) == ["storage_content"]
    assert result.entries["bhkw-heat_central"].scalars == {}  # sequences only


def test_sequences_keep_8761st_row_on_datetime_index(shipped_data: Path) -> None:
    sequences = read(shipped_data / "results" / "adlershof").entries["bhkw-electricity"].sequences

    assert isinstance(sequences.index, pd.DatetimeIndex)
    assert len(sequences) == 8761
    assert sequences.index[0] == pd.Timestamp("2050-01-01 00:00")
    assert sequences.index[-1] == pd.Timestamp("2051-01-01 00:00")
    assert math.isnan(sequences["flow"].iloc[-1])


def test_scalars_only_entry_has_empty_sequences(tmp_path: Path) -> None:
    (tmp_path / "pv-electricity-scalars.csv").write_text("variable_name;2050-01-01\ninvest;3.5\n")

    entry = read(tmp_path).entries["pv-electricity"]

    assert entry.scalars == {"invest": 3.5}
    assert entry.sequences.empty


def test_edited_file_is_reparsed(tmp_path: Path) -> None:
    scalars = tmp_path / "pv-electricity-scalars.csv"
    scalars.write_text("variable_name;2050-01-01\ninvest;1.0\n")
    assert read(tmp_path).entries["pv-electricity"].scalars == {"invest": 1.0}

    scalars.write_text("variable_name;2050-01-01\ninvest;2.0\n")
    stat = scalars.stat()
    os.utime(scalars, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))  # mtime resolution can be coarse

    assert read(tmp_path).entries["pv-electricity"].scalars == {"invest": 2.0}


def test_sequence_outcomes_are_entry_variable_pairs(shipped_data: Path) -> None:
    outcomes = sequence_outcomes(read(shipped_data / "results" / "adlershof"))

    assert ("bhkw-electricity", "flow") in outcomes
    assert ("battery_large-None", "storage_content") in outcomes
    assert ("bhkw-electricity", "invest") not in outcomes  # Result Scalar
