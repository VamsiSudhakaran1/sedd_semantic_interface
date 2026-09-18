# E172-0225 engineering observations and fixture strategy

**OBSERVED — Status: both reference schemas analyzed; synthetic fixtures validated;
supplied TrackSys sample analyzed with explicit XML-syntax limitations.**
No runtime parser, adapter or comparator was implemented. Findings derive from
XML declarations and the received sample, not copied standards prose.

## Reference evidence

**OBSERVED X00 — Source received.** The user supplied `E172-0225-SEDD-Schema.xsd`
on 2026-09-18 (92,338 bytes), SHA-256
`23678aef0204ffbb654403077895be8db9f48b00c7a30934589c259c74f09810`.
Original bytes are preserved locally in ignored `work/references/`. The
[public schema URL](https://dom.semi.org/web/wstandards.nsf/37F6244E9929719388258C4400652DC9/$file/E172-0225-SEDD-Schema.xsd)
is its previously discovered source; this hash identifies the received file,
not an independently authenticated SEMI release. `e172_schema_inventory.json`
records declaration paths, attributes and original source lines without annotations.
Line references below refer to the original received file.

**OBSERVED X00b — Imported schema received.** The supplied E173 ZIP is 4,376 bytes,
SHA-256 `674be022c347639e8a21703feb283fa98fbde395f115b7145c09410e1d596baa`.
It contains the exact import filename from E172 line 32:
`E173-0415-SECSIIMessageNotation-Schema.xsd` (29,725 bytes), SHA-256
`cc339254dd145c19b9d73a892890d8f05dedff4a1389ac934762aad55da6ff30`.
This imported schema has no further imports/includes. Both unmodified schemas
compile offline. Declaration locations are in `e173_schema_inventory.json`.
The earlier missing-dependency blocker is resolved.

**OBSERVED X00c — Sample received.** `tracksys_sample.xml` is 342,528 bytes,
SHA-256 `777d4b5ec3ccf94342fc73aaea1f40ade11d6172c4dad8693fb25bff96fd6ceb`.
The supplied bytes are preserved locally without repair. The first XML error is
line 7988, column 271: angle-bracket text inside Exception is interpreted as
unclosed DATAID/RPTID elements. Additional syntax errors occur around lines
8081, 8343 and 8347. Whole-document XSD validation is therefore not possible.
A browser-style introductory comment is present; the download/copy transformation
history is unknown. Do not attribute these defects to the original SEMI file
without obtaining its original bytes.

## Namespace and top-level structure

**OBSERVED X01 — Namespace (line 2).** The target namespace is
`urn:semi-org:xsd.SEDD`; the schema declares `xs` for XML Schema and `smn` for
`urn:semi-org:xsd.SMN`. It does not set `elementFormDefault` or
`attributeFormDefault`, and contains no local `form` overrides. Thus the global
`DataDictionary` root is qualified, while local SEDD children/attributes are
unqualified under XSD defaults. Prefix spelling is not identity. A default SEDD
namespace applied to all descendants does not match these local declarations.
Imported `smn:SECSMessage` is a global element reference and retains its namespace.

**OBSERVED X02 — Ordered root sequence (lines 33–1293).** These children are
listed in schema sequence order; multiplicities are derived from declarations:

| Child | Occurrences | Source line |
| --- | --- | --- |
| SEDDHeader | 1 | 39 |
| CollectionEvents | 1 | 103 |
| DataVariables | 1 | 259 |
| StatusVariables | 1 | 342 |
| EquipmentConstants | 1 | 425 |
| Alarms | 1 | 513 |
| RecipeVariableParameters | 1..many; RecipeType attribute required | 603, 679 |
| VariableFormats | 1 | 698 |
| SECSMessages | 0..1, nillable | 735 |
| RemoteCommands | 0..1, nillable | 759 |
| SEMIStandards | 0..1, nillable | 878 |
| DefaultReportDefinitions | 0..1, nillable | 1023 |
| DefaultEventReportLinks | 0..1, nillable | 1080 |
| EquipmentCharacterization | 0..1, nillable | 1133 |

**OBSERVED X02b — Header and empty containers.** Header children are MDLN,
SOFTREV, optional EquipmentID, Supplier, CreateDate and Description, in that order
(lines 45–90). CreateDate is an XSD date. MDLN/SOFTREV are strings up to 20
characters; Supplier is up to 80 and Description up to 4096. Required inventory
containers permit zero entity children. An empty RecipeVariableParameters still
needs RecipeType. Representing this section as metadata does not authorize recipe
management functionality; it remains outside the product's operational scope.

**OBSERVED X03 — Revision metadata.** No dedicated root revision attribute or
schema `version` attribute is declared. SOFTREV occurs in the equipment header.
The filename supplies an external revision label, not an in-document revision
selector. The supplied XSD alone does not establish reliable adapter detection.

**ASSUMPTION A01 — Revision detection, PENDING.** Inspect the TrackSys root and
metadata before choosing revision signals; do not treat SOFTREV, a prefix, a
filename or a schemaLocation URL as conclusive revision evidence.

## Entities, identity and references

**OBSERVED X04 — Variable identities (lines 259–512, 1301–1307).** DataVariable
uses VID/DVVALNAME; StatusVariable uses SVID/SVNAME; EquipmentConstant uses
ECID/ECNAME. The identifiers are `xs:unsignedLong`. `UniqueVariableID` spans all
three categories, selecting VID, SVID or ECID. The earlier plan's reused 701 IDs
are therefore an adversarial collision case, not a valid baseline. The declared
constraint concerns XSD numeric values; source lexical spelling can still be
retained for provenance. This alone does not decide cross-version match policy.

**OBSERVED X04b — Scalar properties.** DV/SV have required Format and Description,
optional MinValue/MaxValue, and zero or more UNITS. EC has optional ECMIN, ECMAX,
ECDEF, zero or more UNITS, and required Format/Description. Range/default values
are strings in this XSD. Do not infer their interface data types from XSD string.

**OBSERVED X05 — Enforced links and scope (lines 1294–1333).** The XSD declares
variable Format keyrefs to VariableFormat/FormatName. It also declares uniqueness
for CEID, ALID, FormatName, RecipeType and RVPName in their respective scopes.
It has no declared keyref for event VID, alarm SetEvent/ClearEvent, or report/link
identifiers. Those fields' existence does not prove target resolution. Dangling
and ambiguous targets need explicit canonical handling in a later increment.

**OBSERVED X06 — Events (lines 103–257).** CollectionEvent contains CEID, CENAME,
optional VALIDDVS, optional RelevantVariables, optional StateTransition, required
Description, then optional Source, SEMIStandard and WellKnownName. Both variable
containers contain zero or more numeric VID values with an optional name
attribute. StateTransition has StateModel, TransitionID, PreviousState and NewState
strings. These are two distinct variable lists; merging their meanings loses data.

**ASSUMPTION A02 — Event reference semantics, PENDING.** The field structures are
observed, but target-kind restrictions, direct relationship labels and the sample's
actual usage must be reviewed. Do not synthesize a state-machine entity or an edge
from descriptive text. Report traversal is distinct from an explicit event VID.

**OBSERVED X07 — Alarms (lines 513–601).** Alarm declares ALCD as xs:byte, ALID as
xs:unsignedLong, ALTX up to 120 characters, AlarmName, optional numeric SetEvent
and ClearEvent, Description, and optional Source/SEMIStandard/WellKnownName.
Set/clear fields must remain distinct; the synthetic candidate uses two CEIDs.

## Commands, formats, messages, reports and metadata

**OBSERVED X08 — Remote commands (lines 759–876).** RemoteCommand contains Name,
optional AssociatedParameters, repeated optional ObjectSpecifier, and required
Documentation. Optional useS2F21/useS2F41/useS2F49 booleans each declare a false
default. AssociatedParameters contains one or more Parameter elements: the child declares
1..1, but its enclosing sequence declares 1..unbounded (line 788). Parameter has Name, ValueFormat of `smn:DataItem`, and
Description. Optional IsRequired has Yes/No/Conditional values, not xs:boolean.

**OBSERVED X08b — Multiplicity correction.** The earlier schema-only note incorrectly
considered the Parameter element in isolation. Two parameters validate because
the containing sequence repeats. `relationships/e172-multiple-parameters.xml`
locks down this discovery as a positive example. Conditional requiredness remains
separate from boolean false.

**OBSERVED X09 — Variable formats (lines 698–733, 1308–1333).** VariableFormat has
FormatName (up to 80 characters) and SECSData typed as imported `smn:DataItem`.
Variable Format fields refer to FormatName through explicit keyrefs. Imported list/primitive structure is defined by E173; see M02 below.

**OBSERVED X10 — Messages (lines 735–757).** SECSMessages contains zero or more
references to imported `smn:SECSMessage`. This file does not define that element's
stream/function fields, direction or structure grammar. The imported declarations are now inspected and exercised by original fixtures;
see M01 below.

**OBSERVED X11 — Reports and event/report links (lines 1023–1131).** A
DefaultReportDefinition requires RPTID, DefaultReportName and VIDList containing
one or more VID values; Description is optional. Its container's CanBeDeleted is
optional. DefaultEventReportLinks instead requires CanBeDeleted when non-nil;
EventReportLink has CEID, RPTIDList with one or more RPTID, and optional Description.
No report or link keyrefs occur in this XSD. Repeated member order is retained.

**ASSUMPTION A04 — Sequence semantics, PENDING.** XML schema sequence order is not
the same question as canonical semantic ordering. Do not sort report members or
message structures, or erase significant text, without evidence. Attribute order,
prefix spelling and indentation-only changes have separate mechanics probes.

**OBSERVED X12 — WKN and standards (lines 103–601, 878–1021, 1334 onward).**
WellKnownName is an optional string on events, DV, SV, EC and alarms. Their
SEMIStandard is an optional SEMIStandardType string. The named type is a plain
string restriction; it does not embed an official WKN registry. SupportedSEMIStandard
contains SEMIStandardName and SEMIStandard, optional requirement groups and notes.
Requirement metadata includes declared fields such as Section, RequirementID,
ParentRequirementID and Implemented. Store interface metadata without converting
it into product compliance certification or gating behavior.

**ASSUMPTION A05 — Identity authority, PENDING.** A matching string is not proof
that a WKN is official or globally unique. Establish vocabulary and scope evidence
before assigning WELL_KNOWN_NAME matches. Synthetic labels claim no SEMI status.

**OBSERVED X13 — Descriptions and provenance.** Description, Documentation and
Source occur as separate text fields. Source is not a substitute for input-file,
XML-path or source-line provenance. The schema inspection records original line
numbers and declaration paths. Runtime provenance preservation is still pending.

**OBSERVED X14 — Unknown content.** No xs:any or xs:anyAttribute wildcard appears
in this supplied XSD. EquipmentCharacterization explicitly names SubstrateLocations,
BatchLocations, EPTModules, EquipmentModules and Loadports. Arbitrary foreign
extensions are not automatically schema-valid. Their preservation as unsupported
content is a canonical design question, separate from schema validity.

**ASSUMPTION A06 — Unknown preservation, PENDING.** Decide how the future adapter
retains unsupported declared sections and schema-invalid extensions without
silently discarding them or presenting them as understood entities.

## Imported messages and formats

**OBSERVED M01 — Message metadata.** E173 line 42 declares SECSMessage; required
`s` and `f` attributes (lines 65/70) are xs:integer without explicit range facets
here. Optional direction values are H to E, E to H and Both. Description, Header,
SECSData and Exception children are qualified in `urn:semi-org:xsd.SMN`.
The optional attribute spelling `mnenomic` at line 131 is retained as declared.
The schema also declares replyBit, replyOption, blocking and transport metadata.
XSD acceptance does not establish protocol-valid stream/function ranges or a
unique cross-version identity; these remain separate semantic questions.

**OBSERVED M02 — DataItem structure.** E173 DataItem at line 291 has a repeatable
choice of primitive, list and compound elements, including LST, UI4, ASC, SET,
ENU and BIT. DataItemBase at line 640 extends xs:string, so a primitive-looking
name does not itself enforce numeric payload validity in this schema. Attributes
include name, id, length, description, dataItemName, maxLength and minLength;
length bounds are strings. SET (line 431), ENU (478) and BIT (525) have distinct
nested shapes. E172's unqualified SECSData/ValueFormat wrappers use this imported
type, whose child elements are SMN-qualified. Synthetic examples exercise UI4,
ASC and LST; exhaustive compound-type semantics are explicitly pending.

**ASSUMPTION A08 — Semantic bounds, PENDING.** Do not infer complete SECS numeric
ranges, encoding, length-expression grammar, enum/bit meaning or sequence
normalization from successful XSD validation. Further domain evidence is needed
before those rules become adapter or comparison behavior.

## TrackSys observations and limits

**OBSERVED S01 — Root/header.** Line 2 uses a qualified DataDictionary root with
unqualified SEDD children and xsi:schemaLocation naming the E172-0225 XSD. Header
at line 18 has MDLN Model404, SOFTREV 1.0 and Supplier TrackSys; EquipmentID is
present but empty. CreateDate is 2014-06-12. These values demonstrate why equipment
software/date metadata cannot be treated as the SEDD schema revision.

**OBSERVED S02 — Successfully closed prefix.** A non-recovering XML pull parse
stopped at the first syntax error. Before that point, complete sections contained
185 CollectionEvent, 93 DataVariable, 104 StatusVariable, 7 EquipmentConstant,
46 Alarm and 67 VariableFormat elements. Comments are excluded from these counts.
There are two complete RecipeVariableParameters containers. Entity examples start
at lines 27, 3927, 4674, 5488, 5556 and 6101 respectively. The prefix includes
161 StateTransition elements and both SetEvent and ClearEvent on all 46 alarms.
No WellKnownName appears in this parsed prefix; that is not a claim about the
standard's support or the unparsed remainder. The prefix contains 28 closed
SECSMessage elements; that is not the document's total message count.

**OBSERVED S03 — Independently inspected fragments.** Complete, unchanged textual
sections following the error were separately parsed as XML fragments, without
repairing or pretending to parse the complete document. RemoteCommands starts at
line 9168 and contains 7 commands; one has one Parameter. SEMIStandards at line
9209 has one SupportedSEMIStandard. DefaultReportDefinitions at line 9346 has one
report plus CanBeDeleted; DefaultEventReportLinks at line 9358 has one link plus
CanBeDeleted. EquipmentCharacterization at line 9367 contains its five declared
sections. Fragment observations do not establish whole-document nesting, global
identity constraints, or schema validity.

**ASSUMPTION A09 — Sample verification, PENDING.** Original well-formed download
bytes are needed to validate the entire TrackSys document and resolve any
sample/schema discrepancies. No recovered tree is used as a parser contract.
The observed filename/schemaLocation alone does not authenticate a revision.

## Fixture strategy and current checks

**OBSERVED X15 — Original fixtures.** `manifest.json` accounts for all original
fixture files and their evidence. The E172 synthetic documents use the observed
root namespace, unqualified local fields, and qualified SMN children where needed.
`relationships/e172-complete.xml` covers every declared core entity category,
state-transition metadata, named formats, a command parameter, a nested message,
report/link references and fictional WKN/standard strings. No fixture is a copied
or truncated TrackSys document; fictional WKNs are not claimed to be official.

**OBSERVED X15b — Validation.** `docs/e172_validation_results.json` records schema
fingerprints, fixture fingerprints, validator versions and the actual outcomes
for 22 schema-based fixtures. 18 are XSD-valid; 4 are deliberately XSD-invalid:
qualified local children, duplicate variable IDs across categories, undefined
format, and unknown foreign extension. Dangling report/variable and alarm/event
identifiers can be XSD-valid because their target relationships lack XSD keyrefs.
They must still remain unresolved in future canonical processing.

**OBSERVED X15c — Change fixtures.** Eleven independent text-field changes have
an explicit before/after path and expected future change category in
`changes/change-cases.json`. A separate message-structure case adds a BOO field.
The original neutral probes isolate XML prefix, indentation and attribute-order
noise, and significant text differences. Canonical comparison is not implemented;
these are fixture expectations, not comparison test results.

**ASSUMPTION A10 — Remaining change coverage, PENDING.** Entity add/remove,
implementation-ID matching, data-type/format changes, and generic relationship
add/remove behavior still have scenario plans rather than canonical output
assertions. Unknown-change classification, ambiguous identity and unsupported
compound formats require later model/comparator decisions. No planned rule has
been added to runtime parser behavior.

**OBSERVED X16 — Verification boundary.** Inventory tests cover every contract
concept, candidate structure, single-change integrity and recorded validation
fingerprints. The offline utility reproduces XSD checks using only the two pinned
local schemas and denies every other schema resolution. Neither the utility nor
these fixtures implement the production secure loader. DTD payloads are not
expanded, external addresses are never fetched, and report text is never executed.
Depth/size boundaries await explicit loader limits. Reference bytes are ignored by
Git; no standards prose is copied into the source distribution.

## Canonical concept to fixture coverage matrix

**OBSERVED X17 — Accounting.** Evidence status refers only to inspected schema
structure. Every concept has a source observation or an explicit PENDING entry.
Full sample validation remains pending because the supplied sample is malformed.
Synthetic XSD results are recorded separately from canonical implementation status.

| Canonical concept | Label | Status | Evidence | Original XML / plans |
| --- | --- | --- | --- | --- |
| Equipment metadata | OBSERVED | OBSERVED | X02 | `minimal/e172-empty.xml`, `relationships/e172-complete.xml` |
| Status Variables | OBSERVED | OBSERVED | X04 | `relationships/e172-complete.xml` |
| Data Variables | OBSERVED | OBSERVED | X04 | `relationships/e172-complete.xml` |
| Equipment Constants | OBSERVED | OBSERVED | X04 | `relationships/e172-complete.xml` |
| Collection Events | OBSERVED | OBSERVED | X06 | `relationships/e172-event-alarm-report.xml`, `relationships/e172-complete.xml` |
| Alarms | OBSERVED | OBSERVED | X07 | `relationships/e172-event-alarm-report.xml`, `relationships/e172-complete.xml` |
| Remote Commands | OBSERVED | OBSERVED | X08 | `relationships/e172-event-alarm-report.xml`, `relationships/e172-complete.xml` |
| Remote Command Parameters | OBSERVED | OBSERVED | X08, M02 | `relationships/e172-complete.xml` |
| Supported SECS Messages | OBSERVED | OBSERVED | X10, M01 | `relationships/e172-complete.xml` |
| Variable Formats | OBSERVED | OBSERVED | X09, M02 | `relationships/e172-complete.xml` |
| Default Reports | OBSERVED | OBSERVED | X11 | `relationships/e172-event-alarm-report.xml`, `relationships/e172-complete.xml` |
| Event/Report Links | OBSERVED | OBSERVED | X11 | `relationships/e172-event-alarm-report.xml`, `relationships/e172-complete.xml` |
| SEMI Standards metadata | OBSERVED | OBSERVED | X12 | `relationships/e172-event-alarm-report.xml`, `relationships/e172-complete.xml` |
| Well-Known Names | OBSERVED | OBSERVED | X12 | `relationships/e172-complete.xml` |
| descriptions | OBSERVED | OBSERVED | X13 | `minimal/e172-empty.xml`, `relationships/e172-complete.xml` |
| provenance | ASSUMPTION | PENDING | X13 | `minimal/equipment-plan.json`, `relationships/extensions-plan.json` |
| unresolved references | OBSERVED | OBSERVED | X05 | `relationships/e172-event-alarm-report.xml`, `relationships/e172-complete.xml` |
| unknown extensions | ASSUMPTION | PENDING | X14 | `relationships/extensions-plan.json` |

## Relationship evidence and remaining work

**OBSERVED X18 — Available structural evidence.** Event variable lists and
state-transition fields: X06. Report-to-variable and event-to-report identifiers:
X11. Alarm set/clear identifiers: X07. Command parameter containment: X08.
Entity WKN/standard fields: X12. Variable-to-format keyrefs: X09.
Supported message wrapper/import: X10. All eleven requested patterns are accounted
for; identifier resolution policy remains pending; imported structures now have M01/M02 evidence.

**ASSUMPTION A07 — Remaining evidence, PENDING.** The schemas and available sample
content have been studied. A well-formed original TrackSys download is still
needed for full-document validation. Runtime identity resolution, provenance,
unknown preservation and unexercised compound-format semantics remain explicitly
pending. These gaps must not silently become parser behavior.

**OBSERVED X19 — Reproducing developer validation.** With the original supplied
schemas in `work/references/`, install `.[references]` and run:

```sh
python tools/validate_reference_fixtures.py --references work/references --sample work/references/tracksys_sample.xml --output docs/e172_validation_results.json
```

The utility checks source fingerprints and records the sample's syntax failure
without attempting recovery. It does not fetch schemaLocation URLs.
