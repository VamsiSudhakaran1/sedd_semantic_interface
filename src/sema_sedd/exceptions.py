"""Typed error categories for interface ingestion and semantic processing."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sema_sedd.diagnostics import Diagnostic, DiagnosticEntityContext


class SeddError(Exception):
    """Base class for expected application errors."""


class InputError(SeddError):
    """An input cannot be read or interpreted."""


class XmlSecurityError(InputError):
    """XML violates the secure loader policy."""


class UnsafeXmlError(XmlSecurityError):
    """The input uses forbidden XML features or exceeds structural limits."""


class InvalidXmlError(InputError):
    """The input is empty, incorrectly encoded, or not well-formed XML."""


class InputTooLargeError(InputError):
    """The input exceeds the configured byte limit."""


class UnsupportedRevisionError(InputError):
    """No adapter supports the detected document revision."""


class UnsupportedSeddVersionError(UnsupportedRevisionError):
    """No safe semantic mapping is available; retain a detected label if present."""

    status = "unsupported"
    default_diagnostic_code = "UNSUPPORTED_REVISION"

    def __init__(
        self,
        message: str,
        *,
        detected_revision: str | None = None,
        diagnostic_code: str | None = None,
        source: str | None = None,
        source_line: int | None = None,
        entity_context: DiagnosticEntityContext | None = None,
    ) -> None:
        super().__init__(message)
        self.detected_revision = detected_revision
        self.diagnostic_code = diagnostic_code
        self.source = source
        self.source_line = source_line
        self.entity_context = entity_context

    @property
    def diagnostic(self) -> Diagnostic:
        """Expose an unsupported input through the shared diagnostic contract."""
        from sema_sedd.diagnostics import Diagnostic, DiagnosticSeverity
        from sema_sedd.model import SourceProvenance

        provenance = (
            SourceProvenance(source_document=self.source, line=self.source_line)
            if self.source
            else None
        )
        return Diagnostic(
            self.diagnostic_code or self.default_diagnostic_code,
            str(self),
            DiagnosticSeverity.ERROR,
            provenance,
            self.entity_context,
        )


class SemanticError(SeddError):
    """A semantic operation cannot be completed."""


class ReportError(SeddError):
    """A report cannot be generated or written."""


class ModelValidationError(SemanticError):
    """A canonical object violates a model invariant or field type."""


class EntitySelectionError(SemanticError):
    """An explicit entity selector is invalid, missing, or ambiguous."""


class AdapterRegistrationError(SeddError):
    """An adapter registry or adapter result violates its contract."""


class AmbiguousSeddVersionError(UnsupportedSeddVersionError):
    """Multiple registered adapters claim the same document."""

    status = "ambiguous"
    default_diagnostic_code = "AMBIGUOUS_REVISION"
