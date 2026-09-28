# Security and performance hostile audit

Prompt 20, 2026-09-28. All fixtures are original synthetic data. External XML,
identifiers, namespace bindings, descriptions, message bodies, schema hints, and
file paths are treated as untrusted. No standards prose or downloaded test inputs
are included in the regression suite.

## Findings and fixes

| Finding | Fix | Regression evidence in `tests/test_hostile_audit.py` |
| --- | --- | --- |
| Each native-ID/name/WKN lookup scanned its entire index, including an unnecessary untyped preflight lookup | Exact dictionary lookup by type and selector; untyped checks enumerate the fixed canonical type set | `test_native_and_wkn_selectors_use_constant_time_index_lookups` rejects index iteration |
| Inspect, explore, and interface HTML scanned all relationships and command parameters for each entity | Build incoming/outgoing/candidate/containment adjacency once and use local lists | `test_rendering_and_cli_relationships_use_one_shared_adjacency` counts actual graph visits |
| Report-to-event dependency joins scanned all outgoing report links repeatedly | Separate event-edge index; lazy joins | `test_dependency_report_join_uses_event_index` forbids scanning outgoing lists |
| Ambiguous references could multiply candidate storage; candidate inspection could expand it again | Aggregate candidate-occurrence and projected-candidate work budgets | Collision and candidate-projection fanout tests |
| A shallow dependency join could still have enormous breadth | Shared evidence-path budget per dependency index; abort the operation instead of truncating facts | `test_dependency_join_fanout_is_bounded` |
| Character callbacks repeatedly concatenated growing strings | Buffer Expat text and join pending fragments at content boundaries | Fragmented text order test plus callback-count test using 100,000 character references |
| Namespace declarations escaped attribute counting; expanded names and provenance paths could amplify tiny input | Count namespace declarations, bound names and expanded content, and budget aggregate provenance paths | Namespace-size/count/expansion and provenance amplification tests |
| Mixed message content could retain the same large descendant region at many levels | Limit total opaque nodes constructed, including repeated retention | `test_retained_mixed_message_tree_has_work_budget` |
| Unknown/multibyte encoding declarations could leak Python codec exceptions | Convert them to controlled `InvalidXmlError` with source coordinates | Malformed Unicode and encoding parameterized tests |
| Depth overrides could bypass the safe recursion envelope | Hard ceiling of 64, with lower caller limits allowed | Rejected excessive depth and successful deep-message pipeline tests |
| Input path checks missed redirects in ancestors, mapped network drives, Windows devices/streams, and invalid path strings | Validate lexical paths before filesystem probes; reject redirected ancestors; check regular files before and after open | Path-abuse, Windows device/stream, mapped-drive, mocked reparse, symlink, and FIFO tests |
| A hard-linked HTML destination could overwrite an input; failed writes could damage an existing report | Check file identity and write through a temporary sibling followed by atomic replacement | Hard-link and failed-write tests |
| HTML and JSON output could amplify valid input into unbounded strings | Bound HTML fragment accumulation and final length; stream JSON encoding into bounded chunks | HTML budget and controlled CLI JSON-budget tests |
| Model validation repeatedly decomposed the same typing annotations | Fast primitive checks and cached annotation shapes; retain strict value validation | Existing adversarial domain-model tests plus the complete suite |

Existing DTD/XXE rejection, namespace admission by adapters, HTML escaping, opaque
entity anchors, and restrictive report CSPs held under the expanded attack tests.
There is no dynamic HTML insertion, script interpolation from input, external
JavaScript, XInclude fetch, schema fetch, or network client in the runtime pipeline.
The script/markup tests inspect the generated HTML tree: only the fixed application
script remains, with no injected executable elements, event attributes, or URLs.

