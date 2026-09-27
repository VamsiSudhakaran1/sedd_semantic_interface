"""Public revision-neutral adapter contracts, registry, and ingestion pipeline."""

from sema_sedd.adapters.base import (
    AdapterDiagnostic,
    AdapterResult,
    DiagnosticSeverity,
    SeddAdapter,
    SupportLevel,
)
from sema_sedd.adapters.defaults import default_registry
from sema_sedd.adapters.pipeline import load_interface
from sema_sedd.adapters.registry import AdapterRegistry, RevisionAssessment, RevisionStatus
from sema_sedd.adapters.revisions import RevisionDetection, detect_revision

__all__ = [
    "AdapterDiagnostic",
    "AdapterResult",
    "DiagnosticSeverity",
    "SeddAdapter",
    "SupportLevel",
    "AdapterRegistry",
    "RevisionAssessment",
    "RevisionStatus",
    "RevisionDetection",
    "detect_revision",
    "default_registry",
    "load_interface",
]
