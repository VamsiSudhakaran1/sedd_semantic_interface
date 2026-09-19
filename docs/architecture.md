# Foundation boundaries

The master product contract is the architectural invariant. Implement increments
sequentially; the supplied attachment includes only prompts 0 and 1 in full.

| Package | Planned responsibility |
| --- | --- |
| parser | Bounded secure XML loading and revision detection, without network access |
| adapters | Evidence-backed revision-specific extraction, initially E172-0225 |
| model | CanonicalEquipmentInterface, provenance, unknowns and unresolved references |
| graph | Traverse only relationships supported by canonical evidence |
| compare | Deterministic matching with recorded reasons and semantic changes |
| report | Machine-readable and escaped human-readable output |
| cli | User-facing commands over these layers |

The CLI currently supports help/version. The parser package now provides bounded,
offline XML ingestion with source positions and a non-authoritative revision hint.
The model package provides immutable canonical objects, provenance, explicit
references and unknowns, and versioned deterministic JSON. It imports no XML or
parser types. `CanonicalEquipmentInterface` aliases `EquipmentInterface`.
Revision adapters and identity/reference resolution remain unimplemented. See
[xml_ingestion.md](xml_ingestion.md) and [canonical_model.md](canonical_model.md)
for the public boundaries and the model architecture challenge. Source evidence
and local keys must be supplied explicitly; no relationships are inferred.

Future comparison must distinguish irrelevant XML ordering from semantically
meaningful sequence information such as message structures. Whitespace handling
must be defined per field, without silently destroying meaningful text.

Runtime version metadata comes from the installed distribution. Development uses
an editable installation. No runtime dependency or network access is needed for
help/version, XML ingestion, or canonical model construction/serialization.
