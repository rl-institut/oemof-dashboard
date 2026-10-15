# Result file naming → Flows and nodes

Type: research
Status: resolved
Blocked by: —

## Question

How do Result file names (`<from>-<to>-scalars.csv`, `<node>-None-sequences.csv`, …) map to Flows and nodes, given Component names themselves contain `-` (e.g. `heat_central-gas_boiler`)? Which tool writes this layout (oemof-tabular postprocessing / custom pipeline), is there a documented rule, and can the split be resolved (a) with a Datapackage's node names, (b) without one? Also list the `variable_name` values and sequence column names that occur, and what they mean.

## Comments

Research: research/01-result-file-naming.md

## Answer

Files are written by resqdb (`export.py::store_results_in_folder`) from solph `processing.results()` as `f"{label0}-{label1}-{scalars|sequences}.csv"`; labels = Datapackage `name`, `None` = node-level key. No escaping, no documented rule. With a Datapackage's names all 120 files split uniquely; with bus names only 19/85 are ambiguous (`<bus>-<x>-<bus>`), resolvable by heuristics; without names: not reliably. Reader must surface residual ambiguity, not guess. Result folder is named after the resqdb scenario, which links `datapackage:` explicitly. Scalars: `invest`, `total`, `init_content`; sequences: `flow`, `storage_content`; 8761 rows (last = extra solph step). Detail: [research/01-result-file-naming.md](../research/01-result-file-naming.md).
