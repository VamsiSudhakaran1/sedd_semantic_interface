"""Revision boundary regressions; fictional syntax is not a real SEMI revision."""

from __future__ import annotations

import ast
import socket
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from sema_sedd.adapters import (
    AdapterRegistry,
    AdapterResult,
    RevisionStatus,
    SupportLevel,
    default_registry,
    detect_revision,
    load_interface,
)
from sema_sedd.adapters.e172_0225 import E172_0225Adapter
from sema_sedd.cli import main
from sema_sedd.compare import ChangeKind, compare_interfaces
from sema_sedd.exceptions import UnsupportedSeddVersionError
from sema_sedd.graph import ResolutionState, resolve_references
from sema_sedd.model import (
    CanonicalType,
    DefaultReport,
    EntityReference,
    EquipmentInterface,
    EquipmentMetadata,
    SourceProvenance,
    StatusVariable,
    UnknownExtension,
)
from sema_sedd.parser import SourcedDocument, load_xml
from sema_sedd.report import ReportSource, render_interface_html, report_from_changes

NS = "urn:semi-org:xsd.SEDD"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
FAKE_NS = "urn:sema-sedd:fictional-adapter-test:v2"


def xml_document(tmp_path: Path, hint: str | None, *, namespace: str = NS) -> SourcedDocument:
    declaration = f' xmlns="{namespace}"' if namespace else ""
    schema = f' xsi:schemaLocation="{hint}"' if hint is not None else ""
    path = tmp_path / "document.xml"
    path.write_text(f'<DataDictionary{declaration} xmlns:xsi="{XSI}"{schema}/>', encoding="utf-8")
    return load_xml(path)


@pytest.mark.parametrize(
    "location",
    [
        "E172-0225-SEDD-Schema.xsd",
        "https://example.invalid/schemas/E172-0225-SEDD-Schema.xsd?ignored=1#fragment",
        "../schemas/E172-0225-SEDD-Schema.xsd",
        "C:\\schemas\\E172-0225-SEDD-Schema.xsd",
        "https://example.invalid/E172-%30%32%32%35-SEDD-Schema.xsd",
    ],
)
def test_identification_is_lexical_and_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    location: str,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Network access attempted")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    document = xml_document(tmp_path, f"{NS} {location}")
    assert detect_revision(document).revision_hint == "E172-0225"
    assert default_registry().assess(document).status is RevisionStatus.SUPPORTED


@pytest.mark.parametrize("namespace", [NS, "urn:future:unimplemented"])
@pytest.mark.parametrize("revision", ["E172-0124", "E172-9999"])
def test_unknown_revision_is_identified_but_never_mapped(
    tmp_path: Path,
    namespace: str,
    revision: str,
) -> None:
    document = xml_document(
        tmp_path, f"{namespace} {revision}-SEDD-Schema.xsd", namespace=namespace
    )
    assessment = default_registry().assess(document)
    assert assessment.detection.revision_hint == revision
    assert assessment.status is RevisionStatus.UNSUPPORTED
    assert assessment.supported_revisions == ()
    for requested in (None, "E172-0225", revision):
        with pytest.raises(UnsupportedSeddVersionError) as caught:
            load_interface(document.source, revision=requested)
        assert caught.value.detected_revision == revision
        assert caught.value.status == "unsupported"
        assert revision in str(caught.value)
    with pytest.raises(UnsupportedSeddVersionError) as direct:
        E172_0225Adapter().parse(document)
    assert direct.value.detected_revision == revision


