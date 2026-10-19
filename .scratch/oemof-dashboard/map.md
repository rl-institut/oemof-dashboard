# oemof Dashboard

Label: wayfinder:map

## Destination

A handoff-ready spec (with locked architecture decisions) for a local, single-user Dash app that explores a Datapackage and/or Result independently, cross-links matching Components, compares Outcomes across Results, and saves/reloads Dashboards — ready to slice into build issues.

## Notes

- Domain: oemof-tabular Datapackages (`datapackages/`) and CSV Results (`results/`). Glossary: `CONTEXT.md` — use its terms.
- Locked at charting:
  - Planning only; build happens after the map as normal issues (TDD/worktree flow).
  - Local single-user tool started from CLI, opens in browser.
  - GUI: **Dash** (Plotly). No oemof/oemof-tabular runtime dependency (read files directly); no npm build step.
  - Datapackage and Result selected independently; matching by Component name only.
  - Outcome = Result Scalar or Result Sequence; comparison across variables and across Results.
  - Dashboard = JSON file, re-applicable to any Result by name; missing Outcomes shown as missing.
  - Graph view: auto-layout, Bus-centred, Result values overlaid on Flows when a Result is loaded.
  - Scale target: ≤ few hundred Components, ≤ ~100k steps per sequence.
- Skills every session: `ponytail:ponytail` (minimal deps/code), `dataviz` for chart decisions, `mattpocock-skills:domain-modeling` when terms change.
- Research findings live in `.scratch/oemof-dashboard/research/` (repo has no commits yet, so no `research/*` branches).

## Decisions so far

- [Result file naming → Flows and nodes](issues/01-result-file-naming.md): resqdb joins labels with `-`; unique split needs Datapackage names (bus-only heuristics otherwise); variables invest/total/init_content, flow/storage_content.
- [Dash building blocks](issues/02-dash-building-blocks.md): dash + dash-cytoscape only; CSS grid + pattern-matching callbacks; Store/Upload/Download + pydantic for Dashboard file; Scattergl (≈8 WebGL charts/page limit).
- [Energy system model from a Datapackage](issues/03-energy-system-model.md): Connections from bus `foreignKeys` only, undirected; Input Sequences via sequence `foreignKeys`; Flow direction only from Results; Outcome = Result × Result Entry (stem) × variable, split only against a selected Datapackage; mismatches listed, never guessed.
- [Outcome selection and comparison](issues/04-outcome-selection.md): one picker (graph pre-filters); chart = Entry×variable list × global Result Selection; Input Sequences mixable in sequence charts, scalars separate; one y-axis, real timestamps, 8761st row kept; missing → "(missing)" legend entry.
- [Chart set and Dashboard file](issues/05-charts-and-dashboard-file.md): kinds sequence (line/stacked area/duration curve) · scalar (bar) · system (Sankey, Σ flow, needs Datapackage); color = Entry×variable with optional per-chart override, Result via dash/subplot/group; file = version 1 + ordered charts (half/full) + Result Selection/Datapackage as non-binding defaults.
- [UI layout and navigation prototype](issues/06-ui-layout-prototype.md): variant A Explorer, three panes (selectors+picker · resizable graph over chart grid · combined Component inspector); graph click → inspector + picker filter, chart chips → back to node; series editable per chart after creation.
- [Packaging, launch and data discovery](issues/07-packaging-and-discovery.md): `oemof-dashboard [ROOT] [--datapackages DIR] [--results DIR]` (defaults `ROOT/datapackages`, `ROOT/results`); subfolders discovered by marker files, rescanned on page load, parsed lazily + cached; deps dash, dash-cytoscape, pandas; Python ≥3.12; pure readers `datapackage.py`/`result.py` apart from `app.py`/`cli.py`.
- [Bus balance view](issues/08-bus-balance-view.md): system-kind type for one Bus; in above / out below zero from split `flow`s (storage, excess, shortage not special-cased); subplot per Result; residual line only if nonzero; stack order Σ desc; Dashboard stores Bus name.
- [Error handling for malformed input](issues/09-error-handling.md): load what's usable, skipped items become Input Warnings (selector ⚠ n, inspector list, log); Refused input (unreadable root, duplicate names, nothing usable) stays listed ✖; bad Dashboard file → banner, charts untouched.

## Not yet specified

## Out of scope

- Result formats other than the current CSV folder layout (pickles, single-file scalars/sequences, solph dumps): reader kept swappable, but not part of this effort.
- Static HTML export / sharing without Python.
- Multi-user / server deployment.
- Parameter diff between two Datapackages.
- Linking metadata (stored link from a Result to its Datapackage, e.g. resqdb scenario YAML `datapackage:`): name matching is enough for this effort.
- Manual graph layout persisted in the Dashboard: auto-layout is decided; manual layout is an extra on top of it.
- Derived comparisons and deferred chart options (difference to a reference Result, per-chart Result override, second y-axis, time-index alignment): deliberately deferred in Outcome selection and Chart set.
- Multi-period Results (scalars with several period columns): files of that shape are skipped with an Input Warning; see [Error handling for malformed input](issues/09-error-handling.md).
- Heatmap (day×hour) and downsampling: only needed beyond the scale target.
