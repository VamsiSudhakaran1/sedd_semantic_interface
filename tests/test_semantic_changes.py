"""Semantic changes, provenance-independent comparisons, and adversarial noise."""

import json
import random
import xml.etree.ElementTree as ET
from dataclasses import replace
from itertools import permutations
from pathlib import Path

import pytest

from sema_sedd.adapters import load_interface
from sema_sedd.compare import (
    ChangeCategory,
    ChangeKind,
    ChangeSet,
    IssueKind,
    compare_interfaces,
    to_change_set_dict,
    to_change_set_json,
)
from sema_sedd.model import (
    Alarm,
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
    VariableFormat,
    WellKnownName,
    WknAuthority,
    to_canonical_json,
)
from sema_sedd.model.domain import InterfaceEntity

FIXTURES = Path(__file__).parent / "fixtures"


def catalogue(*entities: InterfaceEntity) -> EquipmentInterface:
    return EquipmentInterface(
        status_variables=tuple(e for e in entities if isinstance(e, StatusVariable)),
        data_variables=tuple(e for e in entities if isinstance(e, DataVariable)),
        equipment_constants=tuple(e for e in entities if isinstance(e, EquipmentConstant)),
        collection_events=tuple(e for e in entities if isinstance(e, CollectionEvent)),
        alarms=tuple(e for e in entities if isinstance(e, Alarm)),
        remote_commands=tuple(e for e in entities if isinstance(e, RemoteCommand)),
        variable_formats=tuple(e for e in entities if isinstance(e, VariableFormat)),
        supported_messages=tuple(e for e in entities if isinstance(e, SupportedMessage)),
        default_reports=tuple(e for e in entities if isinstance(e, DefaultReport)),
        event_report_links=tuple(e for e in entities if isinstance(e, EventReportLink)),
        standard_references=tuple(e for e in entities if isinstance(e, StandardReference)),
    )


def verified(value: str) -> WellKnownName:
    return WellKnownName(
        value=value,
        authority="fictional-registry",
        scope="fixture",
        authority_status=WknAuthority.VERIFIED,
        provenance=(SourceProvenance(source_document="synthetic-registry.json"),),
    )


def kinds(changes: ChangeSet) -> set[ChangeKind]:
    return {kind for entity in changes.entity_changes for kind in entity.kinds}


def ref(kind: CanonicalType, identifier: str) -> EntityReference:
    return EntityReference(target_types=(kind,), implementation_id=identifier)


@pytest.mark.parametrize(
    "entity,field,value,expected",
    [
        (StatusVariable(key="v", implementation_id="1"), "name", "New", ChangeKind.NAME_CHANGED),
        (
            StatusVariable(key="v", implementation_id="1"),
            "data_type",
            "U4",
            ChangeKind.DATA_TYPE_CHANGED,
        ),
        (StatusVariable(key="v", implementation_id="1"), "units", ("C",), ChangeKind.UNIT_CHANGED),
        (
            StatusVariable(key="v", implementation_id="1"),
            "minimum",
            "-20",
            ChangeKind.RANGE_CHANGED,
        ),
        (StatusVariable(key="v", implementation_id="1"), "maximum", "20", ChangeKind.RANGE_CHANGED),
        (
            EquipmentConstant(key="v", implementation_id="1"),
            "default",
            "5",
            ChangeKind.DEFAULT_CHANGED,
        ),
        (
            StatusVariable(key="v", implementation_id="1"),
            "wkn",
            WellKnownName(value="unverified.new"),
            ChangeKind.WELL_KNOWN_NAME_CHANGED,
        ),
        (Alarm(key="a", implementation_id="1"), "code", 4, ChangeKind.ALARM_CHANGED),
        (Alarm(key="a", implementation_id="1"), "text", "On-wire text", ChangeKind.ALARM_CHANGED),
        (RemoteCommand(key="c", name="START"), "use_s2f41", True, ChangeKind.COMMAND_CHANGED),
        (
            SupportedMessage(key="m", stream=1, function=1),
            "direction",
            MessageDirection.BOTH,
            ChangeKind.SUPPORTED_MESSAGE_CHANGED,
        ),
        (
            SupportedMessage(key="m", stream=1, function=1),
            "reply_bit",
            True,
            ChangeKind.SUPPORTED_MESSAGE_CHANGED,
        ),
        (
            StandardReference(key="s", designation="Synthetic"),
            "revision",
            "2",
            ChangeKind.STANDARD_METADATA_CHANGED,
        ),
    ],
)
def test_property_categories(
    entity: InterfaceEntity,
    field: str,
    value: object,
    expected: ChangeKind,
) -> None:
    new = replace(entity, **{field: value})  # type: ignore[arg-type]
    changes = compare_interfaces(catalogue(entity), catalogue(new))
    assert len(changes.entity_changes) == 1
    change = changes.entity_changes[0]
    assert len(change.properties) == 1
    assert change.properties[0].field == field
    assert change.properties[0].kind is expected
    assert change.categories == (ChangeCategory.INTERFACE_CHANGE,)
    assert changes.has_interface_changes and not changes.has_documentation_changes


