"""Single-file HTML explorer sections, search evidence, relationships, and safety."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from sema_sedd.adapters import load_interface
from sema_sedd.cli import main
from sema_sedd.graph import resolve_references
from sema_sedd.model import EquipmentInterface, StatusVariable
from sema_sedd.report import ReportSource, render_interface_html

FIXTURES = Path(__file__).parent / "fixtures"
COMPLETE = FIXTURES / "relationships" / "e172-complete.xml"


class TagCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)


def hinted(tmp_path: Path, source: Path) -> Path:
    root = '<sedd:DataDictionary xmlns:sedd="urn:semi-org:xsd.SEDD">'
    replacement = (
        '<sedd:DataDictionary xmlns:sedd="urn:semi-org:xsd.SEDD" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="urn:semi-org:xsd.SEDD E172-0225-SEDD-Schema.xsd">'
    )
    data = source.read_text(encoding="utf-8")
    assert root in data
    output = tmp_path / source.name
    output.write_text(data.replace(root, replacement, 1), encoding="utf-8")
    return output


def test_single_file_cli_has_sections_search_and_relationships(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = hinted(tmp_path, COMPLETE)
    output = tmp_path / "interface.html"
    assert main(["report", str(source), "--html", str(output)]) == 0
    assert capsys.readouterr().out == f"Wrote HTML report to {output.resolve()}\n"
    html = output.read_text(encoding="utf-8")
    for heading in (
        "Overview",
        "Variables",
        "Events",
        "Reports",
        "Alarms",
        "Remote Commands",
        "Messages",
        "Standards/WKN",
        "Diagnostics",
    ):
        assert f">{heading}</h2>" in html
    assert "Lantern17" in html
    assert "Search identifier, name, WKN, or description" in html
    assert "Source ID: 702" in html
    assert "urn:sema-sedd:fictional:702" in html
    assert "Incoming relationships" in html and "Outgoing relationships" in html
    assert "parameters[0]" in html
    assert "Well-Known Name directory" in html
    assert "Provenance" in html
    assert "S99F1" in html or "SyntheticMessage" in html
    assert "connect-src 'none'" in html
    assert "<script>" in html and "<style>" in html
    assert main(["report", str(source), "--html", str(output)]) == 0
    assert output.read_text(encoding="utf-8") == html


def test_search_index_uses_exact_requested_fields(tmp_path: Path) -> None:
    source = hinted(tmp_path, COMPLETE)
    graph = resolve_references(load_interface(source).interface)
    html = render_interface_html(graph, ReportSource(str(source), "E172-0225"))
    match = re.search(
        r"<details class='entity-view'[^>]+data-search='([^']*syntheticstate[^']*)'", html
    )
    assert match is not None
    search = match.group(1)
    assert "702" in search
    assert "syntheticstate" in search
    assert "urn:sema-sedd:fictional:702" in search
    assert "original synthetic variable" in search
    assert "input.addEventListener('input', update)" in html


def test_unresolved_reference_is_not_presented_as_resolved(tmp_path: Path) -> None:
    source = hinted(tmp_path, FIXTURES / "relationships" / "e172-dangling-event-variable.xml")
    graph = resolve_references(load_interface(source).interface)
    html = render_interface_html(graph, ReportSource(str(source), "E172-0225"))
    assert "UNRESOLVED_REFERENCE" in html
    assert "unsupported" in html
    assert "No resolved incoming relationships recorded." in html


def test_source_text_is_escaped_and_offline() -> None:
    variable = StatusVariable(
        key="x",
        implementation_id="44",
        name="X <script>alert(1)</script>",
        description="Description </script><img src=x onerror=alert(1)>",
    )
    graph = resolve_references(EquipmentInterface(status_variables=(variable,)))
    html = render_interface_html(graph, ReportSource("a.xml", "E172-0225"))
    parsed = TagCollector()
    parsed.feed(html)
    assert parsed.tags.count("script") == 1
    assert "img" not in parsed.tags and "link" not in parsed.tags
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert "connect-src 'none'" in html
    assert "fetch(" not in html


def test_cli_rejects_overwriting_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = hinted(tmp_path, COMPLETE)
    original = source.read_bytes()
    with pytest.raises(SystemExit) as error:
        main(["report", str(source), "--html", str(source)])
    assert error.value.code == 2
    assert "destination must differ" in capsys.readouterr().err
    assert source.read_bytes() == original
