# Spec: oemof Dashboard

Label: ready-for-agent
Source: [map](map.md) and its resolved tickets 01–09. Glossary: `CONTEXT.md`.

## Problem Statement

An energy system modeller works with oemof-tabular Datapackages and the CSV Results of their solved runs. To get an overview of a setup, or to investigate an odd Result, they currently open dozens of CSV files by hand, guess which Result file belongs to which Component (Component names contain `-`, so file names like `heat_central-gas_boiler-heat_central-sequences.csv` are ambiguous), and write throwaway plotting scripts for every question. Comparing the same Outcome across several Results (different solver, constraints or edited attributes) means repeating this work per Result. Nothing they build survives the session, and malformed input fails silently or crashes the script.

## Solution

A local, single-user Dash app, started with `oemof-dashboard [ROOT]`, that opens in the browser. The user selects a Datapackage and a Result Selection independently. With a Datapackage, they see the energy system as a Bus-centred network graph, inspect each Component's Parameters, Connections and Input Sequences, and jump between a Component and its Outcomes. Result Entries are matched to Flows and nodes by Component name against the selected Datapackage, never guessed; mismatches are listed. The user builds a grid of charts (line, stacked area, duration curve, bar, Sankey, Bus balance) whose series are Outcomes × the global Result Selection, so one chart compares Results directly. The chart arrangement is saved as a Dashboard JSON file and re-applied to any other Result Selection; Outcomes that don't exist there are shown as "(missing)". Malformed input is loaded as far as usable, with every skipped item reported as an Input Warning.

## User Stories

### Launch and discovery

1. As a modeller, I want to start the app with `oemof-dashboard` in a project folder, so that it finds `datapackages/` and `results/` there without configuration.
2. As a modeller, I want to pass a ROOT path, so that I can start the app from anywhere.
3. As a modeller, I want to override the Datapackage and Result folders with `--datapackages` / `--results`, so that I can use folders with other names or locations.
4. As a modeller, I want to choose the port with `--port`, so that I can run it next to other local services.
5. As a modeller, I want the browser to open automatically on launch, so that I don't have to copy a URL.
6. As a modeller, I want the app to bind to `127.0.0.1` only, so that my data isn't exposed on the network.
7. As a developer, I want Dash debug mode only with `--debug`, so that normal use is quiet and fast.
8. As a modeller, I want a missing Datapackage or Result folder to give an empty selector and a log line instead of a crash, so that I can still use the other half.
9. As a modeller, I want every direct subfolder with a `datapackage.json` listed as a Datapackage, named after the folder, so that discovery needs no registry.
10. As a modeller, I want every direct subfolder with at least one `*-scalars.csv` or `*-sequences.csv` listed as a Result, so that new runs appear automatically.
11. As a modeller, I want other subfolders ignored with one log line each, so that I know why a folder isn't listed.
12. As a modeller, I want a browser refresh to rescan the folders, so that a Result written while the app runs appears without a restart.
13. As a modeller, I want an edited file re-parsed on the next reload, so that I see my fix without restarting.
14. As a modeller, I want to install the tool with `uv tool install` or `pip install`, so that it fits my usual Python setup.

### Datapackage

15. As a modeller, I want to select one Datapackage, so that Result Entries can be matched to my Components.
16. As a modeller, I want to use the app without any Datapackage, so that I can look at a Result whose setup I don't have.
17. As a modeller, I want element rows with `type == "bus"` shown as Buses and all other element rows as Components, so that the model matches oemof-tabular.
18. As a modeller, I want Connections derived from `foreignKeys` that reference the bus resource (string or list `fields`), so that the graph reflects what the Datapackage declares.
19. As a modeller, I want bus fields shown as Connections rather than as Parameters, so that the Parameter list only holds real attributes.
20. As a modeller, I want a Datapackage without `foreignKeys` (or without a bus resource) shown with unconnected Components and an Input Warning, so that I still see its Components.
21. As a modeller, I want Parameters that reference an Input Sequence recognised via sequence `foreignKeys`, so that I can open the referenced timeseries.
22. As a modeller, I want a reference to a missing sequence column shown as broken, so that I spot typos in my setup.
23. As a modeller, I want non-numeric scalar Parameters shown as text, so that string attributes like carriers are visible.

