# Inspect CLI

`sedd inspect FILE` securely loads a local SEDD document, selects its revision
adapter, builds the canonical model, resolves references, and displays a read-only
summary.

```powershell
sedd inspect equipment.xml
sedd inspect equipment.xml --json
sedd inspect equipment.xml --type alarm
sedd inspect equipment.xml --type alarm --id 1001
sedd inspect equipment.xml --wkn urn:example:status
```

The document must contain enough schema-location evidence for the adapter registry
to select a revision. An unknown, contradictory, or absent revision hint produces
a controlled command error; inspection does not guess a revision from the file
name or content.

## Summary

Text and JSON output include:

- the selected SEDD revision and resolved source path;
- canonical equipment metadata;
- counts for every supported entity category, including zero counts;
- all non-resolved reference outcomes after the resolver runs;
- root-level source sections retained as unsupported material;
- loader and adapter diagnostics that still apply.

The adapter's `REFERENCE_RESOLUTION_PENDING` diagnostic is omitted after this
command successfully completes reference resolution. Other diagnostics, including
revision-hint limitations and unknown retained content, remain visible.

## Entity filters

`--type`, `--id`, and `--wkn` select detailed entities. Filters are optional,
exact, case-sensitive, whitespace-preserving, and conjunctive. IDs remain strings,
so `702` and `0702` are distinct. `--type` accepts canonical names shown by
`sedd inspect --help`, such as `status_variable`, `alarm`, and
`remote_command_parameter`. A selection with no matches is a successful result
with count zero.

Each selected entity includes its complete canonical data and immediate
relationships. Immediate relationships cover outgoing references, incoming
resolved references, ambiguous incoming candidate links, and explicit remote
command/parameter containment. No fuzzy match or inferred relationship is added.

## JSON contract

`--json` emits compact UTF-8 JSON with `inspection_schema_version: "1.0"` and one
trailing newline. Object keys, unordered entity inventories, diagnostics,
unsupported sections, unresolved outcomes, selected entities, and immediate
relationships have deterministic ordering. Meaningful ordered fields inside
canonical entities retain their order.

The JSON contains the resolved absolute source path, provenance, and local entity
keys. It is deterministic for the same input at the same path, but it is not a
portable semantic fingerprint.
