"""Bounded, offline XML ingestion independent of revision vocabularies."""

from sema_sedd.parser.ingest import (
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_DEPTH,
    Diagnostic,
    SourcedDocument,
    SourceLocation,
    XmlElement,
    load_sedd,
    load_xml,
)

__all__ = [
    "DEFAULT_MAX_BYTES",
    "DEFAULT_MAX_DEPTH",
    "Diagnostic",
    "SourceLocation",
    "SourcedDocument",
    "XmlElement",
    "load_sedd",
    "load_xml",
]
