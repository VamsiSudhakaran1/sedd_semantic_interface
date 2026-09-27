"""File-loading facade for the canonical-only JSON report package."""

from pathlib import Path

from sema_sedd.adapters import load_interface
from sema_sedd.compare import compare_interfaces
from sema_sedd.compare._values import JsonData
from sema_sedd.graph import relationship_diagnostics, resolve_references
from sema_sedd.report import ReportDiagnostic, ReportSource, report_from_changes


def report_files(
    source_a: str | Path,
    source_b: str | Path,
    *,
    revision_a: str | None = None,
    revision_b: str | None = None,
) -> dict[str, JsonData]:
    """Load two local sources, compare them, and build a versioned report."""
    a = load_interface(source_a, revision=revision_a)
    b = load_interface(source_b, revision=revision_b)
    return report_from_changes(
        compare_interfaces(a.interface, b.interface),
        ReportSource(str(Path(source_a).resolve()), a.revision),
        ReportSource(str(Path(source_b).resolve()), b.revision),
        diagnostics_a=tuple(
            ReportDiagnostic.from_diagnostic(d)
            for d in (*a.diagnostics, *relationship_diagnostics(resolve_references(a.interface)))
        ),
        diagnostics_b=tuple(
            ReportDiagnostic.from_diagnostic(d)
            for d in (*b.diagnostics, *relationship_diagnostics(resolve_references(b.interface)))
        ),
    )