def test_documentation_is_separate_and_significant_text_is_preserved() -> None:
    old = StatusVariable(key="v", implementation_id="1", description="alpha beta")
    new = replace(old, description="alphabeta")
    changes = compare_interfaces(catalogue(old), catalogue(new))
    assert not changes.has_interface_changes
    assert changes.has_documentation_changes and changes.is_complete
    property_ = changes.entity_changes[0].properties[0]
    assert property_.kind is ChangeKind.DESCRIPTION_CHANGED
    assert property_.old_value == "alpha beta" and property_.new_value == "alphabeta"
    spaced = compare_interfaces(catalogue(old), catalogue(replace(old, description=" alpha beta ")))
    assert spaced.has_documentation_changes  # Leaf strings are not indentation.


def test_mixed_documentation_and_structural_changes_remain_separate() -> None:
    old = StatusVariable(key="v", implementation_id="1", units=("C",), description="Old")
    new = replace(old, units=("K",), description="New")
    changes = compare_interfaces(catalogue(old), catalogue(new))
    assert changes.has_documentation_changes and changes.has_interface_changes
    assert {p.category for p in changes.entity_changes[0].properties} == set(
        (
            ChangeCategory.DOCUMENTATION_CHANGE,
            ChangeCategory.INTERFACE_CHANGE,
        )
    )


def test_id_continuity_suppresses_false_report_and_alarm_link_changes() -> None:
    old_variable = StatusVariable(key="old/v", implementation_id="44", wkn=verified("V"))
    new_variable = replace(old_variable, key="new/v", implementation_id="8044")
    old_event = CollectionEvent(key="old/e", implementation_id="100", wkn=verified("E"))
    new_event = replace(old_event, key="new/e", implementation_id="200")
    report = DefaultReport(
        key="old/r", implementation_id="1", variables=(ref(CanonicalType.STATUS_VARIABLE, "44"),)
    )
    alarm = Alarm(
        key="old/a", implementation_id="1", set_event=ref(CanonicalType.COLLECTION_EVENT, "100")
    )
    old = catalogue(old_variable, old_event, report, alarm)
    new = catalogue(
        new_variable,
        new_event,
        replace(report, key="new/r", variables=(ref(CanonicalType.STATUS_VARIABLE, "8044"),)),
        replace(alarm, key="new/a", set_event=ref(CanonicalType.COLLECTION_EVENT, "200")),
    )
    snapshots = to_canonical_json(old), to_canonical_json(new)
    changes = compare_interfaces(old, new)
    assert kinds(changes) == {ChangeKind.ENTITY_MODIFIED, ChangeKind.IMPLEMENTATION_ID_CHANGED}
    assert len(changes.entity_changes) == 2
    assert all(c.match is not None and not c.relationships for c in changes.entity_changes)
    assert changes.is_complete
    assert snapshots == (to_canonical_json(old), to_canonical_json(new))


def test_additions_removals_and_missing_identity_uncertainty() -> None:
    old = catalogue(StatusVariable(key="old", implementation_id="1"))
    new = catalogue(StatusVariable(key="new", implementation_id="2"))
    changes = compare_interfaces(old, new)
    assert kinds(changes) == {ChangeKind.ENTITY_ADDED, ChangeKind.ENTITY_REMOVED}
    assert changes.is_complete
    unknown = compare_interfaces(EquipmentInterface(), catalogue(StatusVariable(key="unknown")))
    assert not unknown.entity_changes and not unknown.is_complete
    assert unknown.issues[0].kind is IssueKind.INSUFFICIENT_IDENTITY


