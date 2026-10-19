# 10: Chart chips → graph nodes

**What to build:** Each chart header shows chips for the nodes its series belong to. Clicking a chip selects that node in the inspector and highlights it in the graph, closing the loop Outcome → Component.

**Blocked by:** 05 — Matching Results to the Datapackage

**Status:** ready-for-agent

- [ ] Chips derived from the chart's matched Result Entries (and Bus for Bus balance / Bus filter)
- [ ] Unmatched entries produce no chip
- [ ] Chip click selects the node and highlights it in the graph
- [ ] Without a Datapackage no chips are shown
- [ ] Tests: chip derivation is pure and tested on adlershof; app smoke test still green
