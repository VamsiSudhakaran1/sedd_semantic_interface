# Safe XML ingestion

`sema_sedd.parser.load_xml(path)` reads a local XML file and returns a
`SourcedDocument`. It preserves expanded element and attribute names, mixed-content
order, the resolved source path, byte count, root namespace, raw schema location,
and one-based start-tag positions. `load_sedd` remains an alias for this secure
loader. For example:

```python
from sema_sedd.parser import load_xml
from sema_sedd.adapters import default_registry

document = load_xml("equipment.xml")
print(document.root.tag, document.root.location)
assessment = default_registry().assess(document)
print(assessment.detection.revision_hint, assessment.status)
```

The loader accepts UTF-8 XML, including non-ASCII text, without assuming a
particular root, namespace, or standard revision. The adapter layer interprets
schema hints and decides whether a document has supported semantics. A future
namespace can therefore reach a registered adapter without editing the loader.
An unexpected namespace is still rejected by the normal `load_interface` pipeline
when no adapter supports it. Schema hints never cause network or filesystem reads.
The generic XML tree contains no canonical entities.

As of Prompt 18, `SourcedDocument.revision_hint` and schema-hint diagnostics have
moved to `detect_revision(document)` in `sema_sedd.adapters`. Loader diagnostics
remain reserved for generic XML concerns. Root/version rejection occurs at adapter
selection rather than during XML ingestion. See
[revision_adapters.md](revision_adapters.md) for routing and deliberate selection.

The parser requires Expat 2.7.2 or newer, with external parameter parsing disabled.
It rejects DOCTYPE and entity declarations before expansion, and buffers character
callbacks to avoid repeatedly copying fragmented text. Unknown and unsupported
encoding declarations produce controlled `InvalidXmlError` failures.

Only local regular files are admitted. Network/URL paths, Windows devices and
alternate streams, mapped network drives, and symlink/reparse ancestors are rejected.
Regular-file checks occur before opening and against the opened descriptor; POSIX
opens use no-follow and nonblocking flags where available. These checks are not a
sandbox against a separate process concurrently replacing filesystem ancestors.

Default limits are 10 MiB input, 64 nested elements, 100,000 elements, and 128
attributes plus namespace declarations per element. `max_bytes`, `max_elements`,
and `max_attributes` accept positive overrides. `max_depth` can be lowered but
cannot exceed the hard safe ceiling of 64. Additional fixed ceilings are 1,024
characters per expanded name or namespace declaration and 16 Mi characters of
expanded names/attributes/text. The E172 adapter also caps aggregate provenance
paths at 16 Mi characters and retained opaque nodes at 100,000. Exceeding an
adapter budget raises `ResourceLimitError`; no partial interface is returned.
The input is read in bounded chunks with pre-read and incremental byte limits.
See [the hostile audit](security_performance_audit.md) for graph/output limits and
measured large-input behavior.

Expected failures have typed exceptions in `sema_sedd.exceptions`:

| Exception | Meaning |
| --- | --- |
| `InvalidXmlError` | Empty, malformed, or incorrectly encoded XML |
| `UnsupportedSeddVersionError` | Adapter selection cannot safely map the document (not raised by the generic loader) |
| `UnsafeXmlError` | Forbidden XML declaration or exceeded structural limit |
| `InputTooLargeError` | Byte limit exceeded |

Filesystem read failures use `InputError`. Error messages use fixed wording plus
line and column where applicable; they do not echo untrusted XML text, system IDs,
or file contents. `Diagnostic` codes are likewise controlled. Source positions
refer to opening tags, and the raw content tree retains text for later adapters
to interpret without silently normalizing it.
