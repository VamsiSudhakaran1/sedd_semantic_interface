"""Executable original tutorial examples without downloaded reference artifacts."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from examples.compare_demo import main as demo_main
from examples.compare_demo import prepare_demo_interface
from sema_sedd.adapters import load_interface
from sema_sedd.cli import main
from sema_sedd.compare import ChangeKind, compare_interfaces
from sema_sedd.graph import ResolutionState, resolve_references
from sema_sedd.model import WknAuthority
from sema_sedd.report import ReportSource, report_from_changes

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
OLD = EXAMPLES / "machine-v1.xml"
NEW = EXAMPLES / "machine-v2.xml"


def test_xml_examples_expose_changes_without_claiming_wkn_verification() -> None:
    old, new = load_interface(OLD), load_interface(NEW)
    assert old.revision == new.revision == "E172-0225"
    for adapted in (old, new):
        assert all(item.severity.value == "INFO" for item in adapted.diagnostics)
        assert all(
            rel.state is ResolutionState.RESOLVED
            for rel in resolve_references(adapted.interface).relationships
        )
        pressure = next(v for v in adapted.interface.status_variables if v.name == "Pressure")
        assert pressure.wkn is not None
        assert pressure.wkn.authority_status is WknAuthority.UNVERIFIED
        assert pressure.data_type is None
    changes = compare_interfaces(old.interface, new.interface)
    assert changes.is_complete
    assert len(changes.matching.matches) == 11
    assert sum(c.kind is ChangeKind.ENTITY_ADDED for c in changes.entity_changes) == 2
    assert sum(c.kind is ChangeKind.ENTITY_REMOVED for c in changes.entity_changes) == 2
    assert not any(ChangeKind.IMPLEMENTATION_ID_CHANGED in c.kinds for c in changes.entity_changes)
    unchanged = {
        "UnchangedReady",
        "Started",
        "Stopped",
        "ReadyReport",
        "CountFormat",
        "DemoMessage",
    }
    for change in changes.entity_changes:
        subject = change.new_entity or change.old_entity
        assert subject is not None
        assert subject.name is None or subject.name not in unchanged


def test_fictional_evidence_demo_covers_every_documented_semantic_change() -> None:
    old = prepare_demo_interface(load_interface(OLD).interface)
    new = prepare_demo_interface(load_interface(NEW).interface)
    changes = compare_interfaces(old, new)
    report = report_from_changes(
        changes, ReportSource("v1", "E172-0225"), ReportSource("v2", "E172-0225")
    )
    assert report["summary"] == {
        "is_complete": True,
        "matched": 12,
        "changed_entities": 8,
        "added": 1,
        "removed": 1,
        "changes": 10,
        "interface_changes": 9,
        "documentation_changes": 1,
        "unknown_changes": 0,
        "unresolved": 0,
        "diagnostics": 0,
    }
    pressure = next(
        c
        for c in changes.entity_changes
        if c.new_entity is not None and c.new_entity.name == "Pressure"
    )
    assert pressure.kind is ChangeKind.ENTITY_MODIFIED
    assert pressure.match is not None and pressure.match.strategy.value == "WELL_KNOWN_NAME"
    assert {p.kind for p in pressure.properties} == {
        ChangeKind.IMPLEMENTATION_ID_CHANGED,
        ChangeKind.DATA_TYPE_CHANGED,
    }
    assert pressure.old_entity is not None and pressure.new_entity is not None
    assert pressure.old_entity.implementation_id == "44"
    assert pressure.new_entity.implementation_id == "144"
    assert pressure.new_entity.wkn is not None
    assert any(
        p.source_document == "examples/fictional-wkn.json"
        for p in pressure.new_entity.wkn.provenance
    )
    rows = report["changes"]
    assert isinstance(rows, list)
    codes = [row["change_id"] for row in rows if isinstance(row, dict)]
    assert set(codes) == {
        "SV_ADDED",
        "SV_REMOVED",
        "SV_IMPLEMENTATION_ID_CHANGED",
        "SV_DATA_TYPE_CHANGED",
        "SV_DESCRIPTION_CHANGED",
        "VF_FORMAT_CHANGED",
        "DR_REPORT_CONTENT_CHANGED",
        "ERL_EVENT_REPORT_LINK_CHANGED",
        "AL_ALARM_EVENT_LINK_CHANGED",
    }
    assert codes.count("AL_ALARM_EVENT_LINK_CHANGED") == 2
    changed_report = next(
        c
        for c in changes.entity_changes
        if c.new_entity is not None and c.new_entity.name == "CycleReport"
    )
    assert len(changed_report.relationships[0].added) == 1
    assert len(changed_report.relationships[0].removed) == 1


def test_reorder_alone_creates_no_semantic_changes(tmp_path: Path) -> None:
    # Only bundled trusted synthetic data is read by the standard-library test helper.
    tree = ET.parse(OLD)
    root = tree.getroot()
    root[:] = list(reversed(list(root)))
    inventories = {
        "StatusVariables",
        "CollectionEvents",
        "VariableFormats",
        "DefaultReportDefinitions",
        "Alarms",
    }
    singleton_records = {
        "SEDDHeader",
        "StatusVariable",
        "CollectionEvent",
        "VariableFormat",
        "DefaultReportDefinition",
        "Alarm",
        "EventReportLink",
    }
    for node in root.iter():
        if node.tag in inventories or node.tag in singleton_records:
            node[:] = list(reversed(list(node)))
        node.attrib = dict(reversed(list(node.attrib.items())))
    reordered = tmp_path / "reordered.xml"
    tree.write(reordered, encoding="utf-8", xml_declaration=True)
    changes = compare_interfaces(load_interface(OLD).interface, load_interface(reordered).interface)
    assert changes.is_complete
    assert not changes.entity_changes
    assert not changes.issues


@pytest.mark.parametrize(
    "command",
    [
        ["inspect", str(OLD)],
        ["inspect", str(OLD), "--type", "status_variable", "--id", "44", "--json"],
        ["explore", str(OLD), "event:1001", "--depth", "2"],
        ["explore", str(OLD), "alarm:72", "--json"],
        ["explore", str(NEW), "wkn:urn:example:machine:pressure", "--depth", "1"],
        ["compare", str(OLD), str(NEW), "--include-documentation", "--no-color"],
        ["compare", str(OLD), str(NEW), "--only-changed", "--json"],
    ],
)
def test_documented_cli_commands_execute(
    command: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(command) == 0
    output = capsys.readouterr()
    assert output.out and not output.err
    if "--json" in command:
        assert isinstance(json.loads(output.out), dict)


def test_both_documented_html_modes_write_local_reports(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for inputs, name in (([str(OLD)], "interface.html"), ([str(OLD), str(NEW)], "comparison.html")):
        output = tmp_path / name
        assert main(["report", *inputs, "--html", str(output)]) == 0
        text = output.read_text(encoding="utf-8")
        assert "ExampleMachine" in text if name == "interface.html" else "SEDD comparison" in text
        assert "Content-Security-Policy" in text
    assert not capsys.readouterr().err


def test_demo_script_outputs_deterministic_public_report(
    capsys: pytest.CaptureFixture[str],
) -> None:
    demo_main()
    first = capsys.readouterr().out
    demo_main()
    assert first == capsys.readouterr().out
    assert json.loads(first)["report_schema_version"] == "2.0"
