"""Canonical model behavior without parsing XML or assuming matching policy."""

import importlib
import json
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError, is_dataclass, replace
from typing import cast

import pytest

from sema_sedd.exceptions import ModelValidationError
from sema_sedd.model import (
    MODEL_SCHEMA_VERSION,
    Alarm,
    CanonicalEquipmentInterface,
    CanonicalType,
    CollectionEvent,
    DataStructure,
    DataVariable,
    DefaultReport,
    EntityReference,
    EquipmentConstant,
    EquipmentInterface,
    EquipmentMetadata,
    EventReportLink,
    JsonArray,
    JsonObject,
    MessageDirection,
    RemoteCommand,
    RemoteCommandParameter,
    Requiredness,
    SourceProvenance,
    StandardReference,
    StateTransition,
    StatusVariable,
    SupportedMessage,
    UnknownExtension,
    UnresolvedReason,
    UnresolvedReference,
    VariableFormat,
    WellKnownName,
    WknAuthority,
    to_canonical_dict,
    to_canonical_json,
)
from sema_sedd.parser import SourceLocation, XmlElement

PROVENANCE = SourceProvenance(
    source_document="synthetic.json",
    source_revision="future-1",
    source_path="/variables/0",
    path_kind="json_pointer",
    source_identifier="007",
    line=4,
    column=3,
)


def reference(kind: CanonicalType, key: str, native_id: str | None = None) -> EntityReference:
    return EntityReference(target_types=(kind,), target_key=key, implementation_id=native_id)


def complete_interface() -> EquipmentInterface:
    """Original, source-independent example covering all domain concepts."""
    wkn = WellKnownName(value="fictional.temperature", authority="synthetic registry", scope="lab")
    standard = StandardReference(key="standard", designation="Fictional-17", revision="1")
    shape = DataStructure(
        kind="list",
        children=(
            DataStructure(
                kind="unsigned_integer",
                name="count",
                value="0001",
                attributes=JsonObject(entries=(("length", "1..N"),)),
            ),
            DataStructure(kind="text", name="label"),
        ),
    )
    variable_format = VariableFormat(key="format", name="CountAndLabel", structure=(shape,))
    sv = StatusVariable(
        key="sv",
        implementation_id="7",
        name="Temperature",
        description="CafÃ© Î²",
        wkn=wkn,
        provenance=(PROVENANCE,),
        format=reference(CanonicalType.VARIABLE_FORMAT, "format"),
        standards=(reference(CanonicalType.STANDARD_REFERENCE, "standard"),),
        units=("K",),
        minimum="-1.0",
        maximum="MAX",
        declared_source="Fixture author",
    )
    dv = DataVariable(key="dv", implementation_id="8", name="Count")
    ec = EquipmentConstant(key="ec", implementation_id="9", default="0010", units=("count",))
    event = CollectionEvent(
        key="event",
        implementation_id="11",
        name="CycleStart",
        valid_data_variables=(reference(CanonicalType.DATA_VARIABLE, "dv", "8"),),
        relevant_variables=(reference(CanonicalType.STATUS_VARIABLE, "sv", "7"),),
        state_transition=StateTransition(
            state_model="cycle", transition_id="start", previous_state="idle", new_state="active"
        ),
    )
    alarm = Alarm(
        key="alarm",
        implementation_id="19",
        code=1,
        text="Synthetic warning",
        set_event=reference(CanonicalType.COLLECTION_EVENT, "event", "11"),
        clear_event=EntityReference(
            implementation_id="999", target_types=(CanonicalType.COLLECTION_EVENT,)
        ),
    )
    parameter = RemoteCommandParameter(
        key="command/mode",
        name="MODE",
        requiredness=Requiredness.CONDITIONAL,
        value_format=(shape,),
    )
    command = RemoteCommand(
        key="command", name="PREPARE", parameters=(parameter,), use_s2f41=True, use_s2f21=False
    )
    message = SupportedMessage(
        key="message",
        stream=1,
        function=1,
        direction=MessageDirection.HOST_TO_EQUIPMENT,
        structure=(shape,),
    )
    report = DefaultReport(
        key="report",
        implementation_id="21",
        variables=(
            reference(CanonicalType.DATA_VARIABLE, "dv", "8"),
            reference(CanonicalType.STATUS_VARIABLE, "sv", "7"),
        ),
    )
    link = EventReportLink(
        key="link",
        event=reference(CanonicalType.COLLECTION_EVENT, "event"),
        reports=(reference(CanonicalType.DEFAULT_REPORT, "report"),),
    )
    assert alarm.clear_event is not None
    unresolved = UnresolvedReference(
        owner_key="alarm",
        relationship="clear_event",
        reference=alarm.clear_event,
        reason=UnresolvedReason.NOT_FOUND,
    )
    extension = UnknownExtension(
        name="Calibration",
        namespace="urn:fictional",
        content=(
            "before",
            UnknownExtension(name="Hint", content=("opaque",)),
            "after",
        ),
        provenance=(PROVENANCE,),
    )
    return EquipmentInterface(
        equipment=EquipmentMetadata(
            model="Lantern",
            implementation_id="",
            software_revision="1.2",
            supplier="Synthetic",
            created_date="2026-09-19",
        ),
        provenance=(PROVENANCE,),
        status_variables=(sv,),
        data_variables=(dv,),
        equipment_constants=(ec,),
        collection_events=(event,),
        alarms=(alarm,),
        remote_commands=(command,),
        supported_messages=(message,),
        variable_formats=(variable_format,),
        default_reports=(report,),
        event_report_links=(link,),
        standard_references=(standard,),
        unresolved_references=(unresolved,),
        unknown_extensions=(extension,),
        reports_can_be_deleted=False,
        event_report_links_can_be_deleted=True,
    )


