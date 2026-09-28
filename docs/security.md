# Security

XML, names, descriptions, identifiers, namespaces, schema hints, and paths are
untrusted. Processing reads local regular files and performs no schema/entity/DTD
or XInclude fetch, network request, or telemetry.

The loader requires Expat 2.7.2+, rejects DOCTYPE/entities, bounds input/structure,
and converts XML/Unicode/encoding failures to controlled exceptions. Network paths,
mapped Windows network drives, device/alternate streams, and symlink/reparse ancestors
are rejected. Ordinary local paths remain supported. These checks do not sandbox
an independent process racing to replace filesystem ancestors.

HTML escapes values, uses opaque anchors, and has a restrictive CSP with a hash for
its fixed script. Input never supplies executable markup/script bodies. Search/filter
controls work offline. Outputs cannot alias inputs, including hard links. Atomic
replacement preserves an existing report when writing fails; cleanup errors are controlled.

## Resource ceilings

| Resource | Ceiling |
| --- | --- |
| XML input | 10 MiB default |
| Nesting | 64 hard ceiling; can be lowered |
| XML elements | 100,000 default |
| Attributes plus namespace declarations per element | 128 default |
| Expanded name / namespace declaration | 1,024 characters |
| Expanded XML content / aggregate adapter paths | 16 Mi characters each |
| Opaque nodes constructed | 100,000 |
| Candidate occurrences per resolution | 250,000 |
| Candidate projection / dependency evidence | 250,000 work units each |
| Explore | Depth 0-8 with visited-set cycle protection |
| HTML / JSON output | 64 Mi Unicode characters each |

Byte, element, and attribute defaults allow explicit library overrides; fixed ceilings
still apply. Character limits are not byte/RSS limits. Exhaustion raises
`InputTooLargeError`, `UnsafeXmlError`, or `ResourceLimitError`, without successful
partial results or truncated reports.

[XML ingestion](xml_ingestion.md) documents the API;
[the hostile audit](security_performance_audit.md) records detailed attacks, regression
proofs, verification scope, and measured memory/performance. Reports preserve source
paths/content and do not redact confidential data before a caller shares output.

For vulnerability reports, provide a minimal original reproducer, affected version
and runtime, command, and expected/actual behavior. Keep private equipment files,
proprietary schemas, credentials, and private source paths out of public reports.
Start with sanitized examples and arrange an appropriate private channel if needed.
