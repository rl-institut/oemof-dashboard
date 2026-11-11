# 13: Datapackage values in charts, distinguishable from Result values

**What to build:** The modeller can chart Input Scalars (numeric scalar Parameters, Datapackage × Component × Parameter) in bar charts next to Result Scalars, and Input Sequences — already allowed in sequence charts — become clearly distinguishable from Result Sequences. Every chart with both kinds tells at a glance which values come from the Datapackage and which from a Result.

**Blocked by:** 06 — Stacked area, duration curve and Input Sequences; 07 — Bar chart; 12 — Dashboard file

**Status:** ready-for-agent

- [ ] Legend split into two titled sections "Datapackage" and "Result" (`legendgrouptitle`) in sequence and bar charts holding both kinds
- [ ] Input Sequences drawn as step lines (`shape="hv"`) in line, duration curve and stacked area charts; colour still from the palette, Result still by dash style
- [ ] Input Scalars selectable in bar charts (picker and series multi-select); text-valued Parameters never offered
- [ ] Input Scalars shown once in an extra x-category named after the Datapackage, leftmost, as hatched bars (`marker.pattern.shape="/"`) in the series colour
- [ ] Two y-axes only when a chart holds both kinds: Datapackage values on the left axis titled "Datapackage", Result values on the right axis titled "Result"; stacked area does the same per subplot. A chart with one kind keeps one untitled left axis
- [ ] Input Scalar from a Datapackage other than the selected one → "(missing)", as for Input Sequences
- [ ] Inspector: "+ chart" on numeric Parameters (→ bar chart) and on unbroken Input Sequences (→ sequence chart)
- [ ] Input Scalar and Input Sequence series keys stay distinguishable, so the picker, add-chart routing by kind and the Dashboard file never confuse them; existing Dashboard files still load
- [ ] System charts (Sankey, Bus balance) unchanged
- [ ] Tests: bar chart with Input Scalars and Outcomes (category, hatch, axes, missing); step shape and axis split in each sequence chart type; single-kind charts keep one axis; legend sections; Dashboard round-trip with Input Scalars