@pytest.mark.parametrize(
    ("hint", "code", "candidates"),
    [
        (
            f"{NS} E172-0225-SEDD-Schema.xsd {NS} E172-9999-SEDD-Schema.xsd",
            "AMBIGUOUS_SCHEMA_HINT",
            ("E172-0225", "E172-9999"),
        ),
        (
            f"{NS} E172-0225-SEDD-Schema.xsd {NS} unknown.xsd",
            "AMBIGUOUS_SCHEMA_HINT",
            ("E172-0225",),
        ),
        (f"{NS} http://[broken/schema.xsd", "MALFORMED_SCHEMA_HINT", ()),
        (f"{NS} E172-0225-SEDD-Schema.xsd stray", "MALFORMED_SCHEMA_HINT", ()),
        (f"{NS} other.xsd?name=E172-0225-SEDD-Schema.xsd", "UNRECOGNIZED_SCHEMA_HINT", ()),
        (f"{NS} E172-0225-SEDD-Schema.xsd.bak", "UNRECOGNIZED_SCHEMA_HINT", ()),
        (f"{NS} E172-０２２５-SEDD-Schema.xsd", "UNRECOGNIZED_SCHEMA_HINT", ()),
    ],
)
def test_conflicting_or_malformed_hints_cannot_select_semantics(
    tmp_path: Path,
    hint: str,
    code: str,
    candidates: tuple[str, ...],
) -> None:
    document = xml_document(tmp_path, hint)
    detection = detect_revision(document)
    assert detection.revision_hint is None
    assert detection.diagnostic_code == code
    assert detection.candidates == candidates
    for requested in (None, "E172-0225"):
        with pytest.raises(UnsupportedSeddVersionError):
            default_registry().adapt(document, revision=requested)


def test_duplicate_identical_hints_and_imported_hints(tmp_path: Path) -> None:
    one = f"{NS} E172-0225-SEDD-Schema.xsd"
    document = xml_document(tmp_path, f"{one} {one} urn:unrelated E172-9999-SEDD-Schema.xsd")
    assert default_registry().assess(document).status is RevisionStatus.SUPPORTED
    only_import = xml_document(tmp_path, "urn:unrelated E172-0225-SEDD-Schema.xsd")
    assert detect_revision(only_import).revision_hint is None
    assert default_registry().assess(only_import).status is RevisionStatus.UNSUPPORTED


def test_no_namespace_hint_identifies_label_without_admitting_root(tmp_path: Path) -> None:
    path = tmp_path / "no-namespace.xml"
    path.write_text(
        f'<Anything xmlns:xsi="{XSI}" xsi:noNamespaceSchemaLocation="E172-9999-SEDD-Schema.xsd"/>',
        encoding="utf-8",
    )
    document = load_xml(path)
    assert document.namespace == ""
    assert detect_revision(document).revision_hint == "E172-9999"
    assert default_registry().assess(document).status is RevisionStatus.UNSUPPORTED


def test_no_hint_is_indeterminate_not_latest_revision(tmp_path: Path) -> None:
    document = xml_document(tmp_path, None)
    assert default_registry().assess(document).status is RevisionStatus.INDETERMINATE
    with pytest.raises(UnsupportedSeddVersionError):
        default_registry().adapt(document)
    assert default_registry().adapt(document, revision="E172-0225").revision == "E172-0225"


def test_cli_reports_identified_unsupported_revision_without_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    document = xml_document(tmp_path, f"{NS} E172-9999-SEDD-Schema.xsd")
    with pytest.raises(SystemExit) as caught:
        main(["inspect", str(document.source), "--json"])
    assert caught.value.code == 2
    output = capsys.readouterr()
    assert not output.out
    assert "Unsupported SEDD revision" in output.err and "E172-9999" in output.err
    assert "Traceback" not in output.err


