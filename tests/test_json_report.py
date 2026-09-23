"""Public JSON contract, evidence preservation, and byte-stable examples."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from sema_sedd.compare import ChangeKind, compare_interfaces
from sema_sedd.exceptions import ReportError
from sema_sedd.model import (
    CanonicalType,
    DefaultReport,
    EntityReference,
    EquipmentInterface,
    SourceProvenance,
    StatusVariable,
    SupportedMessage,
    WellKnownName,
    WknAuthority,
)
from sema_sedd.report import (
    REPORT_SCHEMA_VERSION,
    ReportDiagnostic,
    ReportSource,
    public_change_id,
    report_from_changes,
    report_json,
    report_schema,
)
from sema_sedd.reporting import report_files

ROOT = Path(__file__).parent
SOURCES = (ReportSource("before.xml", "E172-0225"), ReportSource("after.xml", "E172-0225"))


def basic_report() -> Any:
    old = StatusVariable(key="sv", implementation_id="44", data_type="U4", description="Old note")
    new = replace(old, data_type="I4", description="Revised note")
    variable = EntityReference(
        target_types=(CanonicalType.STATUS_VARIABLE,), implementation_id="44"
    )
    report = DefaultReport(key="dr", implementation_id="7", variables=(variable,))
    a = EquipmentInterface(status_variables=(old,), default_reports=(report,))
    b = EquipmentInterface(status_variables=(new,), default_reports=(report,))
    return report_from_changes(
        compare_interfaces(a, b),
        *SOURCES,
        diagnostics_a=(ReportDiagnostic("FIXTURE_NOTE", "Synthetic example", "info"),),
    )


def ambiguous_report() -> Any:
    a = EquipmentInterface(
        supported_messages=(
            SupportedMessage(key="a1", stream=1, function=13),
            SupportedMessage(key="a2", stream=1, function=13),
        )
    )
    b = EquipmentInterface(
        supported_messages=(
            SupportedMessage(key="b1", stream=1, function=13),
            SupportedMessage(key="b2", stream=1, function=13),
        )
    )
    return report_from_changes(compare_interfaces(a, b), *SOURCES)


@pytest.mark.parametrize("name,factory", [("basic", basic_report), ("ambiguous", ambiguous_report)])
def test_public_snapshots_are_deterministic(name: str, factory: Callable[[], Any]) -> None:
    expected = (ROOT / "snapshots" / f"report-{name}-v1.json").read_text(encoding="utf-8")
    output = report_json(factory())
    assert output == expected
    assert output == report_json(factory())
    assert json.loads(output)["report_schema_version"] == REPORT_SCHEMA_VERSION


def test_change_codes_categories_context_and_diagnostics() -> None:
    report = basic_report()
    schema = cast(Any, report_schema())
    assert set(report) == set(schema["required"])
    assert {row["change_id"] for row in report["changes"]} == {
        "SV_DATA_TYPE_CHANGED",
        "SV_DESCRIPTION_CHANGED",
    }
    assert {row["category"] for row in report["changes"]} == {
        "INTERFACE_CHANGE",
        "DOCUMENTATION_CHANGE",
    }
    assert report["summary"]["changes"] == 2
    assert report["summary"]["matched"] == 2
    assert report["summary"]["is_complete"] is True
    context = report["dependency_context"][0]
    assert context["source_a"]["statements"] == ["Referenced by 1 default report."]
    assert context["source_b"]["statements"] == ["Referenced by 1 default report."]
    assert report["diagnostics"][0]["source"] == "a"
    assert "StatusVariable" not in report_json(report)
    assert "PropertyChange" not in report_json(report)


def test_ambiguous_identity_is_unresolved_with_public_evidence() -> None:
    report = ambiguous_report()
    assert report["summary"]["is_complete"] is False
    assert report["changes"] == []
    assert report["matches"] == []
    assert {item["issue_code"] for item in report["unresolved"]} == {"AMBIGUOUS_IDENTITY"}
    evidence = report["unresolved"][0]["identity_ambiguity"]["evidence"][0]
    assert evidence["source_a_keys"] == ["a1", "a2"]
    assert evidence["source_b_keys"] == ["b1", "b2"]
    assert "old_keys" not in evidence and "new_keys" not in evidence


def test_added_removed_and_relationship_codes() -> None:
    variable = StatusVariable(key="sv", implementation_id="44")
    empty = EquipmentInterface()
    filled = EquipmentInterface(status_variables=(variable,))
    added: Any = report_from_changes(compare_interfaces(empty, filled), *SOURCES)
    removed: Any = report_from_changes(compare_interfaces(filled, empty), *SOURCES)
    assert added["changes"][0]["change_id"] == "SV_ADDED"
    assert removed["changes"][0]["change_id"] == "SV_REMOVED"

    first = EntityReference(target_types=(CanonicalType.STATUS_VARIABLE,), implementation_id="44")
    second = EntityReference(target_types=(CanonicalType.STATUS_VARIABLE,), implementation_id="45")
    before = EquipmentInterface(
        status_variables=(variable, StatusVariable(key="sv2", implementation_id="45")),
        default_reports=(DefaultReport(key="dr", implementation_id="7", variables=(first,)),),
    )
    after = replace(
        before,
        default_reports=(DefaultReport(key="dr", implementation_id="7", variables=(second,)),),
    )
    relationship_report: Any = report_from_changes(compare_interfaces(before, after), *SOURCES)
    relationship = relationship_report["changes"][0]
    assert relationship["change_id"] == "DR_REPORT_CONTENT_CHANGED"
    assert relationship["scope"] == "relationship"
    assert relationship["relationship_delta"]["added"]
    assert relationship["relationship_delta"]["removed"]


def test_verified_wkn_continuity_exposes_implementation_id_change() -> None:
    wkn = WellKnownName(
        value="synthetic.temperature",
        authority="fictional-registry",
        scope="fixture",
        authority_status=WknAuthority.VERIFIED,
        provenance=(SourceProvenance(source_document="synthetic-registry.json"),),
    )
    before = EquipmentInterface(
        status_variables=(StatusVariable(key="old", implementation_id="44", wkn=wkn),)
    )
    after = EquipmentInterface(
        status_variables=(StatusVariable(key="new", implementation_id="8044", wkn=wkn),)
    )
    report: Any = report_from_changes(compare_interfaces(before, after), *SOURCES)
    assert [row["change_id"] for row in report["changes"]] == ["SV_IMPLEMENTATION_ID_CHANGED"]
    assert report["matches"][0]["strategy"] == "WELL_KNOWN_NAME"
    assert report["matches"][0]["evidence"][0]["identity"] == [
        "fictional-registry",
        "fixture",
        "synthetic.temperature",
    ]


def test_code_registry_is_explicit_and_rejects_unsupported_type() -> None:
    assert public_change_id(CanonicalType.STATUS_VARIABLE, ChangeKind.DATA_TYPE_CHANGED) == (
        "SV_DATA_TYPE_CHANGED"
    )
    assert all(
        re.fullmatch(r"[A-Z]+_[A-Z_]+", public_change_id(CanonicalType.ALARM, kind))
        for kind in ChangeKind
    )
    with pytest.raises(ReportError):
        public_change_id(CanonicalType.UNKNOWN_EXTENSION, ChangeKind.ENTITY_ADDED)
    with pytest.raises(ReportError):
        ReportSource("", "E172-0225")
    with pytest.raises(ReportError):
        ReportDiagnostic("X", "message", "fatal")


def test_schema_contract_is_bundled_and_refs_are_local() -> None:
    schema: Any = report_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["report_schema_version"] == {"const": REPORT_SCHEMA_VERSION}
    assert schema["additionalProperties"] is False
    definitions = schema["$defs"]

    def visit(value: object) -> None:
        if isinstance(value, dict):
            if "$ref" in value:
                assert value["$ref"].startswith("#/$defs/")
                assert value["$ref"].split("/")[-1] in definitions
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)


def test_report_files_runs_adapter_pipeline_and_keeps_uncertainty() -> None:
    before = ROOT / "fixtures" / "changes" / "e172-alarm-clear.xml"
    after = ROOT / "fixtures" / "changes" / "e172-alarm-link-after.xml"
    report: Any = report_files(before, after, revision_a="E172-0225", revision_b="E172-0225")
    assert report["source_a"]["path"] == str(before.resolve())
    assert report["source_b"]["path"] == str(after.resolve())
    assert report["source_a"]["revision"] == "E172-0225"
    assert report["tool_version"]
    assert report["diagnostics"]
    assert report_json(report) == report_json(
        report_files(before, after, revision_a="E172-0225", revision_b="E172-0225")
    )
