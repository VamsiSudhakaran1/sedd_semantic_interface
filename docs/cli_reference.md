# CLI reference

`sedd` and `python -m sema_sedd` expose the same interface. Use `sedd --help`,
`sedd --version`, or `sedd COMMAND --help`. Quote paths containing spaces.
Input reads are local and read-only.

## Inspect

```text
sedd inspect FILE [--json] [--type TYPE] [--id ID] [--wkn VALUE]
```

Shows revision, equipment metadata, counts, unresolved references, unsupported sections,
and diagnostics. Filters combine exactly; selected entities show immediate relations.
IDs and WKNs are exact strings. Contract: [inspect_cli.md](inspect_cli.md).

## Explore

```text
sedd explore FILE ENTITY [--depth N] [--json]
```

ENTITY is `event:ID`, `alarm:ID`, `status-variable:ID`, or `wkn:VALUE`, and must match
exactly one entity. Depth defaults to 1 and accepts 0-8. Each visited entity includes
properties and incoming/outgoing relations. Resolved links and command containment
are traversed; ambiguous candidates remain visible without becoming traversal edges.
Contract: [explore_cli.md](explore_cli.md).

## Compare

```text
sedd compare OLD NEW [--json] [--type TYPE] [--only-changed]
    [--include-documentation] [--no-color]
```

Sections cover summary, additions/removals, identity-preserving changes, properties,
relationships, documentation-only changes, unresolved items, and diagnostics.
`--only-changed` hides unchanged matches; documentation is hidden unless enabled.
`--no-color` disables ANSI color. JSON is always plain. Type filters affect the view,
not identity matching. Contract: [compare_cli.md](compare_cli.md).

## Report

```text
sedd report FILE --html OUTPUT
sedd report OLD NEW --html OUTPUT
```

One input creates an interface explorer; two create a comparison report. Documentation
is included with local visibility controls. Output is self-contained, escaped HTML
with fixed local script. Existing outputs are replaced atomically; parent directories
must exist. Output cannot alias an input. There is no report `--json` flag; use compare
JSON or the [stable library report API](json_report_contract.md).
Guides: [interface explorer](interface_explorer.md), [comparison HTML](html_report.md).

## Filter names

Inspect accepts:

```text
status_variable data_variable equipment_constant collection_event alarm
remote_command remote_command_parameter supported_message variable_format
default_report event_report_link standard_reference
```

Compare also accepts `equipment_interface` and `equipment_metadata`. `--type` uses
underscores; explore uses the explicit hyphenated `status-variable:ID` selector.
Unknown/abbreviated flags are rejected.

## JSON and exit status

| Output | Version field | Current value |
| --- | --- | --- |
| Inspect | `inspection_schema_version` | `2.0` |
| Explore | `exploration_schema_version` | `1.0` |
| Compare | `comparison_schema_version` | `2.0` |
| Library report / demo.json | `report_schema_version` | `2.0` |
| Canonical model | `model_schema_version` | `1.0` |

Status 0 means successful execution, regardless of findings. Status 2 indicates
arguments, input, unsupported revision, selection, resource, or report-write errors.
No compatibility verdict is encoded in exit status. Output is deterministic for
identical inputs and paths; retained provenance can differ across source locations.