class FictionalAdapter:
    """Only test scaffolding: attribute-based syntax with a different root/namespace."""

    revision = "TEST-FICTIONAL-V2"

    def detect_support(self, document: SourcedDocument) -> SupportLevel:
        return (
            SupportLevel.SUPPORTED
            if document.root.tag == f"{{{FAKE_NS}}}Interface"
            and document.root.attribute("edition") == "test-v2"
            else SupportLevel.UNSUPPORTED
        )

    def parse(self, document: SourcedDocument) -> AdapterResult:
        assert self.detect_support(document) is SupportLevel.SUPPORTED
        variable, report = document.root.children
        provenance = (
            SourceProvenance(
                source_document=str(document.source),
                source_revision=self.revision,
                source_path="/fictional/interface",
                path_kind="xml",
            ),
        )
        return AdapterResult(
            EquipmentInterface(
                equipment=EquipmentMetadata(model=document.root.attribute("model")),
                provenance=provenance,
                status_variables=(
                    StatusVariable(
                        key="fictional-variable",
                        implementation_id=variable.attribute("id"),
                        name=variable.attribute("label"),
                        units=(variable.attribute("unit") or "",),
                        provenance=provenance,
                    ),
                ),
                default_reports=(
                    DefaultReport(
                        key="fictional-report",
                        implementation_id=report.attribute("id"),
                        name=report.attribute("label"),
                        provenance=provenance,
                        variables=(
                            EntityReference(
                                target_types=(
                                    CanonicalType.STATUS_VARIABLE,
                                    CanonicalType.DATA_VARIABLE,
                                    CanonicalType.EQUIPMENT_CONSTANT,
                                ),
                                implementation_id=report.attribute("member"),
                                provenance=provenance,
                            ),
                        ),
                    ),
                ),
            ),
            self.revision,
        )


def paired_sources(tmp_path: Path) -> tuple[Path, Path]:
    first = tmp_path / "original.xml"
    first.write_text(
        f'''<s:DataDictionary xmlns:s="{NS}" xmlns:xsi="{XSI}"
        xsi:schemaLocation="{NS} E172-0225-SEDD-Schema.xsd">
        <SEDDHeader><MDLN>TestMachine</MDLN></SEDDHeader>
        <StatusVariables><StatusVariable><SVID>44</SVID><SVNAME>Count</SVNAME>
        <UNITS>count</UNITS></StatusVariable></StatusVariables>
        <DefaultReportDefinitions><DefaultReportDefinition><RPTID>7</RPTID>
        <DefaultReportName>Inventory</DefaultReportName><VIDList><VID>44</VID></VIDList>
        </DefaultReportDefinition></DefaultReportDefinitions>
        <CollectionEvents/><DataVariables/><EquipmentConstants/><Alarms/><VariableFormats/>
        </s:DataDictionary>''',
        encoding="utf-8",
    )
    second = tmp_path / "fictional.xml"
    second.write_text(
        f'''<Interface xmlns="{FAKE_NS}" edition="test-v2" model="TestMachine">
        <Variable id="44" label="Count" unit="count"/>
        <Report id="7" label="Inventory" member="44"/>
        </Interface>''',
        encoding="utf-8",
    )
    return first, second


def test_distinct_revision_syntax_compares_and_resolves_without_downstream_changes(
    tmp_path: Path,
) -> None:
    first, second = paired_sources(tmp_path)
    for adapters in (
        (E172_0225Adapter(), FictionalAdapter()),
        (FictionalAdapter(), E172_0225Adapter()),
    ):
        registry = AdapterRegistry(adapters)
        old = load_interface(first, registry=registry)
        new = load_interface(second, registry=registry)
        assert old.revision != new.revision
        assert old.interface.provenance[0].source_revision == "E172-0225"
        assert new.interface.provenance[0].source_revision == FictionalAdapter.revision
        equal = compare_interfaces(old.interface, new.interface)
        assert not equal.entity_changes and equal.is_complete
        assert len(equal.matching.matches) == 2
        for interface in (old.interface, new.interface):
            graph = resolve_references(interface)
            assert len(graph.relationships) == 1
            assert graph.relationships[0].state is ResolutionState.RESOLVED
            assert "Incoming relationships" in render_interface_html(
                graph,
                ReportSource("fixture.xml", "test"),
            )
        changed = replace(
            new.interface,
            status_variables=(replace(new.interface.status_variables[0], units=("items",)),),
        )
        cross = compare_interfaces(old.interface, changed)
        same = compare_interfaces(new.interface, changed)
        for changes in (cross, same):
            assert changes.is_complete and len(changes.entity_changes) == 1
            change = changes.entity_changes[0]
            assert change.properties[0].kind is ChangeKind.UNIT_CHANGED
            assert change.old_context is not None
            assert change.old_context.statements == ("Referenced by 1 default report.",)
            report = report_from_changes(
                changes, ReportSource("a", old.revision), ReportSource("b", new.revision)
            )
            rows = report["changes"]
            assert isinstance(rows, list)
            row = rows[0]
            assert isinstance(row, dict)
            assert row["change_id"] == "SV_UNIT_CHANGED"


