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

The parser uses Python's Expat engine with external parameter parsing disabled.
It rejects all DOCTYPE declarations and entity declarations, including external
DTDs and XXE. It reads only the supplied local regular file; UNC paths and a
symlink at the supplied path are rejected. Default limits are 10 MiB of input,
64 nested elements, 100,000 elements total, and 128 attributes per element.
Callers may lower or raise these positive limits with `max_bytes`, `max_depth`,
`max_elements`, and `max_attributes`. The input is read in bounded chunks, with
both a pre-read size check and an incremental byte counter.

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
