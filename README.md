# sema-sedd

A local-first semantic explorer and comparison engine for semiconductor equipment
interfaces represented by SEMI E172 SEDD files. The product name is temporary.

## Current scope

Prompts 0–4 establish the architectural contract, Python package foundation,
reference observations, secure XML ingestion, and an XML-independent canonical model.
The CLI supports `sedd --help` and `sedd --version` (also `python -m sema_sedd`).
The library can ingest local SEDD XML and infer an E172-0225 revision hint from
`xsi:schemaLocation`. The model library provides immutable typed entities, explicit
reference/unknown states, and deterministic canonical JSON. Revision adapters,
runtime XSD validation, semantic matching, graph operations, and reports remain
unimplemented. See [docs/canonical_model.md](docs/canonical_model.md) for the API,
identity boundaries, and architecture review.
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

The application operates offline and read-only on inputs. The library XML loader
rejects DTDs and entity declarations, enforces byte and structural limits, and
never resolves external resources. Its revision hint is not proof of schema
validity or E172 conformance. See [docs/xml_ingestion.md](docs/xml_ingestion.md)
for its API and limits.

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
semantic design questions are explicitly pending. The canonical model is now
available; converting XML into that model still requires a revision adapter.

To reproduce the reference checks, place the original supplied XSDs and sample in
`work/references/`, then run:

```sh
python -m pip install -e ".[references]"
python tools/validate_reference_fixtures.py --references work/references --sample work/references/SEDD_TrackSys_Model404_0225.xml --output docs/e172_validation_results.json
```

The utility uses only pinned local schemas and performs no network requests.
The original reference inputs are intentionally excluded from version control.
