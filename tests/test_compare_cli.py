"""Compare CLI projection, filtering, diagnostics and execution exit status."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from sema_sedd.cli import main
from sema_sedd.cli.compare import build_comparison, render_text

FIXTURES = Path(__file__).parent / "fixtures"
BASE = FIXTURES / "relationships" / "e172-complete.xml"
ROOT = '<sedd:DataDictionary xmlns:sedd="urn:semi-org:xsd.SEDD">'
HINTED = (
    '<sedd:DataDictionary xmlns:sedd="urn:semi-org:xsd.SEDD" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xsi:schemaLocation="urn:semi-org:xsd.SEDD E172-0225-SEDD-Schema.xsd">'
)


def hinted(tmp_path: Path, source: Path) -> Path:
    data = source.read_text(encoding="utf-8")
    assert ROOT in data
    target = tmp_path / source.name
    target.write_text(data.replace(ROOT, HINTED, 1), encoding="utf-8")
    return target


def pair(tmp_path: Path, after_name: str) -> tuple[Path, Path]:
    return hinted(tmp_path, BASE), hinted(tmp_path, FIXTURES / "changes" / after_name)


def invoke(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sema_sedd", "compare", *(str(value) for value in args)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_text_has_required_sections_and_factual_details(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new = pair(tmp_path, "e172-report.xml")
    assert main(["compare", str(old), str(new), "--no-color"]) == 0
    text = capsys.readouterr().out
    sections = (
        "Summary",
        "Added",
        "Removed",
        "Identity-preserving changes",
        "Property changes",
        "Relationship changes",
        "Documentation-only changes",
        "Unresolved items",
        "Diagnostics",
    )
    assert [text.index(section) for section in sections] == sorted(text.index(s) for s in sections)
    assert "REPORT_CONTENT_CHANGED" in text
    assert "variables:" in text
    assert "Unresolved items" in text
    assert "UNKNOWN_CONTENT" in text
    assert "\x1b[" not in text


def test_json_is_deterministic_and_uses_semantic_kinds(tmp_path: Path) -> None:
    old, new = pair(tmp_path, "e172-unit.xml")
    first = invoke(old, new, "--json")
    second = invoke(old, new, "--json")
    assert first.returncode == second.returncode == 0
    assert first.stderr == second.stderr == ""
    assert first.stdout == second.stdout and first.stdout.endswith("\n")
    data = json.loads(first.stdout)
    assert data["comparison_schema_version"] == "2.0"
    assert data["old_revision"] == data["new_revision"] == "E172-0225"
    assert data["summary"]["property_changes"] == 1
    assert len(data["property_changes"]) == 1
    property_change = data["property_changes"][0]
    assert property_change["change"]["kind"] == "UNIT_CHANGED"
    assert property_change["subject"]["type"] == "status_variable"
    assert data["identity_preserving_changes"][0]["match"]["strategy"] == "NATIVE_ID"
    assert data["summary"]["diagnostics"] == len(data["diagnostics"])
    assert all(
        item["diagnostic"]["code"] != "REFERENCE_RESOLUTION_PENDING" for item in data["diagnostics"]
    )


def test_type_filter_is_exact_and_keeps_source_wide_diagnostics(tmp_path: Path) -> None:
    old, new = pair(tmp_path, "e172-unit.xml")
    variable = json.loads(invoke(old, new, "--json", "--type", "status_variable").stdout)
    alarm = json.loads(invoke(old, new, "--json", "--type", "alarm").stdout)
    assert variable["summary"]["property_changes"] == 1
    assert alarm["summary"]["property_changes"] == 0
    assert alarm["identity_preserving_changes"] == []
    assert alarm["summary"]["matched"] == 1
    assert alarm["diagnostics"] == variable["diagnostics"]
    assert all(
        item["subject"]["type"] == "status_variable" for item in variable["property_changes"]
    )
    invalid = invoke(old, new, "--type", "StatusVariable")
    assert invalid.returncode == 2 and "invalid choice" in invalid.stderr


def test_added_and_removed_sections_show_definite_entity_changes(tmp_path: Path) -> None:
    old = hinted(tmp_path, BASE)
    removed = tmp_path / "removed.xml"
    original = old.read_text(encoding="utf-8")
    changed, count = re.subn(
        r"<StatusVariables>.*?</StatusVariables>",
        "<StatusVariables/>",
        original,
        count=1,
        flags=re.DOTALL,
    )
    assert count == 1
    removed.write_text(changed, encoding="utf-8")
    removal = json.loads(invoke(old, removed, "--json", "--type", "status_variable").stdout)
    addition = json.loads(invoke(removed, old, "--json", "--type", "status_variable").stdout)
    assert removal["summary"]["removed"] == 1
    assert removal["removed"][0]["kind"] == "ENTITY_REMOVED"
    assert removal["added"] == []
    assert addition["summary"]["added"] == 1
    assert addition["added"][0]["kind"] == "ENTITY_ADDED"
    assert addition["removed"] == []
    assert invoke(old, removed).returncode == invoke(removed, old).returncode == 0


def test_equipment_metadata_type_filter(tmp_path: Path) -> None:
    old = hinted(tmp_path, BASE)
    updated = tmp_path / "supplier.xml"
    updated.write_text(
        old.read_text(encoding="utf-8").replace(
            "<Supplier>Example Fabrication Lab</Supplier>",
            "<Supplier>Fixture Supplier Two</Supplier>",
            1,
        ),
        encoding="utf-8",
    )
    data = json.loads(invoke(old, updated, "--json", "--type", "equipment_metadata").stdout)
    assert data["summary"]["property_changes"] == 1
    assert data["property_changes"][0]["subject"]["type"] == "equipment_metadata"


def test_only_changed_hides_confirmed_unchanged_matches(tmp_path: Path) -> None:
    old, new = pair(tmp_path, "e172-unit.xml")
    default = json.loads(invoke(old, new, "--json").stdout)
    filtered = json.loads(invoke(old, new, "--json", "--only-changed").stdout)
    assert default["unchanged_matches"]
    assert filtered["unchanged_matches"] == []
    assert default["property_changes"] == filtered["property_changes"]
    assert default["summary"]["matched"] == filtered["summary"]["matched"]
    assert "Unchanged matched entities" in invoke(old, new).stdout
    assert "Unchanged matched entities" not in invoke(old, new, "--only-changed").stdout


def test_documentation_is_opt_in_and_mixed_changes_keep_interface_facts(tmp_path: Path) -> None:
    old, doc = pair(tmp_path, "e172-description.xml")
    hidden = json.loads(invoke(old, doc, "--json").stdout)
    shown = json.loads(invoke(old, doc, "--json", "--include-documentation").stdout)
    assert hidden["documentation_only_changes"] == []
    assert hidden["summary"]["hidden_documentation_only_changes"] == 1
    assert shown["summary"]["documentation_only_changes"] == 1
    assert shown["property_changes"][0]["change"]["kind"] == "DESCRIPTION_CHANGED"
    assert "hidden" in invoke(old, doc).stdout
    assert "Changed synthetic description." in invoke(old, doc, "--include-documentation").stdout

    # The same matched entity can have an interface and a documentation edit.
    mixed_xml = (FIXTURES / "changes" / "e172-unit.xml").read_text(encoding="utf-8")
    mixed_xml = mixed_xml.replace(
        "Original synthetic variable.", "Changed synthetic description.", 1
    )
    mixed = tmp_path / "mixed.xml"
    mixed.write_text(mixed_xml.replace(ROOT, HINTED, 1), encoding="utf-8")
    without_docs = json.loads(invoke(old, mixed, "--json").stdout)
    with_docs = json.loads(invoke(old, mixed, "--json", "--include-documentation").stdout)
    assert [row["change"]["kind"] for row in without_docs["property_changes"]] == ["UNIT_CHANGED"]
    assert {row["change"]["kind"] for row in with_docs["property_changes"]} == {
        "UNIT_CHANGED",
        "DESCRIPTION_CHANGED",
    }


@pytest.mark.parametrize(
    "name,kind,section",
    [
        ("e172-report.xml", "REPORT_CONTENT_CHANGED", "relationship_changes"),
        ("e172-alarm-clear.xml", "ALARM_EVENT_LINK_CHANGED", "relationship_changes"),
        ("e172-name.xml", "NAME_CHANGED", "property_changes"),
        ("e172-wkn.xml", "WELL_KNOWN_NAME_CHANGED", "property_changes"),
    ],
)
def test_existing_change_fixtures_have_specific_json_findings(
    tmp_path: Path, name: str, kind: str, section: str
) -> None:
    old, new = pair(tmp_path, name)
    result = invoke(old, new, "--json", "--only-changed")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert any(row["change"]["kind"] == kind for row in data[section])


def test_json_no_color_flag_does_not_change_machine_output(tmp_path: Path) -> None:
    old, new = pair(tmp_path, "e172-unit.xml")
    assert invoke(old, new, "--json").stdout == invoke(old, new, "--json", "--no-color").stdout
    view = build_comparison(old, new)
    assert "\x1b[36mSummary\x1b[0m" in render_text(view, color=True)
    assert "\x1b[" not in render_text(view, color=False)


def test_multiline_source_text_cannot_create_spurious_report_lines(tmp_path: Path) -> None:
    old = hinted(tmp_path, BASE)
    edited = tmp_path / "multiline.xml"
    edited.write_text(
        old.read_text(encoding="utf-8").replace(
            "<ALTX>Synthetic warning</ALTX>",
            "<ALTX>Synthetic warning\nDiagnostics (999)</ALTX>",
            1,
        ),
        encoding="utf-8",
    )
    result = invoke(old, edited, "--no-color", "--only-changed")
    assert result.returncode == 0
    assert "Synthetic warning\\nDiagnostics (999)" in result.stdout
    assert "Diagnostics (999)" not in result.stdout.splitlines()


def test_unresolved_and_ambiguous_findings_exit_zero(tmp_path: Path) -> None:
    source = hinted(tmp_path, FIXTURES / "relationships" / "e172-ambiguous-message.xml")
    result = invoke(source, source, "--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["summary"]["is_complete"] is False
    assert data["unresolved_items"]
    assert any(item["kind"] == "AMBIGUOUS_IDENTITY" for item in data["unresolved_items"])


def test_insignificant_xml_noise_exits_zero_without_semantic_changes(tmp_path: Path) -> None:
    old = hinted(tmp_path, BASE)
    new = tmp_path / "noise.xml"
    new.write_text(
        old.read_text(encoding="utf-8")
        .replace("<sedd:DataDictionary", "<alt:DataDictionary")
        .replace("</sedd:DataDictionary>", "</alt:DataDictionary>")
        .replace("xmlns:sedd=", "xmlns:alt=")
        .replace("\n  ", "\n    "),
        encoding="utf-8",
    )
    result = invoke(old, new, "--json", "--only-changed")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["added"] == data["removed"] == []
    assert data["identity_preserving_changes"] == []


def test_execution_errors_only_affect_exit_status(tmp_path: Path) -> None:
    old, new = pair(tmp_path, "e172-unit.xml")
    missing = invoke(old, tmp_path / "missing.xml")
    malformed = tmp_path / "malformed.xml"
    malformed.write_text("<broken>", encoding="utf-8")
    broken = invoke(old, malformed)
    incomplete = invoke(old)
    assert all(item.returncode == 2 for item in (missing, broken, incomplete))
    assert all(
        item.stdout == "" and "Traceback" not in item.stderr
        for item in (missing, broken, incomplete)
    )
    assert invoke(old, new).returncode == 0
