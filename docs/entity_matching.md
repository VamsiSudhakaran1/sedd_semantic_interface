# Cross-version entity matching

Prompt 11 adds `sema_sedd.compare.match_interfaces(old, new)`. Both arguments must
be canonical `EquipmentInterface` objects. The function is deterministic, offline,
and read-only. It imports only model types and application exceptions. It never
loads XML, invokes an adapter, resolves references, or compares source paths.

```python
from sema_sedd.compare import match_interfaces

result = match_interfaces(old_interface, new_interface)
for match in result.matches:
    print(match.old_entity.key, match.new_entity.key, match.strategy, match.confidence)
    for change in match.changes:
        print(change.kind, change.old_value, change.new_value)
```

This API matches versions of the same equipment-interface lineage, as selected by
the caller. It cannot establish that two arbitrary files describe that lineage.
Different model/supplier labels do not automatically authorize or reject a match.
Equipment metadata is not an inventory entity and is not matched by this API.

## Evidence and explicit engineering policy

The evidence below refers to independently recorded observations in
[e172_observations.md](e172_observations.md). Schema identity fields and uniqueness
constraints establish structure and scope; they do **not** prove that a supplier
never reuses an ID across versions. The following continuity rules are explicit
application policy. They do not change XML parser behavior or assert SEMI rules.

| Strategy | Exact signal | Evidence and limits |
| --- | --- | --- |
| `NATIVE_ID` | Canonical type + nonblank implementation ID | X04, X06, X07, X11 describe native variable/event/alarm/report IDs. Enabled for SV, DV, EC, events, alarms and default reports only. The model's generic ID field does not authorize this strategy for other types. |
| `WELL_KNOWN_NAME` | Canonical type + verified authority + scope + value | X12/A05 and the canonical WKN contract require explicit authority evidence. Both sides must record `WknAuthority.VERIFIED`. |
| `COMMAND_NAME` | Exact remote-command name | X08 identifies the command's Name field. Ordinary entity names are not command identities. |
| `PARAMETER_NAME` | Confirmed old/new command pair + exact parameter name | X08/X08b describe parameters contained within commands. Identical names in different commands remain separate. |
| `FORMAT_NAME` | Exact format name | X05/X09 provide explicit references to FormatName. Structure equality is not identity evidence. |
| `STANDARD_DESIGNATION` | Exact standard designation | X12 distinguishes designation from display name and requirement metadata. Revision metadata is retained, not used to split identity. No designation parsing or alias expansion occurs. |
| `EVENT_IDENTITY` | Confirmed old/new event pair addressed by resolved link references | X11 records a link's event and report list. Policy treats a unique link per confirmed event as continuous while preserving report changes. Repeated links for that event remain ambiguous. |
| `STREAM_FUNCTION` | Complete exact stream/function pair | M01 supplies the fields; S05 demonstrates duplicates even with direction. Repeated S/F entries are ambiguous; direction, transport, name, and structure cannot break the tie. |

All tokens include canonical type. Type changes are not inferred as continuity.
IDs and names are not case-folded, stripped, or converted to numbers. `007`, `7`,
and ` 7` are distinct. Missing, empty and whitespace-only identity fields supply
no matching evidence; `0` is usable. These choices are separate from reference
resolution, which can preserve and resolve explicitly supplied empty selectors.

Descriptions, arbitrary names (including exact equal display labels), local keys,
source paths, XML positions, unknown extensions, and structure similarity never
establish identity. No numeric score, fuzzy matching, LLM inference, or maximum
bipartite matching is used.

## WKN trust boundary

A raw matching WKN string is insufficient. `VERIFIED` is a caller-supplied evidence
claim and requires authority, scope, nonblank value and provenance in the model.
The matcher accepts this claim; it does not authenticate a registry or certify an
official name. It retains both full input entities, including the original WKN
evidence and provenance. Authority and scope are compared exactly.

The E172-0225 adapter currently emits `UNVERIFIED` WKNs because its XML strings do
not establish registry authority. They remain visible in input/output entities but
are not matching signals. Supplying a string that looks official, an authority
label alone, or matching unverified strings cannot trigger WKN continuity. Tests
use a fictional registry to exercise the trust contract, not claim official SEMI
names. Authoritative vocabulary verification remains pending outside this API.

## Conflict handling and precedence

The algorithm builds identity groups over the **complete** inventories before
accepting any pair. It then finds connected components of entity occurrences and
identity tokens. An entity is distinguished by side plus local key, so identical
keys in different documents never create an identity edge.

A match requires exactly one old entity and one new entity in its component,
shared evidence, and no contradictory populated identity signals. Any duplicate
identity on either side, even without a counterpart for that particular token,
keeps the whole component ambiguous. A unique secondary signal cannot hide that
collision. One-sided collisions are also reported as ambiguity.

If two signals point to different counterparts, the entire component remains
ambiguous. No pair is removed first to make the remaining evidence look unique.
Even a possible globally unique assignment does not authorize guessing. A pair
with equal ID but different verified WKNs is ambiguous even when neither WKN
finds another counterpart. The same veto applies to contradictory populated
command/parameter names, format names, designations, S/F pairs or confirmed event
identities. Missing or unverified information is not itself a contradiction.

