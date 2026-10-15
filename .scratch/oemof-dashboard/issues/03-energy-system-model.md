# Energy system model from a Datapackage

Type: grilling
Status: resolved
Assignee: Hendrik Huyskens
Blocked by: 01

## Question

How is a Datapackage read into Components, Buses, Flows, Parameters and Input Sequences? Which fields define connections (`bus`, `from_bus`, `to_bus`, `electricity_bus`, `fuel_bus`, `heat_bus`, …; `foreignKeys` in `datapackage.json` vs. column-name heuristics), how a Parameter that references an Input Sequence is detected, how Flow direction is derived per Component type, and how a Result node/Flow is matched to a Datapackage Component (including Results without a Datapackage and names present on only one side).

## Answer

Grilled 2026-10-15 against the 9 Datapackages in `resqdb/datapackages/` (all have `foreignKeys`).

- **Buses / Components**: Buses are element rows with `type == "bus"`. Every other element row is a Component.
- **Connections**: these come only from `datapackage.json` `foreignKeys` that reference the bus resource. `fields` can be a string or a list. Column names are never used as a fallback. A Datapackage without `foreignKeys` shows its Components unconnected, with a warning. Bus fields appear as Connections, not as Parameters.
- **Input Sequence references**: a `foreignKey` that points at a sequences resource marks the Parameter. Its value is a column name in that resource. An Input Sequence is identified by (resource, column). A missing column shows as a broken reference.
- **Direction**: the Datapackage gives none, so Connections are undirected and there is no per-type direction table. Direction comes only from Result Flows. One Connection carries 0, 1 or 2 Flows (a storage has 2).
- **Result addressing**: an Outcome is Result × Result Entry (file stem, as written) × variable. Splitting needs no heuristic. A stem is split into (from, to) / (node, None) only against a selected Datapackage, using the strategy (a) from the research: both sides must be names in that Datapackage. Without a Datapackage, a Result is shown as a flat list of Result Entries, with no graph.
- **Mismatches**: a stem with 0 or more than 1 valid splits goes to "unmatched", with the reason, and is never guessed. A Component with no Result Entry is shown as "no Outcomes in this Result". If fewer than about 50 % of stems match, a banner says "Datapackage likely doesn't belong to this Result". A split Flow with no matching Connection is still drawn, marked "not in Datapackage", and also listed as unmatched.
- **Glossary**: added **Connection** and **Result Entry**. Updated **Flow** (it comes from a Result and attaches to a Connection) and **Outcome** (Result × Result Entry × variable).