def test_ambiguity_never_becomes_false_additions_or_removals() -> None:
    old = catalogue(StatusVariable(key="old", implementation_id="1", wkn=verified("A")))
    new = catalogue(StatusVariable(key="new", implementation_id="1", wkn=verified("B")))
    changes = compare_interfaces(old, new)
    assert not changes.entity_changes and not changes.is_complete
    assert all(i.kind is IssueKind.AMBIGUOUS_IDENTITY for i in changes.issues)


def test_report_order_duplicates_and_retargeting_are_explicit() -> None:
    a = StatusVariable(key="a", implementation_id="1")
    b = StatusVariable(key="b", implementation_id="2")
    first, second = ref(CanonicalType.STATUS_VARIABLE, "1"), ref(CanonicalType.STATUS_VARIABLE, "2")
    report = DefaultReport(key="report", implementation_id="10", variables=(first, second))
    changes = compare_interfaces(
        catalogue(a, b, report), catalogue(a, b, replace(report, variables=(second, first)))
    )
    relationship = changes.entity_changes[0].relationships[0]
    assert relationship.kind is ChangeKind.REPORT_CONTENT_CHANGED
    assert relationship.order_changed and not relationship.added and not relationship.removed
    duplicate = compare_interfaces(
        catalogue(a, b, report), catalogue(a, b, replace(report, variables=(first, first, second)))
    )
    delta = duplicate.entity_changes[0].relationships[0]
    assert len(delta.added) == 1 and not delta.removed
    assert ChangeKind.RELATIONSHIP_ADDED in kinds(duplicate)


def test_alarm_set_and_clear_are_distinct_roles() -> None:
    first = CollectionEvent(key="e1", implementation_id="1")
    second = CollectionEvent(key="e2", implementation_id="2")
    alarm = Alarm(
        key="a",
        implementation_id="10",
        set_event=ref(CanonicalType.COLLECTION_EVENT, "1"),
        clear_event=ref(CanonicalType.COLLECTION_EVENT, "2"),
    )
    new = replace(alarm, set_event=alarm.clear_event, clear_event=alarm.set_event)
    changes = compare_interfaces(catalogue(first, second, alarm), catalogue(first, second, new))
    relations = changes.entity_changes[0].relationships
    assert {r.field for r in relations} == {"set_event", "clear_event"}
    assert all(r.kind is ChangeKind.ALARM_EVENT_LINK_CHANGED for r in relations)
    assert all(len(r.added) == len(r.removed) == 1 for r in relations)


def test_unresolved_relationship_change_is_unknown_not_an_invented_edge() -> None:
    old = Alarm(
        key="a", implementation_id="10", set_event=ref(CanonicalType.COLLECTION_EVENT, "404")
    )
    new = replace(old, set_event=ref(CanonicalType.COLLECTION_EVENT, "405"))
    changes = compare_interfaces(catalogue(old), catalogue(new))
    assert not changes.is_complete and not changes.has_interface_changes
    relationship = changes.entity_changes[0].relationships[0]
    assert relationship.category is ChangeCategory.UNKNOWN_CHANGE
    assert relationship.kind is ChangeKind.ALARM_EVENT_LINK_CHANGED
    assert ChangeKind.RELATIONSHIP_ADDED not in kinds(changes)


def test_pointer_to_ambiguous_identity_does_not_claim_retargeting() -> None:
    old = catalogue(
        StatusVariable(key="v", implementation_id="1", wkn=verified("A")),
        DefaultReport(
            key="r", implementation_id="10", variables=(ref(CanonicalType.STATUS_VARIABLE, "1"),)
        ),
    )
    new = replace(old, status_variables=(replace(old.status_variables[0], wkn=verified("B")),))
    changes = compare_interfaces(old, new)
    assert not changes.has_interface_changes and not changes.is_complete
    assert any(i.kind is IssueKind.UNCERTAIN_TARGET_IDENTITY for i in changes.issues)


