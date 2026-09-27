# Diagnostics and uncertainty

`sema_sedd.diagnostics.Diagnostic` is the revision-neutral record used by adapters
and graph resolution. It contains a stable code, controlled message,
`DiagnosticSeverity` (`INFO`, `WARNING`, `ERROR`), source provenance, and an
`entity_context` with canonical type and key. `source` and `source_line` are
available directly from provenance. When a user-constructed canonical model has
no provenance, those fields are null rather than invented. A registered adapter's
missing provenance/context is filled with the input document and interface context
by the registry. XML-backed E172 diagnostics identify the owning entity when
possible and the actual line where the issue was observed.

| Code | Severity | Meaning |
| --- | --- | --- |
| `UNKNOWN_ELEMENT` | WARNING | An unmapped XML element was retained as an opaque extension |
| `UNSUPPORTED_EXTENSION` | WARNING | A known unsupported section, attribute, or mixed content was retained |
| `UNRESOLVED_REFERENCE` | WARNING | Exact resolution could not establish one target |
| `AMBIGUOUS_REFERENCE` | WARNING | Exact resolution found multiple candidates |
| `MISSING_OPTIONAL_METADATA` | INFO | Optional description metadata was absent; no value was supplied |
| `MISSING_REQUIRED_STRUCTURE` | ERROR | A required field or section was absent; no value was supplied |
| `UNSUPPORTED_REVISION` | ERROR | No compatible adapter could safely map the input |

Existing detailed codes such as `INVALID_FIELD`, `AMBIGUOUS_FIELD`, `NIL_CONTENT`,
`UNSUPPORTED_FIELD_SHAPE`, and schema-hint codes remain available. Uninterpretable
scalar values are retained as extensions and produce `INVALID_FIELD` at `ERROR`.
Repeated singleton values produce `AMBIGUOUS_FIELD` at `ERROR`, with no arbitrary
first-value selection. A missing description produces only an `INFO` diagnostic;
it does not change a canonical field from null to a guessed value.

The adapter emits `REFERENCE_RESOLUTION_PENDING` while references are unprocessed.
After resolution, inspect, compare, and reports omit that provisional code and
emit one `UNRESOLVED_REFERENCE` or `AMBIGUOUS_REFERENCE` per unresolved graph edge.
The relationship model retains the precise state, reason, selector, and candidates;
no diagnostic resolves a relationship by itself. Unknown extensions remain in the
canonical model, and comparison remains incomplete when they prevent certainty.

Inspection and comparison JSON formats are version `2.0`; their diagnostic rows
include `source`, `source_line`, `entity_context`, and provenance. Comparison also
keeps its old/new side label. The stable JSON report is version `2.0` and retains
`source` as side `a`/`b`, adding `source_path`, `source_line`, and
`entity_context`. Its [schema](../src/sema_sedd/report/schema_v2.json) lists all
required fields. HTML views escape these values and show source and owner context.
Older version 1 schemas and snapshots remain in the repository for consumers that
need to recognize the previous contract.

Unsupported revisions fail before canonical parsing. The typed
`UnsupportedSeddVersionError` exposes `diagnostic_code`, `source`, `source_line`,
`entity_context`, and the recognized revision label when available. Its
`.diagnostic` property returns the same structured record as a failed adapter
assessment. The CLI prints the code and a controlled error message with an
execution failure status. No output asserts semantic
validity for an unsupported input.