def test_all_requested_types_and_relationships_survive_serialization() -> None:
    model = complete_interface()
    result = json.loads(to_canonical_json(model))
    assert result["model_schema_version"] == MODEL_SCHEMA_VERSION
    data = result["interface"]
    assert CanonicalEquipmentInterface is EquipmentInterface
    assert len(model.entities()) == 12
    assert len({entity.canonical_type for entity in model.entities()}) == 12
    assert data["status_variables"][0]["format"]["target_key"] == "format"
    assert data["status_variables"][0]["standards"][0]["target_key"] == "standard"
    assert data["status_variables"][0]["provenance"][0]["source_identifier"] == "007"
    assert data["collection_events"][0]["valid_data_variables"][0]["target_key"] == "dv"
    assert data["collection_events"][0]["relevant_variables"][0]["target_key"] == "sv"
    assert data["collection_events"][0]["state_transition"]["new_state"] == "active"
    assert data["alarms"][0]["set_event"]["target_key"] == "event"
    assert data["alarms"][0]["clear_event"]["target_key"] is None
    assert data["event_report_links"][0]["reports"][0]["target_key"] == "report"
    assert data["remote_commands"][0]["parameters"][0]["requiredness"] == "conditional"
    assert data["supported_messages"][0]["structure"][0]["children"][0]["value"] == "0001"
    assert data["equipment_constants"][0]["default"] == "0010"
    assert data["unresolved_references"][0]["reason"] == "not_found"
    for entity in model.entities():
        for field in (
            "canonical_type",
            "implementation_id",
            "name",
            "description",
            "wkn",
            "provenance",
            "unknown_extensions",
            "extension_metadata",
        ):
            assert hasattr(entity, field)


def test_identifier_changes_do_not_rewrite_wkn_or_establish_matches() -> None:
    before = StatusVariable(
        key="before/a", implementation_id="17", wkn=WellKnownName(value="fictional.temperature")
    )
    after = replace(before, key="after/b", implementation_id="99")
    assert before.wkn == after.wkn
    assert before != after
    assert before.implementation_id == "17"
    assert to_canonical_json(EquipmentInterface(status_variables=(before,))) != to_canonical_json(
        EquipmentInterface(status_variables=(after,))
    )


