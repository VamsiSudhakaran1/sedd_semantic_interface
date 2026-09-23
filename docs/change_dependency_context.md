# Factual change dependency context

`compare_interfaces(old, new)` automatically attaches `old_context` and
`new_context` to every `EntityChange`. Property and relationship edits on the same
entity share that entity's context. Context describes its graph neighbourhood;
it does not assert that a particular property edit affects every referrer.

Added entities have only new context; removed entities have only old context.
Modified entities retain both independently. This preserves a dependency removed
in the new revision and handles implementation-ID changes using each revision's
resolved graph. It never unions old and new counts or relies on ID equality across
revisions. Documentation changes receive context as well as interface changes.

```python
from sema_sedd.compare import compare_interfaces, to_change_set_json

# old_interface and new_interface are canonical EquipmentInterface objects.
changes = compare_interfaces(old_interface, new_interface)
for change in changes.entity_changes:
    for side, context in (("old", change.old_context), ("new", change.new_context)):
        if context is not None:
            for statement in context.statements:
                print(f"{side}: {statement}")
print(to_change_set_json(changes))
```

The graph API is also available independently:

```python
from sema_sedd.graph import build_dependency_index, resolve_references

index = build_dependency_index(resolve_references(old_interface))
context = index.context_for(entity_key)  # Document-local canonical key.
```

The index holds immutable incoming/outgoing adjacency built once per graph.
The implementation imports canonical and graph types, with no parser or adapter
dependency. It does not perform network or filesystem I/O.

## Evidence and included paths

Only `RESOLVED` relationships from `RelationshipModel` establish dependencies.
Each `Dependency` includes its kind, related entity key/type, implementation ID,
name, and all supporting `DependencyEvidence` records. Each evidence record
contains original-direction edges with owner, role, target, and the full resolved
reference, including its selectors and source provenance. Joined edges are a set
of supporting facts, not a claim that every edge points along a directed path.

| Changed subject | Dependency kind | Required graph evidence |
| --- | --- | --- |
| Any catalogued entity | `REFERENCED_BY` | A resolved edge targeting the subject |
| Variable | `REFERENCED_BY` | Includes reports containing it and events directly referencing it |
| Variable | `EVENT_VIA_REPORT` | Report's `variables[i]` targets the variable; the same link's `reports[j]` targets that report and `event` targets an event |
| Collection event | `LINKED_REPORT` | The same link's `event` targets the subject and `reports[i]` targets a report |
| Collection event | `REFERENCED_BY` | Includes alarms' `set_event`/`clear_event` references, keeping both roles |
| Default report | `LINKED_EVENT` | The same link's `reports[i]` targets the subject and `event` targets an event |

Direct references also cover format and standards users. Event/report link
records themselves are retained as direct referrers, separately from the events
or reports identified by a join. Joins check owner and target canonical types as
well as exact relationship roles. No path uses more than three reference edges.
There is no recursive traversal or unrestricted propagation through the graph.

An equipment/interface metadata change has an explicit context with a null
subject key and a statement that it has no catalogued entity in the reference
graph. Command parameter containment is not a reference edge in the current
`RelationshipModel`, so this increment does not invent a containment dependency.

## Counts and factual language

Counts deduplicate by related entity key within each dependency kind. Repeated
report members, both alarm roles, multiple report paths, or duplicate link records
do not inflate the entity count. All distinct reference occurrences remain in
the evidence. An event may legitimately occur in both the direct and report-mediated
groups; these groups are stated separately and are not added together.

Example output from the tests:

```text
Referenced by 4 collection events and 2 default reports.
Linked through containing reports to 2 collection events.
```

For a changed event the output can include:

```text
Referenced by 1 alarm and 1 event/report link.
Linked to 2 default reports.
```

These statements describe declared graph facts. They do not score risk, label
severity, predict host behaviour, or claim an application will fail. Context does
not change matching decisions, change categories, or `ChangeSet.is_complete`.

## Exclusions and limits

Ambiguous candidates are never counted. Unresolved, missing, wrong-type, and
unsupported/untyped references do not establish dependencies. Every edge of a
join must be resolved; one missing endpoint prevents the joined claim. In
particular, pending E172 event-variable target-type semantics remain pending:
matching the VID text to an existing variable cannot substitute for graph evidence.

Names, descriptions, shared IDs, WKN resemblance, XML proximity and inventory
membership create no edges. A sibling report sharing an event with a containing
report is not thereby a referrer of the variable. Alarms referencing a linked
event are not automatically propagated into variable context. Cycles do not
trigger any additional traversal.

`excluded_unresolved_graph_relationships` counts all unresolved and ambiguous
occurrences in that side's graph. It is deliberately graph-wide: excluded edges
cannot safely be assigned to a particular dependency subject. Existing comparison
issues retain the uncertainty details. Unknown extensions remain outside these
known graph paths. Empty context therefore says only:

```text
No dependencies found in the supported resolved graph paths.
```

The output does not claim the absence of real-world dependencies. Context is
limited to canonical reference edges and the joins listed above.

## Serialization and verification

Context and evidence are sorted deterministically. Change JSON includes both
context objects and their `statements`, as additive fields in change schema `1.0`.
Absent-side context is JSON null. Original source evidence is retained; as with
the rest of the change JSON, this is not a source-independent semantic fingerprint.

`tests/test_dependency_context.py` includes 22 cases covering all three variable
types, event/alarm/report inclusion, excluded unrelated entities, sibling reports,
ambiguous candidates, incomplete joins, duplicate counts and proof preservation,
both direct event roles, generic format/standards referrers, bounded cycles,
before/after changes, additions/removals, verified WKN ID continuity, deterministic
inventory permutations, singleton metadata, and invalid API boundaries. A tracked
synthetic XML fixture additionally verifies adapter/resolver/comparison integration
without an external file dependency. The isolated wheel smoke test exercises the
public graph API and context attached to semantic changes.
