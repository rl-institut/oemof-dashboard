# oemof Dashboard

Local tool to explore oemof energy system setups and their simulation results, for a quick overview and for investigating odd results.

## Inputs

**Datapackage**:
An energy system setup in oemof-tabular datapackage form: Components, Buses and Input Sequences. One Datapackage can have many Results.
_Avoid_: scenario, model, input data

**Result**:
The output of one solved run of a Datapackage (one folder of scalars and sequences). Runs differ by solver, constraints or edited attributes.
_Avoid_: run, output, solution

## Energy system

**Node**:
Any Bus or Component, i.e. one named element row of the Datapackage and one vertex of the network graph. A Result Entry of the form `<node>-None` holds Outcomes of the node itself rather than of a Flow.
_Avoid_: vertex, element

**Component**:
A node of the energy system other than a Bus (e.g. heat pump, storage, demand), with Parameters.
_Avoid_: element, asset; "node" when only Components are meant

**Bus**:
A node connecting Components; it carries one energy carrier.

**Connection**:
An undirected link between a Component and a Bus, declared in the Datapackage by one of the Component's bus fields. Carries zero, one or two Flows.
_Avoid_: link, edge

**Flow**:
A directed edge from one node to another (Component→Bus or Bus→Component), known from a Result. Attaches to the Connection between the same two nodes.

**Parameter**:
An attribute of a Component in the Datapackage, either a scalar value or a reference to an Input Sequence.

## Values

**Input Sequence**:
A timeseries in the Datapackage, referenced by a Component Parameter (e.g. profiles, efficiencies).
_Avoid_: profile (only one kind of Input Sequence)

**Input Scalar**:
A Component Parameter with a numeric scalar value (e.g. capacity, capacity_cost), addressed as Datapackage × Component × Parameter. Text-valued Parameters are not Input Scalars.
_Avoid_: input element, element

**Result Entry**:
A named item of a Result holding Result Scalars and/or Result Sequences; resolves to a Flow or a node only when matched against a Datapackage.
_Avoid_: stem, file

**Result Scalar**:
A single value in a Result, attached to a Flow or to a node (e.g. invest, total).

**Result Sequence**:
A timeseries in a Result, attached to a Flow or to a node (e.g. flow, storage content).

**Outcome**:
Any Result Scalar or Result Sequence picked for display, addressed as Result × Result Entry × variable; Outcomes from one or several Results can be compared together.

## Views

**Result Selection**:
The set of Results currently compared; every chart shows its Outcomes for each Result in it.

**Bus balance**:
For one Bus, its incoming Flows against its outgoing Flows over time, per Result.

**Dashboard**:
A saved, reloadable arrangement of charts.

## Input problems

**Input Warning**:
A defect found while reading a Datapackage or Result that skips one item (row, resource, file) but keeps the rest of the input usable. Listed with the input, never silently dropped.
_Avoid_: issue, error

**Refused input**:
A Datapackage or Result that can't be used at all (root file unreadable, duplicate names, nothing usable left). Stays listed in its selector with the reason, but can't be selected.
_Avoid_: broken, invalid
