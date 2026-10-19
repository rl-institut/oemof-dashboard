# 08: Sankey chart

**What to build:** With a Datapackage selected, the modeller adds a system chart of type Sankey showing the energy flows of the whole system (or of one Bus via an optional filter), one Sankey per Result side by side.

**Blocked by:** 05 — Matching Results to the Datapackage

**Status:** ready-for-agent

- [ ] System kind with type sankey; config holds an optional Bus filter instead of a series list; offered only with a selected Datapackage
- [ ] Nodes = Buses and Components, links = split Flows, value = plain sum of `flow`, trailing NaN dropped, labelled "Σ flow"
- [ ] Flows without `flow` get no link and are listed in a notice
- [ ] Node and link colour follows the Bus
- [ ] One Sankey per Result, side by side
- [ ] Tests: figure builder Σ values and links against adlershof, Bus filter, notice for Flows without `flow`, several Results
