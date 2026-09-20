"""Adversarial tests for cross-version identity; fictional registries only."""

import os
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from itertools import permutations
from pathlib import Path

import pytest

from sema_sedd.adapters import load_interface
from sema_sedd.compare import (
    AmbiguityReason,
    IdentityChangeKind,
    MatchConfidence,
    MatchingResult,
    MatchStrategy,
    UnmatchedReason,
    match_interfaces,
)
from sema_sedd.exceptions import ModelValidationError
from sema_sedd.graph import resolve_references
from sema_sedd.model import (
    Alarm,
    CanonicalType,
    CollectionEvent,
    DataVariable,
    DefaultReport,
    EntityReference,
    EquipmentConstant,
    EquipmentInterface,
    EventReportLink,
    MessageDirection,
    RemoteCommand,
    RemoteCommandParameter,
    SourceProvenance,
    StandardReference,
    StatusVariable,
    SupportedMessage,
    UnknownExtension,
    VariableFormat,
    WellKnownName,
    WknAuthority,
    to_canonical_json,
)
from sema_sedd.model.domain import InterfaceEntity


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


def verified(
    value: str, *, authority: str = "fictional-registry", scope: str = "fixture"
) -> WellKnownName:
    return WellKnownName(
        value=value,
        authority=authority,
        scope=scope,
        authority_status=WknAuthority.VERIFIED,
        provenance=(SourceProvenance(source_document="synthetic-registry.json"),),
    )


def pairs(result: MatchingResult) -> set[tuple[str, str]]:
    return {(item.old_entity.key, item.new_entity.key) for item in result.matches}


def assert_partition(
    old: EquipmentInterface, new: EquipmentInterface, result: MatchingResult
) -> None:
    old_keys = [item.old_entity.key for item in result.matches]
    new_keys = [item.new_entity.key for item in result.matches]
    old_keys.extend(e.key for group in result.ambiguities for e in group.old_entities)
    new_keys.extend(e.key for group in result.ambiguities for e in group.new_entities)
    old_keys.extend(item.entity.key for item in result.unmatched_old)
    new_keys.extend(item.entity.key for item in result.unmatched_new)
    assert len(old_keys) == len(set(old_keys)) == len(old.entities())
    assert len(new_keys) == len(set(new_keys)) == len(new.entities())
    assert set(old_keys) == {e.key for e in old.entities()}
    assert set(new_keys) == {e.key for e in new.entities()}


@pytest.mark.parametrize(
    "entity",
    [
        StatusVariable(key="old", implementation_id="007"),
        DataVariable(key="old", implementation_id="007"),
        EquipmentConstant(key="old", implementation_id="007"),
        CollectionEvent(key="old", implementation_id="007"),
        Alarm(key="old", implementation_id="007"),
        DefaultReport(key="old", implementation_id="007"),
    ],
)
def test_native_identity_matches_scoped_type_with_complete_evidence(
    entity: InterfaceEntity,
) -> None:
    new_entity = replace(entity, key="new", name="Changed display label", description="Changed")
    result = match_interfaces(catalogue(entity), catalogue(new_entity))
    match = result.matches[0]
    assert match.old_entity is entity
    assert match.new_entity is new_entity
    assert match.strategy is MatchStrategy.NATIVE_ID
    assert match.confidence is MatchConfidence.EXACT_IDENTITY
    assert match.evidence[0].identity == ("007",)
    assert match.evidence[0].old_keys == ("old",)
    assert match.evidence[0].new_keys == ("new",)
    assert not match.changes


