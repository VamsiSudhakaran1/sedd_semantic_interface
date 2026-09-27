"""Deterministic registry: no first-match routing or implicit fallback revision."""

from dataclasses import dataclass
from enum import StrEnum

from sema_sedd.adapters.base import AdapterDiagnostic, AdapterResult, SeddAdapter, SupportLevel
from sema_sedd.adapters.revisions import RevisionDetection, detect_revision
from sema_sedd.exceptions import (
    AdapterRegistrationError,
    AmbiguousSeddVersionError,
    UnsupportedSeddVersionError,
)
from sema_sedd.model import EquipmentInterface, SourceProvenance
from sema_sedd.parser import SourcedDocument


class RevisionStatus(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    INDETERMINATE = "indeterminate"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class RevisionAssessment:
    """Read-only routing assessment; does not parse canonical entities."""

    detection: RevisionDetection
    status: RevisionStatus
    supported_revisions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AdapterRegistry:
    adapters: tuple[SeddAdapter, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.adapters, tuple) or any(
            not isinstance(adapter, SeddAdapter) for adapter in self.adapters
        ):
            raise AdapterRegistrationError("Registry requires a tuple of SeddAdapter instances")
        revisions = [adapter.revision for adapter in self.adapters]
        if any(not isinstance(revision, str) or not revision.strip() for revision in revisions):
            raise AdapterRegistrationError("Adapter revision must be a nonempty string")
        if len(revisions) != len(set(revisions)):
            raise AdapterRegistrationError("Duplicate registered adapter revision")

    @property
    def revisions(self) -> tuple[str, ...]:
        return tuple(sorted(adapter.revision for adapter in self.adapters))

    def assess(self, document: SourcedDocument) -> RevisionAssessment:
        decisions = tuple((a.revision, self._support(a, document)) for a in self.adapters)
        supported = tuple(sorted(r for r, s in decisions if s is SupportLevel.SUPPORTED))
        status = (
            RevisionStatus.AMBIGUOUS
            if len(supported) > 1
            else RevisionStatus.SUPPORTED
            if supported
            else RevisionStatus.INDETERMINATE
            if any(s is SupportLevel.INDETERMINATE for _, s in decisions)
            else RevisionStatus.UNSUPPORTED
        )
        return RevisionAssessment(detect_revision(document), status, supported)

    @staticmethod
    def _unsupported(document: SourcedDocument, message: str) -> UnsupportedSeddVersionError:
        detection = detect_revision(document)
        label = detection.revision_hint or ", ".join(detection.candidates)
        detail = f"; detected schema hint: {label}" if label else ""
        return UnsupportedSeddVersionError(
            f"Unsupported SEDD revision{detail}. {message}",
            detected_revision=detection.revision_hint,
            diagnostic_code=detection.diagnostic_code or "UNSUPPORTED_REVISION",
        )

    def select(self, document: SourcedDocument, *, revision: str | None = None) -> SeddAdapter:
        if revision is not None:
            selected = next((a for a in self.adapters if a.revision == revision), None)
            if selected is None or self._support(selected, document) is SupportLevel.UNSUPPORTED:
                raise self._unsupported(document, "Requested adapter is absent or incompatible")
            return selected
        assessment = self.assess(document)
        if assessment.status is RevisionStatus.AMBIGUOUS:
            raise AmbiguousSeddVersionError("Multiple adapters report support; select a revision")
        if not assessment.supported_revisions:
            raise self._unsupported(document, "No compatible adapter selected; no semantics parsed")
        return next(a for a in self.adapters if a.revision == assessment.supported_revisions[0])

    def adapt(self, document: SourcedDocument, *, revision: str | None = None) -> AdapterResult:
        selected = self.select(document, revision=revision)
        result = selected.parse(document)
        if (
            not isinstance(result, AdapterResult)
            or type(result.interface) is not EquipmentInterface
            or not isinstance(result.diagnostics, tuple)
            or any(not isinstance(d, AdapterDiagnostic) for d in result.diagnostics)
        ):
            raise AdapterRegistrationError("Adapter returned an invalid canonical result")
        if result.revision != selected.revision:
            raise AdapterRegistrationError("Adapter returned a different revision")
        loader_diagnostics = tuple(
            AdapterDiagnostic(
                diagnostic.code,
                diagnostic.message,
                provenance=SourceProvenance(
                    source_document=str(document.source),
                    line=diagnostic.location.line if diagnostic.location else None,
                    column=diagnostic.location.column if diagnostic.location else None,
                ),
            )
            for diagnostic in document.diagnostics
        )
        detection = detect_revision(document)
        hint_diagnostics = (
            (
                AdapterDiagnostic(
                    detection.diagnostic_code,
                    "Revision schema hint is missing, unrecognized, malformed, or ambiguous",
                    provenance=SourceProvenance(
                        source_document=str(document.source),
                        line=document.root.location.line,
                        column=document.root.location.column,
                    ),
                ),
            )
            if detection.diagnostic_code
            else ()
        )
        return AdapterResult(
            result.interface,
            result.revision,
            loader_diagnostics + hint_diagnostics + result.diagnostics,
        )

    @staticmethod
    def _support(adapter: SeddAdapter, document: SourcedDocument) -> SupportLevel:
        support = adapter.detect_support(document)
        if not isinstance(support, SupportLevel):
            raise AdapterRegistrationError("Adapter returned an invalid support decision")
        return support
