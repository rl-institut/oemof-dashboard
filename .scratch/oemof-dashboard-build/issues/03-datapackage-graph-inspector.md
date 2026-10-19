# 03: Datapackage → network graph and inspector

**What to build:** The modeller selects a Datapackage and sees its energy system as an auto-laid-out, Bus-centred network graph in a resizable pane. Clicking a Component or Bus fills the inspector with its Datapackage side: type/resource, Connections (as links to the Bus), Parameters and Input Sequences. Without a Datapackage the graph is empty. Introduces the pure datapackage reader as test seam.

**Blocked by:** 01 — Walking skeleton

**Status:** ready-for-agent

- [ ] Reader: element rows with `type == "bus"` → Buses, all others → Components
- [ ] Connections only from `foreignKeys` referencing the bus resource (`fields` string or list), undirected; bus fields not listed as Parameters
- [ ] Datapackage without `foreignKeys` → Components unconnected, recorded as warning
- [ ] Input Sequence references from sequence `foreignKeys`, identified by (resource, column); missing column → shown as broken
- [ ] Non-numeric scalar Parameters shown as text
- [ ] Graph: dash-cytoscape, kept in static layout with only `elements` updated; Buses central (start with `cose`, try `breadthfirst`/`cose-bilkent`/`dagre`); pane resizable via CSS `resize`, graph re-measures after resize
- [ ] Clicking a node selects it in the inspector; clicking a Connection link selects the Bus
- [ ] Tests: reader against adlershof Datapackage (Buses, Components, Connections, Input Sequence references, broken reference on a `tmp_path` fixture); app smoke test still green