### Result and matching

24. As a modeller, I want to select one or more Results as the Result Selection, so that every chart compares them.
25. As a modeller, I want each Result shown as its Result Entries (file stems as written) with their variables, so that I can address any Outcome.
26. As a modeller, I want Result Entries split into (from, to) Flows or (node, None) nodes only when both sides are names in the selected Datapackage, so that splits are exact.
27. As a modeller, I want a Result Entry with zero or several valid splits listed as unmatched with its reason, so that ambiguity is never guessed away.
28. As a modeller, I want a banner "Datapackage likely doesn't belong to this Result" when fewer than ~50 % of Result Entries match, so that I notice a wrong pairing.
29. As a modeller, I want a split Flow without a matching Connection still drawn but marked "not in Datapackage", so that Result and setup disagreements are visible.
30. As a modeller, I want a Component without any Result Entry marked "no Outcomes in this Result", so that I see what wasn't written.
31. As a modeller, I want Result Scalars (`invest`, `total`, `init_content`, …) and Result Sequences (`flow`, `storage_content`, …) read as written, so that any variable resqdb writes is available.
32. As a modeller, I want the 8761st row of sequences kept as read, so that `storage_content`'s end value is visible and `flow` ends in a gap.

### Network graph

33. As a modeller, I want the selected Datapackage shown as an auto-laid-out, Bus-centred network graph, so that I grasp the system's structure at a glance.
34. As a modeller, I want Flow direction arrows and Σ flow on the graph edges for the first Result in the Result Selection, so that I see which way energy moves and how much.
35. As a modeller, I want to resize the graph pane by dragging, so that I can give the graph or the charts more room.
36. As a modeller, I want clicking a node to select it in the inspector and pre-filter the Outcome picker, so that I go from a Component to its Outcomes in one click.
37. As a modeller, I want an empty graph without a Datapackage, so that the rest of the app still works.

### Inspector

38. As a modeller, I want an inspector for the selected Component or Bus showing type/resource, Connections, Parameters and Input Sequences, so that I can read the setup without opening CSVs.
39. As a modeller, I want Connections in the inspector to link to their Bus, so that I can walk the system.
40. As a modeller, I want the inspector to list the node's Outcomes per Result Entry × variable with a "+ chart" action, so that I can chart one directly.
41. As a modeller, I want "in n/m Results" next to an Outcome missing from some Results, so that I know the comparison is partial.
42. As a modeller, I want an "Add Bus balance" action in the inspector of a selected Bus, so that I can open its balance in one click.
43. As a modeller, I want the inspector with nothing selected to summarise Result Entries, the unmatched list and all Input Warnings per input, so that I have one place to check data quality.

### Outcome picker and charts

