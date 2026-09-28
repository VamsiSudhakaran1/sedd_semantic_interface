# Supported revisions

| Input | Default support |
| --- | --- |
| E172-0225 with evidenced namespace/root and compatible revision hint | Implemented adapter; evidenced mapping and explicit unknowns |
| Other recognizable E172 labels | Identified where possible; unsupported; no semantic fallback |
| Missing/conflicting hints | Indeterminate/unsupported unless deliberate compatible library selection is justified |
| Other namespaces/roots | Secure syntax loading; semantics need a registered supporting adapter |
| Standalone E173/SMN files | No standalone E173 input adapter; SMN structures are mapped inside E172-0225 |

A schema filename is a hint, not proof of validity. Renaming it cannot make an
unsupported format safe to interpret. The CLI has no force-revision flag. Library
selection retains the compatibility checks in [revision_adapters.md](revision_adapters.md).

Current mapping includes equipment metadata, SV/DV/EC, events, alarms, commands and
parameters, messages, formats, reports, event/report links, and standards metadata.
Unknown fields/sections are retained with diagnostics. Complete compound-format
interpretation and authoritative WKN vocabulary verification remain pending.
See [limitations](limitations.md) and [entity mapping](e172_entity_parser.md).

A future revision needs reliable technical evidence, independent observations,
original fixtures, and adapter tests. Fictional test adapters are scaffolding, not
claimed standards support. Downstream comparison/reporting use the same canonical
model. [Version resilience](version_resilience.md) documents the boundary audit.
