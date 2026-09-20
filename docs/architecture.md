# Foundation boundaries

The master product contract is the architectural invariant. Implement increments
sequentially; the supplied attachment includes only prompts 0 and 1 in full.

| Package | Planned responsibility |
| --- | --- |
| parser | Bounded secure XML loading and revision detection, without network access |
| adapters | Evidence-backed revision-specific extraction, initially E172-0225 |
| model | CanonicalEquipmentInterface, provenance, unknowns and unresolved references |
| graph | Build exact indexes, resolve references conservatively, and expose relationship outcomes |
| compare | Deterministic matching with recorded reasons and semantic changes |
| report | Machine-readable and escaped human-readable output |
| cli | Deterministic inspect and bounded explore output, plus future user-facing commands over these layers |

The CLI supports help/version, read-only inspection, and bounded relationship
exploration in text or JSON. The parser package provides bounded, offline XML
ingestion with source positions and a non-authoritative revision hint.
The model package provides immutable canonical objects, provenance, explicit
references and unknowns, and versioned deterministic JSON. It imports no XML or
parser types. `CanonicalEquipmentInterface` aliases `EquipmentInterface`.
An explicit registry now selects E172-0225 or caller-supplied adapters.
Reference resolution is implemented as a revision-neutral graph phase; cross-version
identity matching remains unimplemented. See
[xml_ingestion.md](xml_ingestion.md) and [canonical_model.md](canonical_model.md)
for the public boundaries and the model architecture challenge.
[revision_adapters.md](revision_adapters.md) describes routing, structural mapping,
and import-boundary tests. Comparison, graph, and report packages must never
import concrete revision adapters. Source evidence
and local keys must be supplied explicitly; no relationships are inferred.
[e172_entity_parser.md](e172_entity_parser.md) records the field-level conversion
and preservation rules for the initial E172-0225 adapter.
[reference_resolution.md](reference_resolution.md) records exact index identities,
the three-state relationship model, and the audited ambiguity rules.
[inspect_cli.md](inspect_cli.md) records summary fields, exact filters, immediate
relationship output, and the deterministic inspection JSON contract.
[explore_cli.md](explore_cli.md) records exact selectors, bidirectional traversal
over resolved canonical relationships, the hard depth bound, and the deterministic
exploration JSON contract.

Future comparison must distinguish irrelevant XML ordering from semantically
meaningful sequence information such as message structures. Whitespace handling
must be defined per field, without silently destroying meaningful text.

Runtime version metadata comes from the installed distribution. Development uses
an editable installation. No runtime dependency or network access is needed for
help/version, XML ingestion, revision mapping, or canonical model construction/serialization.
