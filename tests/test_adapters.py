"""Adapter routing, evidence-backed mapping, and downstream independence."""

import ast
import json
import socket
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import ClassVar

import pytest

from sema_sedd.adapters import (
    AdapterDiagnostic,
    AdapterRegistry,
    AdapterResult,
    SeddAdapter,
    SupportLevel,
    default_registry,
    detect_revision,
    load_interface,
)
from sema_sedd.adapters.e172_0225 import E172_0225Adapter
from sema_sedd.exceptions import (
    AdapterRegistrationError,
    AmbiguousSeddVersionError,
    InputTooLargeError,
    InvalidXmlError,
    UnsafeXmlError,
    UnsupportedSeddVersionError,
)
from sema_sedd.model import (
    EquipmentInterface,
    EquipmentMetadata,
    JsonArray,
    JsonObject,
    MessageDirection,
    Requiredness,
    SourceProvenance,
    UnresolvedReason,
    WknAuthority,
    to_canonical_json,
)
from sema_sedd.parser import SourcedDocument, load_sedd

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = '<s:DataDictionary xmlns:s="urn:semi-org:xsd.SEDD" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
HINT = ' xsi:schemaLocation="urn:semi-org:xsd.SEDD E172-0225-SEDD-Schema.xsd"'


def document(tmp_path: Path, body: str = "", *, hint: str = HINT) -> SourcedDocument:
    path = tmp_path / "input.xml"
    path.write_text(f"{ROOT}{hint}>{body}</s:DataDictionary>", encoding="utf-8")
    return load_sedd(path)


@dataclass(frozen=True)
class FakeSecondAdapter:
    """A test-only second revision: different fields, same canonical output API."""

    revision: ClassVar[str] = "TEST-SECOND"

    def detect_support(self, document: SourcedDocument) -> SupportLevel:
        return (
            SupportLevel.SUPPORTED
            if document.schema_location == "urn:semi-org:xsd.SEDD test-second.xsd"
            else SupportLevel.UNSUPPORTED
        )

    def parse(self, document: SourcedDocument) -> AdapterResult:
        device = next(child for child in document.root.children if child.tag == "Device")
        equipment = EquipmentMetadata(
            model=device.attribute("label"),
            provenance=(
                SourceProvenance(
                    source_document=str(document.source), source_revision=self.revision
                ),
            ),
        )
        return AdapterResult(
            EquipmentInterface(equipment=equipment),
            self.revision,
            (AdapterDiagnostic("FAKE_SECOND", "Second adapter used"),),
        )


def test_protocol_is_structural_and_default_registry_is_explicit() -> None:
    assert isinstance(E172_0225Adapter(), SeddAdapter)
    assert isinstance(FakeSecondAdapter(), SeddAdapter)
    assert default_registry().revisions == ("E172-0225",)
    assert default_registry() is not default_registry()


def test_two_revisions_use_the_same_pipeline_and_downstream_json(tmp_path: Path) -> None:
    registry = AdapterRegistry((FakeSecondAdapter(), E172_0225Adapter()))
    assert registry.revisions == ("E172-0225", "TEST-SECOND")
    first = document(tmp_path, "<SEDDHeader><MDLN>First</MDLN><SOFTREV>1</SOFTREV></SEDDHeader>")
    first_result = load_interface(first.source, registry=registry)
    second = document(
        tmp_path,
        '<Device label="Second"/>',
        hint=' xsi:schemaLocation="urn:semi-org:xsd.SEDD test-second.xsd"',
    )
    assert detect_revision(second).revision_hint is None
    second_result = load_interface(second.source, registry=registry)
    assert first_result.revision == "E172-0225"
    assert second_result.revision == "TEST-SECOND"
    for result, expected in ((first_result, "First"), (second_result, "Second")):
        assert (
            json.loads(to_canonical_json(result.interface))["interface"]["equipment"]["model"]
            == expected
        )
    assert [d.code for d in second_result.diagnostics] == [
        "UNRECOGNIZED_SCHEMA_HINT",
        "FAKE_SECOND",
    ]
    reversed_registry = AdapterRegistry(registry.adapters[::-1])
    assert reversed_registry.adapt(second) == second_result