The runtime now refuses Expat older than 2.7.2. This follows the minimum identified
by the [Python XML security documentation](https://docs.python.org/3/library/xml.html#xml-security),
including native parser protections that application callbacks cannot replace.
The audited runtime has Expat 2.8.3.

## Explicit resource limits

| Resource | Default or fixed ceiling |
| --- | --- |
| Input bytes | 10 MiB; explicit library override available |
| XML depth | 64 hard ceiling; can be lowered |
| XML elements | 100,000; explicit library override available |
| Attributes plus namespace declarations per element | 128; explicit library override available |
| Expanded name or namespace declaration | 1,024 characters |
| Expanded XML names, attributes, and text combined | 16 Mi characters |
| Aggregate adapter provenance paths | 16 Mi characters |
| Opaque XML nodes constructed | 100,000 |
| Reference candidate occurrences | 250,000 per resolution |
| Candidate projection work | Sum of squared candidate counts <= 250,000 per adjacency build |
| Dependency evidence paths considered | 250,000 across calls on one dependency index |
| Explore depth | 0–8; visited-set traversal terminates on cycles |
| HTML / JSON output | 64 Mi Unicode characters each |

Character limits are not byte or resident-memory limits. A Unicode character may
use multiple bytes. Exhaustion raises a typed `ResourceLimitError` (or the loader's
existing `UnsafeXmlError` / `InputTooLargeError`). No incomplete graph, truncated
report, arbitrary ambiguity winner, or successful partial CLI output is returned.
A fresh dependency index starts a new work budget. Depth limits alone are not used
as protection against broad graphs. Hard limits can reject otherwise valid but
exceptionally large documents or reports; that is an execution failure, not a
semantic finding or a compliance verdict.

Input paths are not confined to one directory: ordinary caller-selected local
files and relative paths remain supported. Filesystem checks do not constitute a
sandbox against an independently malicious process racing to replace ancestors.
POSIX no-follow/nonblocking opens strengthen the final-file check. Output replacement
preserves an existing report on a failed write and does not follow an output symlink.

## Reproducible profiles

Use the installed/editable package and the repository's original fixture generator:

```sh
python tools/profile_hostile.py --entities 1000 --relationships 5000 --compare --html --output work/profile-1k
python tools/profile_hostile.py --entities 10000 --relationships 50000 --compare --html --output work/profile-10k
python tools/profile_hostile.py --entities 10000 --relationships 50000 --compare --changed --output work/profile-changes
python tools/profile_hostile.py --entities 1 --relationships 50000 --compare --html --output work/profile-repeated
python tools/profile_hostile.py --entities 1000 --relationships 5000 --description 8000 --compare --html --memory --output work/profile-descriptions
python tools/profile_hostile.py --entities 1000 --relationships 5000 --message-items 20000 --compare --html --memory --output work/profile-messages
```

Add `--profile` for `profile.pstats`, and `--memory` for peak traced Python allocations.
Those instruments add overhead; keep instrumented timings separate from ordinary
wall times. Each generated document also contains one default report, and the message
case contains one supported message. Repeated reference occurrences are preserved.
`--changed` changes every variable's datatype and exercises dependency generation;
the other comparisons establish zero changes against the same canonical model.

Measurements below are single local Windows AMD64 runs with Python 3.12.14 and
Expat 2.8.3. They are descriptive measurements, not cross-machine performance
promises. Timing noise and allocator/cache effects matter. Automated regressions
assert lookup/traversal work and limits rather than fragile timing thresholds.
The first 10k baseline comparison was interrupted by a session pause; its timing
was discarded. Raw results for completed runs are in
[security_performance_results.json](security_performance_results.json).

| Uninstrumented case | Parse | Resolve | Compare | Interface HTML |
| --- | ---: | ---: | ---: | ---: |
| 1,000 variables, 5,000 references | 0.32 s | 0.13 s | 0.59 s | 0.07 s |
| 10,000 variables, 50,000 references | 3.90 s | 2.57 s | 11.66 s | 1.12 s |
| 10,000 changed variables, 50,000 references | 3.96 s | 2.47 s | 16.00 s | Not requested |
| One variable, 50,000 repeated references | 2.57 s | 1.20 s | 6.60 s | 0.73 s |

| Memory-instrumented case | Input | Peak traced allocations | Output HTML |
| --- | ---: | ---: | ---: |
| 10,000 variables, 50,000 references | 2.13 MB | 334.1 MiB | 46.5 MB |
| 1,000 descriptions of 8,000 characters | 8.17 MB | 133.1 MiB | 20.6 MB |
| 20,000 message items plus 1,000 variables / 5,000 references | 0.37 MB | 162.1 MiB | 29.3 MB |

Tracing starts after fixture generation and includes parsed/canonical models,
resolution, comparison, HTML construction, and encoding. It measures Python
allocations, not full-process RSS or browser memory. Both the loaded and resolved
models are deliberately retained by the harness. HTML is output-sized work; a
46 MB document can still be expensive for a browser even though generation is
bounded. Browser rendering performance is not measured by this CLI audit.

## Validation scope

The full suite includes XXE, external and parameter DTDs, entity expansion, UTF-8
and UTF-16 attack encodings, malformed Unicode and codec declarations, recursion,
oversize input, namespace spoofing/rebinding, XInclude retention, filesystem path
abuse, malicious HTML/scripts, crafted exact identifiers, repeated references,
cycles, collision fanout, dependency fanout, large descriptions, and large message
structures. No reference download is required. Platform-specific live symlink
creation and FIFO tests may skip where the host lacks the capability; a mocked
reparse-ancestor regression still runs. Linux CI exercises the FIFO and symlink
paths, while Windows CI exercises device, stream, and mapped-drive path handling.

Final local verification: **501 passed, 2 platform/capability skips**; Ruff lint and
format checks passed; strict mypy passed for both Windows and Linux target settings;
sdist and wheel builds passed. The built wheel was installed into an isolated
target and verified from outside the source checkout using the approved existing
Python interpreter: 1,000-entity filtered inspection, atomic HTML output, bundled
schema loading, XXE rejection, and module entry point all passed. Linux runtime
execution was not performed locally. The fresh-venv console-executable smoke test
remains unavailable under the host's previously observed Windows Application
Control restriction; this audit does not claim that check passed.
