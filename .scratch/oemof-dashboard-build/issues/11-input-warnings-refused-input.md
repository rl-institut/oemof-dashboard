# 11: Input Warnings and Refused input

**What to build:** Malformed Datapackages and Results load as far as usable. Every skipped item becomes an Input Warning (input, location, reason), shown as ⚠ n in the selector, listed in the inspector "nothing selected" summary and logged once per parse. Input that can't be used at all stays listed as Refused input with ✖ and the reason, not selectable.

**Blocked by:** 05 — Matching Results to the Datapackage

**Status:** ready-for-agent

- [ ] Datapackage refused when `datapackage.json` missing/invalid JSON, duplicate names in any element resource (Buses included), or no usable element row
- [ ] Datapackage warnings: resource CSV missing/unparseable (skip; references into it → broken), bus resource missing (unconnected), row without `name` (skip), row without `type` (kept as "unknown"), non-numeric Input Sequence values (NaN, one warning with count)
- [ ] Result warnings: CSV unparseable/header only, sequences index not datetime, scalars not `variable_name` + exactly one value column (incl. multi-period), non-numeric values (NaN, one warning per file with count) — each skips the file
- [ ] Files not named `<stem>-scalars.csv` / `<stem>-sequences.csv` ignored, log only; every file skipped → Result refused; differing sequence lengths plotted as-is
- [ ] Selector: ✖ + reason tooltip for Refused input (not selectable), ⚠ n for inputs with warnings
- [ ] Banner on selecting refused input; each warning logged once per parse
- [ ] Tests: every case in both tables on `tmp_path` fixtures through the public reader interfaces