@pytest.mark.parametrize(
    "native_id", [None, "", "0", "0007", "7", "future:alpha", "18446744073709551616"]
)
def test_native_identifiers_are_optional_and_not_numeric_coercions(native_id: str | None) -> None:
    variable = StatusVariable(key="sv", implementation_id=native_id)
    data = json.loads(to_canonical_json(EquipmentInterface(status_variables=(variable,))))
    assert data["interface"]["status_variables"][0]["implementation_id"] == native_id


def test_duplicate_native_ids_and_wkns_are_preserved_with_explicit_ambiguity() -> None:
    wkn = WellKnownName(value="fictional.same")
    a = StatusVariable(key="sv/a", implementation_id="7", wkn=wkn)
    b = StatusVariable(key="sv/b", implementation_id="7", wkn=wkn)
    dv = DataVariable(key="dv/a", implementation_id="7", wkn=wkn)
    ref = EntityReference(implementation_id="7", target_types=(CanonicalType.STATUS_VARIABLE,))
    report = DefaultReport(key="report", variables=(ref, ref))
    unresolved = UnresolvedReference(
        owner_key="report",
        relationship="variables[0]",
        reference=ref,
        reason=UnresolvedReason.AMBIGUOUS,
        candidate_keys=("sv/a", "sv/b"),
    )
    model = EquipmentInterface(
        status_variables=(a, b),
        data_variables=(dv,),
        default_reports=(report,),
        unresolved_references=(unresolved,),
    )
    assert len(model.status_variables) == 2
    assert model.unresolved_references[0].reference.target_key is None
    data = json.loads(to_canonical_json(model))["interface"]
    assert len(data["status_variables"]) == 2
    assert len(data["default_reports"][0]["variables"]) == 2


def test_duplicate_internal_keys_are_rejected_including_parameters() -> None:
    with pytest.raises(ModelValidationError, match="Duplicate document-local"):
        EquipmentInterface(
            status_variables=(StatusVariable(key="same"),),
            data_variables=(DataVariable(key="same"),),
        )
    parameter = RemoteCommandParameter(key="parameter", name="MODE")
    with pytest.raises(ModelValidationError, match="Duplicate document-local"):
        EquipmentInterface(
            remote_commands=(
                RemoteCommand(key="a", parameters=(parameter,)),
                RemoteCommand(key="b", parameters=(parameter,)),
            )
        )


def test_command_parameter_names_are_scoped_and_not_globally_deduplicated() -> None:
    commands = tuple(
        RemoteCommand(
            key=name, parameters=(RemoteCommandParameter(key=f"{name}/mode", name="MODE"),)
        )
        for name in ("a", "b")
    )
    model = EquipmentInterface(remote_commands=commands)
    assert len(model.entities()) == 4


def test_repeated_stream_function_direction_does_not_collapse_messages() -> None:
    a = SupportedMessage(key="a", stream=1, function=1, direction=MessageDirection.BOTH)
    b = replace(a, key="b")
    data = json.loads(to_canonical_json(EquipmentInterface(supported_messages=(a, b))))
    assert len(data["interface"]["supported_messages"]) == 2


def test_wkn_authority_defaults_to_unverified_and_is_separate_from_value() -> None:
    unverified = WellKnownName(value="same", authority="registry", scope="scope")
    verified = replace(unverified, authority_status=WknAuthority.VERIFIED, provenance=(PROVENANCE,))
    other_scope = replace(verified, scope="different")
    assert unverified.authority_status is WknAuthority.UNVERIFIED
    assert unverified != verified != other_scope


@pytest.mark.parametrize("missing", ["authority", "scope", "provenance"])
def test_verified_wkn_requires_recorded_evidence(missing: str) -> None:
    kwargs: dict[str, object] = dict(
        value="name",
        authority="registry",
        scope="scope",
        authority_status=WknAuthority.VERIFIED,
        provenance=(PROVENANCE,),
    )
    kwargs.pop(missing)
    with pytest.raises(ModelValidationError, match="Verified WKN"):
        WellKnownName(**kwargs)  # type: ignore[arg-type]


