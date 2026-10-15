# Dash building blocks

Type: research
Status: resolved
Blocked by: —

## Question

Which Dash pieces cover our needs with the fewest extra dependencies: (1) a user-editable grid of N charts added/removed at runtime (pattern-matching callbacks; draggable grid libs like dash-draggable / dash-dynamic-grid-layout vs. plain CSS grid), (2) a Bus/Component network graph with auto-layout and click selection (dash-cytoscape layouts), (3) serialising and restoring app state as a JSON Dashboard file (dcc.Store, dcc.Upload/Download), (4) plotting 8760-step sequences × many series responsively (Scattergl, resampling). Report current versions, install footprint, and maintenance status of each extra package.

## Comments

Research: research/02-dash-building-blocks.md

## Answer

Only one extra package beyond dash (4.4.1; installs on Python 3.14, app run on 3.14 untested; no pandas needed). (1) Chart grid: plain CSS grid + pattern-matching callbacks + `Patch()`; reject dash-draggable (stale, dict-id bug) and dash-dynamic-grid-layout (immature). (2) Network graph: dash-cytoscape 1.0.2 (no Python deps); start with `cose`, try `breadthfirst` with Buses as roots or bundled `cose-bilkent`/`dagre`; keep the graph in the static layout and update only `elements` (Dash 4 issue #229). (3) Dashboard file: `dcc.Store` + `dcc.Download`/`dcc.Upload`, stdlib json, validated with pydantic (already a Dash dep); Dash persistence unsuitable. (4) Long sequences: `Scattergl` covers scale target; browser WebGL context limit ≈ 8 Scattergl charts per page; reject plotly-resampler (pins plotly<7, pulls pandas). Detail: [research/02-dash-building-blocks.md](../research/02-dash-building-blocks.md).
