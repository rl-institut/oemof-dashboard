# Packaging, launch and data discovery

Type: grilling
Status: resolved
Assignee: Hendrik Huyskens
Blocked by: 02

## Question

How is the app launched and where does it find data: CLI shape (`oemof-dashboard <root>` with `datapackages/` + `results/`, or arbitrary paths), how Datapackages and Results are discovered/validated, final dependency list in `pyproject.toml` (dash, plotly, extras from research; pandas yes/no), Python version (pyproject says ≥3.14 — check Dash support), and module layout (readers vs. app) for testability.

## Answer

Grilled 2026-10-16.

- **CLI**: `oemof-dashboard [ROOT] [--datapackages DIR] [--results DIR] [--port 8050] [--debug]`.
  - ROOT defaults to cwd.
  - The Datapackage folder is `ROOT/datapackages` unless `--datapackages` overrides it (any name). Same for `ROOT/results` and `--results`.
  - A missing folder → empty selector and a log line, no abort.
- **Discovery**: direct subfolders only; name = subfolder name.
  - Datapackage = subfolder with `datapackage.json`.
  - Result = subfolder with at least one `*-scalars.csv` or `*-sequences.csv`.
  - Any other subfolder is ignored and logged (one line each).
  - Name collisions are impossible: names are unique within a folder, and Datapackages and Results live in separate folders.
- **Rescan**: on every page load / browser refresh (cheap `listdir`).
- **Validation**: lazy, on selection. The parse is cached with `functools.lru_cache` keyed on (path, mtime). How errors are shown stays in the error-handling fog of the map.
- **Dependencies**: `dash`, `dash-cytoscape`, `pandas` (brings numpy, which plotly sends as base64 typed arrays); pydantic comes via dash. Dev: `pytest`, `ruff`. Build backend `uv_build`.
- **Python**: `requires-python >=3.12`, tested on 3.12 and 3.14. A smoke test of a Dash app on 3.14 goes into the first build issue (research caveat).
- **Module layout**: `src/oemof_dashboard/`:
  - `datapackage.py` and `result.py`: pure readers, no Dash, tested against `tests/test_data`.
  - `dashboard_file.py`: pydantic model, version 1.
  - `app.py`: layout and callbacks, smoke-tested only.
  - `cli.py`: argument parsing, discovery, launch.
  - No extra layers.
- **Launch**: `[project.scripts] oemof-dashboard = "oemof_dashboard.cli:main"`. Binds to `127.0.0.1`, opens the browser via stdlib `webbrowser`, Dash debug only with `--debug`. No `--no-browser` flag. Install via `uv tool install` / `pip install`.