def test_missing_empty_and_false_have_distinct_json_representations() -> None:
    model = EquipmentInterface(
        equipment=EquipmentMetadata(implementation_id="", description=""),
        collection_events=(
            CollectionEvent(key="event", valid_data_variables=None, relevant_variables=()),
        ),
        remote_commands=(RemoteCommand(key="command", parameters=(), use_s2f21=False),),
        supported_messages=(SupportedMessage(key="message", structure=None),),
    )
    data = json.loads(to_canonical_json(model))["interface"]
    assert data["equipment"]["implementation_id"] == ""
    assert data["equipment"]["description"] == ""
    assert data["equipment"]["name"] is None
    assert data["collection_events"][0]["valid_data_variables"] is None
    assert data["collection_events"][0]["relevant_variables"] == []
    assert data["remote_commands"][0]["use_s2f21"] is False
    assert data["remote_commands"][0]["use_s2f41"] is None
    assert data["supported_messages"][0]["structure"] is None


def test_future_revision_and_unknown_extensions_are_retained_without_interpretation() -> None:
    extension = UnknownExtension(
        name="Future",
        namespace="urn:future:vendor",
        reason="unknown revision",
        attributes=JsonObject(entries=(("{urn:future}flag", "new"),)),
        content=(" left ", UnknownExtension(name="Child", content=("Î²",)), " right "),
        metadata=JsonObject(entries=(("payload", JsonArray(items=(None, False, 3))),)),
    )
    model = EquipmentInterface(
        provenance=(replace(PROVENANCE, source_revision="E172-future"),),
        unknown_extensions=(extension,),
        variable_formats=(
            VariableFormat(key="future", structure=(DataStructure(kind="future_vendor_encoding"),)),
        ),
    )
    data = json.loads(to_canonical_json(model))["interface"]
    preserved = data["unknown_extensions"][0]
    assert preserved["namespace"] == "urn:future:vendor"
    assert preserved["content"][0] == " left "
    assert preserved["content"][1]["content"] == ["Î²"]
    assert preserved["content"][2] == " right "
    assert preserved["metadata"]["payload"] == [None, False, 3]
    assert data["provenance"][0]["source_revision"] == "E172-future"
    assert data["variable_formats"][0]["structure"][0]["kind"] == "future_vendor_encoding"


def test_inventory_and_metadata_map_permutations_produce_identical_json() -> None:
    a, b = StatusVariable(key="a"), StatusVariable(key="b")
    model = EquipmentInterface(
        status_variables=(b, a), extension_metadata=JsonObject(entries=(("z", 1), ("a", 2)))
    )
    reordered = replace(
        model, status_variables=(a, b), extension_metadata=JsonObject(entries=(("a", 2), ("z", 1)))
    )
    assert to_canonical_json(model) == to_canonical_json(reordered)
    assert model.status_variables == (b, a)  # Serialization never mutates the input.


@pytest.mark.parametrize("sequence", ["report", "parameters", "message", "links"])
def test_semantic_sequence_permutations_remain_visible(sequence: str) -> None:
    model = complete_interface()
    if sequence == "report":
        report = model.default_reports[0]
        assert report.variables is not None
        changed = replace(
            model, default_reports=(replace(report, variables=report.variables[::-1]),)
        )
    elif sequence == "parameters":
        command = model.remote_commands[0]
        params = (RemoteCommandParameter(key="p/1"), RemoteCommandParameter(key="p/2"))
        model = replace(model, remote_commands=(replace(command, parameters=params),))
        changed = replace(model, remote_commands=(replace(command, parameters=params[::-1]),))
    elif sequence == "links":
        link = model.event_report_links[0]
        second_report = DefaultReport(key="report/2")
        reports = (
            reference(CanonicalType.DEFAULT_REPORT, "report"),
            reference(CanonicalType.DEFAULT_REPORT, "report/2"),
        )
        model = replace(
            model,
            default_reports=(*model.default_reports, second_report),
            event_report_links=(replace(link, reports=reports),),
        )
        changed = replace(model, event_report_links=(replace(link, reports=reports[::-1]),))
    else:
        message = model.supported_messages[0]
        assert message.structure is not None
        structure = message.structure[0]
        changed = replace(
            model,
            supported_messages=(
                replace(
                    message, structure=(replace(structure, children=structure.children[::-1]),)
                ),
            ),
        )
    assert to_canonical_json(model) != to_canonical_json(changed)


