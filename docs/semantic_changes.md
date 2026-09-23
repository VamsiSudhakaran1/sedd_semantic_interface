# Canonical semantic changes

`compare_interfaces(old, new)` compares immutable canonical interfaces. It imports
no XML loader or revision adapter. The pipeline resolves references on both sides,
runs the conservative identity matcher, reconciles target identities, and compares
properties and relationship roles. It does not mutate the inputs or access a network.

```python
from sema_sedd.compare import compare_interfaces, to_change_set_json
from sema_sedd.model import EquipmentInterface, StatusVariable

old = EquipmentInterface(
    status_variables=(StatusVariable(key="old-sv", implementation_id="44", units=("count",)),)
)
new = EquipmentInterface(
    status_variables=(StatusVariable(key="new-sv", implementation_id="44", units=("items",)),)
)
changes = compare_interfaces(old, new)
assert changes.has_interface_changes
assert changes.is_complete
print(to_change_set_json(changes))
```

The four public immutable, runtime-validated records are:

| Record | Meaning |
| --- | --- |
| `ChangeSet` | Matching result, entity changes, comparison issues, completeness and category summaries |
| `EntityChange` | Added, removed, or modified entity; original old/new snapshots, accepted match where applicable, property and relationship changes |
| `PropertyChange` | Canonical field, exact before/after values, specific change kind, category |
| `RelationshipChange` | Canonical role, reconciled endpoints, added/removed member multiplicities, pure reorder and missing/present indicators, category |

Equipment metadata and interface-level fields occupy singleton slots rather than
inventories; their changes have no fabricated entity match. Match snapshots retain
strategy, deterministic confidence category, evidence, and source provenance.
`to_change_set_dict()` and `to_change_set_json()` use change schema version `1.0`.
Prompt 13 adds `old_context` and `new_context` to each `EntityChange`, including
dependency evidence and factual summary statements in JSON. These are additive
fields in schema `1.0`; see [change_dependency_context.md](change_dependency_context.md).

## Classification and coverage

| Represented information | Change kinds and policy |
| --- | --- |
| Entity inventories | `ENTITY_ADDED`, `ENTITY_REMOVED`, `ENTITY_MODIFIED`, subject to sufficient identity evidence |
| Implementation ID | `IMPLEMENTATION_ID_CHANGED`; confirmed continuity prevents removal/addition |
| WKN | `WELL_KNOWN_NAME_CHANGED` for value, authority, or scope; trust-status-only changes are unknown `IDENTITY_EVIDENCE_CHANGED` |
| Names, descriptions | `NAME_CHANGED` is interface information; `DESCRIPTION_CHANGED` is documentation |
| Datatypes, formats | `DATA_TYPE_CHANGED`, `FORMAT_CHANGED`; compare format references and ordered format definitions |
| Units, bounds, defaults | `UNIT_CHANGED`, `RANGE_CHANGED`, `DEFAULT_CHANGED`; exact represented values |
| Relationships | Typed role and target changes; additions/removals, duplicates, ordering and optional presence are retained |
| Alarms | `ALARM_EVENT_LINK_CHANGED` distinguishes set from clear; other alarm metadata uses `ALARM_CHANGED` |
| Reports | `REPORT_CONTENT_CHANGED` retains variable order and multiplicity |
| Event/report links | `EVENT_REPORT_LINK_CHANGED` retains event identity and ordered reports |
| Commands and parameters | `COMMAND_CHANGED`, `COMMAND_PARAMETER_CHANGED`; membership, scoped identity, requiredness, format, and other parameter properties |
| Messages | `SUPPORTED_MESSAGE_CHANGED`, `MESSAGE_STRUCTURE_CHANGED`; presence, headers, direction, blocking metadata and ordered data structures |
| Standards | `STANDARD_METADATA_CHANGED`; declarations, requirement groups and member metadata, with notes separated as documentation |
| Other represented metadata | Equipment, interface and state-transition change kinds; unsupported fields remain explicitly unknown |

`DOCUMENTATION_CHANGE` covers descriptions, declared source, notes, created date,
and descriptions nested within message/format structures. Protocol data, names,
and alarm text remain `INTERFACE_CHANGE`; alarm text can be transmitted to a host.
An entity can contain both categories. These categories do not assert compatibility,
operational impact, or severity.

Unknown extensions and opaque metadata are preserved and compared as
`UNKNOWN_CHANGE`. Their presence also makes comparison incomplete even when
unchanged. Known structure and its documentation/opaque annotations are compared
separately. Arbitrary extension content is never interpreted as a known domain field.

## Identity and uncertainty

The [matching policy](entity_matching.md) remains authoritative. This engine does
not fuzzy-match names/descriptions, infer a rename from similar properties, or use
source positions as identity. A caller-verified, exact, non-conflicting official
WKN can establish continuity across implementation-ID changes. The adapter alone
does not verify WKN authority. Conflicting verified WKN/native-ID evidence remains
ambiguous; it cannot be bypassed to manufacture a WKN property change. An unverified
WKN value can change on an entity accepted through its unique native ID.

An unmatched entity is definitely added/removed only with `NO_COUNTERPART` and no
opposite-side ambiguity or missing identity for that entity type. Otherwise an
`INSUFFICIENT_IDENTITY` issue retains the uncertainty. Parameters can follow a
conclusively added/removed parent command; an uncertain parent does not permit
cross-command matching.

