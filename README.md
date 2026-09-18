# sema-sedd

A local-first semantic explorer and comparison engine for semiconductor equipment
interfaces represented by SEMI E172 SEDD files. The product name is temporary.

## Current scope

Prompts 0 and 1 establish the architectural contract and Python package foundation.
The CLI supports `sedd --help` and `sedd --version` (also `python -m sema_sedd`).
No XML parsing, revision support, semantic matching, graph operations, or reports
are implemented yet. The initial planned adapter target is E172-0225.
Unsupported commands exit with an argument error; they never claim successful processing.

## Development

Python 3.12 or later is required. From this repository:

```sh
python -m venv .venv
# Windows PowerShell: .venv/Scripts/Activate.ps1
# POSIX shell: source .venv/bin/activate
python -m pip install -e ".[dev]"
sedd --help
sedd --version
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m build
```

CI runs these checks on Windows and Linux, then installs the built wheel into a
separate environment and checks both the console script and module entry point.

## Architecture

Read [MASTER_PRODUCT_CONTRACT.md](MASTER_PRODUCT_CONTRACT.md) before changes.
The processing boundary is secure loader → revision detection → revision adapter →
`CanonicalEquipmentInterface` → graph / comparison / reporting. Revision-specific
XML assumptions belong in adapters. Unknown information must remain explicit.

The application will operate offline and read-only on inputs. Future parsing must
reject unsafe XML and perform no network requests. No E172 compatibility or XML
security guarantees are claimed by this foundation, which does not parse XML.

See [docs/architecture.md](docs/architecture.md) for module responsibilities and
[docs/build-prompts.md](docs/build-prompts.md) for the supplied sequential roadmap.
The repository is MIT licensed; it does not reproduce SEMI standards or imply
SEMI endorsement or certification.

## Reference analysis status

[Prompt 2 observations and coverage matrix](docs/e172_observations.md) cover the
E172/E173 schemas and the complete original TrackSys sample. The unmodified sample
passes offline XSD validation. All 26 synthetic XSD outcomes match expectations
(22 valid and 4 intentionally invalid). The sample also demonstrates unresolved
identifiers and repeated message identities despite schema validity. Remaining
semantic design questions are explicitly pending; runtime canonical processing
remains unimplemented.

To reproduce the reference checks, place the original supplied XSDs and sample in
`work/references/`, then run:

```sh
python -m pip install -e ".[references]"
python tools/validate_reference_fixtures.py --references work/references --sample work/references/SEDD_TrackSys_Model404_0225.xml --output docs/e172_validation_results.json
```

The utility uses only pinned local schemas and performs no network requests.
The original reference inputs are intentionally excluded from version control.
