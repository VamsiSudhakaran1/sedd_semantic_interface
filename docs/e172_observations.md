# E172-0225 engineering observations and fixture strategy

**OBSERVED — Prompt 2 reference analysis and fixture strategy complete. Both original
reference schemas and the complete TrackSys download have been analyzed. The
unmodified sample and positive synthetic fixtures pass offline XSD validation.
Remaining semantic design questions are explicitly ASSUMPTION / PENDING.**
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

**OBSERVED X00c — Original sample received and validated.**
`SEDD_TrackSys_Model404_0225.xml` is 387,563 bytes, SHA-256
`10de748939ba7ac2fd9b233d6df5361aa2bef9a98dd1d3961853eda4da2b765b`.
The supplied original download is well-formed and passes both unmodified schemas
without repair, entity resolution or network retrieval. Source URL:
[TrackSys Model 404 XML](https://dom.semi.org/web/wstandards.nsf/3F009B878C57ABB388258C44006550D6/$file/SEDD_TrackSys_Model404_0225.xml).
The earlier 342,528-byte `tracksys_sample.xml` copy was malformed; it is superseded
as reference evidence. All sample source lines and counts below now refer to the
387,563-byte original download. The access and syntax blockers are resolved.

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

**ASSUMPTION A01 — Revision detection, PENDING.** The inspected TrackSys root provides a schemaLocation hint, but revision-selection
policy still requires a deliberate adapter design; do not treat SOFTREV, a prefix, a
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
observed and sample membership is inspected in S04. General target-kind restrictions
and direct relationship labels still require an explicit canonical design. Do not synthesize a state-machine entity or an edge
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
type, whose child elements are SMN-qualified. Synthetic examples exercise UI4, ASC, LST, ENU, BIT and SET. These fixtures verify
structural syntax; exhaustive compound-type semantics remain explicitly pending.

**ASSUMPTION A08 — Semantic bounds, PENDING.** Do not infer complete SECS numeric
ranges, encoding, length-expression grammar, enum/bit meaning or sequence
normalization from successful XSD validation. Further domain evidence is needed
before those rules become adapter or comparison behavior.

## TrackSys observations

**OBSERVED S01 — Root/header.** Line 2 uses a qualified DataDictionary root with
unqualified SEDD children and xsi:schemaLocation naming the E172-0225 XSD. Header
at line 18 has MDLN Model404, SOFTREV 1.0 and Supplier TrackSys; EquipmentID is
present but empty. CreateDate is 2014-06-12. Equipment software/date metadata
therefore cannot be treated as the SEDD schema revision.

**OBSERVED S02 — Complete document inventory.** `tracksys_observations.json`
records counts, source paths and lines from a strict, non-recovering full parse:

| Entity or field | Count | First source line |
| --- | --- | --- |
| CollectionEvent | 185 | 27 |
| DataVariable | 93 | 3927 |
| StatusVariable | 104 | 4674 |
| EquipmentConstant | 7 | 5488 |
| Alarm | 46 | 5556 |
| VariableFormat | 67 | 6101 |
| SMN SECSMessage | 92 | 7635 |
| RemoteCommand | 7 | 9322 |
| Associated Parameter | 1 | 9325 |
| SupportedSEMIStandard | 1 | 9364 |
| DefaultReportDefinition | 1 | 9504 |
| EventReportLink | 1 | 9520 |
| StateTransition | 161 | 31 |
| WellKnownName | 0 | Not present |

**OBSERVED S03 — Structure and optionality.** Two RecipeVariableParameters
containers occur. All 46 alarms have both set and clear identifiers. Six of the
seven commands have no associated Parameter; schema optionality accommodates
this. No RelevantVariables entries or WellKnownName elements occur anywhere in
this sample. Their schema support is nonetheless observed; sample absence is not
an unsupported-feature rule. Variable formats use primitive values, nested LST,
ENU and BIT shapes, including 47 ENU nodes and one BIT node. The sample contains
EquipmentCharacterization's five named sections. All counts exclude XML comments.

**OBSERVED S04 — Explicit references can remain unresolved.** Numeric target
membership checks find 1,327 event VALIDDVS/VID occurrences; value 0 has no declared
DataVariable target. The 46 alarm SetEvent values (4000 through 4090, even) and
46 ClearEvent values (4001 through 4091, odd) have no declared CollectionEvent
targets. The event/report link points to RPTID 101, while the declared default
report has RPTID 87001. The link's CEID exists, and all three default report VIDs
have declared variable targets. Exact field paths are in the observation JSON.
These results coexist with successful XSD validation: the XSD has no keyrefs for
these fields. Preserve unresolved identifiers and evidence; never invent missing
entities or silently retarget identifiers to a plausible match.

**ASSUMPTION A09 — Special identifier meaning, PENDING.** The absent target for
VID 0 does not establish whether 0 is a sentinel or a sample omission. The alarm
and report mismatches likewise do not establish intent. Preserve the observed
values; do not repair the sample or infer semantics from numeric proximity.

**OBSERVED S05 — Message identities can be ambiguous.** S1F1, S1F2, S1F13 and
S1F14 each occur twice. S1F1 (lines 7635/8882) and S1F2 (7641/8888) even repeat
with the same direction. The S1F13 and S1F14 pairs have opposite directions.
Thus stream/function alone, or even stream/function/direction, does not uniquely
identify every message entry in this sample. Strong-evidence collisions need an
explicit ambiguous state rather than first-match behavior. The original synthetic
`e172-ambiguous-message.xml` repeats a stream/function/direction combination with
a different name to keep this issue visible without copying sample content.

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
for 26 schema-based fixtures. 22 are XSD-valid; 4 are deliberately XSD-invalid:
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
The complete original sample passes XSD validation. This does not establish
semantic reference completeness or canonical implementation status.

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
| Supported SECS Messages | OBSERVED | OBSERVED | X10, M01, S05 | `relationships/e172-complete.xml`, `relationships/e172-ambiguous-message.xml` |
| Variable Formats | OBSERVED | OBSERVED | X09, M02 | `relationships/e172-complete.xml`, `relationships/e172-compound-formats.xml` |
| Default Reports | OBSERVED | OBSERVED | X11 | `relationships/e172-event-alarm-report.xml`, `relationships/e172-complete.xml` |
| Event/Report Links | OBSERVED | OBSERVED | X11 | `relationships/e172-event-alarm-report.xml`, `relationships/e172-complete.xml` |
| SEMI Standards metadata | OBSERVED | OBSERVED | X12 | `relationships/e172-event-alarm-report.xml`, `relationships/e172-complete.xml` |
| Well-Known Names | OBSERVED | OBSERVED | X12 | `relationships/e172-complete.xml` |
| descriptions | OBSERVED | OBSERVED | X13 | `minimal/e172-empty.xml`, `relationships/e172-complete.xml` |
| provenance | ASSUMPTION | PENDING | X13 | `minimal/equipment-plan.json`, `relationships/extensions-plan.json` |
| unresolved references | OBSERVED | OBSERVED | X05, S04 | `relationships/e172-event-alarm-report.xml`, `relationships/e172-complete.xml`, `relationships/e172-dangling-event-variable.xml`, `relationships/e172-dangling-report-link.xml` |
| unknown extensions | ASSUMPTION | PENDING | X14 | `relationships/extensions-plan.json` |

## Relationship evidence and remaining work

**OBSERVED X18 — Available structural evidence.** Event variable lists and
state-transition fields: X06. Report-to-variable and event-to-report identifiers:
X11. Alarm set/clear identifiers: X07. Command parameter containment: X08.
Entity WKN/standard fields: X12. Variable-to-format keyrefs: X09.
Supported message wrapper/import: X10. All eleven requested patterns are accounted
for; identifier resolution policy remains pending; imported structures now have M01/M02 evidence.

**ASSUMPTION A07 — Remaining semantic design, PENDING.** Both schemas and the
full original sample have been studied; no reference file is outstanding.
Runtime identity resolution, provenance retention, unknown preservation and full
compound-format interpretation are future increments. Their pending status is
explicit in this ledger and coverage matrix. They must not silently become parser
behavior. Completing this research increment does not claim a working parser.

**OBSERVED X19 — Reproducing developer validation.** With the original supplied
schemas in `work/references/`, install `.[references]` and run:

```sh
python tools/validate_reference_fixtures.py --references work/references --sample work/references/SEDD_TrackSys_Model404_0225.xml --output docs/e172_validation_results.json
```

The utility checks source fingerprints and requires the recorded original sample
to remain well-formed and XSD-valid. It does not recover or rewrite XML. It does not fetch schemaLocation URLs.
