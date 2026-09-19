"""Revision-neutral adapter contracts; outputs contain only domain objects."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from sema_sedd.model import EquipmentInterface, SourceProvenance
from sema_sedd.parser import SourcedDocument


class SupportLevel(StrEnum):
    SUPPORTED = "supported"
    INDETERMINATE = "indeterminate"
    UNSUPPORTED = "unsupported"


class DiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class AdapterDiagnostic:
    code: str
    message: str
    severity: DiagnosticSeverity = DiagnosticSeverity.WARNING
    provenance: SourceProvenance | None = None


@dataclass(frozen=True, slots=True)
class AdapterResult:
    interface: EquipmentInterface
    revision: str
    diagnostics: tuple[AdapterDiagnostic, ...] = ()


@runtime_checkable
class SeddAdapter(Protocol):
    """Map already-secured XML into the domain without I/O or downstream imports.

    Detection is pure and conservative. Direct parse is deliberate selection and
    may accept indeterminate support, but must reject contradictory evidence.
    """

    @property
    def revision(self) -> str: ...

    def detect_support(self, document: SourcedDocument) -> SupportLevel: ...

    def parse(self, document: SourcedDocument) -> AdapterResult: ...
