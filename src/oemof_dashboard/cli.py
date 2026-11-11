"""Command line entry point: argument parsing, input discovery and launch."""

import argparse
import logging
import os
import threading
import webbrowser
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger(__name__)


def _discover(folder: Path, kind: str, is_input: Callable[[Path], bool]) -> list[str]:
    # Runs on every page load, so an unreadable folder must not raise.
    try:
        subfolders = sorted(entry for entry in folder.iterdir() if entry.is_dir())
    except FileNotFoundError:
        log.warning("%s folder %s not found, no %ss listed", kind, folder, kind)
        return []
    except OSError as error:
        log.warning("%s folder %s not readable (%s), no %ss listed", kind, folder, error.strerror, kind)
        return []
    names = []
    for sub in subfolders:
        try:
            found = is_input(sub)
        except OSError as error:
            log.info("Ignoring %s: not readable (%s)", sub, error.strerror)
            continue
        if found:
            names.append(sub.name)
        else:
            log.info("Ignoring %s: not a %s", sub, kind)
    return names


def discover_datapackages(folder: Path) -> list[str]:
    """List the Datapackages in a folder.

    A Datapackage is a direct subfolder holding a `datapackage.json`. Other subfolders are ignored with
    one log line each; a missing or unreadable folder gives an empty list and a log line.

    Args:
        folder: Datapackage folder to scan.

    Returns:
        Sorted Datapackage names (subfolder names).
    """
    return _discover(folder, "Datapackage", lambda sub: (sub / "datapackage.json").is_file())


def discover_results(folder: Path) -> list[str]:
    """List the Results in a folder.

    A Result is a direct subfolder holding at least one `*-scalars.csv` or `*-sequences.csv` file. Other
    subfolders are ignored with one log line each; a missing or unreadable folder gives an empty list and a
    log line.

    Args:
        folder: Result folder to scan.

    Returns:
        Sorted Result names (subfolder names).
    """
    return _discover(
        folder,
        "Result",
        lambda sub: any(
            file.is_file() for pattern in ("*-scalars.csv", "*-sequences.csv") for file in sub.glob(pattern)
        ),
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line.

    Args:
        argv: Arguments without the program name; `None` reads `sys.argv`.

    Returns:
        Namespace with `root`, `datapackages` and `results` (resolved against ROOT unless overridden),
        `port` and `debug`.
    """
    parser = argparse.ArgumentParser(prog="oemof-dashboard", description="Explore oemof Datapackages and Results.")
    parser.add_argument("root", nargs="?", type=Path, default=Path(), help="project folder (default: cwd)")
    parser.add_argument("--datapackages", type=Path, help="Datapackage folder (default: ROOT/datapackages)")
    parser.add_argument("--results", type=Path, help="Result folder (default: ROOT/results)")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--debug", action="store_true", help="enable Dash debug mode")
    args = parser.parse_args(argv)
    args.datapackages = args.datapackages or args.root / "datapackages"
    args.results = args.results or args.root / "results"
    return args


def main(argv: list[str] | None = None) -> None:
    """Start the dashboard on 127.0.0.1 and open it in the browser.

    Args:
        argv: Arguments without the program name; `None` reads `sys.argv`.
    """
    from oemof_dashboard.app import create_app  # deferred: app imports discovery from here

    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app = create_app(args.datapackages, args.results)
    url = f"http://127.0.0.1:{args.port}/"
    # The debug reloader re-runs main in a child process; open the browser only in the parent.
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        # ponytail: fixed 1 s head start for the server, no readiness polling
        threading.Timer(1, webbrowser.open, [url]).start()
    app.run(host="127.0.0.1", port=args.port, debug=args.debug)