44. As a modeller, I want one searchable Outcome picker (Result Entry × variable) filtered to the Result Selection, so that I can find any Outcome by name.
45. As a modeller, I want to add a chart from the picker, so that I can start a comparison.
46. As a modeller, I want a chart's series to be its Entry×variable list multiplied by the Result Selection, so that "same Outcome across Results" and "several Outcomes in one Result" are one mechanism.
47. As a modeller, I want to mix Input Sequences (Datapackage × resource × column) with Result Sequences in sequence charts, so that I can compare a profile with the dispatch it drives.
48. As a modeller, I want Input Sequences not multiplied over Results, so that a profile appears once.
49. As a modeller, I want sequence charts to accept only sequences and scalar charts only scalars, so that a chart never mixes incompatible values.
50. As a modeller, I want a chart's kind fixed at creation and its type switchable within the kind with the series list kept, so that I can try another view without rebuilding.
51. As a modeller, I want line charts on real timestamps with a shared datetime x-axis, so that I can read when things happen.
52. As a modeller, I want each Result shown by dash style in line and duration curve charts, with a warning above 4 Results, so that colour stays for the Outcome.
53. As a modeller, I want stacked area charts as one subplot per Result with shared axes, so that stacks don't overlap.
54. As a modeller, I want duration curves (values sorted descending, NaN dropped, x = rank in hours), so that I can compare utilisation.
55. As a modeller, I want bar charts with Results as x groups and Entry×variable as bars in a group, so that I can compare scalars like `invest` across Results.
56. As a modeller, I want a Sankey per Result side by side, nodes = Buses and Components, links = Flows valued by Σ flow (trailing NaN dropped), so that I see the energy balance of the whole system.
57. As a modeller, I want an optional Bus filter on a Sankey, so that I can focus on one carrier.
58. As a modeller, I want Flows without a `flow` sequence listed in a Sankey notice, so that missing links are explained.
59. As a modeller, I want Sankey node and link colours to follow the Bus, so that carriers are recognisable.
60. As a modeller, I want a Bus balance chart for one Bus with incoming Flows stacked above zero and outgoing below, one subplot per Result, so that I can check dispatch around a Bus.
61. As a modeller, I want Bus balance series labelled by the other node and stacked by Σ flow descending over the whole Result Selection, so that the order is identical in every subplot.
62. As a modeller, I want a residual line only when Σin − Σout is significantly nonzero (max |residual| > 1e-6 × max Flow value), so that real imbalances stand out and rounding noise doesn't.
63. As a modeller, I want storages, excess and shortage treated as ordinary Flows in the Bus balance, so that the view stays predictable.
64. As a modeller, I want Sankey and Bus balance offered only with a selected Datapackage, so that I never see a chart that can't be computed.
65. As a modeller, I want colour to encode Entry×variable / Input Sequence in fixed palette order, never the Result, so that one Outcome keeps its colour everywhere.
66. As a modeller, I want an optional hex colour override per chart and series item, so that I can match a colour convention.
67. As a modeller, I want one autoscaled y-axis per chart, so that charts stay simple; I make a second chart when scales clash.
68. As a modeller, I want an Outcome missing from a Result shown as a legend entry suffixed "(missing)" without a trace, so that a partial comparison is obvious and the rest still renders.
69. As a modeller, I want each chart card to have an editable multi-select of its series limited to its kind, so that I can refine a chart after creating it.
70. As a modeller, I want an emptied chart to stay and a × to remove it, so that editing doesn't destroy my layout by accident.
71. As a modeller, I want to set a chart's width to half or full and reorder charts up/down, so that I can arrange the grid.
72. As a modeller, I want an optional chart title with an automatic default, so that charts are labelled without effort.
73. As a modeller, I want chips in the chart header linking to the chart's nodes, so that clicking one selects and highlights the node in the graph.
74. As a modeller, I want a warning when more than 8 WebGL charts are on the page, so that I understand blank charts caused by the browser limit.
75. As a modeller, I want changing the Result Selection to re-apply every chart, so that the whole Dashboard follows my comparison.

### Dashboard file

76. As a modeller, I want to download the current chart arrangement as a Dashboard JSON file, so that I can reuse it later.
77. As a modeller, I want to upload a Dashboard file and have it replace the current charts, so that I restore a saved analysis.
78. As a modeller, I want the stored Result Selection and Datapackage applied on load when they exist, with a notice when they don't, so that a Dashboard is reusable with other Results.
79. As a modeller, I want Outcomes, Input Sequences and Buses not present in the current inputs shown as "(missing)", so that a Dashboard re-applies across Results without failing.
80. As a modeller, I want an invalid Dashboard file (bad JSON, schema failure, unknown version) refused with a banner while my current charts stay untouched, so that a bad file never costs me work.

### Input problems

