# Explore CLI

`sedd explore FILE ENTITY` loads a local SEDD document through the secure XML
loader and adapter registry, resolves canonical references, selects exactly one
canonical entity, and displays its bounded relationship neighborhood.

## Selectors

Selectors use the first colon as a delimiter. Values are compared exactly and
are not case-folded, trimmed, or converted to numbers:

```text
event:1001
alarm:72
status-variable:44
wkn:urn:example:variable:44
```

The first three forms match the canonical type and its implementation ID. The
`wkn:` form searches all canonical entity types for the exact Well-Known Name
value. A selector that matches no entity or more than one entity is a controlled
error. The command never chooses an arbitrary match.

## Traversal

`--depth N` sets the maximum number of edges from the selected root. The default
is 1, depth 0 displays only the selected entity, and the accepted range is 0–8.
The fixed upper bound prevents an unbounded traversal even when a document has
cycles.

Traversal is bidirectional across references whose resolution state is
`RESOLVED`, and across explicit remote-command parameter containment. Each entity
is visited once at its shortest distance from the root. `UNRESOLVED` and
`AMBIGUOUS` relationships are displayed on visited entities but are never
traversed. Ambiguous candidate entities are likewise not traversed.

Every visited entity displays:

- canonical identity, implementation ID, name, description, and WKN;
- non-relationship properties, including provenance and preserved extensions;
- incoming relationships;
- outgoing relationships.

Relationship fields are separated from properties. This avoids presenting a
reference selector as if it were an ordinary scalar property.

## JSON output

`--json` emits compact UTF-8 JSON with sorted object keys and one trailing
newline. The top-level `exploration_schema_version` is currently `1.0`. The
document records the resolved source path, SEDD revision, parsed selector,
maximum depth, root key, and visited entities. Entities are ordered by depth,
canonical type, implementation ID, and document-local key. Relationship arrays
are deterministic.

Example:

```sh
sedd explore equipment.xml alarm:72 --depth 2 --json
```

The command reads the input and emits output only. It does not modify the SEDD
file or access the network.
