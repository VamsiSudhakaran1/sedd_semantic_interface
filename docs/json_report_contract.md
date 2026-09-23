# JSON report contract

`sema_sedd.report` publishes version `1.0` of a deterministic comparison report.
`report_from_changes(change_set, source_a, source_b)` projects canonical comparison
results without XML imports or file access. `sema_sedd.reporting.report_files(path_a, path_b)` is a
convenience facade that loads each file through the revision adapter registry;
use `revision_a=` and `revision_b=` when a source has no revision hint. `report_json`
returns compact, key-sorted UTF-8-friendly JSON with one trailing newline.
`report_schema()` reads the [bundled JSON Schema](../src/sema_sedd/report/schema_v1.json)
from the installed package without network access.

```python
from sema_sedd.report import report_json
from sema_sedd.reporting import report_files

report = report_files("before.xml", "after.xml")
print(report_json(report), end="")
```

The required top-level fields are `report_schema_version`, `tool_version`,
`source_a`, `source_b`, `summary`, `matches`, `changes`, `dependency_context`,
`unresolved`, and `diagnostics`. `source_a` and `source_b` identify the input paths
and selected SEDD revisions. `summary.is_complete` reflects comparison certainty;
it does not mean the input was XSD-validated or certified. Counts refer to the
published arrays and to changed entities, as named. One changed entity can emit
multiple `changes` rows.

Each change has a public `change_id`, category, scope, subject, field, before and
after values, and a relationship delta when applicable. The ID is a **change-type
code**, not a unique occurrence key: two changed status variables can both have
`SV_DATA_TYPE_CHANGED`. The subject identifies the entity on each input side.
Codes use an explicit type prefix and a versioned change-kind suffix. Prefixes
are `SV` status variable, `DV` data variable, `EC` equipment constant, `CE`
collection event, `AL` alarm, `RC` remote command, `RCP` remote command
parameter, `SM` supported message, `VF` variable format, `DR` default report,
`ERL` event/report link, `STD` standard reference, `EQ` equipment metadata, and
`EI` equipment interface. The full suffix registry is defined by
`public_change_id` in the report module. Unsupported type/kind pairs fail closed
instead of producing a derived code. The report contains public string tokens,
never Python class names.

`matches` records exact identity strategy, categorical confidence, and the
supporting tokens and source keys. `unresolved` contains uncertain identities,
references, and unknown content; ambiguous matching evidence appears there and
does not become a confirmed change. `dependency_context` records factual
before/after graph context for each changed entity, including dependency evidence
and statements. It is not a risk score. `diagnostics` retains adapter messages
with an `a` or `b` source label; the provisional
`REFERENCE_RESOLUTION_PENDING` adapter message is removed because comparison
has already run reference resolution.

The schema version controls the external JSON shape and meaning. Existing
`change_id` meanings are not reused. A breaking field or meaning change requires
a new major report schema version; additive fields or codes require a documented
version change. `tool_version` independently identifies the package build.
Consumers should validate `report_schema_version` before interpreting fields.
The earlier `sedd compare --json` output has its own
`comparison_schema_version` and layout; it is a separate CLI presentation format.
Call this report API when integrating a machine consumer of the stable contract.

The byte-for-byte [basic](../tests/snapshots/report-basic-v1.json) and
[ambiguous](../tests/snapshots/report-ambiguous-v1.json) snapshots pin the
serialization, source labels, change codes, evidence, and uncertainty behavior.
