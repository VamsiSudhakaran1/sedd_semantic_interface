# Original machine examples

`machine-v1.xml` and `machine-v2.xml` describe fictional ExampleMachine equipment.
All values/descriptions are original. The namespace/schema hint names the supported
mapping, but this tutorial makes no XSD conformance claim. No external schema,
official equipment sample, or proprietary artifact is required.

From the repository root:

```sh
sedd inspect examples/machine-v1.xml
sedd explore examples/machine-v1.xml alarm:72 --depth 2
sedd compare examples/machine-v1.xml examples/machine-v2.xml --include-documentation --no-color
sedd report examples/machine-v1.xml --html interface.html
sedd report examples/machine-v1.xml examples/machine-v2.xml --html comparison.html
python examples/compare_demo.py > demo.json
```

## Intended changes

| Demonstration | Before / after | XML CLI | Fictional evidence tutorial |
| --- | --- | --- | --- |
| Addition | NewCounter 47 absent / present | `SV_ADDED` | Same |
| Removal | LegacyCounter 46 present / absent | `SV_REMOVED` | Same |
| ID change with same WKN | Pressure 44 / 144; exact `urn:example:machine:pressure` retained | Removed + added; raw WKN unverified | `SV_IMPLEMENTATION_ID_CHANGED`, via `WELL_KNOWN_NAME` |
| Datatype | ReadingFormat `UI4` / `FP4` | `VF_FORMAT_CHANGED` in structure | Also `SV_DATA_TYPE_CHANGED`, canonical `U4` / `F4` |
| Report relationship | CycleReport 5001 replaces LegacyCounter with NewCounter; pressure follows its new ID | `DR_REPORT_CONTENT_CHANGED` | Pressure endpoint reconciles; only counter replacement is a membership delta |
| Event/report link | Event 1001 gains ReadyReport 5002 | `ERL_EVENT_REPORT_LINK_CHANGED` | Same |
| Alarm/event links | Alarm 72 swaps set/clear events 1001 and 1002 | Two `AL_ALARM_EVENT_LINK_CHANGED` rows | Same |
| Documentation | CycleCount 45 description gains “since reset” | `SV_DESCRIPTION_CHANGED` when enabled | Same, `DOCUMENTATION_CHANGE` |
| XML reorder | Inventory, singleton field, format/report definition, message attribute order | No changes to UnchangedReady, Started/Stopped, ReadyReport, CountFormat, DemoMessage | Same |

Report member and message data order remain meaningful and are preserved. The
unchanged subset proves that XML occurrence paths are not identity. Tests separately
reorder all inventories, singleton fields, and attributes in v1 while preserving
protocol order, then verify zero semantic changes for that isolated reorder.

## Evidence boundaries

Production parsing does not authenticate WKN authority. Equal XML WKN strings remain
`UNVERIFIED`. Normal CLI comparison has 11 matches, two additions, and two removals;
one inventory pair is the pressure renumbering. The output does not fabricate continuity.

`compare_demo.py` uses only the bundled tutorial files. Original `fictional-wkn.json`
declares one fictional value, authority, scope, and two pressure IDs. The script labels
that value `VERIFIED` under the canonical caller-evidence contract and retains the
registry as provenance. It does not claim an official SEMI WKN or verify arbitrary
input files. Production callers need reliable authority evidence for such claims.

The script separately maps the fixture's two expressly defined simple primitive
kinds (`ui4`, `fp4`) to scalar labels (`U4`, `F4`). Other shapes are rejected. It adds
no general format inference to the XML adapter, which keeps the structured format
and leaves scalar `data_type` unset.

The tutorial uses public report schema `2.0`: 12 matches, one addition, one removal,
eight changed entities, ten rows (nine interface, one documentation), no unresolved
items, and complete comparison within its fictional evidence scope. Its manually
constructed library report omits adapter routing diagnostics; matching evidence and
before/after provenance remain visible.
