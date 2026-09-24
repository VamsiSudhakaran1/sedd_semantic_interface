# sema-sedd

A local-first semantic explorer and comparison engine for semiconductor equipment
interfaces represented by SEMI E172 SEDD files. The product name is temporary.

## Current scope

Prompts 0–7 establish the architectural contract, Python package foundation,
reference observations, secure XML ingestion, a canonical model, revision adapters,
E172-0225 entity conversion, and conservative reference resolution.
Prompt 9 adds `sedd inspect FILE` with deterministic text/JSON summaries and exact
entity filters. Prompt 10 adds `sedd explore FILE ENTITY` with exact selectors,
incoming and outgoing relationships, deterministic JSON, and traversal bounded to
depth 0–8. The CLI also supports `sedd --help` and `sedd --version` (including through
`python -m sema_sedd`).
Prompt 11 adds the canonical `match_interfaces(old, new)` API with recorded identity
evidence, categorical confidence, explicit collisions/conflicts, and implementation
ID changes established by verified WKN continuity.
Prompt 12 adds `compare_interfaces(old, new)` with typed semantic changes,
documentation/interface classification, matching-aware relationship deltas,
explicit uncertainty, and deterministic change JSON.
Prompt 13 attaches separate before/after dependency context to every entity
change, using resolved graph evidence and factual counts without risk scoring.
Prompt 14 adds `sedd compare OLD NEW` with text/JSON sections, canonical type
filtering, documentation opt-in, and exit status based only on execution success.
Prompt 15 adds a versioned machine-readable report API with public change codes,
a bundled JSON Schema, and deterministic snapshots.
Prompt 16 adds `sedd report OLD NEW --html FILE`, producing a self-contained,
offline HTML comparison with search, filters, source evidence, and diagnostics.
The library can ingest local SEDD XML and infer an E172-0225 revision hint from
`xsi:schemaLocation`. The model library provides immutable typed entities, explicit
reference/unknown states, and deterministic canonical JSON. An explicit adapter
registry now maps E172-0225 structures into that model and preserves unsupported
content with diagnostics. The graph package now indexes exact identities and produces
an exhaustive three-state relationship model. Runtime XSD validation and general
graph APIs remain unimplemented.
See [docs/canonical_model.md](docs/canonical_model.md) for the API,
identity boundaries, and architecture review.
See [docs/revision_adapters.md](docs/revision_adapters.md) for `load_interface()`,
revision selection, extension preservation, and registering other adapters.
See [docs/e172_entity_parser.md](docs/e172_entity_parser.md) for the complete
entity mapping and its explicit non-resolution boundary.
See [docs/reference_resolution.md](docs/reference_resolution.md) for index keys,
resolution states, and the audited no-assumption rules.
See [docs/inspect_cli.md](docs/inspect_cli.md) for inspect output, filters, and its
versioned JSON contract.
See [docs/explore_cli.md](docs/explore_cli.md) for selectors, bounded traversal,
relationship visibility, and its versioned JSON contract.
See [docs/entity_matching.md](docs/entity_matching.md) for cross-version identity
policy, evidence precedence, WKN trust boundaries, and ambiguity handling.
See [docs/semantic_changes.md](docs/semantic_changes.md) for the semantic change
API, coverage, ordering rules, and a reproducible comparison with XML diff output.
See [docs/change_dependency_context.md](docs/change_dependency_context.md) for
dependency paths, evidence, counts, exclusions, and before/after context.
See [docs/compare_cli.md](docs/compare_cli.md) for compare sections, flags,
the JSON contract, and exit-status behavior.
See [docs/json_report_contract.md](docs/json_report_contract.md) for the standalone
machine-readable report API, public change IDs, and bundled JSON Schema.
See [docs/html_report.md](docs/html_report.md) for HTML report generation and its
offline review controls.
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
available, and E172-0225 XML can now be mapped into it through the registry.
Complete compound-format interpretation and authoritative WKN vocabulary
verification remain pending. Cross-version identity matching is implemented with
the explicit evidence policy documented above.

To reproduce the reference checks, place the original supplied XSDs and sample in
`work/references/`, then run:

```sh
python -m pip install -e ".[references]"
python tools/validate_reference_fixtures.py --references work/references --sample work/references/SEDD_TrackSys_Model404_0225.xml --output docs/e172_validation_results.json
```

The utility uses only pinned local schemas and performs no network requests.
The original reference inputs are intentionally excluded from version control.
