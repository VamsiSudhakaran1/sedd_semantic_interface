# Reference resolution

Prompt 7 adds a revision-neutral phase after canonical parsing:

```text
load_interface(...).interface
    -> build_reference_indexes(...)
    -> resolve_references(...)
    -> RelationshipModel
```

The graph package imports the canonical model and never imports an XML parser or
revision adapter. Resolution is deterministic, local, and offline.

```python
from sema_sedd.adapters import load_interface
from sema_sedd.graph import build_reference_indexes, resolve_references

parsed = load_interface("equipment.xml").interface
indexes = build_reference_indexes(parsed)
relationships = resolve_references(parsed, indexes)

resolved_interface = relationships.interface
for relationship in relationships.relationships:
    print(relationship.owner_key, relationship.role, relationship.state)
```

## Outcomes

Every `EntityReference` owned by a catalogued entity produces one `Relationship`
with exactly one state:

| State | Meaning |
| --- | --- |
| `RESOLVED` | Exactly one candidate satisfies every supplied selector, target-type constraint, and scope constraint. The copied reference contains its document-local `target_key`. |
| `UNRESOLVED` | No safe target can be selected. The reason is `NOT_FOUND`, `WRONG_TYPE`, `MISSING_SELECTOR`, or `UNSUPPORTED`. |
| `AMBIGUOUS` | At least two candidates satisfy all constraints. Every candidate key is retained and no target is selected. |

The returned interface replaces the adapter's `NOT_ATTEMPTED` ledger. Resolved
references are embedded in their owning entities. Unresolved and ambiguous
references are recorded in `EquipmentInterface.unresolved_references`. The
`RelationshipModel` validates that its outcomes cover every entity reference and
agree exactly with that ledger.

## Indexes

`ReferenceIndexes` retains collisions rather than overwriting them. It contains:

- entity key and canonical-type indexes;
- canonical type plus exact native identifier;
- canonical type plus exact name;
- canonical type plus exact WKN value, authority, and scope;
- remote-command name identity;
- supported-message stream/function identity;
- standard designation;
- explicit remote-command ownership for command parameters.

S/F collisions remain visible in the index because the observed sample proves
that stream/function does not always identify one message. The current canonical
`EntityReference` has no S/F selector fields, so that index is exposed for later
identity and graph operations and is not used to invent a reference selector.

## Conservative rules

All string comparisons are exact, case-sensitive, and whitespace-preserving.
There is no numeric conversion, leading-zero normalization, fuzzy matching,
description matching, proximity repair, or first-candidate selection. An empty
string is an explicit selector and remains distinct from a missing selector.

Native identifiers and names are scoped by the reference's declared target types.
Name selectors for standards also consider the canonical standard designation;
this is required because the E172 adapter preserves the `SEMIStandard` selector
as a designation. WKN matching requires exact value, authority, and scope. The
authority-status flag records evidence quality and is not treated as part of the
lexical WKN identity.

When several selectors are present, their candidate sets are intersected. A
resolver never chooses a priority selector or falls back after conflicting
evidence. If an exact selector exists only on a disallowed entity type, the result
is `UNRESOLVED/WRONG_TYPE`.

An unresolved reference with no declared target type is
`UNRESOLVED/UNSUPPORTED`. This preserves Prompt 2's pending event-variable
target-kind semantics and prevents an identifier collision in an unrelated
category from becoming a relationship. Parameter scope uses the canonical
command-to-parameter containment index; it does not infer ownership from local-key
text.

Already resolved canonical references remain resolved after aggregate model
validation has confirmed their target membership and type. Re-running the
resolver is idempotent. Caller-supplied indexes are accepted only when their
complete entity catalogue equals the interface being resolved.

## Verification

Tests cover exact valid references, missing targets, empty and lexical string IDs,
duplicate identifiers, ambiguity, wrong-type targets, missing selectors,
unsupported target semantics, conflicting selectors, WKNs, standard designations,
command and S/F collisions, foreign indexes, idempotence, and the complete
parse/index/resolve/relationship pipeline over synthetic E172 fixtures.
