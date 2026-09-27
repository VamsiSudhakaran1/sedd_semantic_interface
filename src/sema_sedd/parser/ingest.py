"""Ingest untrusted SEDD XML without resolving external resources."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn
from xml.parsers import expat

from sema_sedd.exceptions import (
    InputError,
    InputTooLargeError,
    InvalidXmlError,
    UnsafeXmlError,
)

XSI_SCHEMA_LOCATION = "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation"
XSI_NO_NAMESPACE_SCHEMA_LOCATION = (
    "{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation"
)

DEFAULT_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_DEPTH = 64
DEFAULT_MAX_ELEMENTS = 100_000
DEFAULT_MAX_ATTRIBUTES = 128
_CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """One-based source position at the opening tag."""

    line: int
    column: int


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Stable diagnostic code and controlled human-readable message."""

    code: str
    message: str
    location: SourceLocation | None = None


@dataclass(frozen=True, slots=True)
class XmlElement:
    """Generic XML node with content order and expanded names retained."""

    tag: str
    attributes: tuple[tuple[str, str], ...]
    content: tuple[str | XmlElement, ...]
    location: SourceLocation

    @property
    def children(self) -> tuple[XmlElement, ...]:
        """Return direct child elements without altering mixed-content order."""
        return tuple(part for part in self.content if isinstance(part, XmlElement))

    def attribute(self, name: str) -> str | None:
        """Look up an expanded attribute name."""
        return next((value for key, value in self.attributes if key == name), None)


@dataclass(frozen=True, slots=True)
class SourcedDocument:
    """Secured XML and raw schema hints; revision interpretation belongs to adapters."""

    source: Path
    byte_count: int
    namespace: str
    schema_location: str | None
    root: XmlElement
    diagnostics: tuple[Diagnostic, ...]


@dataclass(slots=True)
class _MutableElement:
    tag: str
    attributes: tuple[tuple[str, str], ...]
    location: SourceLocation
    content: list[str | _MutableElement] = field(default_factory=list)


def _expanded(name: str) -> str:
    """Expat's namespace separator omits the opening brace."""
    return f"{{{name}" if "}" in name else name


def _freeze(node: _MutableElement) -> XmlElement:
    return XmlElement(
        tag=node.tag,
        attributes=node.attributes,
        content=tuple(
            _freeze(part) if isinstance(part, _MutableElement) else part for part in node.content
        ),
        location=node.location,
    )


def load_xml(
    path: str | os.PathLike[str],
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_elements: int = DEFAULT_MAX_ELEMENTS,
    max_attributes: int = DEFAULT_MAX_ATTRIBUTES,
) -> SourcedDocument:
    """Read local SEDD XML with byte and structural limits and no external access.

    This checks XML syntax and security limits, not document vocabulary or XSD
    validity. Namespace admission and revision interpretation belong to adapters.
    """
    if min(max_bytes, max_depth, max_elements, max_attributes) < 1:
        raise ValueError("All XML limits must be positive")
    source = Path(path)
    if os.fspath(path).startswith(("\\", "//")) or source.is_symlink():
        raise InputError("XML input must be a local regular file")
    parser = expat.ParserCreate(namespace_separator="}")
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    stack: list[_MutableElement] = []
    root: _MutableElement | None = None
    element_count = 0

    def position() -> SourceLocation:
        return SourceLocation(parser.CurrentLineNumber, parser.CurrentColumnNumber + 1)

    def unsafe(message: str) -> NoReturn:
        raise UnsafeXmlError(
            f"{message} at line {parser.CurrentLineNumber}, column {parser.CurrentColumnNumber + 1}"
        )

    def start(name: str, attrs: dict[str, str]) -> None:
        nonlocal root, element_count
        if len(stack) >= max_depth:
            unsafe("XML nesting limit exceeded")
        if len(attrs) > max_attributes:
            unsafe("XML attribute limit exceeded")
        element_count += 1
        if element_count > max_elements:
            unsafe("XML element limit exceeded")
        node = _MutableElement(
            _expanded(name),
            tuple((_expanded(key), value) for key, value in attrs.items()),
            position(),
        )
        if stack:
            stack[-1].content.append(node)
        else:
            root = node
        stack.append(node)

    def end(_name: str) -> None:
        stack.pop()

    def characters(value: str) -> None:
        if stack:
            content = stack[-1].content
            if content and isinstance(content[-1], str):
                content[-1] += value
            else:
                content.append(value)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = characters
    parser.StartDoctypeDeclHandler = lambda *_args: unsafe("DOCTYPE is forbidden")
    parser.EntityDeclHandler = lambda *_args: unsafe("Entity declarations are forbidden")

    def reject_external(
        _context: str, _base: str | None, _system_id: str | None, _public_id: str | None
    ) -> int:
        unsafe("External entities are forbidden")

    parser.ExternalEntityRefHandler = reject_external

    byte_count = 0
    try:
        with source.open("rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise InputError("XML input must be a regular file")
            if os.fstat(stream.fileno()).st_size > max_bytes:
                raise InputTooLargeError(f"XML input exceeds {max_bytes} bytes")
            while chunk := stream.read(min(_CHUNK_BYTES, max_bytes - byte_count + 1)):
                byte_count += len(chunk)
                if byte_count > max_bytes:
                    raise InputTooLargeError(f"XML input exceeds {max_bytes} bytes")
                try:
                    parser.Parse(chunk, False)
                except expat.ExpatError as error:
                    raise InvalidXmlError(
                        f"Invalid XML at line {error.lineno}, column {error.offset + 1}"
                    ) from None
            try:
                parser.Parse(b"", True)
            except expat.ExpatError as error:
                raise InvalidXmlError(
                    f"Invalid XML at line {error.lineno}, column {error.offset + 1}"
                ) from None
    except OSError as error:
        raise InputError("Unable to read XML input") from error

    if root is None:
        raise InvalidXmlError("Empty XML input")
    schema_location = next(
        (value for name, value in root.attributes if name == XSI_SCHEMA_LOCATION), None
    )
    return SourcedDocument(
        source=source.resolve(),
        byte_count=byte_count,
        namespace=root.tag[1:].split("}", 1)[0] if root.tag.startswith("{") else "",
        schema_location=schema_location,
        root=_freeze(root),
        diagnostics=(),
    )


# Compatibility spelling: both entry points secure XML without selecting semantics.
load_sedd = load_xml
