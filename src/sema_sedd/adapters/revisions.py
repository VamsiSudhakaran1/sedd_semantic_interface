"""Identify lexical E172 schema hints without asserting support or conformance.

The filename convention is evidence of a declared label only. No schema is read,
and an unimplemented revision never inherits another revision's parser semantics.
"""

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from sema_sedd.parser import SourcedDocument
from sema_sedd.parser.ingest import XSI_NO_NAMESPACE_SCHEMA_LOCATION

_FILENAME = re.compile(r"E172-([0-9]{4})-SEDD-Schema\.xsd", re.ASCII)


@dataclass(frozen=True, slots=True)
class RevisionDetection:
    revision_hint: str | None = None
    candidates: tuple[str, ...] = ()
    schema_locations: tuple[str, ...] = ()
    diagnostic_code: str | None = None


def detect_revision(document: SourcedDocument) -> RevisionDetection:
    """Read only hints associated with the actual root namespace.

    Arbitrary attributes, equipment software revisions, filenames of input files,
    descendant declarations, and hints for imported vocabularies are not evidence.
    Multiple distinct locations remain ambiguous even when their labels agree.
    """
    raw = document.schema_location
    no_namespace = document.root.attribute(XSI_NO_NAMESPACE_SCHEMA_LOCATION)
    locations: tuple[str, ...] = ()
    if raw is not None:
        parts = re.split(r"[ \t\r\n]+", raw.strip(" \t\r\n"))
        if not parts or len(parts) % 2 or not all(parts):
            return RevisionDetection(diagnostic_code="MALFORMED_SCHEMA_HINT")
        locations = tuple(
            sorted(
                {
                    parts[index + 1]
                    for index in range(0, len(parts), 2)
                    if parts[index] == document.namespace
                }
            )
        )
    if not document.namespace and no_namespace is not None:
        parts = re.split(r"[ \t\r\n]+", no_namespace.strip(" \t\r\n"))
        if len(parts) != 1 or not parts[0]:
            return RevisionDetection(diagnostic_code="MALFORMED_SCHEMA_HINT")
        locations = tuple(sorted(set((*locations, parts[0]))))
    if not locations:
        return RevisionDetection(diagnostic_code="MISSING_SCHEMA_HINT")
    labels: set[str] = set()
    for location in locations:
        try:
            filename = unquote(urlsplit(location).path).rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        except ValueError:
            return RevisionDetection(
                schema_locations=locations, diagnostic_code="MALFORMED_SCHEMA_HINT"
            )
        match = _FILENAME.fullmatch(filename)
        if match is not None:
            labels.add(f"E172-{match[1]}")
    candidates = tuple(sorted(labels))
    if len(locations) > 1:
        return RevisionDetection(
            candidates=candidates,
            schema_locations=locations,
            diagnostic_code="AMBIGUOUS_SCHEMA_HINT",
        )
    return RevisionDetection(
        revision_hint=candidates[0] if candidates else None,
        candidates=candidates,
        schema_locations=locations,
        diagnostic_code=None if candidates else "UNRECOGNIZED_SCHEMA_HINT",
    )
