# Canonical domain model

Prompt 4 introduces `EquipmentInterface`, also exported as
`CanonicalEquipmentInterface` to match the master contract. This is an immutable,
XML-independent Python API. It has no parser imports, filesystem reads, network
operations, adapter selection, identity matcher, or relationship resolver.
`tests/test_model.py` constructs a complete original interface directly in Python.

```python
from sema_sedd.model import (
    EquipmentInterface,
    EquipmentMetadata,
    SourceProvenance,
    StatusVariable,
    WellKnownName,
    to_canonical_json,
)

interface = EquipmentInterface(
    equipment=EquipmentMetadata(model="Lantern", software_revision="1.2"),
    status_variables=(
        StatusVariable(
            key="sv/temperature/occurrence-1",
            implementation_id="007",
            name="Temperature",
            wkn=WellKnownName(value="fictional.temperature"),
            provenance=(
                SourceProvenance(
                    source_document="synthetic.json",
                    source_revision="future-1",
                    source_path="/variables/0",
                    path_kind="json_pointer",
                    source_identifier="007",
                ),
            ),
        ),
    ),
)
json_text = to_canonical_json(interface)
```

## Objects and evidence boundaries

Every semantic record has a fixed `canonical_type`, optional `implementation_id`,
`name`, `description`, `wkn`, `declared_source`, `provenance`, `standards`,
`unknown_extensions`, and immutable `extension_metadata`. Those common fields
apply to the equipment interface, equipment metadata, and all entity categories.
Value objects such as provenance and references have their own typed fields;
they do not recursively acquire inappropriate WKN/name/description fields.

| Object | Specific representation | Structural evidence |
| --- | --- | --- |
| EquipmentInterface | Typed inventories, equipment metadata, unresolved references, container deletion metadata | Contract; X02, X11 |
| EquipmentMetadata | Equipment ID in implementation_id; model, software_revision, supplier, created_date | X02b, S01 |
| StatusVariable / DataVariable | Format reference, open data_type, ordered units, lexical minimum/maximum | X04, X04b, X09 |
| EquipmentConstant | Variable fields plus lexical default | X04b |
| CollectionEvent | Separate valid_data_variables and relevant_variables; optional StateTransition | X06 |
| Alarm | Code, text, separate set_event and clear_event references | X07, S04 |
| RemoteCommand | Ordered contained parameters, object specifiers, optional message-family flags | X08 |
| RemoteCommandParameter | Conditional/yes/no/unknown requiredness; ordered value_format | X08b, M02 |
| SupportedMessage | Stream, function, direction, reply metadata, blocking label, header/exception text, ordered structure | M01, S05 |
| VariableFormat | Name and ordered DataStructure nodes | X09, M02 |
| DefaultReport | Ordered variable references, preserving repetitions | X11 |
| EventReportLink | Event reference and ordered report references | X11 |
| StandardReference | Designation, revision, structured requirement-group metadata and notes | X12 |
| WellKnownName | Value, authority, scope, verification status and provenance | X12, A05 |
| EntityReference | Target types, lexical ID/name/WKN selectors, optional scope and resolved local key | X05, S04; model policy below |
| SourceProvenance | Source document/revision/path/path kind, lexical source identifier, line/column | Contract, X13 |
| UnresolvedReference | Owner key, relationship label, selector, reason, candidate keys and provenance | S04, S05 |
| UnknownExtension | Namespace/name, attributes, ordered mixed content, opaque metadata and provenance | X14; model policy below |

Observation labels refer to [e172_observations.md](e172_observations.md). This table
records structural evidence, not claims of standards conformance. The E172-0225
mapping is documented in [e172_entity_parser.md](e172_entity_parser.md).
`DataStructure` represents primitive, list, enum,
bit, set, or future shapes with open `kind` labels, lexical attributes/value, and
ordered children. Adapters must preserve distinct wrappers as nodes where needed;
they must not flatten distinct alternatives. Complete numeric, encoding,
length-expression and compound-format semantics remain pending (A08).

## Identity and reference invariants

Each catalogued entity, including nested command parameters, needs a nonempty
`key` unique **within one EquipmentInterface**. Keys are explicit, document-local
handles. They are not WKNs, native IDs, hashes, random UUIDs, or cross-version match
results. The model never generates them. A future adapter must assign reproducible
keys and disambiguate occurrences without dropping records. Two commands can have
parameters named MODE while their parameter keys remain distinct.

Native identifiers are optional strings. Missing (`None`), empty (`""`), zero
(`"0"`), and alternate lexical forms (`"007"`, `"7"`) are retained distinctly.
No numeric range, case folding, whitespace normalization, global uniqueness, or
cross-category uniqueness is assumed by this source-independent model. A source
adapter may record schema violations while still preserving every entity. Python
dataclass equality compares record contents; it is not semantic identity matching.

A WKN string defaults to `UNVERIFIED`. `VERIFIED` requires an explicit authority,
scope, nonempty value, and provenance. This only records a caller's evidence claim;
the model cannot authenticate a registry or certify that a name is official. Even
a verified WKN may collide. No identity match or automatic merge follows from it.

An `EntityReference` stores observed selectors independently of `target_key`.
A null target means no resolved target is recorded. It does not prove a missing
entity. Adapter output records `NOT_ATTEMPTED` or `MISSING_SELECTOR`; an empty
adapter ledger is not a claim that resolution ran successfully. The separate graph
resolver records `NOT_FOUND`, `WRONG_TYPE`, `AMBIGUOUS`, `MISSING_SELECTOR`, or
`UNSUPPORTED`, embeds unique targets, and produces an exhaustive relationship
model. No name similarity, numeric proximity, or first-match selection occurs.
See [reference_resolution.md](reference_resolution.md).