def test_exact_verified_wkn_records_id_change_not_unmatched_entities() -> None:
    old_entity = StatusVariable(key="old", implementation_id="44", wkn=verified("Temperature"))
    new_entity = replace(old_entity, key="new", implementation_id="8044", name="New label")
    old, new = catalogue(old_entity), catalogue(new_entity)
    snapshots = (to_canonical_json(old), to_canonical_json(new))
    result = match_interfaces(old, new)
    match = result.matches[0]
    assert match.strategy is MatchStrategy.WELL_KNOWN_NAME
    assert match.confidence is MatchConfidence.VERIFIED_WKN
    assert match.evidence[0].identity == ("fictional-registry", "fixture", "Temperature")
    assert match.old_entity.wkn == old_entity.wkn
    assert match.new_entity.wkn == new_entity.wkn
    assert len(match.changes) == 1
    assert match.changes[0].kind is IdentityChangeKind.IMPLEMENTATION_ID_CHANGED
    assert (match.changes[0].old_value, match.changes[0].new_value) == ("44", "8044")
    assert not result.unmatched_old and not result.unmatched_new and not result.ambiguities
    assert snapshots == (to_canonical_json(old), to_canonical_json(new))
    assert_partition(old, new, result)


def test_agreeing_signals_record_all_evidence_and_explanation_precedence() -> None:
    entity = Alarm(key="a", implementation_id="72", wkn=verified("Warning"))
    match = match_interfaces(catalogue(entity), catalogue(replace(entity, key="b"))).matches[0]
    assert match.strategy is MatchStrategy.NATIVE_ID
    assert match.confidence is MatchConfidence.CORROBORATED
    assert [e.strategy for e in match.evidence] == [
        MatchStrategy.NATIVE_ID,
        MatchStrategy.WELL_KNOWN_NAME,
    ]


@pytest.mark.parametrize("value", [None, "", "  ", "\t"])
def test_missing_and_blank_ids_do_not_match_by_key_name_or_description(value: str | None) -> None:
    entity = StatusVariable(
        key="same/path", implementation_id=value, name="Same", description="Same"
    )
    result = match_interfaces(catalogue(entity), catalogue(entity))
    assert not result.matches
    assert result.unmatched_old[0].reason is UnmatchedReason.NO_USABLE_IDENTITY
    assert result.unmatched_new[0].entity is entity


@pytest.mark.parametrize("old_id,new_id", [("007", "7"), ("1", " 1"), ("A", "a")])
def test_lexical_ids_are_never_normalized(old_id: str, new_id: str) -> None:
    old = catalogue(StatusVariable(key="old", implementation_id=old_id))
    new = catalogue(StatusVariable(key="new", implementation_id=new_id))
    result = match_interfaces(old, new)
    assert not result.matches and not result.ambiguities
    assert result.unmatched_old[0].reason is UnmatchedReason.NO_COUNTERPART


def test_zero_is_a_valid_exact_id_and_types_never_cross_match() -> None:
    wkn = verified("Same")
    old = catalogue(StatusVariable(key="old", implementation_id="0", wkn=wkn))
    new = catalogue(
        DataVariable(key="wrong-type", implementation_id="0", wkn=wkn),
        StatusVariable(key="new", implementation_id="0", wkn=wkn),
    )
    result = match_interfaces(old, new)
    assert pairs(result) == {("old", "new")}
    assert result.unmatched_new[0].entity.key == "wrong-type"


def test_unverified_wkn_never_establishes_continuity() -> None:
    unverified = WellKnownName(value="LooksOfficial", authority="SEMI", scope="variables")
    old = catalogue(StatusVariable(key="old", implementation_id="1", wkn=unverified))
    new = catalogue(StatusVariable(key="new", implementation_id="2", wkn=unverified))
    assert not match_interfaces(old, new).matches
    new_verified = catalogue(replace(new.status_variables[0], wkn=verified("LooksOfficial")))
    assert not match_interfaces(old, new_verified).matches


@pytest.mark.parametrize(
    "new_wkn",
    [
        verified("Other"),
        verified("Same", authority="other-registry"),
        verified("Same", scope="other"),
    ],
)
def test_same_native_id_with_different_verified_wkn_is_ambiguous(new_wkn: WellKnownName) -> None:
    old = catalogue(StatusVariable(key="old", implementation_id="1", wkn=verified("Same")))
    new = catalogue(StatusVariable(key="new", implementation_id="1", wkn=new_wkn))
    result = match_interfaces(old, new)
    assert not result.matches and not result.unmatched_old and not result.unmatched_new
    assert result.ambiguities[0].reasons == (AmbiguityReason.CONFLICTING_SIGNALS,)
    assert len(result.ambiguities[0].evidence) == 3


