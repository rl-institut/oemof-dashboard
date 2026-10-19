# 12: Dashboard file save and load

**What to build:** The modeller downloads the current chart arrangement as a Dashboard JSON file and later uploads it — against the same or other Results — to restore it. Stored Result Selection and Datapackage are applied if present; anything not present shows as "(missing)". A bad file is refused with a banner and the current charts stay untouched.

**Blocked by:** 06 — Stacked area, duration curve and Input Sequences; 07 — Bar chart; 08 — Sankey; 09 — Bus balance

**Status:** ready-for-agent

- [ ] pydantic model `version: 1`: optional Result Selection and Datapackage (non-binding defaults), ordered charts with every chart type's config (series/colour overrides/title/width; Sankey Bus filter; Bus balance `bus`)
- [ ] Download via `dcc.Download`, upload via `dcc.Upload`; state in `dcc.Store`
- [ ] Loading replaces the current Dashboard, never merges
- [ ] Missing stored Results/Datapackage → notice; missing Outcomes, Input Sequences and Buses → "(missing)"
- [ ] Invalid JSON, schema failure or unknown `version` → refused whole, banner with reason, current charts untouched
- [ ] Not stored: axis ranges, log scale, per-chart Result override
- [ ] Tests: round-trip of every chart type; refusal of bad JSON, schema failure, unknown version
