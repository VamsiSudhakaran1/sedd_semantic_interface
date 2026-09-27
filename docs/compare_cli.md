# `sedd compare`

Compare two local SEDD files in old-to-new order:

```sh
sedd compare old.xml new.xml
sedd compare old.xml new.xml --json --only-changed
sedd compare old.xml new.xml --type alarm --include-documentation --no-color
```

The command loads each file through the secure loader and revision adapter, then
runs canonical reference resolution, matching, semantic comparison, and factual
dependency context. A schema hint selects an adapter; it does not validate the
file against an XSD. XML WKN text alone is unverified, so the CLI cannot assert
ID continuity from WKN without separate trusted evidence.

## Sections and options

Text output contains Summary, Added, Removed, Identity-preserving changes,
Property changes, Relationship changes, Documentation-only changes, Unresolved
items, and Diagnostics, in that order. It also lists unchanged confirmed matches
by default. Changed entity rows include old and new factual dependency statements.
Property and relationship rows show exact before/after values and change kinds.

| Option | Effect |
| --- | --- |
| `--json` | Emit deterministic compact JSON with one trailing newline. |
| `--type TYPE` | Select one exact canonical type, such as `status_variable`, `alarm`, or `default_report`. Equipment/interface metadata types are available. Adapter diagnostics stay source-wide. |
| `--only-changed` | Hide unchanged confirmed matches. |
| `--include-documentation` | Show documentation-only entities and documentation properties on entities with other changes. The default reports how many documentation-only changes are hidden. |
| `--no-color` | Disable ANSI section colors. Color is used only on a terminal and honors `NO_COLOR`. JSON never contains color codes. |

A matched entity with both documentation and interface edits remains one entity
change. Without `--include-documentation`, the display hides its documentation
properties and retains the interface properties. A documentation-only entity
appears in its own section when requested.

`--type` filters displayed entity changes, unchanged matches, and comparison
issues. Summary `is_complete` always describes the whole comparison: a type
filter cannot make uncertainty elsewhere disappear. Diagnostics from both
input adapters remain visible with old/new side labels. Unresolved items include
ambiguous identity, insufficient identity, unresolved references, uncertain
targets, and unknown content. Candidate references and unknown extensions do
not become confirmed changes.

## JSON contract

The top-level `comparison_schema_version` is `2.0`. Source paths and
revisions, selection options, and the summary precede arrays named `added`,
`removed`, `identity_preserving_changes`, `property_changes`,
`relationship_changes`, `documentation_only_changes`, `unchanged_matches`,
`unresolved_items`, and `diagnostics`. Summary counts describe displayed items
and report `hidden_documentation_only_changes` separately.

Entity change objects retain canonical snapshots, accepted match strategy and
evidence, old/new graph context, categories, change kinds, properties, and
relationships. The Property and Relationship arrays offer a flatter
subject-plus-change view. The selection options apply to both views. Source
provenance is retained, so semantically equivalent files with different
locations need not produce byte-identical JSON. The same inputs and options
produce stable JSON. `--no-color` does not affect JSON.

## Exit status

Status **0** means both files loaded and the comparison rendered. Added or
removed entities, documentation changes, unresolved references, ambiguous
identity, unknown content, and adapter warnings are findings and still exit 0.
Invalid arguments and unreadable, unsafe, malformed, or unsupported input
produce controlled errors and status **2**. The command does not infer
compatibility or predict application failure.

`tests/test_compare_cli.py` covers all sections and options, type filtering,
documentation visibility, deterministic JSON, specific change kinds, ambiguous
and unresolved findings with status 0, syntax-only XML noise, and input errors.
The installed-wheel smoke test exercises the console command with a changed
alarm and pre-existing unresolved reference.