def test_swapped_ids_and_wkns_do_not_let_precedence_select_a_winner() -> None:
    old = catalogue(
        StatusVariable(key="old/a", implementation_id="1", wkn=verified("A")),
        StatusVariable(key="old/b", implementation_id="2", wkn=verified("B")),
    )
    new = catalogue(
        StatusVariable(key="new/a", implementation_id="2", wkn=verified("A")),
        StatusVariable(key="new/b", implementation_id="1", wkn=verified("B")),
    )
    result = match_interfaces(old, new)
    assert not result.matches
    assert len(result.ambiguities) == 1
    assert result.ambiguities[0].reasons == (AmbiguityReason.CONFLICTING_SIGNALS,)
    assert_partition(old, new, result)


def test_conflict_propagates_across_a_component_without_greedy_consumption() -> None:
    old = catalogue(
        StatusVariable(key="old/a", implementation_id="1", wkn=verified("A")),
        StatusVariable(key="old/b", implementation_id="2", wkn=verified("B")),
        StatusVariable(key="old/c", implementation_id="3"),
    )
    new = catalogue(
        StatusVariable(key="new/a", implementation_id="2", wkn=verified("A")),
        StatusVariable(key="new/b", implementation_id="3", wkn=verified("B")),
        StatusVariable(key="new/c", implementation_id="4"),
    )
    result = match_interfaces(old, new)
    assert not result.matches
    assert len(result.ambiguities[0].old_entities) == 3
    assert len(result.ambiguities[0].new_entities) == 2
    assert result.unmatched_new[0].entity.key == "new/c"
    assert_partition(old, new, result)


@pytest.mark.parametrize("duplicate_side", ["old", "new", "both"])
@pytest.mark.parametrize("mechanism", ["id", "wkn"])
def test_collisions_remain_ambiguous_on_either_side(duplicate_side: str, mechanism: str) -> None:
    entity = StatusVariable(
        key="first",
        implementation_id="1" if mechanism == "id" else None,
        wkn=verified("Duplicate") if mechanism == "wkn" else None,
    )
    duplicate = replace(entity, key="second")
    old = catalogue(entity, duplicate) if duplicate_side in {"old", "both"} else catalogue(entity)
    new = catalogue(entity, duplicate) if duplicate_side in {"new", "both"} else catalogue(entity)
    result = match_interfaces(old, new)
    assert not result.matches
    assert AmbiguityReason.IDENTITY_COLLISION in result.ambiguities[0].reasons
    assert_partition(old, new, result)


def test_duplicate_signal_cannot_be_laundered_by_a_unique_secondary_signal() -> None:
    old = catalogue(
        StatusVariable(key="old/a", implementation_id="1", wkn=verified("A")),
        StatusVariable(key="old/b", implementation_id="1", wkn=verified("B")),
    )
    new = catalogue(StatusVariable(key="new/a", implementation_id="9", wkn=verified("A")))
    result = match_interfaces(old, new)
    assert not result.matches
    assert len(result.ambiguities[0].old_entities) == 2
    assert result.ambiguities[0].reasons == (AmbiguityReason.IDENTITY_COLLISION,)


@pytest.mark.parametrize(
    "entity,strategy",
    [
        (RemoteCommand(key="old", name="START"), MatchStrategy.COMMAND_NAME),
        (VariableFormat(key="old", name="Unsigned"), MatchStrategy.FORMAT_NAME),
        (
            StandardReference(key="old", designation="Fictional-1"),
            MatchStrategy.STANDARD_DESIGNATION,
        ),
        (SupportedMessage(key="old", stream=1, function=2), MatchStrategy.STREAM_FUNCTION),
    ],
)
def test_entity_specific_identities(entity: InterfaceEntity, strategy: MatchStrategy) -> None:
    match = match_interfaces(catalogue(entity), catalogue(replace(entity, key="new"))).matches[0]
    assert match.strategy is strategy
    assert match.confidence is MatchConfidence.EXACT_IDENTITY


