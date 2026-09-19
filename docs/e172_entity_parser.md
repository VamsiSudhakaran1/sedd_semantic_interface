# E172-0225 entity parser

`E172_0225Adapter` converts the secure loader's generic XML tree into the
XML-independent `EquipmentInterface`. The adapter follows the structural evidence
recorded in [e172_observations.md](e172_observations.md); it does not copy standards
prose, validate against an XSD, resolve references, or claim conformance.

Use the revision-neutral pipeline:

```python
from sema_sedd.adapters import load_interface

result = load_interface("equipment.xml")
interface = result.interface
```

For a document without an E172-0225 schema hint, select the adapter explicitly:

```python
result = load_interface("equipment.xml", revision="E172-0225")
```

## Entity coverage

| E172-0225 structure | Canonical object | Preserved structured fields |
| --- | --- | --- |
| SEDDHeader | EquipmentMetadata | Equipment ID, model, software revision, supplier, date, description |
| StatusVariable | StatusVariable | SVID, name, units, format selector, range, description, source, standard, WKN |
| DataVariable | DataVariable | VID, name, units, format selector, range, description, source, standard, WKN |
| EquipmentConstant | EquipmentConstant | ECID, name, units, format selector, range, default, description, source, standard, WKN |
| CollectionEvent | CollectionEvent | CEID, name, distinct valid/relevant VID lists, state transition, description, source, standard, WKN |
| Alarm | Alarm | byte-sized code, ALID, text, name, separate set/clear selectors, description, source, standard, WKN |
| RemoteCommand | RemoteCommand | name, ordered parameters, object specifiers, documentation, optional message-family flags |
| Parameter | RemoteCommandParameter | name, requiredness, ordered value format, description |
| SMN SECSMessage | SupportedMessage | stream/function, direction, name, mnemonic, reply metadata, blocking, header, exceptions, ordered structures |
| VariableFormat | VariableFormat | format name and ordered SMN data structure |
| DefaultReportDefinition | DefaultReport | string RPTID, name, ordered variable selectors, description |
| EventReportLink | EventReportLink | event selector, ordered report selectors, description |
| SupportedSEMIStandard | StandardReference | name, designation, ordered requirement groups, standard notes |

Each entity has an occurrence-indexed expanded-name XML path as its local `key`.
Its provenance retains the resolved source document, selected adapter revision,
the same XML path, a source identifier when available, and one-based line and
column. Prefix spelling does not affect the path. Occurrence keys preserve
duplicate and missing identifiers; they are not cross-version identities.

All implementation identifiers remain strings, including empty strings, leading
zeros, and values outside an implementation's expected range. Numeric conversion
is limited to fields evidenced as numeric canonical properties: alarm code and
message stream/function. Alarm code is checked against the observed XSD byte
range. Invalid values remain in `UnknownExtension` and produce `INVALID_FIELD`
instead of being coerced or discarded.

## Structured metadata

SMN data items retain their wrapper, ordered children, lexical values, attributes,
source positions, and unknown nested material. Primitive, list, set, enumeration,
and bit structures use stable syntax labels. The adapter does not infer protocol
ranges, encoding rules, or length-expression semantics beyond the recorded schema
evidence.

`StandardReference.requirements` contains one immutable `JsonObject` per
`RequirementGroup`. A group records its optional name, ordered requirements, and
source path, line, and column. Each nested requirement records its optional name,
ordered sections, requirement ID, parent requirement ID, implemented boolean,
compliant label, ordered notes, and source location. Closed compliance labels
follow the observed schema values. Unknown values and unknown group/requirement
fields remain extensions with diagnostics. This representation is descriptive
metadata; it does not turn the product into a compliance checker or PASS/FAIL
system.

## References and unknown material

Every E172 reference is emitted as an `EntityReference` with its original string
selector and provenance. `target_key` remains null. The interface's unresolved
ledger records `NOT_ATTEMPTED`, or `MISSING_SELECTOR` when no selector exists.
No lookup, first-match selection, numeric-proximity repair, WKN match, or inferred
relationship occurs in this parser.

Reference resolution is an explicit downstream graph phase documented in
[reference_resolution.md](reference_resolution.md). It does not alter this parser's
evidence-only boundary.

Unknown elements, attributes, nil content, repeated singleton fields, unsupported
structured scalars, invalid closed values, and unsupported declared sections are
retained as `UnknownExtension` where practical. Diagnostics use controlled codes
and messages without echoing untrusted values. Recipe variable parameters and
equipment characterization remain opaque because they are outside the requested
canonical entity categories. Preservation is loss-aware rather than a byte-for-byte
XML round trip.

The versioned synthetic fixtures exercise every evidenced entity category,
multiple command parameters, compound formats, duplicate message identities,
dangling selectors, WKN/source/standard metadata, unknown content, and string IDs.
Additional inline synthetic inputs cover standard requirement groups and invalid
closed values. When the original TrackSys example exists in `work/references/`,
the development suite additionally verifies its recorded entity counts and its
two standard requirement groups containing 8 and 17 requirements. That test skips
when the untracked example is absent; no download or network access is required.
