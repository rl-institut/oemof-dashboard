import logging
import os
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from dash import Dash

from oemof_dashboard.cli import discover_datapackages, discover_results, main, parse_args


def make_folder(path: Path, *files: str) -> None:
    """Create `path` with an empty file for each name in `files`."""
    path.mkdir(parents=True)
    for name in files:
        (path / name).write_text("")


def test_discovers_datapackages_by_marker_file(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    make_folder(tmp_path / "b_dp", "datapackage.json")
    make_folder(tmp_path / "a_dp", "datapackage.json")
    make_folder(tmp_path / "no_marker", "elements.csv")
    (tmp_path / "datapackage.json").write_text("")  # top-level file, not a subfolder

    with caplog.at_level(logging.INFO):
        assert discover_datapackages(tmp_path) == ["a_dp", "b_dp"]

    assert len(caplog.records) == 1
    assert "no_marker" in caplog.text


def test_discovers_results_by_scalars_or_sequences_file(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    make_folder(tmp_path / "only_scalars", "bhkw-electricity-scalars.csv")
    make_folder(tmp_path / "only_sequences", "bhkw-electricity-sequences.csv")
    make_folder(tmp_path / "other_csv", "bhkw-electricity.csv")
    make_folder(tmp_path / "empty")
    make_folder(tmp_path / "decoy")
    (tmp_path / "decoy" / "bhkw-electricity-scalars.csv").mkdir()  # a folder, not a Result file

    with caplog.at_level(logging.INFO):
        assert discover_results(tmp_path) == ["only_scalars", "only_sequences"]

    assert len(caplog.records) == 3
    for ignored in ("other_csv", "empty", "decoy"):
        assert ignored in caplog.text


@pytest.mark.parametrize("discover", [discover_datapackages, discover_results])
def test_missing_folder_gives_empty_list_and_not_found_log_line(
    discover: Callable[[Path], list[str]], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        assert discover(tmp_path / "nope") == []

    assert len(caplog.records) == 1
    assert "not found" in caplog.text


@pytest.fixture
def unreadable() -> Iterator[Callable[[Path], None]]:
    """Make folders unreadable (mode 000) for one test, restoring them so tmp_path cleanup works."""
    locked: list[Path] = []

    def lock(path: Path) -> None:
        path.chmod(0)
        locked.append(path)

    yield lock
    for path in locked:
        path.chmod(0o755)


def test_unreadable_subfolder_is_ignored_with_log_line(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, unreadable: Callable[[Path], None]
) -> None:
    make_folder(tmp_path / "ok", "datapackage.json")
    make_folder(tmp_path / "locked", "datapackage.json")
    unreadable(tmp_path / "locked")

    with caplog.at_level(logging.INFO):
        assert discover_datapackages(tmp_path) == ["ok"]

    assert "locked" in caplog.text


def test_unreadable_folder_gives_empty_list_and_log_line(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, unreadable: Callable[[Path], None]
) -> None:
    make_folder(tmp_path / "results" / "r1", "bhkw-electricity-sequences.csv")
    unreadable(tmp_path / "results")

    with caplog.at_level(logging.INFO):
        assert discover_results(tmp_path / "results") == []

    assert len(caplog.records) == 1
    assert "not readable" in caplog.text


def test_discovers_shipped_test_data(shipped_data: Path) -> None:
    assert discover_datapackages(shipped_data / "datapackages") == ["adlershof"]
    assert discover_results(shipped_data / "results") == ["adlershof"]


@pytest.mark.parametrize(
    ("argv", "datapackages", "results", "port", "debug"),
    [
        ([], "datapackages", "results", 8050, False),
        (["/data/project"], "/data/project/datapackages", "/data/project/results", 8050, False),
        (
            ["/data/project", "--datapackages", "/dp", "--results", "/res", "--port", "9000", "--debug"],
            "/dp",
            "/res",
            9000,
            True,
        ),
    ],
    ids=["root-defaults-to-cwd", "root-sets-input-folders", "overrides-win-over-root"],
)
def test_parse_args(argv: list[str], datapackages: str, results: str, port: int, debug: bool) -> None:
    args = parse_args(argv)

    assert args.datapackages == Path(datapackages)
    assert args.results == Path(results)
    assert args.port == port
    assert args.debug is debug


class ImmediateTimer:
    """Stands in for `threading.Timer`: runs the function on `start()` without waiting."""

    def __init__(self, _interval: float, function: Callable[..., object], args: list[object]) -> None:
        self.start = lambda: function(*args)


@pytest.fixture
def launched() -> Iterator[tuple[MagicMock, MagicMock]]:
    """Patch out serving and browser opening; yield the `Dash.run` and `webbrowser.open` mocks."""
    with (
        patch.object(Dash, "run") as run,
        patch("webbrowser.open") as open_browser,
        patch("threading.Timer", ImmediateTimer),
        patch.dict(os.environ),
    ):
        os.environ.pop("WERKZEUG_RUN_MAIN", None)
        yield run, open_browser


def test_main_serves_on_localhost_and_opens_browser(launched: tuple[MagicMock, MagicMock], tmp_path: Path) -> None:
    run, open_browser = launched

    main([str(tmp_path), "--port", "9001"])

    run.assert_called_once_with(host="127.0.0.1", port=9001, debug=False)
    open_browser.assert_called_once_with("http://127.0.0.1:9001/")


def test_main_debug_only_with_flag(launched: tuple[MagicMock, MagicMock], tmp_path: Path) -> None:
    run, _ = launched

    main([str(tmp_path), "--debug"])

    assert run.call_args.kwargs["debug"] is True


def test_main_opens_browser_once_under_debug_reloader(launched: tuple[MagicMock, MagicMock], tmp_path: Path) -> None:
    _, open_browser = launched

    with patch.dict(os.environ, {"WERKZEUG_RUN_MAIN": "true"}):  # set in the reloader's child process
        main([str(tmp_path), "--debug"])

    open_browser.assert_not_called()