def test_arbitrary_names_descriptions_paths_and_extension_hints_are_not_identity() -> None:
    old = catalogue(
        Alarm(key="same/path", name="ValveFailure", description="same description"),
        StatusVariable(key="old/sv", name="Temperature", description="same description"),
        DefaultReport(key="old/report", name="SameReport"),
        SupportedMessage(key="old/message", name="SameMessage", stream=1),
    )
    new = catalogue(
        Alarm(key="same/path", name="ValveFailure", description="same description"),
        StatusVariable(key="new/sv", name="Temperatures", description="same description"),
        DefaultReport(key="new/report", name="SameReport"),
        SupportedMessage(key="new/message", name="SameMessage", stream=1),
    )
    result = match_interfaces(old, new)
    assert not result.matches and not result.ambiguities
    assert len(result.unmatched_old) == len(result.unmatched_new) == 4


def test_message_duplicates_are_not_disambiguated_by_direction_or_name() -> None:
    old = catalogue(
        SupportedMessage(
            key="old/a", stream=1, function=1, direction=MessageDirection.HOST_TO_EQUIPMENT
        ),
        SupportedMessage(
            key="old/b", stream=1, function=1, direction=MessageDirection.EQUIPMENT_TO_HOST
        ),
    )
    new = catalogue(
        SupportedMessage(
            key="new/a", stream=1, function=1, direction=MessageDirection.HOST_TO_EQUIPMENT
        )
    )
    result = match_interfaces(old, new)
    assert not result.matches
    assert result.ambiguities[0].reasons == (AmbiguityReason.IDENTITY_COLLISION,)


@pytest.mark.parametrize(
    "old_entity,new_entity",
    [
        (RemoteCommand(key="old", name="START"), RemoteCommand(key="new", name="STOP")),
        (VariableFormat(key="old", name="A"), VariableFormat(key="new", name="B")),
        (
            SupportedMessage(key="old", stream=1, function=1),
            SupportedMessage(key="new", stream=1, function=2),
        ),
    ],
)
def test_wkn_cannot_override_conflicting_entity_specific_identity(
    old_entity: InterfaceEntity, new_entity: InterfaceEntity
) -> None:
    old = catalogue(replace(old_entity, wkn=verified("Shared")))
    new = catalogue(replace(new_entity, wkn=verified("Shared")))
    result = match_interfaces(old, new)
    assert not result.matches
    assert result.ambiguities[0].reasons == (AmbiguityReason.CONFLICTING_SIGNALS,)


def command(key: str, name: str, *, parameter_name: str = "MODE") -> RemoteCommand:
    return RemoteCommand(
        key=key,
        name=name,
        parameters=(RemoteCommandParameter(key=f"{key}/p", name=parameter_name),),
    )


def test_parameters_match_only_inside_confirmed_command_pairs() -> None:
    old = catalogue(command("old/a", "START"), command("old/b", "STOP"))
    new = catalogue(command("new/b", "STOP"), command("new/a", "START"))
    result = match_interfaces(old, new)
    assert pairs(result) == {
        ("old/a", "new/a"),
        ("old/b", "new/b"),
        ("old/a/p", "new/a/p"),
        ("old/b/p", "new/b/p"),
    }
    parameter = next(m for m in result.matches if m.old_entity.key == "old/a/p")
    assert parameter.strategy is MatchStrategy.PARAMETER_NAME
    assert parameter.evidence[0].identity == ("old/a", "new/a", "MODE")
    assert_partition(old, new, result)


def test_ambiguous_command_scope_defers_children_without_cross_matching() -> None:
    old = catalogue(command("old/a", "START"), command("old/b", "START"))
    new = catalogue(command("new/a", "START"))
    result = match_interfaces(old, new)
    assert not result.matches
    assert len(result.ambiguities) == 1
    assert len(result.unmatched_old) == 2
    assert all(u.reason is UnmatchedReason.NO_CONFIRMED_COMMAND_SCOPE for u in result.unmatched_old)
    assert result.unmatched_new[0].dependency_key == "new/a"
    assert_partition(old, new, result)