def test_format_reference_and_format_definition_changes() -> None:
    a, b = VariableFormat(key="a", name="A"), VariableFormat(key="b", name="B")
    old = StatusVariable(
        key="v",
        implementation_id="1",
        format=EntityReference(target_types=(CanonicalType.VARIABLE_FORMAT,), name="A"),
    )
    new = replace(
        old, format=EntityReference(target_types=(CanonicalType.VARIABLE_FORMAT,), name="B")
    )
    changes = compare_interfaces(catalogue(a, b, old), catalogue(a, b, new))
    assert changes.entity_changes[0].relationships[0].kind is ChangeKind.FORMAT_CHANGED
    shape = DataStructure(kind="unsigned_integer", value="0")
    a = replace(a, structure=(shape,))
    changed = replace(a, structure=(replace(shape, kind="ascii"),))
    changes = compare_interfaces(catalogue(a), catalogue(changed))
    assert changes.entity_changes[0].properties[0].kind is ChangeKind.FORMAT_CHANGED


def test_message_structure_order_and_nested_documentation() -> None:
    shape = DataStructure(
        kind="list",
        children=(
            DataStructure(kind="ascii", name="A"),
            DataStructure(kind="unsigned_integer", name="B"),
        ),
    )
    message = SupportedMessage(key="m", stream=1, function=1, structure=(shape,))
    reordered = replace(
        message, structure=(replace(shape, children=tuple(reversed(shape.children))),)
    )
    changes = compare_interfaces(catalogue(message), catalogue(reordered))
    assert ChangeKind.MESSAGE_STRUCTURE_CHANGED in kinds(changes)
    described = replace(
        message,
        structure=(
            replace(
                shape, description="New", attributes=JsonObject(entries=(("description", "New"),))
            ),
        ),
    )
    docs = compare_interfaces(catalogue(message), catalogue(described))
    assert docs.has_documentation_changes and not docs.has_interface_changes


def test_command_parameter_properties_membership_and_whole_command_removal() -> None:
    parameter = RemoteCommandParameter(key="p", name="MODE", requiredness=Requiredness.NO)
    command = RemoteCommand(key="c", name="START", parameters=(parameter,))
    new = replace(command, parameters=(replace(parameter, requiredness=Requiredness.YES),))
    changes = compare_interfaces(catalogue(command), catalogue(new))
    assert len(changes.entity_changes) == 1
    assert changes.entity_changes[0].entity_type is CanonicalType.REMOTE_COMMAND_PARAMETER
    assert ChangeKind.COMMAND_PARAMETER_CHANGED in kinds(changes)
    renamed = replace(command, parameters=(replace(parameter, name="PROFILE"),))
    changes = compare_interfaces(catalogue(command), catalogue(renamed))
    assert {
        ChangeKind.COMMAND_PARAMETER_CHANGED,
        ChangeKind.ENTITY_ADDED,
        ChangeKind.ENTITY_REMOVED,
    } <= kinds(changes)
    removed = compare_interfaces(catalogue(command), EquipmentInterface())
    assert len(removed.entity_changes) == 2 and removed.is_complete
    assert all(c.kind is ChangeKind.ENTITY_REMOVED for c in removed.entity_changes)


def test_equipment_metadata_and_container_presence() -> None:
    old = EquipmentInterface(equipment=EquipmentMetadata(model="Old", description="Old doc"))
    new = replace(
        old,
        equipment=replace(old.equipment, model="New", description="New doc"),
        reports_can_be_deleted=True,
    )
    changes = compare_interfaces(old, new)
    assert changes.has_documentation_changes and changes.has_interface_changes
    assert {ChangeKind.EQUIPMENT_METADATA_CHANGED, ChangeKind.INTERFACE_METADATA_CHANGED} <= kinds(
        changes
    )
    command = RemoteCommand(key="c", name="START")
    presence = compare_interfaces(catalogue(command), catalogue(replace(command, parameters=())))
    assert presence.entity_changes[0].relationships[0].presence_changed


def test_provenance_and_attribute_object_order_never_create_changes() -> None:
    old = VariableFormat(
        key="old",
        name="A",
        structure=(
            DataStructure(
                kind="ascii", attributes=JsonObject(entries=(("length", "4"), ("name", "X")))
            ),
        ),
        provenance=(SourceProvenance(source_document="old.xml", line=1),),
    )
    assert old.structure is not None
    new = replace(
        old,
        key="new",
        provenance=(SourceProvenance(source_document="new.xml", line=99),),
        structure=(
            replace(
                old.structure[0], attributes=JsonObject(entries=(("name", "X"), ("length", "4")))
            ),
        ),
    )
    changes = compare_interfaces(catalogue(old), catalogue(new))
    assert not changes.entity_changes and changes.is_complete


