"""Offline HTML report command with controlled local file output."""

import os
import tempfile
from pathlib import Path

from sema_sedd.adapters import load_interface
from sema_sedd.compare import compare_interfaces
from sema_sedd.exceptions import InputError, ReportError
from sema_sedd.graph import relationship_diagnostics, resolve_references
from sema_sedd.local_files import local_path
from sema_sedd.report import (
    ReportDiagnostic,
    ReportSource,
    render_html_report,
    render_interface_html,
)


def _output_path(destination: Path, *inputs: Path) -> Path:
    try:
        output = local_path(destination)
        for source in inputs:
            source = local_path(source)
            if output.resolve() == source.resolve() or (
                output.exists() and source.exists() and output.samefile(source)
            ):
                raise ReportError("HTML destination must differ from all input files")
        if output.exists() and not output.is_file():
            raise ReportError("HTML destination must be a local regular file")
        return output
    except (InputError, OSError, ValueError) as error:
        raise ReportError("HTML destination and inputs must be local regular files") from error


def _write(output: Path, html: str) -> Path:
    temporary: Path | None = None
    try:
        # Atomic replacement also prevents truncating a hard-linked source.
        output = local_path(output)
        descriptor, name = tempfile.mkstemp(prefix=".sedd-", suffix=".tmp", dir=output.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(html)
        os.replace(temporary, output)
    except (OSError, InputError) as error:
        raise ReportError("Cannot write HTML report: local filesystem error") from error
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as error:
                raise ReportError("Cannot clean temporary HTML report") from error
    return output


def write_html_report(old_path: Path, new_path: Path, destination: Path) -> Path:
    """Compare two files and write one self-contained report."""
    output = _output_path(destination, old_path, new_path)
    old_source = local_path(old_path).resolve()
    new_source = local_path(new_path).resolve()

    old = load_interface(old_path)
    new = load_interface(new_path)
    changes = compare_interfaces(old.interface, new.interface)
    old_graph = resolve_references(old.interface)
    new_graph = resolve_references(new.interface)
    html = render_html_report(
        changes,
        ReportSource(str(old_source), old.revision),
        ReportSource(str(new_source), new.revision),
        diagnostics_a=tuple(
            ReportDiagnostic.from_diagnostic(item)
            for item in (
                *old.diagnostics,
                *relationship_diagnostics(old_graph),
            )
        ),
        diagnostics_b=tuple(
            ReportDiagnostic.from_diagnostic(item)
            for item in (
                *new.diagnostics,
                *relationship_diagnostics(new_graph),
            )
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
        diagnostics=tuple(ReportDiagnostic.from_diagnostic(item) for item in source.diagnostics),
    )
    return _write(output, html)
