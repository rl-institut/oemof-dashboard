# 06: Stacked area, duration curve and Input Sequences in sequence charts

**What to build:** Sequence charts gain the stacked area and duration curve types, and the modeller can add Input Sequences (Datapackage × resource × column) as series next to Result Sequences, e.g. a heat demand profile against the dispatch it drives.

**Blocked by:** 03 — Datapackage → network graph and inspector; 04 — Chart card editing and grid arrangement

**Status:** ready-for-agent

- [ ] Stacked area: one subplot per Result, shared axes
- [ ] Duration curve: values sorted descending, NaN dropped, x = rank in hours (0…n−1); Result by dash style
- [ ] Input Sequences selectable in sequence charts (picker and series multi-select), not multiplied over Results, coloured in the same palette order
- [ ] Non-numeric Input Sequence values → NaN gap
- [ ] Input Sequence from a Datapackage other than the selected one → "(missing)"
- [ ] Tests: figure builder for both types with one/several Results; duration ordering and NaN drop; Input Sequence series appear once