def test_unknown_extensions_are_explicit_and_boolean_is_not_integer() -> None:
    old = StatusVariable(
        key="v", implementation_id="1", extension_metadata=JsonObject(entries=(("flag", True),))
    )
    new = replace(old, extension_metadata=JsonObject(entries=(("flag", 1),)))
    changes = compare_interfaces(catalogue(old), catalogue(new))
    assert not changes.has_interface_changes and not changes.is_complete
    assert ChangeKind.UNKNOWN_CHANGE in kinds(changes)
    assert changes.entity_changes[0].properties[0].category is ChangeCategory.UNKNOWN_CHANGE


def test_unchanged_unresolved_and_opaque_material_does_not_claim_equivalence() -> None:
    entity = Alarm(
        key="a",
        implementation_id="1",
        set_event=ref(CanonicalType.COLLECTION_EVENT, "404"),
        unknown_extensions=(UnknownExtension(name="Vendor"),),
    )
    changes = compare_interfaces(catalogue(entity), catalogue(entity))
    assert not changes.entity_changes and not changes.is_complete
    assert {i.kind for i in changes.issues} == {
        IssueKind.UNKNOWN_CONTENT,
        IssueKind.UNRESOLVED_REFERENCE,
    }


def test_existing_change_catalog_and_message_structure_fixture() -> None:
    cases = json.loads((FIXTURES / "changes/change-cases.json").read_text(encoding="utf-8"))
    for case in cases:
        old = load_interface(FIXTURES / case["before"], revision="E172-0225").interface
        new = load_interface(FIXTURES / case["after"], revision="E172-0225").interface
        changes = compare_interfaces(old, new)
        assert ChangeKind(case["expected_change"]) in kinds(changes), case["after"]
    old = load_interface(
        FIXTURES / "relationships/e172-complete.xml", revision="E172-0225"
    ).interface
    new = load_interface(
        FIXTURES / "changes/e172-message-structure.xml", revision="E172-0225"
    ).interface
    assert ChangeKind.MESSAGE_STRUCTURE_CHANGED in kinds(compare_interfaces(old, new))


@pytest.mark.parametrize("seed", range(12))
def test_xml_element_attribute_and_indentation_permutations_are_noise(
    tmp_path: Path, seed: int
) -> None:
    source = FIXTURES / "relationships/e172-complete.xml"
    root = ET.fromstring(source.read_bytes())
    rng = random.Random(seed)
    for node in root.iter():
        attrs = list(node.attrib.items())
        rng.shuffle(attrs)
        node.attrib.clear()
        node.attrib.update(attrs)
        # Reorder inventory definitions and singleton property elements, but do
        # not change report members, data structures, or command parameter order.
        if node.tag in {
            "{urn:semi-org:xsd.SEDD}DataDictionary",
            "CollectionEvents",
            "StatusVariables",
            "DataVariables",
            "EquipmentConstants",
            "Alarms",
            "VariableFormats",
            "CollectionEvent",
            "StatusVariable",
            "EquipmentConstant",
            "Alarm",
        }:
            children = list(node)
            rng.shuffle(children)
            node[:] = children
    ET.indent(root, space=" " * (seed % 4 + 1))
    path = tmp_path / "permuted.xml"
    path.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
    old = load_interface(source, revision="E172-0225").interface
    new = load_interface(path, revision="E172-0225").interface
    assert source.read_bytes() != path.read_bytes()
    changes = compare_interfaces(old, new)
    assert not changes.entity_changes


def test_inventory_permutations_preserve_nonempty_change_output() -> None:
    old_entities = tuple(
        StatusVariable(key=f"o/{i}", implementation_id=str(i), units=("C",)) for i in range(3)
    )
    new_entities = tuple(replace(e, key=f"n/{i}", units=("K",)) for i, e in enumerate(old_entities))
    expected = to_change_set_json(
        compare_interfaces(catalogue(*old_entities), catalogue(*new_entities))
    )
    for old_order in permutations(old_entities):
        for new_order in permutations(new_entities):
            result = compare_interfaces(catalogue(*old_order), catalogue(*new_order))
            assert to_change_set_json(result) == expected