def test_parameter_duplicates_stay_ambiguous_while_commands_match() -> None:
    old_command = RemoteCommand(
        key="old",
        name="START",
        parameters=(
            RemoteCommandParameter(key="old/a", name="MODE"),
            RemoteCommandParameter(key="old/b", name="MODE"),
        ),
    )
    result = match_interfaces(catalogue(old_command), catalogue(command("new", "START")))
    assert pairs(result) == {("old", "new")}
    assert result.ambiguities[0].reasons == (AmbiguityReason.IDENTITY_COLLISION,)


def link(key: str, event_key: str) -> EventReportLink:
    return EventReportLink(
        key=key,
        event=EntityReference(
            target_types=(CanonicalType.COLLECTION_EVENT,),
            target_key=event_key,
        ),
    )


def test_links_follow_confirmed_event_identity_even_when_event_id_changes() -> None:
    old = catalogue(
        CollectionEvent(key="old/event", implementation_id="1", wkn=verified("Event")),
        link("old/link", "old/event"),
    )
    new = catalogue(
        CollectionEvent(key="new/event", implementation_id="2", wkn=verified("Event")),
        link("new/link", "new/event"),
    )
    result = match_interfaces(old, new)
    assert pairs(result) == {("old/event", "new/event"), ("old/link", "new/link")}
    assert result.matches[1].strategy is MatchStrategy.EVENT_IDENTITY
    assert result.matches[1].evidence[0].identity == ("old/event", "new/event")


def test_unresolved_event_references_are_not_resolved_by_matching() -> None:
    entity = EventReportLink(key="link", event=EntityReference(implementation_id="1"))
    interface = catalogue(CollectionEvent(key="event", implementation_id="1"), entity)
    result = match_interfaces(interface, interface)
    assert pairs(result) == {("event", "event")}
    assert result.unmatched_old[0].reason is UnmatchedReason.NO_USABLE_IDENTITY
    assert entity.event is not None and entity.event.target_key is None


def test_duplicate_links_do_not_use_report_content_to_choose_identity() -> None:
    event = CollectionEvent(key="event", implementation_id="1")
    old = catalogue(event, link("old/a", "event"), link("old/b", "event"))
    new = catalogue(event, link("new", "event"))
    result = match_interfaces(old, new)
    assert pairs(result) == {("event", "event")}
    assert result.ambiguities[0].reasons == (AmbiguityReason.IDENTITY_COLLISION,)


def test_inventory_permutations_and_reversing_versions_preserve_decisions() -> None:
    old_entities = (
        StatusVariable(key="old/a", implementation_id="1", wkn=verified("A")),
        StatusVariable(key="old/b", implementation_id="2", wkn=verified("B")),
        StatusVariable(key="old/c", implementation_id="3"),
    )
    new_entities = (
        StatusVariable(key="new/a", implementation_id="2", wkn=verified("A")),
        StatusVariable(key="new/b", implementation_id="1", wkn=verified("B")),
        StatusVariable(key="new/c", implementation_id="3"),
    )
    expected = match_interfaces(catalogue(*old_entities), catalogue(*new_entities))
    for old_order in permutations(old_entities):
        for new_order in permutations(new_entities):
            assert match_interfaces(catalogue(*old_order), catalogue(*new_order)) == expected
    reversed_result = match_interfaces(catalogue(*new_entities), catalogue(*old_entities))
    assert pairs(reversed_result) == {(b, a) for a, b in pairs(expected)}
    assert {e.key for e in reversed_result.ambiguities[0].new_entities} == {"old/a", "old/b"}


def test_empty_and_one_sided_interfaces_keep_an_exhaustive_partition() -> None:
    assert match_interfaces(EquipmentInterface(), EquipmentInterface()) == MatchingResult()
    old = catalogue(StatusVariable(key="a", implementation_id="1"), StatusVariable(key="b"))
    for first, second in ((old, EquipmentInterface()), (EquipmentInterface(), old)):
        result = match_interfaces(first, second)
        assert not result.matches
        assert_partition(first, second, result)


