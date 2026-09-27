"""Diagnostic codes, evidence, ownership, and unknown-first behavior."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from sema_sedd.adapters import load_interface
from sema_sedd.cli import main
from sema_sedd.diagnostics import DiagnosticCode, DiagnosticSeverity
from sema_sedd.exceptions import UnsupportedSeddVersionError
from sema_sedd.graph import relationship_diagnostics, resolve_references
from sema_sedd.model import (
    Alarm,
    CanonicalType,
    CollectionEvent,
    EntityReference,
    EquipmentInterface,
    SourceProvenance,
)
from sema_sedd.report import report_schema
from sema_sedd.reporting import report_files

NS = "urn:semi-org:xsd.SEDD"
HINT = (
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    f'xsi:schemaLocation="{NS} E172-0225-SEDD-Schema.xsd"'
)


def source(tmp_path: Path, variable: str, *, extras: str = "") -> Path:
    path = tmp_path / "interface.xml"
    path.write_text(
        f'<s:DataDictionary xmlns:s="{NS}" {HINT}>\n'
        "<SEDDHeader><MDLN>Fixture</MDLN></SEDDHeader>\n"
        f"<StatusVariables>{variable}</StatusVariables>\n"
        "<CollectionEvents/><DataVariables/><EquipmentConstants/><Alarms/><VariableFormats/>\n"
        f"{extras}\n</s:DataDictionary>",
        encoding="utf-8",
    )
    return path


def test_unknown_and_optional_diagnostics_have_source_and_entity_context(tmp_path: Path) -> None:
    path = source(
        tmp_path,
        "<StatusVariable><SVID>7</SVID><SVNAME>Count</SVNAME><VendorTag/></StatusVariable>",
        extras="<RecipeVariableParameters/>",
    )
    result = load_interface(path)
    variable = result.interface.status_variables[0]
    assert variable.description is None
    assert [item.name for item in variable.unknown_extensions] == ["VendorTag"]
    by_code = {d.code: d for d in result.diagnostics}
    assert {
        DiagnosticCode.UNKNOWN_ELEMENT,
        DiagnosticCode.UNSUPPORTED_EXTENSION,
        DiagnosticCode.MISSING_OPTIONAL_METADATA,
    } <= set(by_code)
    unknown = by_code[DiagnosticCode.UNKNOWN_ELEMENT]
    assert unknown.severity is DiagnosticSeverity.WARNING
    assert unknown.source == str(path.resolve()) and unknown.source_line == 3
    assert unknown.entity_context is not None
    assert unknown.entity_context.canonical_type is CanonicalType.STATUS_VARIABLE
    assert unknown.entity_context.key == variable.key
    optional = by_code[DiagnosticCode.MISSING_OPTIONAL_METADATA]
    assert optional.severity is DiagnosticSeverity.INFO
    assert optional.entity_context == unknown.entity_context
    extension = by_code[DiagnosticCode.UNSUPPORTED_EXTENSION]
    assert extension.source_line == 5
    assert extension.entity_context is not None
    assert extension.entity_context.canonical_type is CanonicalType.EQUIPMENT_INTERFACE


def test_missing_required_structure_is_error_and_not_invented(tmp_path: Path) -> None:
    path = source(tmp_path, "<StatusVariable><SVNAME>Count</SVNAME></StatusVariable>")
    result = load_interface(path)
    assert result.interface.status_variables[0].implementation_id is None
    missing = next(
        d
        for d in result.diagnostics
        if d.code == DiagnosticCode.MISSING_REQUIRED_STRUCTURE
        and d.entity_context is not None
        and d.entity_context.canonical_type is CanonicalType.STATUS_VARIABLE
    )
    assert missing.severity is DiagnosticSeverity.ERROR
    assert missing.source_line == 3
    assert missing.entity_context is not None
    assert missing.entity_context.key == result.interface.status_variables[0].key


def test_final_reference_states_generate_distinct_diagnostics() -> None:
    provenance = SourceProvenance(source_document="fixture.xml", line=8)
    interface = EquipmentInterface(
        collection_events=(
            CollectionEvent(key="a", implementation_id="10"),
            CollectionEvent(key="b", implementation_id="10"),
        ),
        alarms=(
            Alarm(
                key="alarm",
                implementation_id="1",
                set_event=EntityReference(
                    target_types=(CanonicalType.COLLECTION_EVENT,),
                    implementation_id="10",
                    provenance=(provenance,),
                ),
                clear_event=EntityReference(
                    target_types=(CanonicalType.COLLECTION_EVENT,),
                    implementation_id="404",
                    provenance=(provenance,),
                ),
            ),
        ),
    )
    graph = resolve_references(interface)
    records = relationship_diagnostics(graph)
    assert {d.code for d in records} == {
        DiagnosticCode.UNRESOLVED_REFERENCE,
        DiagnosticCode.AMBIGUOUS_REFERENCE,
    }
    assert all(d.source == "fixture.xml" and d.source_line == 8 for d in records)
    assert all(d.entity_context and d.entity_context.key == "alarm" for d in records)
    set_event = graph.interface.alarms[0].set_event
    clear_event = graph.interface.alarms[0].clear_event
    assert set_event is not None and set_event.target_key is None
    assert clear_event is not None and clear_event.target_key is None
    assert len(graph.interface.unresolved_references) == 2


def test_inspect_and_json_report_publish_the_same_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = source(
        tmp_path,
        "<StatusVariable><SVID>7</SVID><SVNAME>Count</SVNAME><VendorTag/></StatusVariable>",
    )
    assert main(["inspect", str(path), "--json"]) == 0
    inspection = json.loads(capsys.readouterr().out)
    assert inspection["inspection_schema_version"] == "2.0"
    unknown = next(d for d in inspection["diagnostics"] if d["code"] == "UNKNOWN_ELEMENT")
    assert unknown["source"] == str(path.resolve())
    assert unknown["source_line"] == 3
    assert unknown["entity_context"]["canonical_type"] == "status_variable"
    assert unknown["severity"] == "WARNING"
    report = cast(Any, report_files(path, path))
    assert report["report_schema_version"] == "2.0"
    rows = report["diagnostics"]
    assert isinstance(rows, list)
    record = next(d for d in rows if isinstance(d, dict) and d["code"] == "UNKNOWN_ELEMENT")
    assert isinstance(record, dict)
    assert record["source"] == "a" and record["source_path"] == str(path.resolve())
    assert record["source_line"] == 3
    assert record["entity_context"]["canonical_type"] == "status_variable"
    schema = cast(Any, report_schema())
    diagnostic = schema["$defs"]["diagnostic"]
    assert {"source_path", "source_line", "entity_context"} <= set(diagnostic["required"])


def test_unsupported_revision_error_reports_code_source_and_context(tmp_path: Path) -> None:
    path = source(tmp_path, "")
    path.write_text(path.read_text().replace("E172-0225", "E172-9999"), encoding="utf-8")
    with pytest.raises(UnsupportedSeddVersionError) as caught:
        load_interface(path)
    error = caught.value
    assert error.diagnostic_code == DiagnosticCode.UNSUPPORTED_REVISION
    assert error.source == str(path.resolve()) and error.source_line == 1
    assert error.entity_context is not None
    assert error.entity_context.canonical_type is CanonicalType.EQUIPMENT_INTERFACE
    assert "E172-9999" in str(error)
    diagnostic = error.diagnostic
    assert diagnostic.code == DiagnosticCode.UNSUPPORTED_REVISION
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.source == str(path.resolve())
    assert diagnostic.source_line == 1
    assert diagnostic.entity_context == error.entity_context