def test_change_json_has_evidence_categories_and_original_provenance() -> None:
    old = StatusVariable(
        key="old",
        implementation_id="1",
        provenance=(SourceProvenance(source_document="old.xml", line=42),),
    )
    new = replace(old, key="new", name="温度")
    changes = compare_interfaces(catalogue(old), catalogue(new))
    output = to_change_set_json(changes)
    assert output == to_change_set_json(changes) and output.endswith("\n")
    assert "温度" in output
    data = to_change_set_dict(changes)
    assert data["change_schema_version"] == "1.0"
    parsed = json.loads(output)["change_set"]["entity_changes"][0]
    assert parsed["categories"] == ["INTERFACE_CHANGE"]
    assert parsed["match"]["strategy"] == "NATIVE_ID"
    assert parsed["old_entity"]["provenance"][0]["line"] == 42


def test_standards_requirement_locations_order_and_notes() -> None:
    def member(identifier: str, note: str, line: int) -> JsonObject:
        return JsonObject(
            entries=(
                ("requirement_id", identifier),
                ("implemented", True),
                ("notes", JsonArray(items=(note,))),
                ("line", line),
                ("source_path", f"/r/{line}"),
            )
        )

    def standard(members: tuple[JsonObject, ...]) -> StandardReference:
        return StandardReference(
            key="s",
            designation="Synthetic",
            requirements=(
                JsonObject(
                    entries=(
                        ("kind", "requirement_group"),
                        ("name", "G"),
                        ("requirements", JsonArray(items=members)),
                        ("line", 1),
                    )
                ),
            ),
        )

    old = standard((member("A", "Note", 1), member("B", "Other", 2)))
    reordered = standard((member("B", "Other", 99), member("A", "Note", 98)))
    assert not compare_interfaces(catalogue(old), catalogue(reordered)).entity_changes
    changed = standard((member("A", "Revised note", 99), member("B", "Other", 100)))
    result = compare_interfaces(catalogue(old), catalogue(changed))
    assert result.has_documentation_changes and not result.has_interface_changes


def test_state_transition_changes_and_opaque_state_metadata_are_separate() -> None:
    state = StateTransition(state_model="Control", previous_state="Idle", new_state="Run")
    old = CollectionEvent(key="e", implementation_id="1", state_transition=state)
    new = replace(old, state_transition=replace(state, new_state="Stop"))
    changes = compare_interfaces(catalogue(old), catalogue(new))
    assert ChangeKind.STATE_TRANSITION_CHANGED in kinds(changes)
    opaque = replace(
        old, state_transition=replace(state, unknown_extensions=(UnknownExtension(name="Vendor"),))
    )
    changes = compare_interfaces(catalogue(old), catalogue(opaque))
    assert not changes.has_interface_changes and not changes.is_complete
    assert ChangeKind.UNKNOWN_CHANGE in kinds(changes)


def test_unknown_content_on_new_entity_is_retained_as_uncertainty() -> None:
    entity = StatusVariable(
        key="new", implementation_id="1", unknown_extensions=(UnknownExtension(name="Vendor"),)
    )
    changes = compare_interfaces(EquipmentInterface(), catalogue(entity))
    assert ChangeKind.ENTITY_ADDED in kinds(changes)
    assert not changes.is_complete
    assert changes.issues[0].kind is IssueKind.UNKNOWN_CONTENT


def test_opposite_missing_identity_blocks_definite_removal() -> None:
    old = catalogue(StatusVariable(key="old", implementation_id="1"))
    new = catalogue(StatusVariable(key="new"))
    for first, second in ((old, new), (new, old)):
        changes = compare_interfaces(first, second)
        assert not changes.entity_changes and not changes.is_complete
        assert len(changes.issues) == 2


def test_repeated_messages_remain_ambiguous_even_with_identical_inputs() -> None:
    messages = catalogue(
        SupportedMessage(key="a", stream=1, function=1),
        SupportedMessage(key="b", stream=1, function=1),
    )
    changes = compare_interfaces(messages, messages)
    assert not changes.entity_changes and not changes.is_complete
    assert all(i.kind is IssueKind.AMBIGUOUS_IDENTITY for i in changes.issues)