There is one deliberate exception: different native ID **values** do not veto
exact verified WKN continuity. The IDs must still have no competing occurrences
or counterparts anywhere in their identity components. This permits an ID change
without hiding ID reuse or swaps.

After these checks, the primary explanation follows this order: native ID,
verified WKN, entity-specific identity, S/F. This is explanation precedence only;
it never overrides conflict. Native IDs come first because they are directly
addressed interface identities in the recorded structures. WKNs support continuity
across implementation IDs only with explicit authority evidence. Scoped and
entity-specific identities require their corresponding field roles. S/F is used
only when unique because observed messages demonstrate that it is not generally
unique. All agreeing evidence is retained, regardless of the primary strategy.

| Example | Outcome |
| --- | --- |
| Unique type + ID, with changed display name/description | Match by native ID |
| ID 44 becomes 8044, identical verified WKN, no competing ID evidence | WKN match with `IMPLEMENTATION_ID_CHANGED` |
| Equal ID, different verified WKNs | Ambiguous conflicting signals |
| IDs point to A/B while WKNs point to B/A | Whole component ambiguous |
| Duplicate IDs but unique WKNs | Ambiguous collision; no greedy recovery |
| Same S/F appears twice with different directions | Ambiguous collision |
| Equal parameter names in different commands | Separate command scopes |

## Outcomes and evidence records

`MatchingResult` contains `matches`, `ambiguities`, `unmatched_old`, and
`unmatched_new`. Every catalogued input entity, including command parameters, has
exactly one outcome on its side. Ordering uses local keys and fixed token order
only for reproducible presentation; ordering never decides a match.

An `EntityMatch` retains the complete old and new entities, primary `strategy`,
all shared `MatchingEvidence`, categorical `confidence`, and identity `changes`.
Each evidence record includes strategy, canonical type, the exact token, and all
old/new occurrence keys. WKN tokens record authority/scope/value. Dependent tokens
record the confirmed old/new command or event pair. The corresponding match in
the same result explains how that dependency was established.

Confidence categories describe evidence, not estimated correctness:

- `EXACT_IDENTITY`: one unique, non-conflicting native, scoped, named, or S/F signal.
- `VERIFIED_WKN`: exact caller-verified WKN is the sole shared signal.
- `CORROBORATED`: two or more distinct identity fields agree uniquely.

An accepted pair whose stored implementation-ID fields differ carries an
`IdentityChange` with kind `IMPLEMENTATION_ID_CHANGED` and exact old/new values.
This includes a missing-to-present field transition (`None` remains explicit).
Those entities do not appear in unmatched inventories. This increment records
only identity changes, not a full semantic property diff.

`MatchAmbiguity` retains the whole component, all its identity evidence (including
one-sided contradictory values), and `IDENTITY_COLLISION` and/or
`CONFLICTING_SIGNALS`. It records uncertainty; it does not select a candidate.

Unmatched records distinguish `NO_COUNTERPART`, `NO_USABLE_IDENTITY`, and
`NO_CONFIRMED_COMMAND_SCOPE`. A parameter whose parent was not matched retains the
parent key as a dependency. No parameter WKN or name can bypass that scope.
Unmatched inventories do not by themselves assert `REMOVED` or `ADDED`, especially
when evidence or a prerequisite is missing. That classification belongs to a
later semantic comparison increment.

## Dependent identities and bounds

Independent entities are matched first. Parameter matching then uses only
confirmed command pairs. Event/link matching may use already-resolved event
targets only when the events matched. Unresolved/dangling/ambiguous references
are never resolved inside the matcher. Call the separate reference resolver
before matching if event-link identity is needed. A verified WKN on a future
canonical link remains an independent signal, subject to all collision/conflict
checks; reports or their contents never supply identity.

The component walk is iterative and bounded by the supplied finite inventories
and their identity tokens. Duplicate groups are represented once, without
materializing every old/new candidate pair. Traversal work is linear in token
occurrences; deterministic sorting adds sorting costs. Large collisions therefore
do not cause a quadratic pair explosion or recursive traversal.

## Validation

`tests/test_matching.py` exercises all canonical entity categories, ID changes,
WKN authority/scope boundaries, lexical and missing identities, collisions on
either side, one-sided duplicates, swapped and transitive conflicts, scoped
parameters, event-link dependencies, repeated S/F, future revisions, input
immutability, exhaustive outcomes, inventory permutations, process hash seeds,
XML-layer import blocking, and large collision groups. A synthetic XML fixture
also verifies adapter -> resolver -> matcher integration without external files.
The comparison CLI and full semantic diff/report generation remain separate work.

Additional local development verification matched the original TrackSys sample
against itself after reference resolution: 597 matches out of 605 entities per
side, with four ambiguous groups for the repeated S1F1, S1F2, S1F13 and S1F14
messages. No unmatched entities remained. The matcher deliberately does not
short-circuit identical model objects or equal local keys to erase those collisions.
This sample check is optional and is not a test-suite dependency.
