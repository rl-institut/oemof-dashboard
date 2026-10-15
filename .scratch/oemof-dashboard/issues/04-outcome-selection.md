# Outcome selection and comparison

Type: grilling
Status: resolved
Assignee: Hendrik Huyskens
Blocked by: 01

## Question

How does the user address and pick Outcomes (Result × Result Entry × variable, see Energy system model) and Input Sequences, and what does comparing them mean: same Outcome across several Results, several Outcomes in one Result, mixing Input Sequences with Result Sequences in one chart? How are units/scales, differing time indices, and Outcomes missing from some Results handled?

## Answer

Grilled 2026-10-15.

- **Picking**: one searchable Outcome picker (Result Entry × variable), filtered to the Result Selection. Clicking a Component in the network graph pre-filters it. Without a Datapackage, only the picker exists.
- **Series model**: a chart holds a list of Result Entry × variable. Its series are that list × the Result Selection. So "same Outcome across Results" and "several Outcomes in one Result" are one mechanism.
- **Result Selection**: one global set of Results. All charts follow it, and changing it re-applies the whole Dashboard. Per-chart override: not now.
- **Input Sequences**: can be series in sequence charts, addressed as Datapackage × resource × column. They are not multiplied over Results.
- **No mixing**: sequence charts take Result Sequences and Input Sequences. Scalar charts take Result Scalars.
- **Units/scales**: none in the data. One autoscaled y-axis. If scales clash, make a second chart. No second y-axis.
- **Extra time point**: the 8761st row is kept as read. `flow` ends in NaN there (a gap), and `storage_content` keeps its end value.
- **Time indices**: plotted against real timestamps on a shared datetime x-axis. No alignment or resampling, so different years simply don't overlap.
- **Missing Outcome**: the legend entry is suffixed "(missing)" with no trace. Other series render normally.
- **Derived comparisons** (difference to a reference Result, sums): deferred to Not yet specified.
