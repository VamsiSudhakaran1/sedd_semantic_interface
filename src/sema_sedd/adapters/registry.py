"""Deterministic registry: no first-match routing or implicit fallback revision."""

from dataclasses import dataclass

from sema_sedd.adapters.base import AdapterDiagnostic, AdapterResult, SeddAdapter, SupportLevel
from sema_sedd.exceptions import (
    AdapterRegistrationError,
    AmbiguousSeddVersionError,
    UnsupportedSeddVersionError,
)
from sema_sedd.model import EquipmentInterface, SourceProvenance
from sema_sedd.parser import SourcedDocument


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

    def select(self, document: SourcedDocument, *, revision: str | None = None) -> SeddAdapter:
        if revision is not None:
            selected = next((a for a in self.adapters if a.revision == revision), None)
            if selected is None or self._support(selected, document) is SupportLevel.UNSUPPORTED:
                raise UnsupportedSeddVersionError("Requested adapter is absent or incompatible")
            return selected
        candidates = tuple(
            adapter
            for adapter in self.adapters
            if self._support(adapter, document) is SupportLevel.SUPPORTED
        )
        if len(candidates) > 1:
            raise AmbiguousSeddVersionError("Multiple adapters report support; select a revision")
        if not candidates:
            raise UnsupportedSeddVersionError("No supported revision detected; select a revision")
        return candidates[0]

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
        return AdapterResult(
            result.interface, result.revision, loader_diagnostics + result.diagnostics
        )

    @staticmethod
    def _support(adapter: SeddAdapter, document: SourcedDocument) -> SupportLevel:
        support = adapter.detect_support(document)
        if not isinstance(support, SupportLevel):
            raise AdapterRegistrationError("Adapter returned an invalid support decision")
        return support
