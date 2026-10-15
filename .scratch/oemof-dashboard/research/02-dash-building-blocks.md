# Research 02: Dash building blocks

Ticket: `issues/02-dash-building-blocks.md` · Researched 2026-10-15 · Sources: PyPI JSON API, GitHub API/repos, dash.plotly.com, plotly changelogs.

## TL;DR

| Need | Recommendation | Extra deps |
|---|---|---|
| (1) Grid of N charts | Plain CSS grid + pattern-matching callbacks + `Patch()`; order lives in a `dcc.Store` list (move up/down buttons) | **none** |
| (2) Bus/Component graph | `dash-cytoscape` 1.0.2, layout `cose` (built-in); `breadthfirst`/`concentric` with Buses as roots/inner ring as alternatives | **1** (dash-cytoscape, no Python deps) |
| (3) Dashboard JSON file | `dcc.Store` (state) + `dcc.Download` (save) + `dcc.Upload` (load); `json` stdlib | **none** |
| (4) 8760 × many series | `go.Scattergl` with numpy arrays; no resampling at scale target. Mind the WebGL context limit (see below) | **none** (numpy recommended) |

Total extra deps beyond `dash`: **one** (`dash-cytoscape`). Dash does **not** require pandas.

## Dash itself

- Current: **dash 4.4.1** (2026-07-21), `requires_python >=3.9`. Pure-Python wheel (8.9 MB). [PyPI](https://pypi.org/pypi/dash/json)
- Install requires: Flask<3.2, Werkzeug<3.2, plotly>=5, importlib-metadata, typing_extensions, requests, retrying, nest-asyncio, setuptools, janus, pydantic>=2.10, comm. **pandas is not a dependency** (only in the `ci` extra). [PyPI](https://pypi.org/pypi/dash/json)
- plotly 7.1.0 (2026-09-15) requires only `narwhals` + `packaging`; pandas/numpy are optional (`express` extra). [PyPI](https://pypi.org/pypi/plotly/json). Since plotly.py 6.0, numpy arrays are sent as base64 typed arrays ("to keep precision intact") — a reason to pass numpy arrays, not lists, for long sequences. [plotly.py CHANGELOG](https://github.com/plotly/plotly.py/blob/main/CHANGELOG.md)
- Resolved install of `dash` on CPython 3.14.3 = **28 packages** (dash, plotly, flask, werkzeug, jinja2, markupsafe, itsdangerous, click, blinker, pydantic, pydantic-core, annotated-types, typing-inspection, typing-extensions, narwhals, packaging, requests, urllib3, idna, certifi, charset-normalizer, retrying, nest-asyncio, janus, comm, importlib-metadata, zipp, setuptools). Measured by an actual `uv pip install dash` on 3.14.3; it resolved without errors (pydantic-core has cp314 wheels).
- **Python 3.14:** PyPI classifiers only list up to 3.12, but `requires_python >=3.9` allows it, the install resolves on 3.14, and Dash 3.3.0's changelog contains "Fix pkgutil.find_loader removal in Python 3.14", i.e. 3.14 is actively handled upstream. 4.4.0 dropped Python 3.8. [Dash CHANGELOG](https://github.com/plotly/dash/blob/dev/CHANGELOG.md). Not verified: actually running an app on 3.14 (import test was not run, see "Caveats").
- Dash 3.0 (2025-03-17) breaking changes relevant to 3rd-party components: React 18.3.1 default, `defaultProps` on function components deprecated, `run_server` removed (use `app.run`), `_dashprivate`/`loading_state` props removed, components must be generated with `dash-generate-components`. Dash 4.0 (2026-02-03) lists no further breaking changes beyond redesigned dcc Dropdown/Slider defaults. [Dash CHANGELOG](https://github.com/plotly/dash/blob/dev/CHANGELOG.md)

## (1) User-editable grid of N charts

**Core Dash only.** Pattern-matching IDs (`{"type": "chart", "index": n}`) with `ALL`/`MATCH`, and `Patch()` to `.append()` / `del patched[i]` children without resending the whole list (Dash ≥2.9). Since Dash 4.2, `MATCH` in Input/State no longer needs a `MATCH` Output. [Pattern-matching callbacks](https://dash.plotly.com/pattern-matching-callbacks)

Layout via CSS: `display: grid; grid-template-columns: repeat(auto-fill, minmax(480px, 1fr))` in `assets/style.css` (Dash auto-serves `assets/`). Reordering = reorder the chart list in the Dashboard state store and re-render; resizing = a per-chart "wide" toggle (`grid-column: span 2`).

Draggable alternatives (rejected):

| Package | Version / last release | Deps | Maintenance | Dash 3/4 |
|---|---|---|---|---|
| [dash-draggable](https://pypi.org/project/dash-draggable/) | 0.1.2 / 2021-10-03 | none declared | repo last push 2023-01-08, 8 open issues incl. "Dict as id does not work" (#10) — breaks pattern-matching IDs; "update to react-grid-layout 1.3.0" open since 2021 [GitHub](https://github.com/MehdiChelh/dash-draggable/issues) | Untested; predates React 18 / Dash 3 component-API changes |
| [dash-dynamic-grid-layout](https://pypi.org/project/dash-dynamic-grid-layout/) | 0.1.3 / 2025-04-02 | none declared | single release burst; repo last push 2025-04-02, 26 stars [GitHub](https://github.com/pip-install-python/dash-dynamic-grid-layout) | Not stated; PyPI example still uses `app.run_server`, which Dash 3 removed |

Recommendation: **CSS grid + pattern-matching + Patch**, zero deps. Drag-and-drop is a nice-to-have; both libraries are low-maintenance single-author packages with unverified Dash 3/4 compatibility.

## (2) Bus/Component network graph

**[dash-cytoscape](https://pypi.org/pypi/dash-cytoscape/json) 1.0.2**, released 2024-07-15, `requires_python >=3.8`, **no Python dependencies**, sdist only (4.0 MB tar.gz, ships the prebuilt JS bundle — no npm at install). Official Plotly repo, last push 2025-08-09, 69 open issues, not archived. [GitHub](https://github.com/plotly/dash-cytoscape)

Dash 4 risk: [issue #229](https://github.com/plotly/dash-cytoscape/issues/229) — errors (`bb.h undefined`, `this._cy.destroy`) when a Cytoscape component is **mounted via a callback** under Dash 4.x; maintainer called it "a real bug", closed by reporter as not reproducible in a minimal script, no fix released. Mitigation: put `cyto.Cytoscape` in the static layout and only update its `elements`/`stylesheet` from callbacks.

Click selection: callback inputs `tapNodeData`, `tapEdgeData`, `selectedNodeData` (documented in [dash.plotly.com/cytoscape/events](https://dash.plotly.com/cytoscape/events)).

Layouts ([docs](https://dash.plotly.com/cytoscape/layout)):
- Built-in: `preset`, `random`, `grid`, `circle`, `concentric`, `breadthfirst`, `cose`.
- Extra (bundled inside dash-cytoscape, enabled with `cyto.load_extra_layouts()`, larger JS bundle, no extra pip package): `cose-bilkent`, `cola`, `euler`, `spread`, `dagre`, `klay`.

For a bipartite Bus–Component graph (Components connect to 1–3 Buses, Buses are hubs) of 30–300 nodes:
- **`cose`** (force-directed, built-in): default choice; hubs (Buses) naturally centre their Components. Good enough at ≤300 nodes.
- **`breadthfirst` with `roots` = Bus selector** (e.g. `'[type = "bus"]'`; roots are selectors, not IDs): layered view, Buses on top row, Components below — readable for few Buses, gets wide with many.
- **`concentric`** with a `concentric` level function (Buses inner ring): tidy but long edges for multi-Bus Components.
- **`cose-bilkent`** (extra): better compound/hub layout than `cose` if `cose` overlaps too much; same package, just `load_extra_layouts()`.
- `dagre`/`klay` (hierarchical) suit directed flows (source → bus → sink) and are the fallback if energy flow direction should read left-to-right.

Recommendation: **dash-cytoscape, `cose` first**, try `cose-bilkent`/`dagre` in a prototype with `datapackages/adlershof_dummy`.

## (3) Dashboard JSON save/restore

- **`dcc.Store`** (`storage_type="memory"`) holds the Dashboard state dict (chart list, selections). Single source of truth; chart grid is rendered from it.
- **Save:** `dcc.Download` + callback returning `dict(content=json.dumps(state, indent=2), filename="dashboard.json")`. ([dcc.Download docs](https://dash.plotly.com/dash-core-components/download))
- **Load:** `dcc.Upload` gives `contents` as `data:...;base64,<payload>` — `base64.b64decode` → `json.loads` → validate → write into the Store. ([dcc.Upload docs](https://dash.plotly.com/dash-core-components/upload))
- Validation at the trust boundary: pydantic is already a Dash dependency, so a pydantic model for the Dashboard file costs nothing extra.
- **Dash persistence is not a fit** for Dashboards: it only saves *user edits* of form props (`value` etc.) into browser `localStorage`/`sessionStorage`/memory, keyed by component id; callback outputs override saved values. [Persistence docs](https://dash.plotly.com/persistence). Fine as a convenience (e.g. remember last selected Result folder), not as the file format.
- Local single-user tool: since the server runs on the user's machine, "Save" could alternatively write directly to a path server-side; `dcc.Download` keeps it browser-native and avoids path handling.

Recommendation: **Store + Download + Upload + stdlib json (+ pydantic for validation)**, zero extra deps.

## (4) Plotting long sequences

- 8760 steps × tens of series is small for WebGL: use `go.Scattergl` (or `go.Scatter` for a handful of series) with numpy arrays (base64 typed-array transfer since plotly 6).
- **WebGL context limit:** browsers cap active WebGL contexts (Chrome ~16). plotly.js uses a fixed number of contexts per graph (2 since ~v1.33), not shared across graph divs; maintainers advise fewer graphs / removing off-screen ones. [plotly.js #2333](https://github.com/plotly/plotly.js/issues/2333). Practical consequence: **roughly 8 `Scattergl` charts on one page** before the browser drops the oldest context. [PR #6784](https://github.com/plotly/plotly.js/pull/6784) (merged 2023-12) supports loading greggman's `virtual-webgl` script before plotly to share one context — could be served from `assets/` (no pip dep). Simplest rule: SVG `Scatter` below a point threshold, `Scattergl` above; revisit if grids exceed ~8 heavy charts.
- **[plotly-resampler](https://pypi.org/pypi/plotly-resampler/json) 0.11.1** (2026-10-04, classifiers include 3.14, repo active, 1.2k stars [GitHub](https://github.com/predict-idlab/plotly-resampler)). Install requires: dash>=2.11, plotly<7 (**conflicts with current plotly 7.1.0** — would pin plotly to 6.x), numpy>=2.0, pandas>=2.2.3 (on py≥3.13), orjson, [tsdownsample](https://pypi.org/pypi/tsdownsample/json) 0.1.5.1 (Rust wheel, cp314 available, deps numpy). Adds ~30 MB (numpy 16.7 MB + pandas 10.8 MB wheels). Dash integration needs one `FigureResampler` held server-side per graph, registered per graph id; docs warn the global-variable example is "not a good practice" and recommend per-session server-side caching. [Dash integration docs](https://predict-idlab.github.io/plotly-resampler/v0.11.1/dash_app_integration/). Awkward with N dynamically created charts.

Recommendation: **no resampler.** `Scattergl` + numpy covers the scale target (≤~100k steps). If data outgrows it, a ~10-line numpy min/max-per-bucket downsample on zoom (`relayoutData`) is cheaper than plotly-resampler's dep tree (already listed under "Not yet specified" in the map).

## Package summary

| Package | Version | Released | Python deps | Verdict |
|---|---|---|---|---|
| dash | 4.4.1 | 2026-07-21 | 12 direct / 28 total | required |
| plotly | 7.1.0 | 2026-09-15 | narwhals, packaging | via dash |
| dash-cytoscape | 1.0.2 | 2024-07-15 | none | **use** |
| dash-draggable | 0.1.2 | 2021-10-03 | none | reject (stale) |
| dash-dynamic-grid-layout | 0.1.3 | 2025-04-02 | none | reject (unverified on Dash 3+) |
| plotly-resampler | 0.11.1 | 2026-10-04 | pandas, numpy, orjson, tsdownsample, plotly<7 | reject (deps, plotly pin) |
| numpy | 2.5.4 | — | none | optional, recommended for arrays |

## Caveats

- Footprint numbers besides the dash install are from PyPI wheel metadata, not installs.
- Running a Dash 4.4.1 app on Python 3.14 was not executed; evidence is the successful resolve + upstream 3.14 fix. Smoke test it on the first build issue.
- dash-cytoscape Dash 4 behaviour (#229) and the draggable libs' Dash 3+ status are unverified by running code.
