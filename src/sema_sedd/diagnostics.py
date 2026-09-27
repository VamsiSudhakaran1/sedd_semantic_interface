"""Revision-neutral diagnostic contract with explicit source and entity context."""

from dataclasses import dataclass
from enum import StrEnum

from sema_sedd.model import CanonicalType, SourceProvenance


class DiagnosticSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class DiagnosticCode(StrEnum):
    UNKNOWN_ELEMENT = "UNKNOWN_ELEMENT"
    UNSUPPORTED_EXTENSION = "UNSUPPORTED_EXTENSION"
    UNRESOLVED_REFERENCE = "UNRESOLVED_REFERENCE"
    AMBIGUOUS_REFERENCE = "AMBIGUOUS_REFERENCE"
    MISSING_OPTIONAL_METADATA = "MISSING_OPTIONAL_METADATA"
    MISSING_REQUIRED_STRUCTURE = "MISSING_REQUIRED_STRUCTURE"
    UNSUPPORTED_REVISION = "UNSUPPORTED_REVISION"


@dataclass(frozen=True, slots=True)
class DiagnosticEntityContext:
    canonical_type: CanonicalType
    key: str | None = None


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    message: str
    severity: DiagnosticSeverity = DiagnosticSeverity.WARNING
    provenance: SourceProvenance | None = None
    entity_context: DiagnosticEntityContext | None = None

    def __post_init__(self) -> None:
        if not self.code or not self.message or not isinstance(self.severity, DiagnosticSeverity):
            raise ValueError("Diagnostic requires a code, message, and valid severity")

    @property
    def source(self) -> str | None:
        return self.provenance.source_document if self.provenance is not None else None

    @property
    def source_line(self) -> int | None:
        return self.provenance.line if self.provenance is not None else None


def context_data(context: DiagnosticEntityContext | None) -> dict[str, str | None] | None:
    if context is None:
        return None
    return {"canonical_type": context.canonical_type.value, "key": context.key}
