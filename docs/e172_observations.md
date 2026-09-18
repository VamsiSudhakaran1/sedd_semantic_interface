# E172-0225 engineering observations and fixture strategy

**OBSERVED — Status: schema analyzed; sample and imported message schema pending.**
This is a schema-only checkpoint of Prompt 2. No runtime parser or adapter was
implemented. Findings below derive from XML declarations, not copied standards prose.

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

**OBSERVED X00b — Missing sources.** The TrackSys sample was not supplied or found
among matching XML files in Downloads. The schema imports
`E173-0415-SECSIIMessageNotation-Schema.xsd` at line 32; this dependency is also
absent. Offline schema compilation failed because `smn:DataItem` cannot be resolved
(line 717). No stub schema or network resolver was substituted. Full validation
has NOT succeeded, even for fixtures which omit imported content.

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
default. AssociatedParameters contains exactly one Parameter in the received XSD,
not an unbounded list. Parameter has Name, ValueFormat of `smn:DataItem`, and
Description. Optional IsRequired has Yes/No/Conditional values, not xs:boolean.

**ASSUMPTION A03 — Parameter multiplicity, PENDING.** The exactly-one declaration
must be compared with the sample and any authoritative erratum. Do not silently
repair it to many parameters. Conditional requiredness is not equivalent to false.

**OBSERVED X09 — Variable formats (lines 698–733, 1308–1333).** VariableFormat has
FormatName (up to 80 characters) and SECSData typed as imported `smn:DataItem`.
Variable Format fields refer to FormatName through explicit keyrefs. Imported
list/primitive structure is not defined by the supplied file and remains pending.

**OBSERVED X10 — Messages (lines 735–757).** SECSMessages contains zero or more
references to imported `smn:SECSMessage`. This file does not define that element's
stream/function fields, direction or structure grammar. None has been invented
for fixtures. The missing E173 file is required to inspect those declarations.

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

## Fixture strategy and current checks

**OBSERVED X15 — Original fixtures.** Four additional candidate XML files now use
the observed root QName, unqualified children and declaration order:

| Fixture | Purpose | Validation status |
| --- | --- | --- |
| minimal/e172-empty.xml | Required header and empty required containers | PENDING imported schema |
| relationships/e172-event-alarm-report.xml | Two events, distinct alarm links, parameterless command, standards metadata, report and event/report link; variable 799 intentionally unresolved | PENDING imported schema |
| changes/e172-alarm-link-after.xml | Same candidate with only ClearEvent changed from 802 to 801 | PENDING imported schema |
| malformed/e172-qualified-children.xml | Deliberately qualified local children; expected schema rejection | PENDING imported schema |

**OBSERVED X15b — Existing groundwork.** Original JSON plans remain explicitly
ASSUMPTION/PENDING. They are neither canonical serialization nor E172 XML. The
neutral XML probes retain their fixture-only namespace. DTD/entity payloads are
bounded and never expanded in inventory tests. HTML/script-like text is never
executed. Depth/size limits and actual loader security tests await the loader.

**OBSERVED X16 — Verification boundary.** Tests verify manifest completeness,
contract concept accounting, candidate QNames and declared structural examples,
and the single-change pair. They do not prove full XSD validity, E172 conformity,
reference resolution, parser security or canonical comparison behavior. Original
reference files remain outside version control; no standards prose is reproduced.

## Canonical concept to fixture coverage matrix

**OBSERVED X17 — Accounting.** Evidence status refers only to inspected schema
structure. Every concept has a source observation or an explicit PENDING entry.
Sample review and complete-schema validation remain pending for every row.

| Canonical concept | Label | Status | Evidence | Fixtures / plans |
| --- | --- | --- | --- | --- |
| Equipment metadata | OBSERVED | OBSERVED | X02 | `minimal/equipment-plan.json`, `minimal/e172-empty.xml` |
| Status Variables | ASSUMPTION | PENDING | X04 | `relationships/variables-plan.json` |
| Data Variables | ASSUMPTION | PENDING | X04 | `relationships/variables-plan.json` |
| Equipment Constants | ASSUMPTION | PENDING | X04 | `relationships/variables-plan.json` |
| Collection Events | OBSERVED | OBSERVED | X06 | `relationships/links-plan.json`, `relationships/e172-event-alarm-report.xml` |
| Alarms | OBSERVED | OBSERVED | X07 | `relationships/links-plan.json`, `relationships/e172-event-alarm-report.xml` |
| Remote Commands | OBSERVED | OBSERVED | X08 | `relationships/commands-messages-plan.json`, `relationships/e172-event-alarm-report.xml` |
| Remote Command Parameters | ASSUMPTION | PENDING | X08 | `relationships/commands-messages-plan.json` |
| Supported SECS Messages | ASSUMPTION | PENDING | X10 | `relationships/commands-messages-plan.json` |
| Variable Formats | ASSUMPTION | PENDING | X09 | `relationships/variables-plan.json` |
| Default Reports | OBSERVED | OBSERVED | X11 | `relationships/links-plan.json`, `relationships/e172-event-alarm-report.xml` |
| Event/Report Links | OBSERVED | OBSERVED | X11 | `relationships/links-plan.json`, `relationships/e172-event-alarm-report.xml` |
| SEMI Standards metadata | OBSERVED | OBSERVED | X12 | `minimal/equipment-plan.json`, `relationships/e172-event-alarm-report.xml` |
| Well-Known Names | ASSUMPTION | PENDING | X12 | `relationships/variables-plan.json` |
| descriptions | OBSERVED | OBSERVED | X13 | `minimal/equipment-plan.json`, `minimal/e172-empty.xml` |
| provenance | ASSUMPTION | PENDING | X13 | `minimal/equipment-plan.json`, `relationships/extensions-plan.json` |
| unresolved references | OBSERVED | OBSERVED | X05 | `relationships/links-plan.json`, `relationships/e172-event-alarm-report.xml` |
| unknown extensions | ASSUMPTION | PENDING | X14 | `relationships/extensions-plan.json` |

## Relationship evidence and remaining work

**OBSERVED X18 — Available structural evidence.** Event variable lists and
state-transition fields: X06. Report-to-variable and event-to-report identifiers:
X11. Alarm set/clear identifiers: X07. Command parameter containment: X08.
Entity WKN/standard fields: X12. Variable-to-format keyrefs: X09.
Supported message wrapper/import: X10. All eleven requested patterns are accounted
for; identifier resolution policy and imported structures remain pending.

**ASSUMPTION A07 — Completion, PENDING.** Supply the TrackSys Model 404 XML and
`E173-0415-SECSIIMessageNotation-Schema.xsd` (with any further imports it declares).
Hash and inspect them, compile the unmodified local schema set without network
access, report sample/schema inconsistencies, then add format/parameter/message
fixtures and independent one-change variants. Promote fixture validation status
only after running that complete schema; preserve unsupported concepts as pending.
No schema stubs or guessed tag mappings may stand in for missing source evidence.