def test_source_schema_url_differences_are_not_semantic_extension_changes(tmp_path: Path) -> None:
    first, _ = paired_sources(tmp_path)
    old = load_interface(first).interface
    first.write_text(
        first.read_text().replace(
            "E172-0225-SEDD-Schema.xsd", "https://example.invalid/E172-0225-SEDD-Schema.xsd"
        ),
        encoding="utf-8",
    )
    new = load_interface(first).interface
    changes = compare_interfaces(old, new)
    assert changes.is_complete and not changes.entity_changes
    opaque = replace(new, unknown_extensions=(UnknownExtension(name="FutureMaterial"),))
    unknown = compare_interfaces(old, opaque)
    assert not unknown.is_complete  # Actual unknown semantic material still matters.


def test_parser_and_downstream_do_not_encode_revision_vocabulary() -> None:
    root = Path(__file__).parents[1] / "src" / "sema_sedd"
    for package in ("parser", "model", "graph", "compare", "report"):
        for path in (root / package).glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    assert "E172-0225" not in node.value, path
                    assert "urn:semi-org:xsd.SEDD" not in node.value, path
                if package == "parser" and isinstance(node, ast.ImportFrom):
                    assert "adapters" not in (node.module or ""), path


def test_canonical_comparison_executes_with_concrete_adapter_imports_blocked() -> None:
    code = """
import sys
from importlib.abc import MetaPathFinder
class BlockConcrete(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if "e172_0225" in fullname:
            raise AssertionError("Concrete adapter leaked downstream")
sys.meta_path.insert(0, BlockConcrete())
from sema_sedd.compare import compare_interfaces, ChangeKind
from sema_sedd.model import EquipmentInterface, StatusVariable
from sema_sedd.report import report_from_changes, ReportSource
old = EquipmentInterface(status_variables=(StatusVariable(key="a", implementation_id="7"),))
new = EquipmentInterface(status_variables=(
    StatusVariable(key="b", implementation_id="7", units=("K",)),
))
changes = compare_interfaces(old, new)
assert changes.is_complete
assert changes.entity_changes[0].properties[0].kind is ChangeKind.UNIT_CHANGED
report = report_from_changes(
    changes, ReportSource("a", "revision-a"), ReportSource("b", "revision-b"),
)
assert report["changes"]
"""
    subprocess.run([sys.executable, "-c", code], check=True)


def test_ambiguous_assessment_has_no_registration_order_tiebreak(tmp_path: Path) -> None:
    class Competing(FictionalAdapter):
        revision = "TEST-COMPETING"

    _, second = paired_sources(tmp_path)
    for adapters in ((FictionalAdapter(), Competing()), (Competing(), FictionalAdapter())):
        assessment = AdapterRegistry(adapters).assess(load_xml(second))
        assert assessment.status is RevisionStatus.AMBIGUOUS
        assert assessment.supported_revisions == ("TEST-COMPETING", "TEST-FICTIONAL-V2")


def test_foreign_no_namespace_hint_cannot_enable_explicit_current_mapping(tmp_path: Path) -> None:
    path = tmp_path / "wrong-hint.xml"
    path.write_text(
        f'<DataDictionary xmlns="{NS}" xmlns:xsi="{XSI}" '
        'xsi:noNamespaceSchemaLocation="E172-9999-SEDD-Schema.xsd"/>',
        encoding="utf-8",
    )
    with pytest.raises(UnsupportedSeddVersionError):
        load_interface(path, revision="E172-0225")
