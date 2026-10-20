import logging
import math
import os
from pathlib import Path

import pandas as pd
import pytest

from oemof_dashboard.datapackage import Refused
from oemof_dashboard.result import read, scalar_outcomes, sequence_outcomes

GOOD_SCALARS = "variable_name;2050-01-01\ninvest;1.0\n"


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


def test_scalar_outcomes_are_entry_variable_pairs(shipped_data: Path) -> None:
    outcomes = scalar_outcomes(read(shipped_data / "results" / "adlershof"))

    assert {("bhkw-electricity", "invest"), ("battery_large-None", "init_content")} <= outcomes
    assert ("bhkw-electricity", "flow") not in outcomes  # Result Sequence


@pytest.mark.parametrize(
    ("name", "text", "reason"),
    [
        ("pv-electricity-sequences.csv", "", "unparseable"),
        ("pv-electricity-sequences.csv", "timeindex;flow\n2050-01-01 00:00;1;2;3\n", "unparseable"),
        ("pv-electricity-sequences.csv", "timeindex;flow\n", "header only"),
        ("pv-electricity-scalars.csv", "variable_name;2050-01-01\n", "header only"),
        ("pv-electricity-sequences.csv", "timeindex;flow\nfirst;1.0\n", "index not datetime"),
        ("pv-electricity-scalars.csv", "name;2050-01-01\ninvest;1.0\n", "not variable_name + one value column"),
        (
            "pv-electricity-scalars.csv",
            "variable_name;2050-01-01;2060-01-01\ninvest;1.0;2.0\n",
            "not variable_name + one value column",
        ),
    ],
    ids=[
        "empty",
        "ragged",
        "sequences-header-only",
        "scalars-header-only",
        "no-datetime",
        "no-variable-name",
        "multi-period",
    ],
)
def test_bad_file_is_skipped_with_warning(tmp_path: Path, name: str, text: str, reason: str) -> None:
    (tmp_path / "bhkw-electricity-scalars.csv").write_text(GOOD_SCALARS)
    (tmp_path / name).write_text(text)

    result = read(tmp_path)

    assert result.entries.keys() == {"bhkw-electricity"}
    assert len(result.warnings) == 1
    assert result.warnings[0].startswith(f"{name}: ")
    assert reason in result.warnings[0]


def test_non_numeric_values_become_gaps_with_one_warning_per_file(tmp_path: Path) -> None:
    sequences = "timeindex;flow\n2050-01-01 00:00;1.5\n2050-01-01 01:00;x\n2050-01-01 02:00;?\n"
    (tmp_path / "pv-electricity-sequences.csv").write_text(sequences)
    (tmp_path / "pv-electricity-scalars.csv").write_text("variable_name;2050-01-01\ninvest;lots\ntotal;2\n")

    result = read(tmp_path)

    entry = result.entries["pv-electricity"]
    assert entry.sequences["flow"].iloc[0] == 1.5
    assert entry.sequences["flow"].iloc[1:].isna().all()
    assert math.isnan(entry.scalars["invest"])
    assert entry.scalars["total"] == 2.0
    assert result.warnings == [
        "pv-electricity-scalars.csv: 1 non-numeric values read as gaps",
        "pv-electricity-sequences.csv: 2 non-numeric values read as gaps",
    ]


def test_other_files_are_ignored_with_log_line_only(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    (tmp_path / "pv-electricity-scalars.csv").write_text(GOOD_SCALARS)
    (tmp_path / "pv-electricity.csv").write_text("garbage")
    (tmp_path / "notes.txt").write_text("garbage")

    with caplog.at_level(logging.INFO):
        result = read(tmp_path)

    assert result.entries.keys() == {"pv-electricity"}
    assert result.warnings == []
    assert "pv-electricity.csv" in caplog.text
    assert "notes.txt" in caplog.text


@pytest.mark.parametrize("files", [{}, {"pv-electricity-sequences.csv": "", "pv-electricity-scalars.csv": "x;y\n"}])
def test_result_without_usable_file_is_refused(tmp_path: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        (tmp_path / name).write_text(text)

    refused = read(tmp_path)

    assert isinstance(refused, Refused)
    assert refused.reason.startswith("no usable Result file")


def test_warnings_and_refusal_are_logged_once_per_parse(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    (tmp_path / "pv-electricity-scalars.csv").write_text(GOOD_SCALARS)
    (tmp_path / "pv-heat-sequences.csv").write_text("")

    with caplog.at_level(logging.WARNING):
        read(tmp_path)
        read(tmp_path)

    assert len(caplog.records) == 1
    assert str(tmp_path) in caplog.text
    assert "pv-heat-sequences.csv" in caplog.text


def test_sequences_of_different_length_are_read_as_is(tmp_path: Path) -> None:
    (tmp_path / "a-b-sequences.csv").write_text("timeindex;flow\n2050-01-01 00:00;1\n")
    (tmp_path / "c-d-sequences.csv").write_text("timeindex;flow\n2050-01-01 00:00;1\n2050-01-01 01:00;2\n")

    result = read(tmp_path)

    assert [len(result.entries[name].sequences) for name in ("a-b", "c-d")] == [1, 2]
    assert result.warnings == []
