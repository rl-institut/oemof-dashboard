# 02: Result → line chart without a Datapackage

**What to build:** The modeller selects one or more Results as the Result Selection, finds an Outcome (Result Entry × variable) in the searchable picker, and adds a line chart. The chart shows the chosen Outcomes for every Result in the Result Selection; changing the Result Selection re-applies all charts. Works with no Datapackage selected; the inspector "nothing selected" summary lists the Result Entries. Introduces the pure result reader and the pure figure-builder module (no Dash imports) as test seams.

**Blocked by:** 01 — Walking skeleton

**Status:** ready-for-agent

- [ ] Result reader: Result Entries (file stem as written) with Result Scalars by `variable_name` and Result Sequences by column; datetime index; 8761st row kept as read
- [ ] Reader parse cached with `functools.lru_cache` keyed on (path, mtime); parsed lazily on selection
- [ ] Picker lists Result Entry × variable, filtered to the Result Selection, searchable
- [ ] Line chart: series = Entry×variable list × Result Selection; `Scattergl`; real timestamps on shared datetime x-axis; one autoscaled y-axis
- [ ] Colour encodes Entry×variable in fixed palette order (validated categorical palette); Result encoded by dash style; >4 Results → warning
- [ ] Outcome missing from a Result → legend entry suffixed "(missing)", no trace, rest renders
- [ ] Tests: reader against adlershof Result; figure builder for one/several Results, "(missing)", dash styles, palette order
