# Version resilience audit

Prompt 18 audits runtime source, tests, reference tools, and documentation. Only
E172-0225 is implemented in the default registry. A syntactically recognizable
schema label is not proof that a revision exists, is supported, or is conformant.

## Findings and changes

| Area | Finding | Action / boundary |
| --- | --- | --- |
| Secure XML loader | Hardcoded E172 root/namespace prevented new namespaces from reaching adapters; one schema filename was recognized | Removed vocabulary admission and revision interpretation from the loader. It extracts the actual namespace and preserves raw XML, enforcing all existing security limits |
| Revision detection | Unimplemented E172 labels were collapsed to unknown; the registry could not report their identity | Added adapter-layer lexical detection and a read-only registry assessment, retaining candidate labels, schema locations, and diagnostic codes |
| Current adapter | Root names, unqualified children, imported SMN names, field spellings, closed values, and source lexical conversions are E172-0225 rules | Kept these exclusively in `adapters/e172_0225.py` and `_e172_0225_xml.py`; moved root constants there |
| Canonical metadata | Current adapter wrote its revision and schema URL into semantic extension metadata | Removed those transport details from semantic extensions. Revision stays in provenance/result; raw schema location stays in `SourcedDocument` and detection evidence. Genuine unknown extensions retain their existing uncertainty behavior |
| Registry / composition | Lazy concrete import is confined to default registry composition | Preserved no automatic discovery, no first-match rule, and no fallback to the sole installed adapter |
| Model / graph / comparison | No concrete adapter or XML-loader imports; references use canonical roles and explicit target types | Preserved boundaries and added execution tests with concrete imports blocked |
| Reporting / CLI | Report renderers consume canonical models; filesystem commands use the adapter pipeline | No revision branching added. Unsupported CLI inputs report the identified label and exit with a controlled execution error |
| Reference tools / fixtures | Validation tools, fixture manifests, and the semantic demo intentionally name E172-0225 | Kept as explicit development evidence/examples, outside runtime routing. They do not define support for additional revisions |
| Documentation | Loader admission and hint descriptions had become inaccurate | Updated loader and adapter API documentation and migration notes |

DataStructure kind labels, reference roles/target types, and structured standard
requirement keys are canonical contracts, not instructions to parse future XML
with current element spellings. A new adapter must map evidenced semantics into
those contracts. Unknown future data remains opaque. Comparison's reserved
requirement location keys and documentation fields are documented canonical
projection rules; it never dispatches on source revision, XML namespace, or path.

## Identification and unsupported behavior

```python
from sema_sedd.parser import load_xml
from sema_sedd.adapters import default_registry

document = load_xml("equipment.xml")
assessment = default_registry().assess(document)
print(assessment.detection.revision_hint)
print(assessment.status)
```

Only schema hints associated with the actual root namespace participate. An exact
`E172-NNNN-SEDD-Schema.xsd` basename yields a declared label. This is a lexical
convention derived from the supplied schema filename, not evidence of the grammar
or existence of every possible revision. URL query strings, equipment software
revision, arbitrary version attributes, source filenames, and document resemblance
do not establish support. Non-namespaced XML can retain a label from
`xsi:noNamespaceSchemaLocation`; it still requires a compatible adapter.

| Situation | Outcome |
| --- | --- |
| Current root plus exact current hint | Supported by the current adapter, with hint-only diagnostic |
| Current root without a hint | Indeterminate; deliberate library selection is required |
| Identified label without a compatible adapter | Unsupported; error carries `detected_revision`, status and diagnostic code |
| New namespace/root | Secured by loader, assessed by registered adapters; current adapter rejects it |
| Distinct locations, even with equal labels | Ambiguous hint; current adapter refuses mapping |
| Exact repeated location | Deduplicated without changing the assessment |
| Malformed/unknown location | Diagnostic; no automatic current-revision fallback |
| Multiple adapters claiming support | Ambiguous selection; registration order never chooses a winner |

All inspection of hints is local string processing. No URL, XSD import, DTD, or
external entity is fetched. DTD/XXE and structural limits are enforced before
adapter code runs. CLI failures expose fixed messages and recognized numeric
revision labels, not arbitrary untrusted URLs or input contents.

## Extension scaffold and evidence gate

Available local reference evidence covers E172-0225 and its E173 companion schema,
plus the supplied TrackSys example. E173 is an imported notation vocabulary, not
an additional E172 revision adapter. No additional real revision adapter is added.

The existing `SeddAdapter` protocol and `AdapterRegistry` are the production
extension points. `FictionalAdapter` in `tests/test_version_resilience.py` is a
working test scaffold with a different root, namespace, version signal, and field
layout. It is explicitly fictional and is never registered by default.

Before implementing an actual adapter:

1. Record reliable local schema/sample evidence and unresolved semantics.
2. Define conservative root/namespace and revision-signal acceptance in the adapter.
3. Map only evidenced concepts into canonical objects, with source provenance.
4. Preserve unknown content and reject conflicting revision evidence.
5. Register the adapter at composition and test coexistence and cross-adapter
   semantic equivalence/differences. Do not add revision branches downstream.

## Proof and compatibility

Tests compare an E172-0225 document and a fictional attribute-based document with
identical variables and report membership. Their comparison is complete and has
no changes, despite different revision labels, namespaces, paths, and keys. A
units edit produces `SV_UNIT_CHANGED` and the same factual report dependency on
both same-adapter and cross-adapter comparisons. Registry order is reversed as
part of this proof. A subprocess blocks concrete adapter imports and still
executes canonical comparison and report generation.

Other tests cover unidentified/malformed/ambiguous hints, unsupported labels,
explicit override rejection, imported namespaces, identical duplicate hints,
no-namespace hints, URL encoding, no network, and unknown-extension uncertainty.
Static checks keep revision literals out of the parser and downstream packages;
existing import guards keep XML and adapter classes out of domain APIs.

The canonical JSON/report schemas are unchanged. The ingestion API has a deliberate
boundary migration: `load_sedd` remains a spelling alias for `load_xml`, but root
admission now occurs in `load_interface`/the registry. Replace reads of
`document.revision_hint` with `detect_revision(document).revision_hint`. Schema-hint
diagnostics are returned by detection and merged into adapter results. Consumers
that need semantic SEDD validation must use the adapter pipeline, not the raw loader.
