# 09: Bus balance chart

**What to build:** For a selected Bus the modeller clicks "Add Bus balance" in the inspector (or uses the chart menu) and sees incoming Flows stacked above zero and outgoing Flows below, one subplot per Result, with a residual line only when the Bus doesn't balance.

**Blocked by:** 05 — Matching Results to the Datapackage

**Status:** ready-for-agent

- [ ] System kind with type bus_balance; config holds exactly one Bus name; needs a selected Datapackage
- [ ] Counts every split Flow with `to == Bus` (in, positive) or `from == Bus` (out, negative), variable `flow`, including "not in Datapackage" Flows; unmatched Result Entries left out and listed in a notice
- [ ] No special cases for storage, excess, shortage; `storage_content` not shown
- [ ] One series per Flow, labelled with the other node; stack order by Σ flow descending over the whole Result Selection, same in every subplot
- [ ] Residual Σin − Σout drawn only when max |residual| > 1e-6 × max Flow value
- [ ] Bus with no Flows in a Result → empty subplot + "(missing)" notice; Bus not in the Datapackage → "(missing)"
- [ ] Tests: figure builder signs, stack order, residual threshold (balanced adlershof Bus vs. `tmp_path` imbalanced fixture), missing Bus, several Results
