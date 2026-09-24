"""Offline HTML report command with controlled local file output."""

from pathlib import Path

from sema_sedd.adapters import load_interface
from sema_sedd.compare import compare_interfaces
from sema_sedd.exceptions import ReportError
from sema_sedd.graph import resolve_references
from sema_sedd.report import (
    ReportDiagnostic,
    ReportSource,
    render_html_report,
    render_interface_html,
)


def _output_path(destination: Path, *inputs: Path) -> Path:
    output = destination.resolve()
    if output in {source.resolve() for source in inputs}:
        raise ReportError("HTML destination must differ from all input files")
    return output


def _write(output: Path, html: str) -> Path:
    try:
        output.write_text(html, encoding="utf-8", newline="\n")
    except OSError as error:
        raise ReportError(
            f"Cannot write HTML report: {error.strerror or 'filesystem error'}"
        ) from error
    return output


def write_html_report(old_path: Path, new_path: Path, destination: Path) -> Path:
    """Compare two files and write one self-contained report."""
    old_source = old_path.resolve()
    new_source = new_path.resolve()
    output = _output_path(destination, old_path, new_path)

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
    return _write(output, html)


def write_interface_html_report(source_path: Path, destination: Path) -> Path:
    """Render one local SEDD file as a sectioned visual explorer."""
    output = _output_path(destination, source_path)
    source = load_interface(source_path)
    graph = resolve_references(source.interface)
    html = render_interface_html(
        graph,
        ReportSource(str(source_path.resolve()), source.revision),
        diagnostics=tuple(
            ReportDiagnostic(item.code, item.message, item.severity.value, item.provenance)
            for item in source.diagnostics
        ),
    )
    return _write(output, html)
