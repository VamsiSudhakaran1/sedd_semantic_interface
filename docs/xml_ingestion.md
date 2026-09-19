# Safe XML ingestion

`sema_sedd.parser.load_sedd(path)` reads a local XML file and returns a
`SourcedDocument`. It preserves expanded element and attribute names, mixed-content
order, the resolved source path, byte count, and one-based start-tag positions.
For example:

```python
from sema_sedd.parser import load_sedd

document = load_sedd("equipment.xml")
print(document.root.tag, document.root.location)
print(document.revision_hint, document.diagnostics)
```

The loader accepts UTF-8 XML, including non-ASCII text. It requires the
`{urn:semi-org:xsd.SEDD}DataDictionary` root. A recognized local or URL-shaped
`xsi:schemaLocation` filename can produce an `E172-0225` *hint*; the URL is never
opened. Missing, malformed, ambiguous, and unrecognized hints produce stable
diagnostic codes and leave `revision_hint` unset. The hint does not validate the
document against an XSD or authorize a revision-specific parser. The generic XML
tree contains no canonical entities.

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
| `UnsupportedSeddVersionError` | Root element or namespace is not the supported SEDD QName |
| `UnsafeXmlError` | Forbidden XML declaration or exceeded structural limit |
| `InputTooLargeError` | Byte limit exceeded |

Filesystem read failures use `InputError`. Error messages use fixed wording plus
line and column where applicable; they do not echo untrusted XML text, system IDs,
or file contents. `Diagnostic` codes are likewise controlled. Source positions
refer to opening tags, and the raw content tree retains text for later adapters
to interpret without silently normalizing it.
