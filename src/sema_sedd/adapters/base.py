"""Revision-neutral adapter contracts; outputs contain only domain objects."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from sema_sedd.diagnostics import Diagnostic
from sema_sedd.diagnostics import DiagnosticSeverity as DiagnosticSeverity
from sema_sedd.model import EquipmentInterface
from sema_sedd.parser import SourcedDocument

AdapterDiagnostic = Diagnostic


class SupportLevel(StrEnum):
    SUPPORTED = "supported"
    INDETERMINATE = "indeterminate"
    UNSUPPORTED = "unsupported"


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