Changing a parameter name, standard designation, or an event link's identifying
event may produce removal/addition when no independent continuity evidence exists.
These carry the appropriate command-parameter, standards, or event/report domain
change kind. Content similarity cannot prove continuity.

Relationship targets are projected through accepted old/new entity pairs before
comparison. Thus updating a VID after a confirmed variable ID change does not
invent a report membership change. A genuinely different matched target does.
Unresolved or ambiguous endpoints retain their selectors and resolution states;
changed uncertain edges are `UNKNOWN_CHANGE`, not asserted interface changes.
Issues also cover unknowns and unresolved references on added/removed or ambiguous
owners, not only matched entities.

Always inspect `is_complete` and `issues`. Zero entity changes with unresolved
identity, references, or opaque content is not proof of equivalence. Completeness
concerns information represented in the supplied canonical models; it cannot
certify E172 conformance, recover discarded input, or replace adapter diagnostics.

## Ordering, whitespace and deterministic output

Inventory order, attribute order, namespace-prefix spelling, indentation between
structural XML elements, source paths, line numbers, and local occurrence keys
do not by themselves establish a semantic change. XML field extraction remains
the adapter's responsibility. Singleton child fields may move without changing
their canonical values.

Protocol sequences remain ordered: report variables, event/report members, command
parameters, event variable lists, and message/format structures. Duplicate members
are significant. A pure permutation sets `order_changed`; mixed membership edits
still retain the complete ordered before/after values. Missing and empty relationship
lists remain distinct. Standards reference inventories and requirement inventories
are unordered, with duplicate counts preserved.

The canonical `requirement_group` representation receives narrowly scoped handling:
its group/member source path, line and column fields are source evidence, notes
are documentation, and group/member order is ignored. Arbitrary nested JSON is
not stripped or normalized by those field names.

Leaf strings remain exact, including whitespace in descriptions and protocol
values. No blanket trimming, case folding, numeric conversion, or native-ID
normalization is performed. For example, `"007"` and `"7"` are distinct, as are
absent text and an empty string. JSON booleans and numbers remain distinct.

Output ordering is deterministic for equivalent canonical inventories and maps.
The JSON retains original source snapshots, so it is **not a semantic fingerprint**:
two XML files differing only in layout can yield different retained provenance
even though their semantic change lists are empty.

## Comparison with generic XML differences

[compare_semantic_demo.py](../tools/compare_semantic_demo.py) generates
[semantic_diff_examples.json](semantic_diff_examples.json) from tracked synthetic
fixtures. It compares a raw text diff and a namespace-aware positional XML-tree
baseline with this engine. The tree baseline already ignores attribute order and
structural indentation; it compares expanded tags, attributes and leaf text at
numeric child positions. It is deliberately simple, not an optimal tree-edit
algorithm or a claim about every XML diff tool.

Reproduce from the repository with the installed development environment:

```sh
python tools/compare_semantic_demo.py --output docs/semantic_diff_examples.json
```

| Case | Raw added/deleted lines | Positional XML-tree deltas | Semantic entity changes |
| --- | ---: | ---: | --- |
| Inventory reorder, attributes and indentation | 217 | 58 | 0 |
| Description edit | 2 | 1 | 1 documentation change |
| Alarm clear-event target | 2 | 1 | 1 alarm relationship change |
| Report variable target | 2 | 1 | 1 report-content change |
| Verified WKN and implementation-ID continuity | 4 | 2 | 1 implementation-ID change; no relationship change |

The additional semantic information is concrete:

- Reordered inventory entries remain the same entities instead of positional
  replacements. A more sophisticated XML diff may also recognize moves, but does
  not thereby establish canonical identity.
- A description edit is documentation; an alarm clear-event edit identifies the
  alarm role and its resolved event endpoints.
- A report edit identifies variable membership, target types, duplicate counts
  and ordering, rather than only changed VID text.
- An ID change and its updated reference are explained by one accepted entity
  continuity match with WKN evidence. The report still references the same entity.
- Conflicts and unresolved targets remain explicit uncertainty rather than a
  falsely definite diff or a claim that identical text proves semantic completeness.

The continuity example explicitly supplies verification from a **fictional fixture
registry** in the canonical model; the XML alone supplies no authenticated WKN.
These complete synthetic fixtures also contain pre-existing opaque content and
unresolved references. Their comparisons correctly remain incomplete, including
the zero-change noise case. The generated artifact includes these issues.

## Validation and scope

`tests/test_semantic_changes.py` contains 54 tests covering every category above,
all 11 original change-catalog cases, message-structure changes, ambiguous and
missing identities, dangling references, opaque new entities, mixed documentation
and interface edits, and deterministic serialization. Twelve seeded XML
permutations exercise the full loader/adapter/engine path. All 36 pairs of small
inventory permutations verify a nonempty change set is invariant to inventory
construction order. Meaningful protocol-order and leaf-whitespace changes have
separate positive tests, preventing over-normalization.

Optional development verification compared the locally supplied original TrackSys
sample with itself: zero entity changes, with existing identity ambiguity, unknown
content and unresolved references retained. That external file is not a test
dependency. The API operates on canonical models from any revision adapter. A
comparison CLI, rendered reports, and compatibility/impact policy are separate work.
