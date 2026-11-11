# 13: Datapackage values in charts, distinguishable from Result values

**What to build:** The modeller can chart Input Scalars (numeric scalar Parameters, Datapackage × Component × Parameter) in bar charts next to Result Scalars, and Input Sequences — already allowed in sequence charts — become clearly distinguishable from Result Sequences. Every chart with both kinds tells at a glance which values come from the Datapackage and which from a Result.

**Blocked by:** 06 — Stacked area, duration curve and Input Sequences; 07 — Bar chart; 12 — Dashboard file

**Status:** ready-for-agent

- [ ] Datapackage and Result values share one y-axis and one legend; they are told apart by line shape and hatching
- [ ] Input Sequences drawn as step lines (`shape="hv"`) in line, duration curve and stacked area charts; colour still from the palette, Result still by dash style
- [ ] Input Scalars selectable in bar charts (picker and series multi-select); text-valued Parameters never offered
- [ ] Input Scalars shown once in an extra x-category named after the Datapackage, leftmost, as hatched bars (`marker.pattern.shape="/"`) in the series colour
- [ ] Input Scalar from a Datapackage other than the selected one → "(missing)", as for Input Sequences
- [ ] Inspector: "+ chart" on numeric Parameters (→ bar chart) and on unbroken Input Sequences (→ sequence chart)
- [ ] Input Scalar and Input Sequence series keys stay distinguishable, so the picker, add-chart routing by kind and the Dashboard file never confuse them; existing Dashboard files still load
- [ ] System charts (Sankey, Bus balance) unchanged
- [ ] Tests: bar chart with Input Scalars and Outcomes (category, hatch, missing); step shape and one shared axis and legend in each sequence chart type; Dashboard round-trip with Input Scalars
