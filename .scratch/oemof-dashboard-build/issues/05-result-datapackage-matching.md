# 05: Matching Results to the Datapackage

**What to build:** With both a Datapackage and a Result Selection, Result Entries are split into Flows (from, to) or nodes (node, None) against the Datapackage's names. The graph shows Flow direction arrows and Σ flow on edges for the first Result in the Result Selection. The inspector shows a selected node's Outcomes per Result Entry × variable with "+ chart" and "in n/m Results"; clicking a node pre-filters the picker. Mismatches are listed, never guessed.

**Blocked by:** 02 — Result → line chart without a Datapackage; 03 — Datapackage → network graph and inspector

**Status:** ready-for-agent

- [ ] Split only when both sides are Datapackage names; 0 or >1 valid splits → unmatched with reason
- [ ] Inspector "nothing selected" summary shows the unmatched list next to the Result Entries
- [ ] Match ratio < ~50 % → banner "Datapackage likely doesn't belong to this Result"
- [ ] Split Flow without a matching Connection → drawn, marked "not in Datapackage", also listed as unmatched
- [ ] Component with no Result Entry → "no Outcomes in this Result"
- [ ] Graph edges: arrows and Σ flow (plain sum of `flow`, trailing NaN dropped) for the first Result in the Result Selection
- [ ] Inspector Result side: Outcomes per Entry×variable, "+ chart", "in n/m Results"
- [ ] Clicking a graph node pre-filters the Outcome picker
- [ ] Tests: all adlershof Result Entries split uniquely against adlershof; unmatched reasons for 0 and >1 splits on `tmp_path` fixtures; match ratio; "not in Datapackage"; Components without Outcomes
