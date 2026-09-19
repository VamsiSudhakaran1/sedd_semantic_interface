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
No revision adapter or canonical domain support exists yet; see
[xml_ingestion.md](xml_ingestion.md). No speculative standard mappings or entity
relationships are included. Authoritative schema evidence will be needed for adapters.

Future comparison must distinguish irrelevant XML ordering from semantically
meaningful sequence information such as message structures. Whitespace handling
must be defined per field, without silently destroying meaningful text.

Runtime version metadata comes from the installed distribution. Development uses
an editable installation. No runtime dependency or network access is needed for
help/version or XML ingestion.