def test_missing_hint_needs_explicit_selection_not_filename_or_software(tmp_path: Path) -> None:
    doc = document(tmp_path, "<SEDDHeader><SOFTREV>E172-0225</SOFTREV></SEDDHeader>", hint="")
    assert E172_0225Adapter().detect_support(doc) is SupportLevel.INDETERMINATE
    with pytest.raises(UnsupportedSeddVersionError):
        default_registry().adapt(doc)
    result = default_registry().adapt(doc, revision="E172-0225")
    assert result.interface.equipment.software_revision == "E172-0225"
    assert "EXPLICIT_REVISION_SELECTION" in [d.code for d in result.diagnostics]
    assert result.interface.provenance[0].source_revision == "E172-0225"


@pytest.mark.parametrize(
    "hint",
    [
        ' xsi:schemaLocation="urn:semi-org:xsd.SEDD E172-9999.xsd"',
        ' xsi:schemaLocation="unpaired"',
        ' xsi:schemaLocation="urn:semi-org:xsd.SEDD E172-0225-SEDD-Schema.xsd '
        'urn:semi-org:xsd.SEDD other.xsd"',
    ],
)
def test_unknown_or_ambiguous_hints_cannot_be_overridden_silently(
    tmp_path: Path, hint: str
) -> None:
    doc = document(tmp_path, hint=hint)
    for revision in (None, "E172-0225"):
        with pytest.raises(UnsupportedSeddVersionError):
            default_registry().adapt(doc, revision=revision)
    with pytest.raises(UnsupportedSeddVersionError):
        E172_0225Adapter().parse(doc)


def test_wrong_namespace_and_explicit_unknown_revision_are_rejected(tmp_path: Path) -> None:
    doc = document(tmp_path)
    assert (
        E172_0225Adapter().detect_support(replace(doc, namespace="urn:future"))
        is SupportLevel.UNSUPPORTED
    )
    with pytest.raises(UnsupportedSeddVersionError):
        default_registry().adapt(doc, revision="not-installed")
    with pytest.raises(UnsupportedSeddVersionError):
        AdapterRegistry().adapt(doc)


def test_ambiguous_detection_never_picks_registration_order(tmp_path: Path) -> None:
    @dataclass(frozen=True)
    class CompetingAdapter(FakeSecondAdapter):
        revision: ClassVar[str] = "COMPETING"

        def detect_support(self, document: SourcedDocument) -> SupportLevel:
            return SupportLevel.SUPPORTED

    doc = document(tmp_path)
    for adapters in (
        (E172_0225Adapter(), CompetingAdapter()),
        (CompetingAdapter(), E172_0225Adapter()),
    ):
        registry = AdapterRegistry(adapters)
        with pytest.raises(AmbiguousSeddVersionError):
            registry.select(doc)
        assert registry.select(doc, revision="E172-0225").revision == "E172-0225"


def test_duplicate_adapter_revisions_and_contract_mismatch_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(AdapterRegistrationError, match="Duplicate"):
        AdapterRegistry((E172_0225Adapter(), E172_0225Adapter()))

    class BrokenAdapter:
        revision = "broken"

        def detect_support(self, document: SourcedDocument) -> SupportLevel:
            return SupportLevel.SUPPORTED

        def parse(self, document: SourcedDocument) -> AdapterResult:
            return AdapterResult(EquipmentInterface(), "different")

    with pytest.raises(AdapterRegistrationError, match="different revision"):
        AdapterRegistry((BrokenAdapter(),)).adapt(document(tmp_path))


