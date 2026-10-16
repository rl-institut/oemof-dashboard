# UI layout and navigation prototype

Type: prototype
Status: resolved
Assignee: Hendrik Huyskens
Blocked by: 02, 03

## Question

How should the app look and flow: Datapackage/Result selectors, network graph, Component Parameter panel, Input Sequence viewer, Result/Outcome browser, chart grid — and how does the user jump between a Component in the Datapackage and its Outcomes in a Result (and back)? Rough Dash prototype on the adlershof data to react to.

## Comments

Prototype: branch `prototype/ui-layout`, file `.scratch/oemof-dashboard/prototypes/06-ui-layout/ui_layout_prototype.py` — variants A Explorer / B Tabs / C Canvas via `?variant=`; run `uv run --with dash --with dash-cytoscape python .scratch/oemof-dashboard/prototypes/06-ui-layout/ui_layout_prototype.py`.

## Answer

Prototyped 2026-10-16 on adlershof (3 variants: A Explorer, B Tabs, C Canvas). **A Explorer wins**, with two enhancements.

- **Layout**: three fixed panes.
  - left: Datapackage selector, Result Selection, Outcome picker, "Add chart"
  - centre: network graph on top, chart grid (2 columns, auto-fill) below
  - right: inspector
  No tabs and no drawers.
- **Graph pane is resizable**: the user drags it taller or shorter (native CSS `resize`). After a resize the graph re-measures its container. Graph edges carry Σ flow and arrows for the first Result in the Result Selection.
- **Inspector**: one combined panel for the selected Component or Bus.
  - Datapackage side: type/resource, Connections (as links to the Bus), Parameters, Input Sequences.
  - Result side: Outcomes per Result Entry × variable, each with "+ chart", and "in n/m Results" when an Outcome is missing from some Results.
  - With nothing selected: a summary of Result Entries and the unmatched list.
- **Component → Outcomes**: clicking a graph node fills the inspector and pre-filters the picker.
- **Outcome → Component**: chips in the chart header link to the chart's nodes. Clicking one selects that node and highlights it in the graph.
- **Charts are editable after creation**: each chart card has a multi-select of its series. Options are limited to the chart's kind: Result Sequences and Input Sequences for sequence charts, Result Scalars for scalar charts. An emptied chart stays. A chart can also be removed with ×.
- **Without a Datapackage**: the graph is empty, and the picker and inspector summary still work.
