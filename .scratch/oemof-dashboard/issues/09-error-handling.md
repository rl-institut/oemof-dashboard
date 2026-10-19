# Error handling for malformed input

Type: grilling
Status: resolved
Assignee: Hendrik Huyskens
Blocked by: —

## Question

What does the app show and what does it refuse when a Datapackage or Result is malformed or partial? Cases: unreadable or invalid `datapackage.json`, missing or bad resource CSVs, element rows without `name`/`type`, duplicate names, Result CSVs that can't be parsed or have unexpected index/columns, empty Result folders, non-numeric values. For each case, decide whether to refuse the whole input, skip the item with a warning, or degrade silently, and where the message appears (selector, banner, inspector). Already fixed: a Datapackage without `foreignKeys` is shown unconnected with a warning; a broken Input Sequence reference is shown as broken; unmatched Result Entries are listed (see Energy system model).

## Answer

Grilled 2026-10-16. Terms: **Input Warning**, **Refused input** (see `CONTEXT.md`).

- **Policy**: load everything usable. Skip broken items, each skip recorded as an Input Warning (input, location, reason). Refuse the whole input only when its root file is unreadable, names are duplicated, or nothing usable remains. Never guess, never drop silently.
- **Where shown**:
  - Selector: Refused input stays listed with ✖ and reason in tooltip, not selectable. Input with warnings shows ⚠ n.
  - Inspector "nothing selected" summary: full Input Warning list per input, next to the unmatched list.
  - Banner: only for refusal on selection, Dashboard-file refusal, and the existing <50 % match banner.
  - Terminal log: each Input Warning once per parse (cache keyed on (path, mtime), so a fixed file re-parses on reload).
- **Datapackage**:

  | Case | Handling |
  |---|---|
  | `datapackage.json` missing / invalid JSON | refuse |
  | duplicate names in any element resource (Buses included) | refuse |
  | no usable element row at all | refuse |
  | resource CSV missing / unparseable | skip resource, warning; references into it → broken |
  | bus resource missing | Components unconnected, warning (same as no `foreignKeys`) |
  | row without `name` | skip row, warning |
  | row without `type` | keep, type "unknown", warning |
  | non-numeric scalar Parameter | shown as text, no warning |
  | non-numeric Input Sequence value | NaN (gap), one warning with count |

- **Result**:

  | Case | Handling |
  |---|---|
  | CSV unparseable / header only | skip file, warning |
  | sequences index not datetime | skip file, warning |
  | scalars not `variable_name` + exactly one value column | skip file, warning |
  | non-numeric value | NaN (gap), one warning per file with count |
  | file not named `<stem>-scalars.csv` / `<stem>-sequences.csv` | ignore, log only |
  | every file skipped | refuse |
  | sequence lengths differ across files | plot as-is, no warning |

- **Dashboard file**: invalid JSON, pydantic failure or unknown `version` → load refused, banner with reason, current charts untouched. A chart naming an unknown Bus (Bus balance) shows as missing, like a missing Outcome.
- **Out of scope**: multi-period Results (scalars with several period columns).
