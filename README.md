# oemof Dashboard

Local Dash app to explore [oemof-tabular](https://github.com/oemof/oemof-tabular) Datapackages and their
simulation Results — for a quick overview of an energy system and for investigating odd results.

- Network graph of Buses and Components, built from the Datapackage
- Charts of Input Sequences, Result Scalars and Result Sequences, comparable across several Results
- Defects in inputs are listed as warnings instead of silently dropped; unusable inputs are shown with the reason
- Save and load dashboard layouts to/from file

Domain terms are defined in [CONTEXT.md](CONTEXT.md).

## Installation

Requires Python ≥ 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Usage

Expected folder layout:

```
project/
├── datapackages/
│   └── <name>/datapackage.json      # one subfolder per Datapackage
└── results/
    └── <name>/*-scalars.csv         # one subfolder per Result
               *-sequences.csv
```

Start the dashboard (opens http://127.0.0.1:8050/ in the browser):

```bash
uv run oemof-dashboard path/to/project
```

Options:

| Option                  | Default                 |
|-------------------------|-------------------------|
| `ROOT` (positional)     | current directory       |
| `--datapackages FOLDER` | `ROOT/datapackages`     |
| `--results FOLDER`      | `ROOT/results`          |
| `--port PORT`           | `8050`                  |
| `--debug`               | off (Dash debug mode)   |

Try it with the bundled test data:

```bash
uv run oemof-dashboard tests/test_data
```

## Development

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

See [CODING_STANDARDS.md](CODING_STANDARDS.md).
