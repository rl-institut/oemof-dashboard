# 04: Chart card editing and grid arrangement

**What to build:** Every chart card can be refined after creation: edit its series with a multi-select limited to its kind, switch type within its kind (keeping the series list), set an optional title (auto otherwise), set width half/full, move it up/down in the 2-column grid, override a series colour with a hex value, or remove it with ×. An emptied chart stays. A warning appears with more than 8 WebGL charts on the page.

**Blocked by:** 02 — Result → line chart without a Datapackage

**Status:** ready-for-agent

- [ ] Chart config model holds kind, type, optional title, series list, optional per-item colour overrides, width `half | full`
- [ ] Grid via CSS grid + pattern-matching callbacks + `Patch()`
- [ ] Series multi-select offers only items of the chart's kind (sequence charts: Result Sequences; scalar charts: Result Scalars)
- [ ] Kind fixed at creation; type switchable within kind, series list kept
- [ ] Emptied chart stays; × removes it; up/down reorders
- [ ] >8 `Scattergl` charts → warning, no cap
- [ ] Tests: figure builder honours title default, colour overrides and kind/type rules; app smoke test still green