The aggregate checks key uniqueness, membership of resolved targets, declared
target types, and command scope for parameter targets. Known relationship roles
also constrain formats, standards, alarm events, reports, and event/report links.
Ambiguous references require at least two distinct existing candidate keys and
cannot also contain a resolved target. Owner keys must exist. Raw dangling
selectors remain legal. Unresolved relationship labels are descriptive; they are
not parsed as XML paths or used to infer relationships. General event-variable
target-kind restrictions remain an adapter decision (A02).

## Unknowns, provenance and validation

Optional scalar fields use `None` for unspecified information, not a fabricated
value. Optional sequences such as report members, message structure, command
parameters, and event-variable containers distinguish `None` from an explicit
empty tuple. An omitted flag remains `None`; no XSD default is injected. Unknown
requiredness and direction have explicit `UNKNOWN` enum values. The extension
metadata can preserve an unrecognized original label or the reason a field is
unknown. Inventory tuples enumerate the records currently known; they do not
claim a source section is complete, supported, present, or schema-valid.

`SourceProvenance.source_path` is a plain string with an optional `path_kind`.
An adapter may record an XPath, JSON pointer, or another source locator. Source
lines/columns are one-based positive integers. Source revisions are unconstrained
strings; equipment software revision is a separate field. `declared_source` holds
a source document's descriptive Source field separately from ingestion provenance.

`UnknownExtension` preserves unsupported source content without turning it into a
known entity. Attributes use qualified string keys where applicable. Mixed text
and child extensions retain order and whitespace, with namespace, reason, and
provenance. Preservation does not make an extension XSD-valid. No markup is
executed or rendered. A future HTML report must escape all text.

`JsonObject(entries=(("key", value), ...))` and `JsonArray(items=(... ,))` retain
immutable opaque JSON data. Nested maps/arrays use the same wrappers. Duplicate
object member names, mutable containers, foreign objects, non-finite floats and
unpaired Unicode surrogates are rejected. Public dataclasses are frozen and
keyword-only; field validation also rejects incorrect concrete model types,
string values in enum fields, and boolean values in integer fields. XML parser
objects cannot be passed as provenance, structures, extensions, or model roots.
Failures raise `ModelValidationError`. These are model integrity checks, not a
SEMI compliance decision.

## Canonical JSON contract

`to_canonical_dict(interface)` returns a fresh JSON-compatible snapshot;
`to_canonical_json(interface)` emits compact Unicode JSON with sorted object
keys, deterministic finite-number encoding, and no optional spacing or trailing
newline. Encode the result as UTF-8 when writing a file. The envelope contains
`model_schema_version: "1.0"` independently of source E172 revisions, plus
`interface`. Every domain record includes its `canonical_type`; all optional
fields, including nulls, are retained. This is the application's versioned JSON
contract, not a claim of RFC 8785 compatibility or a deserialization API.

Entity inventories and unresolved-ledger entries are sorted by their complete
canonical JSON value; duplicate entries are never deduplicated. Reference target
types and ambiguity candidate keys are also unordered collections. Report
members, event variable lists, command parameters, object specifiers, units,
message/format structure, event/report link members, unknown content, and all
other sequences preserve their supplied order. JSON-object entry order is ignored;
JSON-array order is preserved. Sorting does not mutate the model.

The same represented model yields identical JSON across construction order of
inventories/maps and across process hash seeds. **This JSON is not a semantic
fingerprint.** It includes provenance and local keys, so changed source locations
can change it even when the interface meaning is unchanged. XML whitespace treatment,
normalization, full semantic comparisons, and general change reasons remain
separate work. Cross-version identity matching is now
implemented in [entity_matching.md](entity_matching.md), outside the model layer.
Deterministic serialization must not erase evidence needed by that work.

## Critical architecture challenge

| Challenge | Failure avoided and model decision | Verification |
| --- | --- | --- |
| Identifier changes | Native ID is data, not the local key or immutable cross-version identity; ID changes and WKN evidence remain visible | Before/after ID test |
| WKN identity | Equal WKN strings do not prove authority, scope, uniqueness, or a match; verification metadata is explicit and collisions survive | Authority/evidence, scope, duplicate-WKN tests |
| Missing identifiers | Do not invent native IDs or index records by null; distinct local keys preserve occurrences | Missing/empty/zero/lexical-ID cases |
| Duplicate identifiers | Do not overwrite dictionary entries by native ID, command name, or S/F/direction; only local-key duplication is an integrity error | Same-category and cross-category ID collisions, repeated messages, scoped parameters, ambiguous-reference tests |
| Unknown extensions | Do not discard unsupported content or infer semantics from it; immutable opaque trees preserve structure and text | Mixed content, future namespace, ordering, invalid-object tests |
| Future revisions | No fixed revision enum or XML classes in the public model; source revisions and format labels remain open; JSON has its own version | Future revision/format test, parser-blocked subprocess import, API annotation tests |
| Serialization order | Do not confuse inventory order with protocol sequence order | Inventory/map/hash-seed equivalence and report/parameter/message/link permutation tests |
| Message metadata | A blocking label is not a boolean; lexical labels and header/exception text remain representable | Message metadata regression test |

Deferred decisions are explicit: authoritative WKN verification, native-ID
normalization, and complete compound-format semantics. Prompt 11 implements
cross-version matching with exact lexical identities and explicit ambiguity;
it does not authenticate WKNs or change this model's identity invariants.
Prompt 5 adds a deliberate registry selection policy
and occurrence-based adapter key allocation; see
[revision_adapters.md](revision_adapters.md). No Prompt 2 assumption has silently
become XML parser behavior. The E172-0225 adapter consumes the secure loader and constructs these
objects through this API; graph/comparison/report layers consume the model directly.