def test_unknown_extension_sequence_and_significant_text_are_not_normalized() -> None:
    a = UnknownExtension(name="a", content=(" x ",))
    b = UnknownExtension(name="b", content=("x",))
    model = EquipmentInterface(unknown_extensions=(a, b))
    assert to_canonical_json(model) != to_canonical_json(replace(model, unknown_extensions=(b, a)))
    assert to_canonical_json(model) != to_canonical_json(
        replace(model, unknown_extensions=(replace(a, content=("x",)), b))
    )


def test_utf8_json_preserves_unicode_and_escapes_controls() -> None:
    text = 'CafÃ© Î² "quoted"\n<script>literal</script>'
    output = to_canonical_json(EquipmentInterface(description=text))
    assert "CafÃ© Î²" in output
    assert "\n" not in output
    assert json.loads(output.encode("utf-8"))["interface"]["description"] == text


def test_snapshot_is_detached_from_frozen_model() -> None:
    model = complete_interface()
    snapshot = to_canonical_dict(model)
    snapshot["interface"] = None
    assert json.loads(to_canonical_json(model))["interface"] is not None
    with pytest.raises(FrozenInstanceError):
        model.name = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        model.status_variables[0].implementation_id = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "bad", [float("nan"), float("inf"), float("-inf"), {"a": 1}, [1], object()]
)
def test_extension_metadata_rejects_non_json_or_mutable_values(bad: object) -> None:
    with pytest.raises(ModelValidationError):
        JsonObject(entries=(("bad", bad),))  # type: ignore[arg-type]


def test_duplicate_metadata_members_are_rejected_instead_of_overwritten() -> None:
    with pytest.raises(ModelValidationError, match="Duplicate JSON"):
        JsonObject(entries=(("key", 1), ("key", 2)))


@pytest.mark.parametrize("field,bad", [("line", 0), ("column", -1), ("line", True)])
def test_source_positions_have_positive_integer_types(field: str, bad: object) -> None:
    with pytest.raises(ModelValidationError):
        replace(PROVENANCE, **{field: bad})  # type: ignore[arg-type]


def test_types_reject_coercion_and_wrong_entity_collections() -> None:
    with pytest.raises(ModelValidationError):
        SupportedMessage(key="a", stream=True)
    with pytest.raises(ModelValidationError):
        StatusVariable(key="a", implementation_id=cast(str, 7))
    with pytest.raises(ModelValidationError):
        EquipmentInterface(status_variables=(cast(StatusVariable, DataVariable(key="a")),))
    with pytest.raises(ModelValidationError):
        EquipmentInterface(status_variables=cast(tuple[StatusVariable, ...], []))
    with pytest.raises(ModelValidationError):
        RemoteCommandParameter(key="p", requiredness=cast(Requiredness, "conditional"))


def test_xml_layer_objects_are_rejected_at_domain_api_boundaries() -> None:
    xml = XmlElement(tag="x", attributes=(), content=(), location=SourceLocation(1, 1))
    with pytest.raises(ModelValidationError):
        StatusVariable(key="a", provenance=(cast(SourceProvenance, xml),))
    with pytest.raises(ModelValidationError):
        VariableFormat(key="a", structure=(cast(DataStructure, xml),))
    with pytest.raises(ModelValidationError):
        UnknownExtension(name="x", content=(cast(UnknownExtension, xml),))
    with pytest.raises(ModelValidationError):
        to_canonical_json(cast(EquipmentInterface, xml))