def test_large_collision_is_one_group_not_cartesian_candidate_pairs() -> None:
    old = catalogue(*(StatusVariable(key=f"o/{i}", implementation_id="1") for i in range(1000)))
    new = catalogue(*(StatusVariable(key=f"n/{i}", implementation_id="1") for i in range(1000)))
    result = match_interfaces(old, new)
    assert len(result.ambiguities) == 1
    assert len(result.ambiguities[0].evidence) == 1
    assert len(result.ambiguities[0].evidence[0].old_keys) == 1000
    assert_partition(old, new, result)


def test_synthetic_parsed_models_match_all_categories_after_reference_resolution() -> None:
    fixture = Path(__file__).parent / "fixtures/relationships/e172-complete.xml"
    parsed = load_interface(fixture, revision="E172-0225").interface
    interface = resolve_references(parsed).interface
    result = match_interfaces(interface, interface)
    assert len(result.matches) == len(interface.entities()) == 13
    assert not result.ambiguities and not result.unmatched_old and not result.unmatched_new
    assert {item.old_entity.canonical_type for item in result.matches} == {
        CanonicalType.STATUS_VARIABLE,
        CanonicalType.DATA_VARIABLE,
        CanonicalType.EQUIPMENT_CONSTANT,
        CanonicalType.COLLECTION_EVENT,
        CanonicalType.ALARM,
        CanonicalType.REMOTE_COMMAND,
        CanonicalType.REMOTE_COMMAND_PARAMETER,
        CanonicalType.SUPPORTED_MESSAGE,
        CanonicalType.VARIABLE_FORMAT,
        CanonicalType.DEFAULT_REPORT,
        CanonicalType.EVENT_REPORT_LINK,
        CanonicalType.STANDARD_REFERENCE,
    }


def test_future_revision_and_unknown_content_are_retained_without_becoming_identity() -> None:
    old_entity = StatusVariable(
        key="old",
        implementation_id="1",
        provenance=(SourceProvenance(source_document="old.json", source_revision="future-99"),),
        unknown_extensions=(UnknownExtension(name="VendorIdentity", content=("a",)),),
    )
    new_entity = replace(
        old_entity,
        key="new",
        unknown_extensions=(UnknownExtension(name="VendorIdentity", content=("b",)),),
    )
    match = match_interfaces(catalogue(old_entity), catalogue(new_entity)).matches[0]
    assert match.old_entity.provenance == old_entity.provenance
    assert match.new_entity.unknown_extensions == new_entity.unknown_extensions
    with pytest.raises(FrozenInstanceError):
        match.strategy = MatchStrategy.WELL_KNOWN_NAME  # type: ignore[misc]