def test_synthetic_complete_fixture_maps_all_core_concepts() -> None:
    result = load_interface(FIXTURES / "relationships/e172-complete.xml", revision="E172-0225")
    model = result.interface
    assert len(model.entities()) == 13
    assert model.equipment.model == "Lantern17"
    assert model.equipment.software_revision == "0.1"
    assert model.status_variables[0].implementation_id == "702"
    assert model.data_variables[0].implementation_id == "701"
    assert model.equipment_constants[0].default == "20"
    assert model.equipment_constants[0].units == ("count",)
    variable = model.status_variables[0]
    assert variable.wkn is not None and variable.wkn.authority_status is WknAuthority.UNVERIFIED
    assert variable.declared_source == "Synthetic fixture author"
    assert variable.format is not None and variable.format.name == "SyntheticUnsigned"
    assert variable.standards[0].name == "Synthetic-Only"
    event = model.collection_events[0]
    assert (
        event.valid_data_variables is not None
        and event.valid_data_variables[0].implementation_id == "701"
    )
    assert (
        event.valid_data_variables[0].target_types == ()
    )  # Pending target-kind semantics stay pending.
    assert (
        event.relevant_variables is not None
        and event.relevant_variables[0].implementation_id == "702"
    )
    assert event.state_transition is not None and event.state_transition.new_state == "Active"
    alarm = model.alarms[0]
    assert alarm.set_event is not None and alarm.set_event.implementation_id == "801"
    assert alarm.clear_event is not None and alarm.clear_event.implementation_id == "802"
    command = model.remote_commands[0]
    assert (
        command.parameters is not None
        and command.parameters[0].requiredness is Requiredness.CONDITIONAL
    )
    assert command.use_s2f21 is None  # No source-default injection.
    assert model.supported_messages[0].direction is MessageDirection.HOST_TO_EQUIPMENT
    assert model.variable_formats[0].structure is not None
    assert model.variable_formats[0].structure[0].children[0].kind == "ui4"
    assert model.default_reports[0].variables is not None
    assert [r.implementation_id for r in model.default_reports[0].variables] == ["701", "702"]
    assert model.event_report_links[0].reports is not None
    assert model.event_report_links[0].reports[0].implementation_id == "901"
    assert model.standard_references[0].designation == "Synthetic-Only"
    assert model.event_report_links_can_be_deleted is False
    assert len(model.unresolved_references) == 14
    assert all(r.reason is UnresolvedReason.NOT_ATTEMPTED for r in model.unresolved_references)
    assert all(r.reference.target_key is None for r in model.unresolved_references)
    assert model.unknown_extensions[0].name == "RecipeVariableParameters"
    assert variable.provenance[0].line is not None
    assert variable.provenance[0].source_identifier == "702"
    assert variable.key.endswith("/StatusVariable[1]")


def test_every_evidenced_entity_has_document_identity_and_source_path() -> None:
    model = load_interface(
        FIXTURES / "relationships/e172-complete.xml", revision="E172-0225"
    ).interface
    expected_types = {
        "status_variable",
        "data_variable",
        "equipment_constant",
        "collection_event",
        "alarm",
        "remote_command",
        "remote_command_parameter",
        "supported_message",
        "variable_format",
        "default_report",
        "event_report_link",
        "standard_reference",
    }
    assert {entity.canonical_type.value for entity in model.entities()} == expected_types
    assert model.equipment.provenance
    for entity in model.entities():
        assert entity.provenance
        source = entity.provenance[0]
        assert source.source_document.endswith("e172-complete.xml")
        assert source.source_revision == "E172-0225"
        assert source.path_kind == "expanded_name_path"
        assert source.source_path == entity.key
        assert source.line is not None and source.column is not None


def test_parameters_and_compound_formats_keep_order_and_wrappers() -> None:
    parameters = (
        load_interface(
            FIXTURES / "relationships/e172-multiple-parameters.xml", revision="E172-0225"
        )
        .interface.remote_commands[0]
        .parameters
    )
    assert parameters is not None and len(parameters) == 2
    assert parameters[0].key != parameters[1].key
    formats = load_interface(
        FIXTURES / "relationships/e172-compound-formats.xml", revision="E172-0225"
    ).interface.variable_formats
    assert len(formats) == 4
    shape = formats[-1].structure
    assert shape is not None
    alternatives = shape[0].children[0]
    assert alternatives.kind == "set"
    assert [c.kind for c in alternatives.children] == ["format_choice", "format_choice"]
    assert [c.children[0].kind for c in alternatives.children] == ["ui4", "asc"]


def test_duplicate_ids_messages_and_missing_ids_are_not_dropped(tmp_path: Path) -> None:
    doc = document(
        tmp_path,
        """<StatusVariables>
<StatusVariable><SVID>7</SVID><SVNAME>a</SVNAME></StatusVariable>
<StatusVariable><SVID>7</SVID><SVNAME>b</SVNAME></StatusVariable>
<StatusVariable><SVNAME>missing</SVNAME></StatusVariable>
</StatusVariables>""",
    )
    result = default_registry().adapt(doc)
    assert [v.implementation_id for v in result.interface.status_variables] == ["7", "7", None]
    assert len({v.key for v in result.interface.status_variables}) == 3
    assert "MISSING_REQUIRED_STRUCTURE" in [d.code for d in result.diagnostics]
    messages = load_interface(
        FIXTURES / "relationships/e172-ambiguous-message.xml", revision="E172-0225"
    ).interface.supported_messages
    assert len(messages) == 2
    assert messages[0].stream == messages[1].stream
    assert messages[0].key != messages[1].key


