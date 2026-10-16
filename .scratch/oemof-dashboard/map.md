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

## Not yet specified

- Linking metadata: optional stored link Result → Datapackage beyond pure name matching; note resqdb scenario YAML already holds `datapackage:` (see Result file naming research).
- Manual graph layout persisted in Dashboard.
- Derived comparisons (difference to a reference Result) and deferred knobs: per-chart Result override, second y-axis, step alignment of differing time indices.
- Later chart types (heatmap day×hour) and downsampling if data grows past scale target.
- Error handling for malformed/partial Datapackages and Results (what to show vs. refuse). Already fixed: Datapackage without `foreignKeys` → unconnected + warning; broken Input Sequence reference; unmatched Result Entries (see Energy system model).

## Out of scope

- Result formats other than the current CSV folder layout (pickles, single-file scalars/sequences, solph dumps): reader kept swappable, but not part of this effort.
- Static HTML export / sharing without Python.
- Multi-user / server deployment.
- Parameter diff between two Datapackages.