def test_standards_association_order_ignores_permutation_with_opaque_annotations() -> None:
    a, b = StandardReference(key="a", designation="A"), StandardReference(key="b", designation="B")
    refs = tuple(
        EntityReference(
            target_types=(CanonicalType.STANDARD_REFERENCE,),
            name=n,
            metadata=JsonObject(entries=(("note", n),)),
        )
        for n in ("A", "B")
    )
    old = StatusVariable(key="v", implementation_id="1", standards=refs)
    new = replace(old, standards=tuple(reversed(refs)))
    changes = compare_interfaces(catalogue(a, b, old), catalogue(a, b, new))
    assert not changes.entity_changes
    assert not changes.is_complete  # Preserved metadata is still opaque.


def test_message_data_whitespace_and_missing_vs_empty_values_are_not_erased() -> None:
    old = SupportedMessage(
        key="m", stream=1, function=1, structure=(DataStructure(kind="ascii", value="a b"),)
    )
    new = replace(old, structure=(DataStructure(kind="ascii", value="ab"),))
    assert ChangeKind.MESSAGE_STRUCTURE_CHANGED in kinds(
        compare_interfaces(catalogue(old), catalogue(new))
    )
    constant = EquipmentConstant(key="c", implementation_id="1")
    assert ChangeKind.DEFAULT_CHANGED in kinds(
        compare_interfaces(catalogue(constant), catalogue(replace(constant, default="")))
    )


def test_duplicate_report_member_removal_preserves_multiplicity() -> None:
    entity = StatusVariable(key="v", implementation_id="1")
    reference = ref(CanonicalType.STATUS_VARIABLE, "1")
    report = DefaultReport(key="r", implementation_id="1", variables=(reference, reference))
    changes = compare_interfaces(
        catalogue(entity, report), catalogue(entity, replace(report, variables=(reference,)))
    )
    relationship = changes.entity_changes[0].relationships[0]
    assert len(relationship.removed) == 1 and not relationship.added
    assert not relationship.order_changed


def test_event_report_member_change_and_event_identity_change_are_distinct() -> None:
    event1, event2 = (
        CollectionEvent(key="e1", implementation_id="1"),
        CollectionEvent(key="e2", implementation_id="2"),
    )
    report1, report2 = (
        DefaultReport(key="r1", implementation_id="1"),
        DefaultReport(key="r2", implementation_id="2"),
    )
    link = EventReportLink(
        key="l",
        event=ref(CanonicalType.COLLECTION_EVENT, "1"),
        reports=(ref(CanonicalType.DEFAULT_REPORT, "1"),),
    )
    entities = (event1, event2, report1, report2)
    members = compare_interfaces(
        catalogue(*entities, link),
        catalogue(*entities, replace(link, reports=(ref(CanonicalType.DEFAULT_REPORT, "2"),))),
    )
    assert len(members.entity_changes) == 1
    assert members.entity_changes[0].relationships[0].kind is ChangeKind.EVENT_REPORT_LINK_CHANGED
    changed_event = compare_interfaces(
        catalogue(*entities, link),
        catalogue(*entities, replace(link, event=ref(CanonicalType.COLLECTION_EVENT, "2"))),
    )
    assert {
        ChangeKind.ENTITY_ADDED,
        ChangeKind.ENTITY_REMOVED,
        ChangeKind.EVENT_REPORT_LINK_CHANGED,
    } <= kinds(changed_event)
    assert not changed_event.matching.ambiguities


def test_semantic_change_records_reject_inconsistent_states() -> None:
    from sema_sedd.compare import EntityChange, PropertyChange
    from sema_sedd.exceptions import ModelValidationError

    with pytest.raises(ModelValidationError):
        PropertyChange(
            field="name",
            kind=ChangeKind.NAME_CHANGED,
            category=ChangeCategory.INTERFACE_CHANGE,
            old_value="A",
            new_value="A",
        )
    with pytest.raises(ModelValidationError):
        EntityChange(
            kind=ChangeKind.ENTITY_ADDED, old_entity=StatusVariable(key="v"), new_entity=None
        )
    with pytest.raises(ModelValidationError):
        compare_interfaces("input.xml", EquipmentInterface())  # type: ignore[arg-type]