def test_namespaces_are_matched_exactly_not_by_local_name(tmp_path: Path) -> None:
    doc = document(
        tmp_path,
        """<StatusVariables xmlns:v="urn:vendor">
<v:StatusVariable><v:SVID>7</v:SVID></v:StatusVariable>
<StatusVariable><v:SVID>8</v:SVID><SVNAME>Known</SVNAME></StatusVariable>
</StatusVariables>""",
    )
    model = default_registry().adapt(doc).interface
    assert len(model.status_variables) == 1
    assert model.status_variables[0].implementation_id is None
    assert model.status_variables[0].unknown_extensions[0].namespace == "urn:vendor"
    assert any(ext.name == "StatusVariable" for ext in model.unknown_extensions)


def test_unknown_content_at_root_entity_field_and_format_is_preserved(tmp_path: Path) -> None:
    doc = document(
        tmp_path,
        """<Vendor xmlns="urn:v" flag="x">before<N/>after</Vendor>
<StatusVariables><StatusVariable vendor="keep"><SVID>007</SVID><SVNAME>β</SVNAME>
<Description hint="keep">Café</Description><Extra>unknown</Extra>
</StatusVariable></StatusVariables>
<VariableFormats><VariableFormat><FormatName>F</FormatName><SECSData>
<SMN:Future xmlns:SMN="urn:semi-org:xsd.SMN" a="b"/>
</SECSData></VariableFormat></VariableFormats>""",
    )
    result = default_registry().adapt(doc)
    var = result.interface.status_variables[0]
    assert var.implementation_id == "007" and var.description == "Café" and var.name == "β"
    assert {x.name for x in var.unknown_extensions} == {"Description", "Extra", "StatusVariable"}
    root_ext = next(ext for ext in result.interface.unknown_extensions if ext.name == "Vendor")
    assert root_ext.content[0] == "before" and root_ext.content[2] == "after"
    shape = result.interface.variable_formats[0].structure
    assert shape is not None and shape[0].children == ()
    assert shape[0].unknown_extensions[0].name == "Future"
    assert "UNKNOWN_ELEMENT" in [d.code for d in result.diagnostics]
    assert "urn:v" in to_canonical_json(result.interface)


def test_duplicate_singletons_do_not_silently_use_first_value(tmp_path: Path) -> None:
    doc = document(
        tmp_path,
        """<StatusVariables><StatusVariable><SVID>1</SVID><SVID>2</SVID>
<SVNAME>a</SVNAME></StatusVariable></StatusVariables>""",
    )
    result = default_registry().adapt(doc)
    variable = result.interface.status_variables[0]
    assert variable.implementation_id is None
    assert [e.content for e in variable.unknown_extensions] == [("1",), ("2",)]
    assert "AMBIGUOUS_FIELD" in [d.code for d in result.diagnostics]


def test_duplicate_sections_nil_and_structured_scalars_remain_unknown(tmp_path: Path) -> None:
    doc = document(
        tmp_path,
        """<StatusVariables/><StatusVariables/>
<DataVariables xsi:nil="true"/>
<SEDDHeader><MDLN>left<Unexpected/>right</MDLN><SOFTREV>1</SOFTREV></SEDDHeader>""",
    )
    result = default_registry().adapt(doc)
    assert result.interface.status_variables == () and result.interface.data_variables == ()
    assert result.interface.equipment.model is None
    extension = result.interface.equipment.unknown_extensions[0]
    assert (
        extension.name == "MDLN"
        and extension.content[0] == "left"
        and extension.content[2] == "right"
    )
    assert {d.code for d in result.diagnostics} >= {
        "AMBIGUOUS_FIELD",
        "NIL_CONTENT",
        "UNSUPPORTED_FIELD_SHAPE",
    }


