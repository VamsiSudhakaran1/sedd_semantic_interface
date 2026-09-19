"""E172-0225-only traversal, provenance, and loss-aware field reading."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sema_sedd.adapters.base import AdapterDiagnostic, DiagnosticSeverity
from sema_sedd.model import JsonObject, SourceProvenance, UnknownExtension
from sema_sedd.parser import SourcedDocument, XmlElement

XSI_NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"


def split_name(tag: str) -> tuple[str | None, str]:
    if tag.startswith("{"):
        namespace, name = tag[1:].split("}", 1)
        return namespace, name
    return None, tag


@dataclass
class Context:
    document: SourcedDocument
    revision: str
    diagnostics: list[AdapterDiagnostic] = field(default_factory=list)
    paths: dict[int, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._index(self.document.root, f"/{self.document.root.tag}[1]")

    def _index(self, node: XmlElement, path: str) -> None:
        self.paths[id(node)] = path
        counts: dict[str, int] = {}
        for child in node.children:
            counts[child.tag] = counts.get(child.tag, 0) + 1
            self._index(child, f"{path}/{child.tag}[{counts[child.tag]}]")

    def provenance(self, node: XmlElement, identifier: str | None = None) -> SourceProvenance:
        return SourceProvenance(
            source_document=str(self.document.source),
            source_revision=self.revision,
            source_path=self.paths[id(node)],
            path_kind="expanded_name_path",
            source_identifier=identifier,
            line=node.location.line,
            column=node.location.column,
        )

    def diagnostic(
        self,
        code: str,
        message: str,
        node: XmlElement,
        severity: DiagnosticSeverity = DiagnosticSeverity.WARNING,
    ) -> None:
        self.diagnostics.append(AdapterDiagnostic(code, message, severity, self.provenance(node)))

    def opaque(self, node: XmlElement, reason: str = "unmapped_content") -> UnknownExtension:
        namespace, name = split_name(node.tag)
        return UnknownExtension(
            name=name,
            namespace=namespace,
            reason=reason,
            attributes=JsonObject(entries=node.attributes),
            content=tuple(
                part if isinstance(part, str) else self.opaque(part, reason)
                for part in node.content
            ),
            provenance=(self.provenance(node),),
        )


@dataclass
class Reader:
    context: Context
    node: XmlElement
    consumed: set[int] = field(default_factory=set)
    attributes: set[str] = field(default_factory=set)
    body_used: bool = False
    retained: list[UnknownExtension] = field(default_factory=list)

    def one(self, name: str, *, required: bool = False) -> XmlElement | None:
        nodes = [child for child in self.node.children if child.tag == name]
        if len(nodes) > 1:
            self.context.diagnostic(
                "AMBIGUOUS_FIELD", f"Repeated singleton field retained: {name}", self.node
            )
            return None
        if not nodes:
            if required:
                self.context.diagnostic(
                    "MISSING_FIELD", f"Required field is absent: {name}", self.node
                )
            return None
        node = nodes[0]
        if (node.attribute(XSI_NIL) or "").strip(" \t\r\n") in ("true", "1"):
            self.context.diagnostic(
                "NIL_CONTENT", "Nil content retained without interpretation", node
            )
            return None
        self.consumed.add(id(node))
        return node

    def many(self, name: str) -> tuple[XmlElement, ...]:
        nodes = []
        for child in self.node.children:
            if child.tag != name:
                continue
            if (child.attribute(XSI_NIL) or "").strip(" \t\r\n") in ("true", "1"):
                self.context.diagnostic(
                    "NIL_CONTENT", "Nil content retained without interpretation", child
                )
                continue
            self.consumed.add(id(child))
            nodes.append(child)
        return tuple(nodes)

    def attribute(self, name: str) -> str | None:
        self.attributes.add(name)
        return self.node.attribute(name)

    def leaf(self) -> str | None:
        if self.node.children:
            self.context.diagnostic(
                "UNSUPPORTED_FIELD_SHAPE", "Structured scalar retained", self.node
            )
            self.retained.append(self.context.opaque(self.node, "structured_scalar"))
            self.consumed.update(id(child) for child in self.node.children)
            self.body_used = True
            return None
        self.body_used = True
        return "".join(part for part in self.node.content if isinstance(part, str))

    def text(self, name: str, *, required: bool = False) -> str | None:
        node = self.one(name, required=required)
        if node is None:
            return None
        child = Reader(self.context, node)
        value = child.leaf()
        self.retained.extend(child.finish())
        return value

    def texts(self, name: str) -> tuple[str, ...]:
        values = []
        for node in self.many(name):
            child = Reader(self.context, node)
            value = child.leaf()
            if value is not None:
                values.append(value)
            self.retained.extend(child.finish())
        return tuple(values)

    def integer(self, name: str, *, attribute: bool = False) -> int | None:
        value = self.attribute(name) if attribute else self.text(name)
        if value is None:
            return None
        # Restrict to XML integer lexical syntax, not Python's underscores or Unicode digits.
        if (
            re.fullmatch(r"[+-]?[0-9]+", value.strip(" \t\r\n"))
            and len(value.strip(" \t\r\n")) <= 1000
        ):
            return int(value)
        self.invalid(name, attribute=attribute)
        return None

    def boolean(self, name: str, *, attribute: bool = False) -> bool | None:
        value = self.attribute(name) if attribute else self.text(name)
        if value is None:
            return None
        if value.strip(" \t\r\n") in ("true", "1", "false", "0"):
            return value.strip(" \t\r\n") in ("true", "1")
        self.invalid(name, attribute=attribute)
        return None

    def invalid(self, name: str, *, attribute: bool = False) -> None:
        if attribute:
            self.attributes.discard(name)
        else:
            for child in self.node.children:
                if child.tag == name:
                    self.consumed.discard(id(child))
        self.context.diagnostic(
            "INVALID_FIELD", f"Uninterpretable field retained: {name}", self.node
        )

    def finish(self) -> tuple[UnknownExtension, ...]:
        leftovers = [child for child in self.node.children if id(child) not in self.consumed]
        attrs = tuple(
            (key, value) for key, value in self.node.attributes if key not in self.attributes
        )
        text = tuple(
            part for part in self.node.content if isinstance(part, str) and part.strip(" \t\r\n")
        )
        result = list(self.retained)
        if text and not self.body_used:
            # Retain the whole node to preserve meaningful mixed-content ordering.
            result.append(self.context.opaque(self.node, "unmapped_mixed_content"))
        else:
            result.extend(self.context.opaque(child) for child in leftovers)
            if attrs:
                namespace, name = split_name(self.node.tag)
                result.append(
                    UnknownExtension(
                        name=name,
                        namespace=namespace,
                        reason="unmapped_attributes",
                        attributes=JsonObject(entries=attrs),
                        provenance=(self.context.provenance(self.node),),
                    )
                )
        if leftovers or attrs or (text and not self.body_used):
            self.context.diagnostic(
                "UNKNOWN_CONTENT", "Unmapped source content retained", self.node
            )
        return tuple(result)