@pytest.mark.parametrize("key", ["", " "])
def test_internal_keys_must_be_nonempty(key: str) -> None:
    with pytest.raises(ModelValidationError):
        StatusVariable(key=key)


@pytest.mark.parametrize("target", ["missing", "wrong-type"])
def test_resolved_references_validate_local_membership_and_type(target: str) -> None:
    event = CollectionEvent(key="event")
    alarm = Alarm(key="alarm", set_event=EntityReference(target_key=target))
    with pytest.raises(ModelValidationError):
        EquipmentInterface(
            collection_events=(event,),
            alarms=(alarm,),
            status_variables=(StatusVariable(key="wrong-type"),),
        )


def test_explicit_reference_type_cannot_conflict_with_relationship_role() -> None:
    with pytest.raises(ModelValidationError, match="relationship role"):
        Alarm(key="alarm", set_event=EntityReference(target_types=(CanonicalType.REMOTE_COMMAND,)))
    with pytest.raises(ModelValidationError, match="relationship role"):
        StatusVariable(key="a", format=EntityReference(target_types=(CanonicalType.ALARM,)))


def test_dangling_selectors_are_preserved_and_never_automatically_repaired() -> None:
    ref = EntityReference(implementation_id="999", target_types=(CanonicalType.COLLECTION_EVENT,))
    alarm = Alarm(key="alarm", clear_event=ref)
    model = EquipmentInterface(
        alarms=(alarm,), collection_events=(CollectionEvent(key="nearby", implementation_id="998"),)
    )
    assert model.alarms[0].clear_event == ref
    assert ref.target_key is None
    assert model.unresolved_references == ()  # No resolver has run.


@pytest.mark.parametrize(
    "kind", ["resolved", "one_candidate", "duplicate_candidate", "candidates_without_ambiguity"]
)
def test_unresolved_state_cannot_silently_become_resolved(kind: str) -> None:
    with pytest.raises(ModelValidationError):
        UnresolvedReference(
            owner_key="owner",
            relationship="variables",
            reference=EntityReference(target_key="target" if kind == "resolved" else None),
            reason=UnresolvedReason.AMBIGUOUS
            if kind != "candidates_without_ambiguity"
            else UnresolvedReason.NOT_FOUND,
            candidate_keys={
                "resolved": (),
                "one_candidate": ("a",),
                "duplicate_candidate": ("a", "a"),
                "candidates_without_ambiguity": ("a", "b"),
            }[kind],
        )


def test_unresolved_owner_and_candidate_membership_are_checked() -> None:
    a, b = StatusVariable(key="a"), StatusVariable(key="b")
    unresolved = UnresolvedReference(
        owner_key="missing", relationship="variables", reference=EntityReference()
    )
    with pytest.raises(ModelValidationError, match="owner"):
        EquipmentInterface(status_variables=(a, b), unresolved_references=(unresolved,))
    ambiguous = replace(
        unresolved,
        owner_key="a",
        reason=UnresolvedReason.AMBIGUOUS,
        candidate_keys=("b", "missing"),
    )
    with pytest.raises(ModelValidationError, match="candidate"):
        EquipmentInterface(status_variables=(a, b), unresolved_references=(ambiguous,))


def test_parameter_reference_scope_is_checked() -> None:
    a = RemoteCommand(key="a", parameters=(RemoteCommandParameter(key="a/p"),))
    b = RemoteCommand(key="b", parameters=(RemoteCommandParameter(key="b/p"),))
    ref = EntityReference(target_types=(CanonicalType.REMOTE_COMMAND_PARAMETER,), scope_key="a")
    unresolved = UnresolvedReference(
        owner_key="a",
        relationship="parameters",
        reference=ref,
        reason=UnresolvedReason.AMBIGUOUS,
        candidate_keys=("a/p", "b/p"),
    )
    with pytest.raises(ModelValidationError, match="scope"):
        EquipmentInterface(remote_commands=(a, b), unresolved_references=(unresolved,))


