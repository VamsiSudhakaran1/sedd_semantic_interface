"""Exact, conservative reference indexing and resolution."""

from dataclasses import replace
from pathlib import Path

import pytest

from sema_sedd.adapters import load_interface
from sema_sedd.exceptions import ModelValidationError
from sema_sedd.graph import (
    ResolutionState,
    build_reference_indexes,
    resolve_references,
)
from sema_sedd.model import (
    Alarm,
    CanonicalType,
    CollectionEvent,
    EntityReference,
    EquipmentInterface,
    RemoteCommand,
    RemoteCommandParameter,
    StandardReference,
    StatusVariable,
    SupportedMessage,
    UnresolvedReason,
    VariableFormat,
    WellKnownName,
)

FIXTURES = Path(__file__).parent / "fixtures"


def alarm_reference(
    *, identifier: str | None = None, name: str | None = None
) -> EquipmentInterface:
    return EquipmentInterface(
        collection_events=(CollectionEvent(key="event", implementation_id="10", name="Ready"),),
        alarms=(
            Alarm(
                key="alarm",
                set_event=EntityReference(
                    target_types=(CanonicalType.COLLECTION_EVENT,),
                    implementation_id=identifier,
                    name=name,
                ),
            ),
        ),
    )


def test_valid_reference_resolves_and_is_removed_from_unresolved_ledger() -> None:
    result = resolve_references(alarm_reference(identifier="10"))
    relationship = result.relationships[0]
    assert relationship.state is ResolutionState.RESOLVED
    assert relationship.reason is None
    assert relationship.candidate_keys == ()
    assert relationship.reference.target_key == "event"
    assert result.interface.alarms[0].set_event == relationship.reference
    assert result.interface.unresolved_references == ()


def test_missing_target_is_explicitly_unresolved() -> None:
    result = resolve_references(alarm_reference(identifier="404"))
    relationship = result.relationships[0]
    assert relationship.state is ResolutionState.UNRESOLVED
    assert relationship.reason is UnresolvedReason.NOT_FOUND
    assert relationship.reference.target_key is None
    assert result.interface.unresolved_references[0].reason is UnresolvedReason.NOT_FOUND


def test_duplicate_identifier_is_indexed_without_overwrite_and_resolves_ambiguous() -> None:
    interface = EquipmentInterface(
        collection_events=(
            CollectionEvent(key="event/a", implementation_id="10"),
            CollectionEvent(key="event/b", implementation_id="10"),
        ),
        alarms=(
            Alarm(
                key="alarm",
                set_event=EntityReference(
                    target_types=(CanonicalType.COLLECTION_EVENT,), implementation_id="10"
                ),
            ),
        ),
    )
    indexes = build_reference_indexes(interface)
    assert indexes.by_type[CanonicalType.COLLECTION_EVENT] == ("event/a", "event/b")
    assert indexes.by_native_identifier[(CanonicalType.COLLECTION_EVENT, "10")] == (
        "event/a",
        "event/b",
    )

    result = resolve_references(interface, indexes)
    relationship = result.relationships[0]
    assert relationship.state is ResolutionState.AMBIGUOUS
    assert relationship.reason is UnresolvedReason.AMBIGUOUS
    assert relationship.reference.target_key is None
    assert relationship.candidate_keys == ("event/a", "event/b")
    assert result.interface.unresolved_references[0].candidate_keys == (
        "event/a",
        "event/b",
    )


def test_wrong_type_identifier_never_resolves() -> None:
    interface = EquipmentInterface(
        status_variables=(StatusVariable(key="status", implementation_id="10"),),
        alarms=(
            Alarm(
                key="alarm",
                set_event=EntityReference(
                    target_types=(CanonicalType.COLLECTION_EVENT,), implementation_id="10"
                ),
            ),
        ),
    )
    relationship = resolve_references(interface).relationships[0]
    assert relationship.state is ResolutionState.UNRESOLVED
    assert relationship.reason is UnresolvedReason.WRONG_TYPE
    assert relationship.reference.target_key is None


def test_reference_without_target_type_remains_explicitly_unsupported() -> None:
    interface = EquipmentInterface(
        status_variables=(StatusVariable(key="status", implementation_id="10"),),
        collection_events=(
            CollectionEvent(
                key="event",
                valid_data_variables=(EntityReference(implementation_id="10"),),
            ),
        ),
    )
    relationship = resolve_references(interface).relationships[0]
    assert relationship.state is ResolutionState.UNRESOLVED
    assert relationship.reason is UnresolvedReason.UNSUPPORTED
    assert relationship.reference.target_key is None


def test_multiple_selectors_must_identify_the_same_target() -> None:
    interface = EquipmentInterface(
        collection_events=(
            CollectionEvent(key="event/a", implementation_id="10", name="Other"),
            CollectionEvent(key="event/b", implementation_id="11", name="Ready"),
        ),
        alarms=(
            Alarm(
                key="alarm",
                set_event=EntityReference(
                    target_types=(CanonicalType.COLLECTION_EVENT,),
                    implementation_id="10",
                    name="Ready",
                ),
            ),
        ),
    )
    relationship = resolve_references(interface).relationships[0]
    assert relationship.state is ResolutionState.UNRESOLVED
    assert relationship.reason is UnresolvedReason.NOT_FOUND


