# Quick start

Follow [installation](installation.md), then run from the repository root. Only
original `examples/` files are used; no external schemas or equipment samples are needed.

## Inspect

```sh
sedd inspect examples/machine-v1.xml
sedd inspect examples/machine-v1.xml --type status_variable --id 44 --json
```

Expect E172-0225 and ExampleMachine, four status variables, two events, one alarm,
two formats, two reports, one event/report link, and one supported message. All
references resolve. `REVISION_HINT_ONLY` is INFO: adapter routing does not establish
schema conformance.

## Explore

```sh
sedd explore examples/machine-v1.xml event:1001 --depth 2
sedd explore examples/machine-v1.xml alarm:72 --json
sedd explore examples/machine-v2.xml "wkn:urn:example:machine:pressure" --depth 1
```

Explore shows properties and incoming/outgoing relations and follows resolved links
in either direction. Default depth is 1; allowed depth is 0-8. Exact WKN selection
does not authenticate that WKN or prove version continuity.

## Compare

```sh
sedd compare examples/machine-v1.xml examples/machine-v2.xml --only-changed --no-color
sedd compare examples/machine-v1.xml examples/machine-v2.xml --include-documentation --json
```

Expect NewCounter added, LegacyCounter removed, ReadingFormat changed, CycleReport
contents changed, an event/report link changed, and swapped alarm events. With
documentation enabled, CycleCount's description change appears as documentation.
Pressure changes `44` to `144`; its exact fictional WKN remains unverified, so the
CLI reports that entity as removed/added. UnchangedReady, both events, ReadyReport,
CountFormat, and DemoMessage remain unchanged despite XML reordering. Completeness
is within implemented semantics, not a claim of official WKN or standards validity.

## Local reports

```sh
sedd report examples/machine-v1.xml --html interface.html
sedd report examples/machine-v1.xml examples/machine-v2.xml --html comparison.html
```

Open the files in a browser. Search, filters, details, provenance, diagnostics, and
the comparison documentation toggle work offline. Output must differ from inputs,
including hard-link aliases.

## Canonical evidence tutorial

```sh
python examples/compare_demo.py > demo.json
```

This explicitly fictional library example supplies evidence from `fictional-wkn.json`
and maps its two declared primitive kinds to canonical `data_type` values. It shows
`SV_IMPLEMENTATION_ID_CHANGED` (`44` to `144`) and `SV_DATA_TYPE_CHANGED` (`U4` to `F4`)
without removing/adding Pressure. The report has 12 matches, one addition, one removal,
eight changed entities, and ten change rows: nine interface and one documentation.
See [the example walkthrough](../examples/README.md) for the full evidence boundaries.

## Findings and errors

Successful execution returns 0 even with changes or unresolved items. Invalid inputs,
unsupported revisions, selectors, and exhausted budgets return controlled execution
errors (status 2). JSON is deterministic for identical inputs and paths. Absolute
provenance paths can differ between checkouts. Compare CLI JSON and the stable library
report are separately versioned; see [CLI reference](cli_reference.md) and
[JSON report contract](json_report_contract.md).