def test_invalid_typed_values_are_diagnosed_without_echoing_payload(tmp_path: Path) -> None:
    doc = document(
        tmp_path,
        """<Alarms><Alarm><ALID>1</ALID><AlarmName>A</AlarmName><ALCD>secret</ALCD></Alarm></Alarms>
<RemoteCommands><RemoteCommand useS2F21="secret"><Name>C</Name><AssociatedParameters>
<Parameter IsRequired="secret"><Name>P</Name></Parameter>
</AssociatedParameters></RemoteCommand></RemoteCommands>
<SECSMessages><m:SECSMessage xmlns:m="urn:semi-org:xsd.SMN" s="1_0" f="١"
direction="secret" replyBit="secret"/></SECSMessages>""",
    )
    result = default_registry().adapt(doc)
    assert result.interface.alarms[0].code is None
    assert result.interface.remote_commands[0].use_s2f21 is None
    params = result.interface.remote_commands[0].parameters
    assert params is not None and params[0].requiredness is Requiredness.UNKNOWN
    message = result.interface.supported_messages[0]
    assert message.stream is None and message.function is None and message.reply_bit is None
    assert message.direction is MessageDirection.UNKNOWN
    assert all("secret" not in d.message for d in result.diagnostics)
    assert "secret" in to_canonical_json(result.interface)


@pytest.mark.parametrize(("lexical", "expected"), [("-128", -128), ("+127", 127)])
def test_alarm_code_preserves_the_observed_xsd_byte_boundaries(
    tmp_path: Path, lexical: str, expected: int
) -> None:
    doc = document(
        tmp_path,
        f"<Alarms><Alarm><ALCD>{lexical}</ALCD><ALID>007</ALID>"
        "<ALTX>text</ALTX><AlarmName>Alarm</AlarmName>"
        "<Description>description</Description></Alarm></Alarms>",
    )
    alarm = default_registry().adapt(doc).interface.alarms[0]
    assert alarm.code == expected
    assert alarm.implementation_id == "007"


@pytest.mark.parametrize("lexical", ["-129", "128"])
def test_out_of_range_alarm_code_is_retained_as_unknown(tmp_path: Path, lexical: str) -> None:
    doc = document(
        tmp_path,
        f"<Alarms><Alarm><ALCD>{lexical}</ALCD><ALID>1</ALID>"
        "<ALTX>text</ALTX><AlarmName>Alarm</AlarmName>"
        "<Description>description</Description></Alarm></Alarms>",
    )
    result = default_registry().adapt(doc)
    alarm = result.interface.alarms[0]
    assert alarm.code is None
    assert any(extension.name == "ALCD" for extension in alarm.unknown_extensions)
    assert "INVALID_FIELD" in {diagnostic.code for diagnostic in result.diagnostics}


def test_standard_requirement_groups_map_to_structured_metadata(tmp_path: Path) -> None:
    doc = document(
        tmp_path,
        """<SEMIStandards><SupportedSEMIStandard>
<SEMIStandardName>Fictional Interface</SEMIStandardName>
<SEMIStandard>F-1</SEMIStandard>
<RequirementGroup><Name>Core</Name><Requirement>
<Name>Report status</Name><Section>2.1</Section><Section>Annex A</Section>
<RequirementID>REQ-007</RequirementID><ParentRequirementID>REQ-001</ParentRequirementID>
<Implemented>false</Implemented><Compliant>Partial</Compliant>
<Note>First note</Note><Note>Second note</Note><VendorDetail>preserve me</VendorDetail>
</Requirement></RequirementGroup>
<RequirementGroup><Name>Empty group</Name></RequirementGroup>
<Note>Standard note</Note><Note>Another standard note</Note>
</SupportedSEMIStandard></SEMIStandards>""",
    )
    result = default_registry().adapt(doc)
    standard = result.interface.standard_references[0]
    assert standard.name == "Fictional Interface"
    assert standard.designation == "F-1"
    assert standard.notes == ("Standard note", "Another standard note")
    assert len(standard.requirements) == 2

    group = dict(standard.requirements[0].entries)
    assert group["kind"] == "requirement_group"
    assert group["name"] == "Core"
    assert isinstance(group["requirements"], JsonArray)
    requirement_item = group["requirements"].items[0]
    assert isinstance(requirement_item, JsonObject)
    requirement = dict(requirement_item.entries)
    assert requirement["name"] == "Report status"
    assert isinstance(requirement["sections"], JsonArray)
    assert requirement["sections"].items == ("2.1", "Annex A")
    assert requirement["requirement_id"] == "REQ-007"
    assert requirement["parent_requirement_id"] == "REQ-001"
    assert requirement["implemented"] is False
    assert requirement["compliant"] == "Partial"
    assert isinstance(requirement["notes"], JsonArray)
    assert requirement["notes"].items == ("First note", "Second note")
    assert isinstance(requirement["source_path"], str)
    assert requirement["line"] is not None and requirement["column"] is not None

    empty_group = dict(standard.requirements[1].entries)
    assert empty_group["name"] == "Empty group"
    assert isinstance(empty_group["requirements"], JsonArray)
    assert empty_group["requirements"].items == ()
    vendor = next(
        extension for extension in standard.unknown_extensions if extension.name == "VendorDetail"
    )
    assert vendor.content == ("preserve me",)
    assert vendor.provenance[0].source_path is not None
    assert "UNKNOWN_ELEMENT" in {diagnostic.code for diagnostic in result.diagnostics}


