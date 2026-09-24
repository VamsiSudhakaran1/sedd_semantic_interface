"""Offline HTML report content, escaping, controls, and CLI file behavior."""

from __future__ import annotations

import re
from base64 import b64encode
from dataclasses import replace
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path

import pytest

from sema_sedd.cli import main
from sema_sedd.compare import compare_interfaces
from sema_sedd.model import (
    CanonicalType,
    DefaultReport,
    EntityReference,
    EquipmentInterface,
    SourceProvenance,
    StatusVariable,
    SupportedMessage,
)
from sema_sedd.report import ReportDiagnostic, ReportSource, render_html_report

FIXTURES = Path(__file__).parent / "fixtures"
BASE = FIXTURES / "relationships" / "e172-complete.xml"


class TagCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.script_text = ""
        self._inside_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))
        if tag == "script":
            self._inside_script = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._inside_script = False

    def handle_data(self, data: str) -> None:
        if self._inside_script:
            self.script_text += data


def synthetic_html() -> str:
    name = "Pump <script>alert('bad')</script>"
    old = StatusVariable(
        key="old",
        implementation_id="44",
        name=name,
        description="Earlier note",
        data_type="U4",
        provenance=(
            SourceProvenance(
                source_document="before.xml", source_path="/StatusVariable[1]", line=14
            ),
        ),
    )
    new = replace(
        old,
        description="Later </script><img src=x onerror=alert(1)>",
        data_type="I4",
        provenance=(
            SourceProvenance(
                source_document="after.xml", source_path="/StatusVariable[1]", line=21
            ),
        ),
    )
    reference = EntityReference(
        target_types=(CanonicalType.STATUS_VARIABLE,), implementation_id="44"
    )
    report = DefaultReport(key="report", implementation_id="7", variables=(reference,))
    before = EquipmentInterface(status_variables=(old,), default_reports=(report,))
    after = EquipmentInterface(status_variables=(new,), default_reports=(report,))
    return render_html_report(
        compare_interfaces(before, after),
        ReportSource("before.xml", "E172-0225"),
        ReportSource("after.xml", "E172-0225"),
        diagnostics_a=(
            ReportDiagnostic("SYNTHETIC_NOTE", "Check this input", "info", old.provenance[0]),
        ),
    )


def hinted(tmp_path: Path, source: Path) -> Path:
    root = '<sedd:DataDictionary xmlns:sedd="urn:semi-org:xsd.SEDD">'
    replacement = (
        '<sedd:DataDictionary xmlns:sedd="urn:semi-org:xsd.SEDD" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="urn:semi-org:xsd.SEDD E172-0225-SEDD-Schema.xsd">'
    )
    data = source.read_text(encoding="utf-8")
    assert root in data
    result = tmp_path / source.name
    result.write_text(data.replace(root, replacement, 1), encoding="utf-8")
    return result


def test_report_contains_required_evidence_and_controls() -> None:
    html = synthetic_html()
    assert html.startswith("<!doctype html>")
    for expected in (
        "Summary",
        "Search changed entities",
        "Change filter",
        "Show documentation changes",
        "Before · source A",
        "After · source B",
        "native id",
        "Referenced by 1 default report.",
        "before.xml · /StatusVariable[1] · line 14",
        "after.xml · /StatusVariable[1] · line 21",
        "SYNTHETIC_NOTE",
        "SV_DATA_TYPE_CHANGED",
        "SV_DESCRIPTION_CHANGED",
        "Diagnostics",
    ):
        assert expected in html
    assert "data-category='DOCUMENTATION_CHANGE'" in html
    assert "data-category='INTERFACE_CHANGE'" in html
    assert "data-scope='property'" in html
    assert "id='show-docs' type='checkbox' checked" in html
    assert "addEventListener('input', update)" in html
    assert "<details class='entity-card'>" in html
    assert html == synthetic_html()


def test_untrusted_source_text_is_escaped_and_no_external_assets_load() -> None:
    html = synthetic_html()
    parsed = TagCollector()
    parsed.feed(html)
    tags = [tag for tag, _ in parsed.tags]
    assert tags.count("script") == 1  # The report's own static filter script.
    assert "img" not in tags
    assert "link" not in tags
    assert "iframe" not in tags
    assert "&lt;script&gt;alert" in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert not re.search(r"(?:src|href)\s*=\s*['\"]https?://", html)
    assert "connect-src 'none'" in html
    script_hash = b64encode(sha256(parsed.script_text.encode("utf-8")).digest()).decode("ascii")
    assert f"script-src 'sha256-{script_hash}'" in html
    assert "script-src 'unsafe-inline'" not in html
    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html


def test_incomplete_comparison_shows_uncertainty_without_claiming_no_change() -> None:
    before = EquipmentInterface(
        supported_messages=(
            SupportedMessage(key="a1", stream=1, function=13),
            SupportedMessage(key="a2", stream=1, function=13),
        )
    )
    after = EquipmentInterface(
        supported_messages=(
            SupportedMessage(key="b1", stream=1, function=13),
            SupportedMessage(key="b2", stream=1, function=13),
        )
    )
    html = render_html_report(
        compare_interfaces(before, after),
        ReportSource("a.xml", "E172-0225"),
        ReportSource("b.xml", "E172-0225"),
    )
    assert "Comparison is incomplete" in html
    assert "AMBIGUOUS_IDENTITY" in html
    assert "Identity evidence" in html
    assert "No confirmed changes" in html
    assert "No diagnostics recorded" in html


def test_complete_no_change_report_is_clear() -> None:
    interface = EquipmentInterface(
        status_variables=(StatusVariable(key="sv", implementation_id="44"),)
    )
    html = render_html_report(
        compare_interfaces(interface, interface),
        ReportSource("a.xml", "E172-0225"),
        ReportSource("b.xml", "E172-0225"),
    )
    assert "No semantic changes found in the supported comparison scope." in html
    assert "Comparison is incomplete" not in html


def test_cli_writes_self_contained_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old = hinted(tmp_path, BASE)
    new = hinted(tmp_path, FIXTURES / "changes" / "e172-unit.xml")
    output = tmp_path / "report.html"
    assert main(["report", str(old), str(new), "--html", str(output)]) == 0
    assert capsys.readouterr().out == f"Wrote HTML report to {output.resolve()}\n"
    html = output.read_text(encoding="utf-8")
    assert "SV_UNIT_CHANGED" in html
    assert "Revision E172-0225" in html
    assert "<style>" in html and "<script>" in html
    assert "Unresolved items" in html
    assert main(["report", str(old), str(new), "--html", str(output)]) == 0
    assert output.read_text(encoding="utf-8") == html


def test_cli_rejects_input_overwrite_and_missing_destination(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old = hinted(tmp_path, BASE)
    new = hinted(tmp_path, FIXTURES / "changes" / "e172-unit.xml")
    original = old.read_bytes()
    with pytest.raises(SystemExit) as error:
        main(["report", str(old), str(new), "--html", str(old)])
    assert error.value.code == 2
    assert "destination must differ" in capsys.readouterr().err
    assert old.read_bytes() == original
    with pytest.raises(SystemExit) as error:
        main(["report", str(old), str(new)])
    assert error.value.code == 2
    assert "--html" in capsys.readouterr().err
