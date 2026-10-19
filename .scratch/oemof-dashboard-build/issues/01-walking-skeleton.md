# 01: Walking skeleton — launch, discovery, empty Explorer layout

**What to build:** The modeller runs `oemof-dashboard [ROOT] [--datapackages DIR] [--results DIR] [--port 8050] [--debug]`, the browser opens on `127.0.0.1`, and the app shows the three-pane Explorer layout (left: Datapackage selector, Result Selection, Outcome picker, "Add chart"; centre: graph pane over chart grid; right: inspector) with the selectors listing the discovered Datapackages and Results. Nothing is parsed yet. Spec: `../../oemof-dashboard/spec.md`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Project metadata: dependencies `dash`, `dash-cytoscape`, `pandas`; dev `pytest`, `ruff`; build backend `uv_build`; `requires-python >=3.12`; console script `oemof-dashboard`
- [ ] ROOT defaults to cwd; Datapackage folder `ROOT/datapackages` and Result folder `ROOT/results` unless overridden
- [ ] Datapackage = direct subfolder with `datapackage.json`; Result = direct subfolder with ≥1 `*-scalars.csv` / `*-sequences.csv`; name = subfolder name
- [ ] Other subfolders ignored with one log line each; missing folder → empty selector + log line, no abort
- [ ] Folders rescanned on every page load
- [ ] Binds `127.0.0.1`, opens browser via stdlib `webbrowser`, Dash debug only with `--debug`
- [ ] Tests: discovery on `tmp_path` trees (markers, ignored, missing, overrides), argument parsing, app smoke test (layout builds) — green on Python 3.12 and 3.14
