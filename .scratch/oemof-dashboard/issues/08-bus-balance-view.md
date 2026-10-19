# Bus balance view

Type: grilling
Status: resolved
Assignee: Hendrik Huyskens
Blocked by: 03, 05

## Question

How is a Bus balance computed and shown: which Flows count as in/out of a Bus (direction from Result Flows only, see Energy system model), sign convention, how storages (2 Flows on one Connection) and unmatched Result Entries are treated, whether it is a chart type in the sequence kind (e.g. stacked area with in above / out below zero) or its own view, how it handles several Results in the Result Selection, and whether a residual/imbalance series is shown.

## Answer

Grilled 2026-10-16 against `tests/test_data/results/adlershof` (every Bus has `<bus>-excess` / `<bus>-shortage` Components; storages have one in and one out Flow plus a node entry `storage_content`; `flow` values are ≥ 0).

- **Placement**: it is a new type in the **system** kind, next to Sankey. Its config holds exactly one Bus name instead of a series list. It needs a selected Datapackage. The kind is fixed, so a chart can't switch between Sankey and Bus balance.
- **Flows counted**: every split Flow with `to == Bus` (in) or `from == Bus` (out), variable `flow`. This includes Flows marked "not in Datapackage". Unmatched Result Entries are left out and listed in a notice. A Bus with no Flows in a Result gets an empty subplot and a "(missing)" notice.
- **Sign**: in is positive, stacked above zero. Out is negative, stacked below.
  - Storage needs no special case: its charge Flow is out, its discharge Flow is in. `storage_content` is not shown.
  - Excess and shortage are ordinary Components, with no highlighting.
- **Several Results**: one subplot per Result with shared axes, same as stacked area.
- **Residual**: Σin − Σout is drawn as a line only when max |residual| > 1e-6 × max Flow value. Otherwise no line is drawn.
- **Series**: one per Flow, labelled with the other node. Color follows the usual rule (one per Result Entry, palette order). Stack order is by Σ flow descending over the whole Result Selection, so it is the same in every subplot.
- **Entry point**: an "Add Bus balance" button in the inspector of a selected Bus, plus the chart menu.
- **Dashboard file**: `{kind: system, type: bus_balance, bus, width}`. If the Bus is not in the current Datapackage, the chart shows "(missing)".
- **No scalar/total version**: Sankey with a Bus filter covers totals.