def test_invalid_closed_standard_and_message_values_are_retained(tmp_path: Path) -> None:
    doc = document(
        tmp_path,
        """<SEMIStandards><SupportedSEMIStandard>
<SEMIStandardName>Fictional</SEMIStandardName><SEMIStandard>F-1</SEMIStandard>
<RequirementGroup><Requirement><Compliant>FutureValue</Compliant></Requirement></RequirementGroup>
</SupportedSEMIStandard></SEMIStandards>
<SECSMessages><m:SECSMessage xmlns:m="urn:semi-org:xsd.SMN" s="1" f="2"
blocking="FutureBlock" replyOption="future-option"/></SECSMessages>""",
    )
    result = default_registry().adapt(doc)
    standard = result.interface.standard_references[0]
    group = dict(standard.requirements[0].entries)
    assert isinstance(group["requirements"], JsonArray)
    requirement_item = group["requirements"].items[0]
    assert isinstance(requirement_item, JsonObject)
    requirement = dict(requirement_item.entries)
    assert requirement["compliant"] is None
    assert any(extension.name == "Compliant" for extension in standard.unknown_extensions)
    message = result.interface.supported_messages[0]
    assert message.blocking is None and message.reply_option is None
    unknown_attributes = dict(message.unknown_extensions[0].attributes.entries)
    assert unknown_attributes == {"blocking": "FutureBlock", "replyOption": "future-option"}
    assert [diagnostic.code for diagnostic in result.diagnostics].count("INVALID_FIELD") == 3


@pytest.mark.parametrize(
    "fixture", ["e172-dangling-event-variable.xml", "e172-dangling-report-link.xml"]
)
def test_dangling_relationship_fixtures_remain_pending(fixture: str) -> None:
    result = load_interface(FIXTURES / "relationships" / fixture, revision="E172-0225")
    assert result.interface.unresolved_references
    assert all(r.reference.target_key is None for r in result.interface.unresolved_references)
    assert all(
        r.reason is UnresolvedReason.NOT_ATTEMPTED for r in result.interface.unresolved_references
    )


def test_message_blocks_empty_flags_and_whitespace_are_retained(tmp_path: Path) -> None:
    doc = document(
        tmp_path,
        """<SECSMessages><m:SECSMessage xmlns:m="urn:semi-org:xsd.SMN" s="+001" f="2"
blocking="M" replyBit="1" mnenomic="X" txid="8">
<m:Header> opaque </m:Header><m:Exception>Note</m:Exception><m:SECSData/>
<m:SECSData><m:ASC> x </m:ASC></m:SECSData>
</m:SECSMessage></SECSMessages>""",
    )
    message = default_registry().adapt(doc).interface.supported_messages[0]
    assert message.stream == 1 and message.function == 2 and message.reply_bit is True
    assert message.blocking == "M" and message.mnemonic == "X"
    assert message.header == " opaque " and message.exceptions == ("Note",)
    assert message.structure is not None and len(message.structure) == 2
    assert message.structure[0].children == ()
    assert message.structure[1].children[0].value == " x "
    assert message.unknown_extensions[0].attributes.entries == (("txid", "8"),)


def test_determinism_and_adapter_reuse_do_not_leak_state() -> None:
    doc = load_sedd(FIXTURES / "relationships/e172-complete.xml")
    registry = default_registry()
    first = registry.adapt(doc, revision="E172-0225")
    registry.adapt(load_sedd(FIXTURES / "minimal/e172-empty.xml"), revision="E172-0225")
    second = registry.adapt(doc, revision="E172-0225")
    assert first == second
    assert to_canonical_json(first.interface) == to_canonical_json(second.interface)