81. As a modeller, I want broken items (unparseable resource CSVs, rows without `name`, bad Result files) skipped and recorded as Input Warnings with input, location and reason, so that one defect doesn't hide the rest.
82. As a modeller, I want rows without `type` kept with type "unknown" and a warning, so that the Component stays visible.
83. As a modeller, I want non-numeric values in sequences turned into gaps with one warning per file/resource and a count, so that I see the data is dirty without a flood of messages.
84. As a modeller, I want a Datapackage refused when `datapackage.json` is missing or invalid, names are duplicated, or no usable element row remains, so that I never work on a misleading model.
85. As a modeller, I want a Result refused when every file was skipped, so that an empty Result can't be selected.
86. As a modeller, I want Refused input to stay listed in its selector with ✖ and the reason as tooltip, and inputs with warnings to show ⚠ n, so that I see problems before selecting.
87. As a modeller, I want a banner only for refusal on selection, Dashboard-file refusal and the <50 % match case, so that banners stay meaningful.
88. As a modeller, I want each Input Warning logged once per parse in the terminal, so that I can grep the log.
89. As a modeller, I want files not named `<stem>-scalars.csv` / `<stem>-sequences.csv` ignored with a log line only, so that stray files don't produce warnings.
90. As a modeller, I want multi-period scalar files skipped with an Input Warning, so that an unsupported shape is explained.

## Implementation Decisions

- **Dependencies**: `dash`, `dash-cytoscape`, `pandas` (numpy comes with it; plotly sends arrays as base64 typed arrays). pydantic via dash. No oemof / oemof-tabular runtime dependency, no npm build step, no extra grid/resampling packages. Dev: `pytest`, `ruff`. Build backend `uv_build`. `requires-python >=3.12`, tested on 3.12 and 3.14. A Dash smoke test on 3.14 goes into the first build issue.
- **Modules** (`src/oemof_dashboard/`), no further layers:
  - **datapackage** — pure reader. `read(path)` returns a Datapackage: Buses, Components (name, type, resource, Parameters), Connections (Component ↔ Bus, undirected), Input Sequence references (resource, column) with broken flag, Input Sequence access by (resource, column), and its Input Warnings; or a Refused input with reason.
  - **result** — pure reader plus matching. `read(path)` returns a Result: Result Entries (stem → Result Scalars by variable, Result Sequences by column) and Input Warnings; or a Refused input. A matching function takes a Result and a Datapackage and returns, per Result Entry, either a Flow (from, to) / node split or an unmatched reason, plus the match ratio, Flows not in the Datapackage, and Components without Outcomes.
  - **charts** — pure figure builders: (chart config, loaded Datapackage, Results in the Result Selection) → plotly Figure plus notices. Holds all chart rules: series = list × Result Selection, "(missing)" legend entries, dash style / subplot / group per type, duration curve sorting, Σ flow, Sankey, Bus balance sign/stack order/residual, palette order and overrides. No Dash imports.
  - **dashboard_file** — pydantic model, `version: 1`.
  - **app** — layout and callbacks only; delegates to the modules above.
  - **cli** — argument parsing, discovery, launch.
- **Parsing cache**: `functools.lru_cache` keyed on (path, mtime) around the readers; discovery is a cheap `listdir` on every page load; parsing is lazy on selection.
- **Result addressing**: Outcome = Result × Result Entry (file stem as written) × variable. Splitting into (from, to) or (node, None) only against a selected Datapackage, both sides must be Datapackage names; 0 or >1 valid splits → unmatched. Without a Datapackage, Results are a flat Result Entry list.
- **Flow direction** comes only from Result Flows; a Connection carries 0, 1 or 2 Flows.
- **Chart model**:
  - kinds and types: sequence (line, stacked_area, duration_curve), scalar (bar), system (sankey, bus_balance). Kind fixed at creation, type switchable within kind.
  - sequence/scalar config: kind, type, optional title, series list, optional per-item hex colour overrides, width `half | full`.
  - sankey config: kind, type, optional Bus filter, width. bus_balance config: kind, type, exactly one `bus`, width.
  - series addresses: Result Entry × variable; Input Sequence = Datapackage × resource × column (sequence charts only).
  - not stored: axis ranges, log scale, per-chart Result override.