def test_matcher_import_and_results_are_independent_of_hash_seed_and_xml_layers() -> None:
    code = """
import sys
from importlib.abc import MetaPathFinder
class BlockXml(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(part in fullname for part in ("sema_sedd.adapters", "sema_sedd.parser", "xml")):
            raise AssertionError("XML dependency leaked")
sys.meta_path.insert(0, BlockXml())
from sema_sedd.compare import match_interfaces
from sema_sedd.model import EquipmentInterface, StatusVariable
old = EquipmentInterface(status_variables=tuple(
    StatusVariable(key=k, implementation_id="same") for k in {"b", "a", "c"}))
new = EquipmentInterface(status_variables=(StatusVariable(key="n", implementation_id="same"),))
print(repr(match_interfaces(old, new)))
"""
    outputs = []
    for seed in ("1", "42", "987"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        result = subprocess.run(
            [sys.executable, "-c", code],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1] == outputs[2]


def test_invalid_input_types_fail_at_canonical_boundary() -> None:
    with pytest.raises(ModelValidationError, match="two canonical"):
        match_interfaces("file.xml", EquipmentInterface())  # type: ignore[arg-type]


def test_corroborating_duplicate_tokens_are_collision_not_conflicting_values() -> None:
    first = StatusVariable(key="a", implementation_id="1", wkn=verified("Duplicate"))
    old = catalogue(first, replace(first, key="b"))
    new = catalogue(replace(first, key="new"))
    result = match_interfaces(old, new)
    assert not result.matches
    assert result.ambiguities[0].reasons == (AmbiguityReason.IDENTITY_COLLISION,)


def test_same_wkn_text_in_different_verified_namespaces_does_not_match() -> None:
    old = catalogue(StatusVariable(key="old", wkn=verified("Value")))
    for wkn in (verified("Value", scope="other"), verified("Value", authority="other")):
        result = match_interfaces(old, catalogue(StatusVariable(key="new", wkn=wkn)))
        assert not result.matches and not result.ambiguities
        assert result.unmatched_old[0].reason is UnmatchedReason.NO_COUNTERPART


def test_missing_wkn_does_not_invent_a_conflict_with_native_identity() -> None:
    old = catalogue(StatusVariable(key="old", implementation_id="1", wkn=verified("Value")))
    new = catalogue(StatusVariable(key="new", implementation_id="1"))
    assert pairs(match_interfaces(old, new)) == {("old", "new")}


def test_single_sided_collisions_remain_visible() -> None:
    old = catalogue(
        Alarm(key="a", implementation_id="1"),
        Alarm(key="b", implementation_id="1"),
    )
    result = match_interfaces(old, EquipmentInterface())
    assert not result.unmatched_old
    assert result.ambiguities[0].new_entities == ()
    assert result.ambiguities[0].reasons == (AmbiguityReason.IDENTITY_COLLISION,)


def test_official_wkn_alone_can_match_missing_native_ids() -> None:
    old = catalogue(StatusVariable(key="old", wkn=verified("Value")))
    new = catalogue(StatusVariable(key="new", wkn=verified("Value")))
    match = match_interfaces(old, new).matches[0]
    assert match.strategy is MatchStrategy.WELL_KNOWN_NAME
    assert not match.changes


def test_similar_command_names_never_match() -> None:
    old = catalogue(command("old", "START"))
    new = catalogue(command("new", "Start"))
    result = match_interfaces(old, new)
    assert not result.matches
    assert_partition(old, new, result)


def test_unsupported_native_ids_on_generic_model_fields_do_not_establish_identity() -> None:
    old = catalogue(VariableFormat(key="old", implementation_id="invented-id"))
    new = catalogue(VariableFormat(key="new", implementation_id="invented-id"))
    result = match_interfaces(old, new)
    assert not result.matches
    assert result.unmatched_old[0].reason is UnmatchedReason.NO_USABLE_IDENTITY


def test_wkn_cannot_move_a_parameter_between_confirmed_command_scopes() -> None:
    old = catalogue(
        RemoteCommand(
            key="old/a",
            name="A",
            parameters=(RemoteCommandParameter(key="old/p", name="MODE", wkn=verified("P")),),
        ),
        RemoteCommand(key="old/b", name="B"),
    )
    new = catalogue(
        RemoteCommand(key="new/a", name="A"),
        RemoteCommand(
            key="new/b",
            name="B",
            parameters=(RemoteCommandParameter(key="new/p", name="MODE", wkn=verified("P")),),
        ),
    )
    result = match_interfaces(old, new)
    assert pairs(result) == {("old/a", "new/a"), ("old/b", "new/b")}
    assert result.unmatched_old[0].entity.key == "old/p"
    assert result.unmatched_new[0].entity.key == "new/p"


def test_event_link_wkn_and_confirmed_event_targets_must_agree() -> None:
    old = catalogue(
        CollectionEvent(key="old/a", implementation_id="1"),
        CollectionEvent(key="old/b", implementation_id="2"),
        replace(link("old/link", "old/a"), wkn=verified("Link")),
    )
    new = catalogue(
        CollectionEvent(key="new/a", implementation_id="1"),
        CollectionEvent(key="new/b", implementation_id="2"),
        replace(link("new/link", "new/b"), wkn=verified("Link")),
    )
    result = match_interfaces(old, new)
    assert pairs(result) == {("old/a", "new/a"), ("old/b", "new/b")}
    assert result.ambiguities[0].reasons == (AmbiguityReason.CONFLICTING_SIGNALS,)
