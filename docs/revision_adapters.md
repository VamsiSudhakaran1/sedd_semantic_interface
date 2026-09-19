# Revision adapter architecture

The pipeline is `load_interface(path)` -> secure `load_sedd` -> `AdapterRegistry`
-> selected `SeddAdapter` -> `AdapterResult.interface` (`EquipmentInterface`).
The registry delegates revision detection; adding an adapter does not require
editing comparison, graph, report, model, or generic routing code.

```python
from sema_sedd.adapters import load_interface
from sema_sedd.model import to_canonical_json

result = load_interface("equipment.xml")
json_text = to_canonical_json(result.interface)
for diagnostic in result.diagnostics:
    print(diagnostic.code, diagnostic.message)
```

For a document without a schema hint, deliberate selection is required:

```python
result = load_interface("equipment.xml", revision="E172-0225")
```

This is a library increment. The CLI still provides help/version only.

## Protocol and registry

`SeddAdapter` is a runtime-checkable structural protocol with:

- `revision: str`: the adapter's unique registered label;
- `detect_support(document: SourcedDocument) -> SupportLevel`: a pure assessment;
- `parse(document: SourcedDocument) -> AdapterResult`: revision-specific mapping
  without source I/O, external resource lookup, or downstream processing.

Adapters receive already-secured XML. `AdapterResult` holds only the canonical
interface, the selected revision label, and `AdapterDiagnostic` records. Each
diagnostic has a stable code, fixed message (possibly naming a known schema
field), INFO/WARNING severity, and domain `SourceProvenance`. Untrusted values
are retained in the model rather than interpolated into diagnostic messages.
The registry adds loader diagnostics to adapter diagnostics and rejects an
incorrect result revision, invalid support decision, or noncanonical result.

`AdapterRegistry((adapter_a, adapter_b))` is immutable, requires unique nonempty
revision names, and exposes sorted `revisions`. `select()` returns the selected
adapter; `adapt()` selects and maps. Empty registries and unrecognized requested
revisions raise `UnsupportedSeddVersionError`. Multiple positive detections raise
`AmbiguousSeddVersionError`; registration order is never a tie-breaker. Duplicate
registrations or invalid adapter results raise `AdapterRegistrationError`.

Automatic selection requires exactly one `SUPPORTED` assessment. `INDETERMINATE`
adapters are never automatic fallbacks. Explicit selection may accept indeterminate
support but cannot override `UNSUPPORTED`. Direct use of a concrete adapter's
`parse()` is itself deliberate selection and follows that same restriction.

`default_registry()` creates a fresh registry containing `E172_0225Adapter`.
Only the composition module (`adapters/defaults.py`) imports the concrete adapter,
and that import is lazy. A custom registry replaces the default completely.
No external plugins are discovered or executed automatically; registered adapters
are trusted application code implementing the no-I/O protocol.

## E172-0225 selection policy

The concrete implementation is `adapters/e172_0225.py`, with local traversal
helpers in `_e172_0225_xml.py`. It requires the supported SEDD root and namespace.
An exact loader hint for E172-0225 produces `SUPPORTED`, with a
`REVISION_HINT_ONLY` diagnostic in the result. A missing hint/location produces
`INDETERMINATE`; explicit selection records `EXPLICIT_REVISION_SELECTION`.
An unknown, conflicting, malformed, or ambiguous schema location is unsupported
by this adapter even with an explicit request. Malformed URI text becomes a
controlled loader diagnostic instead of leaking URL-parser exceptions.

This is a deliberate routing policy, not conformance detection. A schema filename
or URL remains untrusted input and is never fetched. The mapper checks relevant
field shapes and preserves failures, but does not perform XSD validation. It does
not infer a revision from source filenames, prefix spelling, equipment software
revision, or resemblance to the sample. Schema-invalid files may produce a partial
model with diagnostics. An empty inventory is not proof of a valid empty section.

The current loader accepts the known SEDD root QName. A future revision in a new
namespace would require extending that loader admission policy explicitly. The
second-adapter test uses the existing SEDD family namespace and different revision
hints/fields; it demonstrates coexistence without changing the loader's revision
hint table or any downstream API.

## Mapping and preservation

Mappings use expanded names, not local-name-only matching. SEDD local children are
unqualified; imported message/data-item elements must use the SMN namespace.
The implementation follows X01–X14, M01–M02 and S01–S05 in
[e172_observations.md](e172_observations.md):