- **Dashboard file**: `{version: 1, result_selection?, datapackage?, charts: [ordered chart configs]}`. Result Selection and Datapackage are non-binding defaults. Invalid → refused whole. Loading replaces, never merges.
- **Layout** (prototype variant A Explorer): left pane = Datapackage selector, Result Selection, Outcome picker, "Add chart"; centre = resizable (CSS `resize`) dash-cytoscape graph above a 2-column CSS grid of chart cards; right = inspector. Graph lives in the static layout, callbacks update only `elements`; graph re-measures after resize. Chart grid via pattern-matching callbacks and `Patch()`. State in `dcc.Store`; file via `dcc.Upload` / `dcc.Download`.
- **Plotting**: `Scattergl` for sequences; real timestamps; no resampling or alignment; one y-axis.
- **CLI**: `oemof-dashboard [ROOT] [--datapackages DIR] [--results DIR] [--port 8050] [--debug]`; entry point `oemof_dashboard.cli:main`; binds `127.0.0.1`; opens browser via stdlib `webbrowser`.
- **Error policy**: as in ticket 09 tables — load what's usable, Input Warnings for skips, refuse only on unreadable root file, duplicate names or nothing usable.

## Testing Decisions

- **Good tests** exercise a module through its public interface with real files and assert on observable output (parsed model, match result, figure data/layout, validation outcome), never on private helpers or intermediate structures. Tests run against `tests/test_data` (adlershof Datapackage, 120-file adlershof Result) and small malformed fixtures written into `tmp_path` per case.
- **Seams**:
  - **datapackage reader**: Buses/Components/Connections/Input Sequence references of adlershof; every ticket-09 Datapackage case (refuse vs. warning vs. text).
  - **result reader + matching**: all adlershof Result Entries split uniquely against adlershof; unmatched reasons for 0 / >1 splits; match ratio; Flows not in Datapackage; every ticket-09 Result case; multi-period scalars skipped.
  - **charts**: per type, figure traces/subplots/legend for one and several Results; "(missing)" entries; duration curve order and NaN drop; Sankey Σ flow and notices; Bus balance signs, stack order, residual threshold, missing Bus; palette order and overrides; >4 Results and >8 WebGL warnings.
  - **dashboard_file**: round-trip of every chart type; refusal of bad JSON, schema failure, unknown version.
  - **cli**: discovery (marker files, ignored folders, missing folders, overrides) on `tmp_path` trees; argument parsing.
  - **app**: smoke test only — layout builds and the server starts (also on Python 3.14).
- **Prior art**: none in the repo yet (no code). The first build issue establishes the pytest layout; the UI prototype on branch `prototype/ui-layout` is reference for layout, not for tests.
- Workflow per issue: TDD, `pytest` and `ruff` green before commit.

## Out of Scope

- Result formats other than the current CSV folder layout (pickles, single-file scalars/sequences, solph dumps).
- Static HTML export / sharing without Python.
- Multi-user / server deployment.
- Parameter diff between two Datapackages.
- Stored links from a Result to its Datapackage (e.g. resqdb scenario YAML); name matching only.
- Manually positioned graph layout saved in the Dashboard.
- Derived comparisons (difference to a reference Result, sums), per-chart Result override, second y-axis, time-index alignment.
- Multi-period Results (skipped with an Input Warning).
- Heatmap (day×hour) and downsampling.
- A `--no-browser` flag.

## Further Notes

- Scale target: ≤ a few hundred Components, ≤ ~100k steps per sequence; above that, downsampling/heatmap become relevant.
- Research details: `research/01-result-file-naming.md` (resqdb naming, variables), `research/02-dash-building-blocks.md` (versions, WebGL limit, cytoscape layouts).
- Graph layout: start with cytoscape `cose`; try `breadthfirst` with Buses as roots or bundled `cose-bilkent` / `dagre` if Bus-centring is weak.
- Current `pyproject.toml` says `>=3.14` and has no dependencies; the first build issue fixes both.