def test_prefix_spelling_does_not_change_source_keys(tmp_path: Path) -> None:
    doc = document(tmp_path, "<SEDDHeader><MDLN>M</MDLN></SEDDHeader>")
    first = default_registry().adapt(doc).interface
    text = (
        doc.source.read_text(encoding="utf-8")
        .replace("s:DataDictionary", "z:DataDictionary")
        .replace("xmlns:s=", "xmlns:z=")
    )
    doc.source.write_text(text, encoding="utf-8")
    second = default_registry().adapt(load_sedd(doc.source)).interface
    assert first == second


def test_network_is_never_used_for_schema_hints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("Network access attempted")

    monkeypatch.setattr(socket.socket, "connect", fail)
    monkeypatch.setattr(socket, "getaddrinfo", fail)
    doc = document(
        tmp_path,
        hint=' xsi:schemaLocation="urn:semi-org:xsd.SEDD https://example.invalid/E172-0225-SEDD-Schema.xsd"',
    )
    assert load_interface(doc.source).revision == "E172-0225"


@pytest.mark.parametrize(
    "name", ["external-dtd.xml", "external-entity.xml", "entity-expansion.xml"]
)
def test_security_rejection_precedes_adapter_selection(name: str) -> None:
    class MustNotRun:
        revision = "spy"

        def detect_support(self, document: SourcedDocument) -> SupportLevel:
            pytest.fail("Adapter detection ran before secure ingestion")

        def parse(self, document: SourcedDocument) -> AdapterResult:
            pytest.fail("Adapter ran before secure ingestion")

    with pytest.raises(UnsafeXmlError):
        load_interface(FIXTURES / "malformed" / name, registry=AdapterRegistry((MustNotRun(),)))


def test_pipeline_propagates_invalid_xml_and_byte_limits(tmp_path: Path) -> None:
    path = tmp_path / "bad.xml"
    path.write_text("<broken>", encoding="utf-8")
    with pytest.raises(InvalidXmlError):
        load_interface(path)
    with pytest.raises(InputTooLargeError):
        load_interface(path, max_bytes=2)


def test_original_tracksys_mapping_matches_observed_inventory() -> None:
    path = Path("work/references/SEDD_TrackSys_Model404_0225.xml")
    if not path.exists():
        pytest.skip("Original reference is intentionally not versioned")
    result = load_interface(path)
    model = result.interface
    expected = {
        "status_variables": 104,
        "data_variables": 93,
        "equipment_constants": 7,
        "collection_events": 185,
        "alarms": 46,
        "variable_formats": 67,
        "supported_messages": 92,
        "remote_commands": 7,
        "standard_references": 1,
        "default_reports": 1,
        "event_report_links": 1,
    }
    assert {name: len(getattr(model, name)) for name in expected} == expected
    assert model.equipment.model == "Model404" and model.equipment.implementation_id == ""
    assert model.equipment.provenance[0].line == 18
    assert len(model.unresolved_references) == 1955
    assert all(ref.reference.target_key is None for ref in model.unresolved_references)
    assert {extension.name for extension in model.unknown_extensions} >= {
        "RecipeVariableParameters",
        "EquipmentCharacterization",
    }
    standard = model.standard_references[0]
    assert len(standard.requirements) == 2
    group_sizes = []
    for group in standard.requirements:
        requirements = dict(group.entries)["requirements"]
        assert isinstance(requirements, JsonArray)
        group_sizes.append(len(requirements.items))
    assert group_sizes == [8, 17]
    assert standard.unknown_extensions == ()


def test_all_versioned_e172_relationship_and_change_fixtures_map_deterministically() -> None:
    for path in sorted(FIXTURES.glob("*/e172-*.xml")):
        # Namespace-invalid documents deliberately remain unsupported, not silently remapped.
        first = load_interface(path, revision="E172-0225")
        second = load_interface(path, revision="E172-0225")
        assert to_canonical_json(first.interface) == to_canonical_json(second.interface), path.name


def test_downstream_packages_cannot_import_adapter_or_parser_layers() -> None:
    source = Path(__file__).parents[1] / "src" / "sema_sedd"
    for package in ("model", "compare", "graph", "report"):
        for path in (source / package).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    modules = [node.module or "", *(alias.name for alias in node.names)]
                else:
                    continue
                assert not any(
                    "adapters" in name or "E172_0225Adapter" in name or "parser" in name
                    for name in modules
                ), path