| Source structure | Canonical representation |
| --- | --- |
| SEDDHeader | EquipmentMetadata, keeping equipment ID separate from model/software revision |
| SV / DV / EC | Separate variable types, lexical identifiers/ranges/default, units and format selectors |
| CollectionEvent | Distinct valid-data and relevant-variable references, StateTransition metadata |
| Alarm | Code/text and distinct set/clear event selectors |
| RemoteCommand / Parameter | Ordered contained parameters, requiredness, value formats and optional flags |
| SMN SECSMessage | Stream/function, direction, mnemonic, reply/blocking/header/exception metadata and ordered structures |
| VariableFormat | Named format with an explicit sequence wrapper and ordered DataStructure nodes |
| DefaultReport / EventReportLink | Ordered member selectors; deletion flags retained at interface level |
| SupportedSEMIStandard | Name/designation, ordered structured requirement groups and standard notes |
| WellKnownName / Source / SEMIStandard | Unverified WKN, declared source text, standard reference selector |

No native ID, name, WKN, or repeated message identity is used as a unique dictionary
key. Local entity keys use occurrence-indexed, prefix-independent expanded-name
source paths. Every record retains source document, selected adapter revision,
path, source identifier where applicable, line, and column. The chosen revision
in provenance describes the mapping applied; it does not certify the input.
These keys are deterministic for unchanged source structure, not cross-version
identity keys. Reordering source occurrences can change their paths.

All explicit references remain selectors with a null `target_key`. The unresolved
ledger records `NOT_ATTEMPTED` (or `MISSING_SELECTOR` for an absent/empty selector),
and the result includes `REFERENCE_RESOLUTION_PENDING`. There is no automatic
resolution, repair, first-match behavior, WKN-authority assertion, or numeric
proximity matching. Event VID target-kind restrictions remain pending (A02).
Command-parameter containment is explicit source structure and maps directly.

Data-item primitive/list/enum/bit/set vocabulary is represented by stable syntactic
kind labels. Each SECSData or ValueFormat wrapper becomes a `sequence` node; list
members, alternatives, repeated message bodies, report members, and parameter
order survive. Lexical data values and length attributes are preserved. This
increment does not infer full numeric ranges, encodings, or compound-format
semantics (A08). Integer fields use bounded ASCII XML integer syntax (at most
1,000 lexical characters); source booleans accept true/false/1/0. Invalid typed
values become unknown with retained source content. Omitted flags remain None;
XSD defaults are not injected.

Unknown elements, attributes, unsupported declared sections, nil content, and
invalid fields are kept as `UnknownExtension` with provenance. Known scalar fields
with unsupported attributes retain those attributes. Structured scalars and
significant mixed content retain complete opaque nodes to avoid losing order.
Unknown data-item tags are retained rather than assigned a known format meaning.
RecipeVariableParameters, EquipmentCharacterization, and logging attributes outside
the mapped message fields are deliberately opaque. Requirement groups map their
observed name, requirements, sections, identifiers, implementation/compliance
fields, notes, and source locations. Unknown nested requirement material remains
opaque. Source preservation is not a claim of XSD validity.

Repeated singleton fields/sections produce `AMBIGUOUS_FIELD` and retain all
occurrences; the mapper does not silently pick the first. Missing required IDs,
names, or main sections produce `MISSING_FIELD`. `NIL_CONTENT`, `INVALID_FIELD`,
`UNSUPPORTED_FIELD_SHAPE`, and `UNKNOWN_CONTENT` distinguish other preservation
cases. This is loss-aware structural mapping, not a complete XSD validator or a
byte-for-byte XML round-trip. Prefix spellings and markup syntax are not domain
identity. Unknown content within a node retains text/order; positions relative
to mapped siblings can be recovered from its source paths.

## Dependency and coexistence checks

`tests/test_adapters.py` registers E172-0225 alongside a test-only second adapter
using a different schema hint and `Device` structure. Both flow through the same
filesystem pipeline and canonical serializer. The loader need not recognize the
second revision. Registry-order reversal leaves routing unchanged; conflicting
support fails explicitly. Another process blocks all concrete E172 imports and
still uses a custom adapter with the downstream packages and serializer.

An import-boundary test forbids adapter/parser dependencies in `model`, `compare`,
`graph`, and `report`. Concrete adapter imports must remain at composition or
adapter implementation/test boundaries. Adding another adapter therefore does
not authorize downstream imports of `E172_0225Adapter`.

Tests cover fixture mappings, unsupported namespaces, no-hint selection, unknown
and malformed hints, ambiguous/duplicate registrations, malformed contract results,
unknown and nil content, duplicate fields and identifiers, sequence preservation,
controlled diagnostics, repeatability, XXE/DTD rejection before adapter execution,
byte limits, and absence of network access. The local original TrackSys sample
matches the recorded 104 SV / 93 DV / 7 EC / 185 CE / 46 alarms / 67 formats /
92 messages / 7 commands / 1 standard / 1 report / 1 link. Its 1,955 explicit
selectors remain pending; sample schema validity never implies resolved links.
The original sample remains untracked and that integration check skips when it is
not available. Versioned synthetic fixture checks always run.

The full field-level mapping and Prompt 6 fixture coverage are described in
[e172_entity_parser.md](e172_entity_parser.md).
