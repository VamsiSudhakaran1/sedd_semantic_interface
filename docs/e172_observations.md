# E172-0225 observations and fixture strategy

**OBSERVED — Status: reference analysis blocked; Prompt 2 is not complete.**
The source index is accessible, but the developer XSD and TrackSys Model 404 XML
bytes have not been retrieved. This document deliberately contains no claimed
schema observations. All canonical mappings are explicitly pending.

## Evidence register

**OBSERVED O01 — Public sources.** On 2026-09-18, the
[SEMI XML files index](https://dom.semi.org/web/wstandards.nsf/schema) listed both
an E172-0225 complementary schema and a TrackSys Model 404 sample under E172-0225.
Listing labels establish availability, not document contents or compatibility.

**OBSERVED O02 — Retrieval result.** Direct HTTPS requests to `dom.semi.org` and
`downloads.semi.org` returned HTTP 403 browser-challenge HTML. The browser rendered
the index, but its download actions did not yield inspectable local files in this
session. The web reader also could not expose either file's content. No source
hash, schema validation result, or sample counts can be reported.

**OBSERVED O03 — Exact references.**

- [Developer schema](https://dom.semi.org/web/wstandards.nsf/37F6244E9929719388258C4400652DC9/$file/E172-0225-SEDD-Schema.xsd)
- [TrackSys Model 404 sample](https://dom.semi.org/web/wstandards.nsf/3F009B878C57ABB388258C44006550D6/$file/SEDD_TrackSys_Model404_0225.xml)

**OBSERVED O04 — Local scope.** The current repository has no revision adapter,
XML loader, canonical model, or third-party reference files. The master contract
names the desired canonical concepts; it is not evidence of E172 element names.
The searched workspace and attachment directories yielded no matching references.

## Engineering observation ledger

Every row below is **ASSUMPTION**, meaning an unresolved engineering question,
not a conclusion about E172. Status **PENDING** blocks use as parser behavior.
Evidence must include exact XSD declaration paths and sample paths where present.
Absence from one sample cannot establish that a schema feature is unsupported.

| ID | Label | Topic | Status | Evidence still required |
| --- | --- | --- | --- | --- |
| A01 | ASSUMPTION | Namespace structure | PENDING | Target namespace, qualification defaults, QName use, imports/includes; do not infer namespace from prefixes or filenames. |
| A02 | ASSUMPTION | Top-level structure | PENDING | Root declaration, containers, compositor rules and multiplicities; no invented SEDD root. |
| A03 | ASSUMPTION | Revision metadata | PENDING | Actual revision fields and sample values, schema versus equipment/software revision, conflicting/missing signals. Filename is not an adapter-selection rule. |
| A04 | ASSUMPTION | Entity types | PENDING | Declarations for each canonical category; schema alternatives and sample presence recorded separately. |
| A05 | ASSUMPTION | Identifiers | PENDING | Lexical types, key/unique constraints and scope, leading-zero rules; do not coerce identifiers to integers speculatively. |
| A06 | ASSUMPTION | References | PENDING | Reference fields, keyrefs/IDREFs if any, target scope, missing and ambiguous targets. |
| A07 | ASSUMPTION | Relationship patterns | PENDING | Direct event-variable, event-report, report-variable, alarm-event, command-parameter and standard/WKN/format relationships. Do not conflate direct edges with graph reachability. |
| A08 | ASSUMPTION | Optionality | PENDING | minOccurs/maxOccurs, attribute use, defaults, nillable and choices, inherited constraints; missing, empty, nil and defaulted values remain distinct until policy is established. |
| A09 | ASSUMPTION | WKN representation | PENDING | Element/attribute shape, scope, namespace, vocabulary authority and collision behavior. A fictional fixture WKN is never an official WKN. |
| A10 | ASSUMPTION | Supported messages | PENDING | Stream/function fields, ranges, direction, metadata and structure grammar; stream/function alone may not capture all distinctions. |
| A11 | ASSUMPTION | Default reports | PENDING | Report identity, member reference syntax, ordering and event-link representation. |
| A12 | ASSUMPTION | Alarms | PENDING | Alarm identity, set/clear event references, optionality and unresolved target representation. |
| A13 | ASSUMPTION | Remote commands | PENDING | Command identity, parameter ownership, optionality, constraints, format and name scope. |
| A14 | ASSUMPTION | Variable formats | PENDING | Inline/named formats, nesting, data types, allowed values, units, ranges and defaults; distinguish lexical XSD types from interface types. |
| A15 | ASSUMPTION | Descriptions and provenance | PENDING | Description shape/mixed content/language; source paths and lines; equipment revision versus schema revision. |
| A16 | ASSUMPTION | Standards metadata | PENDING | Standard identity/revision fields and entity-standard association syntax. |
| A17 | ASSUMPTION | Unknown extensions | PENDING | Wildcards or extension points, foreign namespace handling, preservation boundaries. Unknown is not automatically schema-valid. |
| A18 | ASSUMPTION | Ordering and whitespace | PENDING | Identify unordered collections versus meaningful sequences and text; never sort message structures or strip every space. |

## Original synthetic fixtures

**OBSERVED O05 — Fixture scope.** `tests/fixtures/manifest.json` inventories the
original fixtures. None is claimed to be E172-valid. JSON scenario plans describe
fictional test data and are labeled `ASSUMPTION` / `PENDING`; they are neither
canonical-model serialization nor SEDD wire format. XML mechanics probes use a
project-owned fixture namespace or deliberately generic XML. A future E172 adapter
must never accept this namespace as an alias for a SEMI namespace.

**OBSERVED O06 — Directory responsibilities.**

| Directory | Available material | Still pending |
| --- | --- | --- |
| minimal | Small neutral XML probe and equipment scenario plan | Smallest XSD-valid E172 document with required metadata |
| relationships | Original variable, event/report/alarm, command/message and extension scenario plans | Actual E172 XML encodings and expected resolved/unresolved relationships |
| malformed | Truncated XML, duplicate attribute, undeclared prefix, external entity/DTD, bounded entity expansion, namespace impostor and escaped report markup | Loader assertions and E172 semantic-invalid examples |
| changes | Prefix/attribute-order/indentation pair, significant-text pair and semantic-change scenario plan | E172 before/after pairs and canonical comparison assertions |

**OBSERVED O07 — Scope of checks.** Current tests check inventory integrity,
contract concept coverage, local XML mechanics and preservation of significant
text in the probes. They do not test an E172 parser or claim XXE protection in
application code. DTD probes are inspected as bytes and never expanded by these
tests. Their external addresses are inert fictional test targets, never fetched.
The escaped script payload is text and is never rendered or executed.

**ASSUMPTION A19 — Future fixture promotion, PENDING.** Once both sources are
available, create original minimal and relationship XML against verified
namespace/declarations. Validate against a pinned local schema with network and
entity resolution disabled. Inspect schema imports before loading; obtain any
required dependencies explicitly. Record schema-validation outcome separately
from expected adapter semantics. Confirm the reference sample's own validity;
report discrepancies without repairing or treating the sample as normative.

**ASSUMPTION A20 — Future security/resource checks, PENDING.** A later secure-loader
increment must prove zero network/file resolution for DTD/entity fixtures and
exercise depth/size boundaries with generated bounded inputs. Numeric resource
limits have not been selected here. Namespace and HTML cases are well-formed
adversarial inputs, not necessarily XML syntax errors.

## Canonical concept to fixture coverage matrix

**OBSERVED O08 — Coverage accounting.** Every master-contract concept is listed
below and in the machine-readable manifest. `PENDING` means no E172 evidence was
obtained; scenario coverage does not remove that evidence gap.

| Canonical concept | Classification | Evidence status | Original scenario coverage |
| --- | --- | --- | --- |
| Equipment metadata | ASSUMPTION | PENDING | `minimal/equipment-plan.json`; `changes/semantic-plan.json` |
| Status Variables | ASSUMPTION | PENDING | `relationships/variables-plan.json`; `changes/semantic-plan.json` |
| Data Variables | ASSUMPTION | PENDING | `relationships/variables-plan.json`; `changes/semantic-plan.json` |
| Equipment Constants | ASSUMPTION | PENDING | `relationships/variables-plan.json`; `changes/semantic-plan.json` |
| Collection Events | ASSUMPTION | PENDING | `relationships/links-plan.json`; `changes/semantic-plan.json` |
| Alarms | ASSUMPTION | PENDING | `relationships/links-plan.json`; `changes/semantic-plan.json` |
| Remote Commands | ASSUMPTION | PENDING | `relationships/commands-messages-plan.json`; `changes/semantic-plan.json` |
| Remote Command Parameters | ASSUMPTION | PENDING | `relationships/commands-messages-plan.json`; `changes/semantic-plan.json` |
| Supported SECS Messages | ASSUMPTION | PENDING | `relationships/commands-messages-plan.json`; `changes/semantic-plan.json` |
| Variable Formats | ASSUMPTION | PENDING | `relationships/variables-plan.json`; `changes/semantic-plan.json` |
| Default Reports | ASSUMPTION | PENDING | `relationships/links-plan.json`; `changes/semantic-plan.json` |
| Event/Report Links | ASSUMPTION | PENDING | `relationships/links-plan.json`; `changes/semantic-plan.json` |
| SEMI Standards metadata | ASSUMPTION | PENDING | `minimal/equipment-plan.json`; `changes/semantic-plan.json` |
| Well-Known Names | ASSUMPTION | PENDING | `relationships/variables-plan.json`; `changes/semantic-plan.json` |
| descriptions | ASSUMPTION | PENDING | `minimal/equipment-plan.json`; `changes/semantic-plan.json` |
| provenance | ASSUMPTION | PENDING | `minimal/equipment-plan.json`, `relationships/extensions-plan.json`; `changes/semantic-plan.json` |
| unresolved references | ASSUMPTION | PENDING | `relationships/links-plan.json`; `changes/semantic-plan.json` |
| unknown extensions | ASSUMPTION | PENDING | `relationships/extensions-plan.json`; `changes/semantic-plan.json` |

## Relationship evidence checklist

**ASSUMPTION A21 — All mappings below are PENDING.** These are requested product
relationships, not discovered schema relationships.

| Requested relationship | Scenario | Evidence status |
| --- | --- | --- |
| Collection Event → variables | links-plan | PENDING |
| Collection Event → state-transition metadata | links-plan | PENDING |
| Default Report → variables | links-plan | PENDING |
| Collection Event → default report | links-plan | PENDING |
| Alarm → set event | links-plan | PENDING |
| Alarm → clear event | links-plan | PENDING |
| Remote Command → parameters | commands-messages-plan | PENDING |
| Entity → WKN | variables-plan | PENDING |
| Entity → standard | equipment-plan | PENDING |
| Variable → format | variables-plan | PENDING |
| Supported Message → structure/metadata | commands-messages-plan | PENDING |

## Resuming the analysis

**ASSUMPTION A22 — Completion procedure, PENDING.** Supply the two reference files
in `work/references/` or attach them. Record original filename, exact source URL,
retrieval date, byte length and SHA-256 before analysis. Preserve original bytes.
Replace each pending question with independently written `OBSERVED` findings
linked to exact source paths/lines; preserve genuine unresolved questions as
`ASSUMPTION`. Build the E172 fixture variants only from supported declarations.
Update the coverage manifest with evidence IDs and validate every claimed mapping.
Do not advance adapter implementation on unresolved assumptions.

**OBSERVED O09 — Publication boundary.** No standards prose or reference document
content is copied into this repository. Only the public source links, retrieval
observations, original engineering questions and original synthetic test material
are recorded. Prompt 2 requires further work when the reference bytes arrive.