def test_custom_registry_and_downstream_work_without_importing_e172_adapter() -> None:
    code = """
import sys
from importlib.abc import MetaPathFinder
class BlockConcrete(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if 'e172_0225' in fullname:
            raise AssertionError('Concrete adapter dependency leaked')
sys.meta_path.insert(0, BlockConcrete())
from sema_sedd.adapters import AdapterRegistry, AdapterResult, SupportLevel, load_interface
from sema_sedd.model import EquipmentInterface, EquipmentMetadata, to_canonical_json
from sema_sedd import compare, graph, report
class TestAdapter:
    revision = 'test'
    def detect_support(self, document):
        return SupportLevel.SUPPORTED
    def parse(self, document):
        model = EquipmentInterface(equipment=EquipmentMetadata(model='test'))
        return AdapterResult(model, self.revision)
result = load_interface(sys.argv[1], registry=AdapterRegistry((TestAdapter(),)))
assert '"model":"test"' in to_canonical_json(result.interface)
"""
    subprocess.run(
        [sys.executable, "-c", code, str(FIXTURES / "minimal/e172-empty.xml")], check=True
    )


def test_malformed_schema_uri_produces_a_controlled_diagnostic(tmp_path: Path) -> None:
    doc = document(
        tmp_path, hint=' xsi:schemaLocation="urn:semi-org:xsd.SEDD http://[bad/schema.xsd"'
    )
    assert detect_revision(doc).revision_hint is None
    assert detect_revision(doc).diagnostic_code == "MALFORMED_SCHEMA_HINT"
    with pytest.raises(UnsupportedSeddVersionError):
        default_registry().adapt(doc)


def test_invalid_adapter_decision_is_a_contract_error(tmp_path: Path) -> None:
    class Broken:
        revision = "broken"

        def detect_support(self, document: SourcedDocument) -> SupportLevel:
            return "supported"  # type: ignore[return-value]

        def parse(self, document: SourcedDocument) -> AdapterResult:
            pytest.fail("Invalid decision should prevent parsing")

    for revision in (None, "broken"):
        with pytest.raises(AdapterRegistrationError, match="support decision"):
            AdapterRegistry((Broken(),)).adapt(document(tmp_path), revision=revision)


def test_adapter_result_cannot_leak_an_xml_document(tmp_path: Path) -> None:
    class Broken:
        revision = "broken"

        def detect_support(self, document: SourcedDocument) -> SupportLevel:
            return SupportLevel.SUPPORTED

        def parse(self, document: SourcedDocument) -> AdapterResult:
            return AdapterResult(document, self.revision)  # type: ignore[arg-type]

    with pytest.raises(AdapterRegistrationError, match="canonical result"):
        AdapterRegistry((Broken(),)).adapt(document(tmp_path))


def test_non_xml_whitespace_in_mixed_content_is_not_discarded(tmp_path: Path) -> None:
    doc = document(tmp_path, "<Vendor>\u00a0<Child/>\u00a0</Vendor>")
    ext = default_registry().adapt(doc).interface.unknown_extensions[0]
    assert ext.content[0] == "\u00a0" and ext.content[2] == "\u00a0"
    doc = document(tmp_path, "<SEDDHeader>\u00a0<MDLN>Model</MDLN></SEDDHeader>")
    ext = default_registry().adapt(doc).interface.equipment.unknown_extensions[0]
    assert ext.content[0] == "\u00a0"


def test_nil_with_xml_whitespace_is_retained_without_mapping(tmp_path: Path) -> None:
    doc = document(
        tmp_path, '<StatusVariables xsi:nil=" true "><StatusVariable/></StatusVariables>'
    )
    model = default_registry().adapt(doc).interface
    assert model.status_variables == ()
    assert any(ext.name == "StatusVariables" for ext in model.unknown_extensions)
    doc = document(
        tmp_path, "<SEDDHeader><MDLN>ignored</MDLN></SEDDHeader>", hint=HINT + ' xsi:nil=" true "'
    )
    model = default_registry().adapt(doc).interface
    assert model.equipment.model is None
    assert model.unknown_extensions[0].reason == "nil_document"
