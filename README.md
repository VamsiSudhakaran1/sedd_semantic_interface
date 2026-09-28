# sema-sedd

Explore and compare semiconductor equipment interfaces from local SEDD XML files.
The tool builds a typed canonical model, resolves references, records evidence
behind entity matches, and generates text, JSON, and offline HTML reports.

Release `0.1.0` supports **E172-0225** through the default adapter. Inputs are
read-only; processing requires no network, account, backend, or AI. The original
synthetic examples require no proprietary files.

## Install

Use Python 3.12+ with Expat 2.7.2+. From a checkout:

```sh
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# POSIX shell: source .venv/bin/activate
python -m pip install .
sedd --version
```

[Installation](docs/installation.md) covers Windows/POSIX commands, editable
development, wheels, offline use, and troubleshooting. `python -m sema_sedd`
supports the same commands as `sedd`.

## Try the original examples

Run from the repository root:

```sh
sedd inspect examples/machine-v1.xml
sedd explore examples/machine-v1.xml event:1001 --depth 2
sedd compare examples/machine-v1.xml examples/machine-v2.xml --include-documentation --no-color
sedd report examples/machine-v1.xml --html interface.html
sedd report examples/machine-v1.xml examples/machine-v2.xml --html comparison.html
```

Open the HTML files locally. [Quick start](docs/quick_start.md) explains the output;
[the example walkthrough](examples/README.md) maps each intended change to evidence.
Reordered inventories, fields, and attributes leave unchanged entities unchanged.

The XML changes pressure ID `44` to `144` while retaining its fictional WKN. Raw XML
WKNs remain unverified, so the CLI reports removal/addition for that variable.
A labeled library tutorial supplies fictional registry evidence and canonical
datatype fields to demonstrate identity-preserving ID and datatype changes:

```sh
python examples/compare_demo.py > demo.json
```

This exercises the evidence API and does not verify official SEMI names. Ordinary
XML comparison also detects the wire format change `UI4` to `FP4`.

## Documentation

| Guide | Covers |
| --- | --- |
| [Quick start](docs/quick_start.md) | Inspection, exploration, comparison, local reports |
| [CLI reference](docs/cli_reference.md) | Commands, flags, selectors, JSON versions, exit status |
| [Architecture](docs/architecture.md) | Loader, adapters, canonical model, graph, comparison, reports |
| [Canonical model](docs/canonical_model.md) | Entities, identifiers, references, provenance, unknowns |
| [Matching semantics](docs/entity_matching.md) | Exact identity evidence, WKN trust, collisions and conflicts |
| [Comparison semantics](docs/semantic_changes.md) | Categories, ordered data, reconciled relationships |
| [Supported revisions](docs/supported_revisions.md) | Evidence-backed support and unsupported status |
| [Limitations](docs/limitations.md) | Interpretation, verification, output limits |
| [Security](docs/security.md) | Untrusted input, local files, output safety, resource ceilings |
| [Standards and licensing](docs/standards_licensing.md) | MIT license and independent standards status |
| [Contributing](CONTRIBUTING.md) | Setup, checks, evidence and fixture rules |

Detailed guides cover [resolution](docs/reference_resolution.md),
[dependency context](docs/change_dependency_context.md), [diagnostics](docs/diagnostics.md),
and the [JSON report contract](docs/json_report_contract.md).
The [hostile audit](docs/security_performance_audit.md) includes reproducible profiles.

## Develop

```sh
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m build
```

Read [MASTER_PRODUCT_CONTRACT.md](MASTER_PRODUCT_CONTRACT.md) before architecture
changes. CI is configured for Windows/Linux on Python 3.12-3.14. Optional reference
analysis requires separately supplied schemas; examples and required tests do not.
