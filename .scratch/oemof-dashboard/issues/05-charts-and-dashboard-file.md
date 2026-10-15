# Chart set and Dashboard file

Type: grilling
Status: resolved
Assignee: Hendrik Huyskens
Blocked by: 02, 04

## Question

Which minimal chart types ship (lean: line, stacked area, duration curve, bar/grouped bar across Results, Bus balance), what each chart's configuration is, and what exactly a Dashboard JSON file stores (charts, their Outcomes by name, selected Datapackage and Result Selection or not (Results are one global Result Selection, see Outcome selection and comparison), layout) so it re-applies to another Result?

## Answer

Grilled 2026-10-15.

- **Kinds and types**: a chart's kind is fixed at creation. Its type can be switched within the kind, and the series list stays.
  - **sequence**: line, stacked area, duration curve
  - **scalar**: bar
  - **system**: Sankey
  - Bus balance graduates to its own ticket. Heatmap is still deferred.
- **Color**: always encodes Entry×variable / Input Sequence, never the Result. The default is the validated categorical palette, assigned in fixed order of the series list. An optional hex override can be set per chart and series item.
- **How the Result is shown per type**:
  - line, duration curve: dash style (more than 4 Results → warning)
  - stacked area: one subplot per Result, shared axes
  - bar: x groups are Results, bars in a group are Entry×variable
  - Sankey: one Sankey per Result, side by side
- **Line**: real timestamps on a shared datetime x-axis (see Outcome selection and comparison).
- **Duration curve**: values sorted descending, NaN dropped. x = rank in hours (0…n−1), no timestamps.
- **Sankey**:
  - Nodes are Buses and Components, links are Flows.
  - Link value = plain sum of the `flow` Result Sequence, trailing NaN dropped, labelled "Σ flow". Flows without `flow` get no link and are listed in a notice.
  - Optional Bus filter (empty = whole system). Node and link color follows the Bus.
  - Needs a selected Datapackage; not offered without one.
- **Chart config**: kind, type, optional title (auto otherwise), series list (Result Entry × variable; Input Sequence addresses too for sequence charts), optional color overrides, width `half | full`. Sankey holds a Bus filter instead of a series list. Not stored: axis ranges, log scale, per-chart Result override.
- **Dashboard file**:
  - `version: 1` and the charts in order (CSS grid, reordered with up/down).
  - Result Selection and Datapackage are stored as non-binding defaults: applied on load if present, a notice if missing. Input Sequence series from another Datapackage show "(missing)".
  - Validated with pydantic. An invalid file is refused whole. Loading replaces the current Dashboard; no merge.
- **WebGL limit**: more than 8 Scattergl charts → warning, no cap.