def test_empty_and_lexically_distinct_identifiers_are_not_normalized() -> None:
    empty = EquipmentInterface(
        collection_events=(CollectionEvent(key="empty", implementation_id=""),),
        alarms=(
            Alarm(
                key="alarm",
                set_event=EntityReference(
                    target_types=(CanonicalType.COLLECTION_EVENT,), implementation_id=""
                ),
            ),
        ),
    )
    assert resolve_references(empty).relationships[0].state is ResolutionState.RESOLVED
    padded = replace(
        empty,
        alarms=(
            replace(
                empty.alarms[0],
                set_event=EntityReference(
                    target_types=(CanonicalType.COLLECTION_EVENT,), implementation_id="  "
                ),
            ),
        ),
    )
    assert resolve_references(padded).relationships[0].reason is UnresolvedReason.NOT_FOUND


def test_name_standard_designation_and_wkn_use_exact_indexes() -> None:
    wkn = WellKnownName(value="fictional.format", authority="example", scope="format")
    interface = EquipmentInterface(
        variable_formats=(VariableFormat(key="format", name="Unsigned", wkn=wkn),),
        standard_references=(
            StandardReference(key="standard", name="Display label", designation="Synthetic-1"),
        ),
        status_variables=(
            StatusVariable(
                key="status",
                format=EntityReference(target_types=(CanonicalType.VARIABLE_FORMAT,), wkn=wkn),
                standards=(
                    EntityReference(
                        target_types=(CanonicalType.STANDARD_REFERENCE,), name="Synthetic-1"
                    ),
                ),
            ),
        ),
    )
    result = resolve_references(interface)
    assert {item.reference.target_key for item in result.relationships} == {
        "format",
        "standard",
    }
    indexes = build_reference_indexes(interface)
    assert indexes.by_standard_designation["Synthetic-1"] == ("standard",)
    assert indexes.by_wkn[
        (CanonicalType.VARIABLE_FORMAT, "fictional.format", "example", "format")
    ] == ("format",)


def test_command_and_stream_function_indexes_preserve_collisions() -> None:
    interface = EquipmentInterface(
        remote_commands=(
            RemoteCommand(
                key="command/a",
                name="START",
                parameters=(RemoteCommandParameter(key="command/a/mode", name="MODE"),),
            ),
            RemoteCommand(
                key="command/b",
                name="START",
                parameters=(RemoteCommandParameter(key="command/b/mode", name="MODE"),),
            ),
        ),
        supported_messages=(
            SupportedMessage(key="message/a", stream=1, function=1),
            SupportedMessage(key="message/b", stream=1, function=1),
        ),
    )
    indexes = build_reference_indexes(interface)
    assert indexes.by_command_identity["START"] == ("command/a", "command/b")
    assert indexes.by_stream_function[(1, 1)] == ("message/a", "message/b")
    assert indexes.parameter_owner_by_key == {
        "command/a/mode": "command/a",
        "command/b/mode": "command/b",
    }


def test_nested_command_parameter_references_are_resolved_and_rebuilt() -> None:
    interface = EquipmentInterface(
        remote_commands=(
            RemoteCommand(
                key="command",
                parameters=(
                    RemoteCommandParameter(
                        key="parameter",
                        standards=(
                            EntityReference(
                                target_types=(CanonicalType.STANDARD_REFERENCE,),
                                name="Synthetic-1",
                            ),
                        ),
                    ),
                ),
            ),
        ),
        standard_references=(StandardReference(key="standard", designation="Synthetic-1"),),
    )
    result = resolve_references(interface)
    parameters = result.interface.remote_commands[0].parameters
    assert parameters is not None
    assert parameters[0].standards[0].target_key == "standard"
    assert result.relationships[0].owner_key == "parameter"


def test_synthetic_fixture_runs_parse_index_resolve_relationship_pipeline() -> None:
    parsed = load_interface(
        FIXTURES / "relationships/e172-event-alarm-report.xml", revision="E172-0225"
    ).interface
    result = resolve_references(parsed, build_reference_indexes(parsed))
    states = [item.state for item in result.relationships]
    assert states.count(ResolutionState.RESOLVED) == 4
    assert states.count(ResolutionState.UNRESOLVED) == 1
    assert states.count(ResolutionState.AMBIGUOUS) == 0
    assert len(states) == len(parsed.unresolved_references)
    assert result.interface.unresolved_references[0].reason is UnresolvedReason.NOT_FOUND
    assert resolve_references(result.interface) == result


def test_missing_selector_has_one_explicit_unresolved_state() -> None:
    interface = EquipmentInterface(
        alarms=(
            Alarm(
                key="alarm",
                set_event=EntityReference(target_types=(CanonicalType.COLLECTION_EVENT,)),
            ),
        )
    )
    result = resolve_references(interface)
    assert len(result.relationships) == 1
    assert result.relationships[0].state is ResolutionState.UNRESOLVED
    assert result.relationships[0].reason is UnresolvedReason.MISSING_SELECTOR


def test_indexes_from_another_interface_are_rejected_even_when_keys_match() -> None:
    first = alarm_reference(identifier="10")
    second = replace(
        first,
        collection_events=(replace(first.collection_events[0], implementation_id="11"),),
    )
    with pytest.raises(ModelValidationError, match="different interface"):
        resolve_references(second, build_reference_indexes(first))


def test_graph_layer_has_no_revision_adapter_dependency() -> None:
    graph_source = (Path(__file__).parents[1] / "src/sema_sedd/graph/resolution.py").read_text(
        encoding="utf-8"
    )
    assert "sema_sedd.adapters" not in graph_source
    assert "E172_0225" not in graph_source
