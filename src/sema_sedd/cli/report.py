"""Offline HTML report command with controlled local file output."""

from pathlib import Path

from sema_sedd.adapters import load_interface
from sema_sedd.compare import compare_interfaces
from sema_sedd.exceptions import ReportError
from sema_sedd.report import ReportDiagnostic, ReportSource, render_html_report


def write_html_report(old_path: Path, new_path: Path, destination: Path) -> Path:
    """Compare two files and write one self-contained report."""
    old_source = old_path.resolve()
    new_source = new_path.resolve()
    output = destination.resolve()
    if output in {old_source, new_source}:
        raise ReportError("HTML destination must differ from both input files")

    old = load_interface(old_path)
    new = load_interface(new_path)
    changes = compare_interfaces(old.interface, new.interface)
    html = render_html_report(
        changes,
        ReportSource(str(old_source), old.revision),
        ReportSource(str(new_source), new.revision),
        diagnostics_a=tuple(
            ReportDiagnostic(item.code, item.message, item.severity.value, item.provenance)
            for item in old.diagnostics
        ),
        diagnostics_b=tuple(
            ReportDiagnostic(item.code, item.message, item.severity.value, item.provenance)
            for item in new.diagnostics
        ),
    )
    try:
        output.write_text(html, encoding="utf-8", newline="\n")
    except OSError as error:
        raise ReportError(
            f"Cannot write HTML report: {error.strerror or 'filesystem error'}"
        ) from error
    return output
