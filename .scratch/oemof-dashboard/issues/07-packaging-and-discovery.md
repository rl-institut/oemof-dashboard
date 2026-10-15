# Packaging, launch and data discovery

Type: grilling
Status: open
Blocked by: 02

## Question

How is the app launched and where does it find data: CLI shape (`oemof-dashboard <root>` with `datapackages/` + `results/`, or arbitrary paths), how Datapackages and Results are discovered/validated, final dependency list in `pyproject.toml` (dash, plotly, extras from research; pandas yes/no), Python version (pyproject says ≥3.14 — check Dash support), and module layout (readers vs. app) for testability.
