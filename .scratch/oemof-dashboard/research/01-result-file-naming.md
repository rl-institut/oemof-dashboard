# Research 01: Result file naming → Flows and nodes

Ticket: `issues/01-result-file-naming.md`. Sample: `results/adlershof_2050_mean_rcp85_dummy/` (120 files) against `datapackages/adlershof_dummy`.

## TL;DR

- **The writer is resqdb, not oemof-tabular.** `resqdb/export.py::store_results_in_folder` iterates `oemof.solph` `processing.results()` (here called as `m.results()`) and writes `f"{nodes[0]}-{nodes[1]}-scalars.csv"` (only if scalars are non-empty) and `f"{nodes[0]}-{nodes[1]}-sequences.csv"` (always) with `sep=";"`. [resqdb export.py](https://github.com/rl-institut/resqdb/blob/main/export.py), [resqdb simulation.py](https://github.com/rl-institut/resqdb/blob/main/simulation.py), [resqdb main.py](https://github.com/rl-institut/resqdb/blob/main/main.py). Checked at local commit `5aefe08`.
- **No documented split rule.** The name is just `str(from_node) + "-" + str(to_node)` joined with `-`, which is also allowed inside labels. Nothing escapes it, and nothing documents it beyond the f-string.
- **(a) With the Datapackage node names the split is unambiguous for all 120 files (85 distinct stems).** Every stem has exactly one split where both sides are known names, or the right side is `None`.
- **(b) Without the Datapackage:** bus names alone leave 19/85 stems with two candidates, all of the form `<bus>-<x>-<bus>`. Two tie-breaks resolve all of them correctly: prefer the component label that also appears in another file, otherwise prefer the `<bus>-…`-prefixed label. That is a naming-convention heuristic, not a rule. The file names alone don't reveal which nodes are buses, and the file contents hold no node names.

## How the layout is produced

1. `simulation.simulate_datapackage` builds `EnergySystem.from_datapackage(...)` with oemof-tabular facades (plus resqdb's own heat-pump facades), solves it with CBC and returns `output_data = m.results()`, which is `oemof.solph.processing.results`. Source: [resqdb simulation.py](https://github.com/rl-institut/resqdb/blob/main/simulation.py).
2. `processing.results` returns a dict keyed by oemof tuples. Pyomo variables indexed by a flow give `(from_node, to_node)`. Variables indexed by a single node become `(node, None)`. Source: [solph v0.5.2 processing.py](https://github.com/oemof/oemof-solph/blob/v0.5.2/src/oemof/solph/processing.py):
   ```python
   df_dict = {k if len(k) > 1 else (k[0], None): v[...] for k, v in df.groupby("oemof_tuple")}
   ```
   resqdb's venv pins `oemof.solph 0.5.2.dev1`.
3. The f-string calls `str()` on each key part. `oemof.network` `Entity.__str__` returns `str(self.label)` ([oemof.network entity.py](https://github.com/oemof/oemof-network/blob/dev/src/oemof/network/network/entity.py)). oemof-tabular maps the Datapackage `name` field to `label` (`attributemap ... {"name": "label"}` in [oemof-tabular datapackage/reading.py](https://github.com/oemof/oemof-tabular/blob/dev/src/oemof/tabular/datapackage/reading.py)). So file name parts are exactly the Datapackage `name` values, and the literal `None` marks a node Result.
4. The Result folder name is the resqdb scenario file name, not the Datapackage name (`export.store_results_in_folder(str(file), output_data)` in `main.py`). The scenario YAML links the two, e.g. `scenarios/adlershof_2050_mean_rcp85_dummy.yaml` → `datapackage: adlershof_dummy`. This bears on the open "Linking metadata" point in `map.md`.
5. resqdb also writes the same data to its database, with `from_node` and `to_node` as **separate columns** (`export.store_scenario_results`). That export has no ambiguity, but it isn't in the CSV layout.

Not involved: `oemof.tabular.tools.postprocessing.write_results` and oemoflex `ResultsDataPackage` (used by oemof-B3 / Energy-System-Adlershof) write different layouts (per bus, per component type, `by_variable`).

## File naming rule (as observed + derived from source)

| Pattern | Meaning |
|---|---|
| `<from>-<to>-sequences.csv` | Flow from node `<from>` to node `<to>` (Component→Bus or Bus→Component) |
| `<from>-<to>-scalars.csv` | Scalar variables of that Flow. Written only when non-empty, i.e. for investment flows (35 files here) |
| `<node>-None-sequences.csv` / `-scalars.csv` | Node-level variables (`(node, None)`). Here these are only the 5 storages (`battery_small`, `battery_large`, `storage_aquifer`, `storage_pressure`, `storage_buffer`) |

Observations from the sample:
- All 8 buses (`aquifer, cool_process, cool_space, electricity, gas, heat_central, heat_decentral, heat_lt_central`) are single tokens without `-`. 41 of 66 node names contain `-`.
- Every Flow touches exactly one Bus. This is a structural oemof rule: Components connect only to Buses.
- No `<bus>-None-*` files exist, because the model was solved without duals. If `model.dual` were set, solph would add `(bus, None)` sequences with a `duals` column ([processing.py](https://github.com/oemof/oemof-solph/blob/v0.5.2/src/oemof/solph/processing.py)). That would list the buses without a Datapackage, but it isn't the case here.
- `aquifer-heat_exchanger` is a Component (in `conversion.csv`) whose name starts with a bus name. That is why `aquifer-heat_exchanger-aquifer` and `heat_central-aquifer-heat_exchanger` both occur.

## Empirical split test

Script (throwaway): `/tmp/claude-1001/-home-hendrik-RLI-oemof-dashboard/e803ec8b-5949-449a-8952-262d67c51f01/scratchpad/split_names.py`. For every stem (filename minus `-scalars.csv` / `-sequences.csv`) it tries every split at a `-`.

| Strategy | Stems with 1 candidate | 2 candidates | Notes |
|---|---|---|---|
| (a) both sides ∈ Datapackage `name`s (all `elements/*.csv` incl. `bus.csv`), right side may be `None` | 85/85 | 0 | All 66 Datapackage names occur. Adding the "exactly one Bus" rule changes nothing |
| (b1) bus names only + "exactly one side is a Bus, or right side is `None`" | 66/85 | 19 | All ambiguities are `<bus>-<x>-<bus>`, e.g. `heat_central-gas_boiler-heat_central` → `(heat_central-gas_boiler, heat_central)` or `(heat_central, gas_boiler-heat_central)` |
| (b2) no names at all; guess buses as tokens that are both first and last segment of some stem | fails | — | Picks up storages and heat pumps (e.g. `heatpump_mt`, `pth`) as "buses". 30 stems get no valid split |
| (b3) = (b1) + tie-breaks: prefer the component label also seen as a side in another file, else the `<bus>-`-prefixed label | 85/85, matches (a) | 0 | The second tie-break relies on the naming convention `<carrier>-<tech>` used in these Datapackages, not on any rule |

The 19 (b1) ambiguous stems are the `shortage` (7), `import` (3), `solarthermal` (2), `gas_boiler` (2) and `compression`/`absorption` (3) Components, plus `aquifer-heat_exchanger`. Single-flow sources such as shortage and import can't be resolved from other files. Only the prefix convention resolves them.

Content doesn't help. Scalars files carry only variable names. Sequences files carry only a time index and `flow` / `storage_content`. Neither direction nor node names can be read from values.

### Residual risk even with a Datapackage

The scheme is ambiguous in general. With bus `a`, components `b-c` and `a-b`, and bus `c`, the stem `a-b-c` splits validly both ways, and both splits pass the one-Bus rule. This doesn't occur in the sample. The reader should detect more than one candidate and report it, not pick silently. The clean fix is upstream in resqdb: a separator that labels can't contain, or a written index file. The DB export already stores the nodes separately.

## Variables

### Scalars files (`variable_name;2050-01-01`)

Format: the index name is `variable_name` and there is one value column. The column header `2050-01-01` is **not a period**. It is the name of the scalars Series, which is the first timestamp, because `divide_scalars_sequences` takes `.dropna().iloc[0]` of the pivoted frame. pandas writes a midnight Timestamp as a date-only header (verified). This is a standard, not multi-period, model: multi-period would use `period_scalars`. Source: [processing.py `divide_scalars_sequences`](https://github.com/oemof/oemof-solph/blob/v0.5.2/src/oemof/solph/processing.py).

| `variable_name` | Count | Occurs in | Meaning (solph) |
|---|---|---|---|
| `invest` | 35 | Flow files of investment flows, and `<storage>-None` | Newly invested capacity. Flow: nominal power. Storage node: storage (energy) capacity |
| `total` | 35 | same | Total capacity = `invest` + `existing` (`_total_storage_capacity_rule` in `components/_generic_storage.py`, analogous in `flows/_investment_flow_block.py`) |
| `init_content` | 5 | `<storage>-None` only | Initial storage content variable of `GenericInvestmentStorageBlock` |

### Sequences files (`;<column>`, first column is the unnamed time index)

| Column | Count | Occurs in | Meaning |
|---|---|---|---|
| `flow` | 80 | all Flow files | Flow value per time step (power; energy per step with hourly steps) |
| `storage_content` | 5 | `<storage>-None` | Storage content (energy) at each time point |

Each sequences file has 8761 rows: 2050-01-01 00:00 to **2051-01-01 00:00**. The last row is empty for `flow`. solph adds this extra time point when `remove_last_time_point=False` (the default, used by `m.results()`). Interval variables (`flow`) get NaN there, while time-point variables (`storage_content`) may have a value. The reader should keep or drop that row deliberately. Source: [processing.py `_extract_standard_model_result`](https://github.com/oemof/oemof-solph/blob/v0.5.2/src/oemof/solph/processing.py).

Other names that can appear with other Datapackages or settings, but don't appear here (same source): `duals` on `(bus, None)` when duals are enabled; `status`, `startup`, `shutdown` for nonconvex flows; `old`, `old_end`, `old_exo` plus `period_scalars` in multi-period models. A reader should treat variable names as open-ended.

## Implications for the Dashboard (input to later tickets, not decisions)

- Parsing is deterministic with a Datapackage: build the node set from `bus.csv` + `elements/*.csv` `name`, split at the unique valid `-`, and flag anything with 0 or more than 1 candidates.
- Without a Datapackage, a heuristic split is feasible (b3) but must be marked as a guess. Alternatively, treat a Result as a flat list of stems until a Datapackage is linked.