def test_serialization_is_deterministic_across_process_hash_seeds() -> None:
    code = (
        "from sema_sedd.model import EquipmentInterface, StatusVariable, to_canonical_json; "
        "print(to_canonical_json(EquipmentInterface(status_variables="
        "tuple(StatusVariable(key=k) for k in {'alpha', 'beta', 'gamma'}))))"
    )
    outputs = [
        subprocess.check_output(
            [sys.executable, "-c", code], env={**os.environ, "PYTHONHASHSEED": seed}
        )
        for seed in ("1", "22")
    ]
    assert outputs[0] == outputs[1]


def test_model_import_and_use_without_xml_or_parser_modules() -> None:
    code = """
import sys
from importlib.abc import MetaPathFinder
class BlockXml(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if (fullname.split('.')[0] in ('xml', 'lxml', 'defusedxml')
                or fullname.startswith('sema_sedd.parser')):
            raise AssertionError('XML dependency leaked: ' + fullname)
sys.meta_path.insert(0, BlockXml())
from sema_sedd.model import EquipmentInterface, to_canonical_json
assert to_canonical_json(EquipmentInterface())
"""
    subprocess.run([sys.executable, "-c", code], check=True)


def test_public_model_types_expose_no_xml_api_annotations() -> None:
    module = importlib.import_module("sema_sedd.model")
    from typing import get_type_hints

    for name in module.__all__:
        obj = getattr(module, name)
        if isinstance(obj, type) and is_dataclass(obj):
            hints = str(get_type_hints(obj))
            assert "sema_sedd.parser" not in hints
            assert "xml.etree" not in hints


def test_reference_type_and_candidate_sets_have_canonical_order() -> None:
    a, b = StatusVariable(key="a"), DataVariable(key="b")
    kinds = (CanonicalType.DATA_VARIABLE, CanonicalType.STATUS_VARIABLE)
    unresolved = UnresolvedReference(
        owner_key="a",
        relationship="test_selector",
        reference=EntityReference(target_types=kinds),
        reason=UnresolvedReason.AMBIGUOUS,
        candidate_keys=("a", "b"),
    )
    model = EquipmentInterface(
        status_variables=(a,), data_variables=(b,), unresolved_references=(unresolved,)
    )
    changed = replace(
        model,
        unresolved_references=(
            replace(
                unresolved,
                reference=replace(unresolved.reference, target_types=kinds[::-1]),
                candidate_keys=("b", "a"),
            ),
        ),
    )
    assert to_canonical_json(model) == to_canonical_json(changed)


def test_source_provenance_changes_are_visible_in_json_not_semantic_identity() -> None:
    model = EquipmentInterface(provenance=(PROVENANCE,))
    changed = replace(model, provenance=(replace(PROVENANCE, line=99),))
    assert to_canonical_json(model) != to_canonical_json(changed)


def test_message_metadata_preserves_blocking_labels_and_text() -> None:
    message = SupportedMessage(
        key="m",
        blocking="M",
        header="opaque header",
        exceptions=("Vendor exception",),
        reply_option="optional",
    )
    data = json.loads(to_canonical_json(EquipmentInterface(supported_messages=(message,))))
    assert data["interface"]["supported_messages"][0]["blocking"] == "M"
    assert data["interface"]["supported_messages"][0]["header"] == "opaque header"
    assert data["interface"]["supported_messages"][0]["exceptions"] == ["Vendor exception"]


def test_json_rejects_unpaired_unicode_surrogates() -> None:
    with pytest.raises(ModelValidationError):
        EquipmentInterface(description="\ud800")


def test_finite_json_metadata_numbers_preserve_types() -> None:
    model = EquipmentInterface(
        extension_metadata=JsonObject(
            entries=(
                ("real", 1.25),
                ("integer", 2**80),
                ("boolean", True),
                ("null", None),
            )
        )
    )
    metadata = json.loads(to_canonical_json(model))["interface"]["extension_metadata"]
    assert type(metadata["integer"]) is int
    assert metadata["integer"] == 2**80
    assert metadata["real"] == 1.25
    assert metadata["boolean"] is True
    assert metadata["null"] is None
