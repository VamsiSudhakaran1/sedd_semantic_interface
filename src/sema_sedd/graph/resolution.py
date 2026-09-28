"""Revision-neutral, exact reference indexing and resolution."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Any, cast

from sema_sedd.exceptions import ModelValidationError
from sema_sedd.limits import MAX_CANDIDATE_OCCURRENCES, WorkBudget
from sema_sedd.model import (
    CanonicalType,
    EntityReference,
    EquipmentInterface,
    RemoteCommand,
    StandardReference,
    SupportedMessage,
    UnresolvedReason,
    UnresolvedReference,
    WellKnownName,
)
from sema_sedd.model.domain import InterfaceEntity

type TypeIdentity = tuple[CanonicalType, str]
type WknIdentity = tuple[CanonicalType, str, str | None, str | None]
type StreamFunctionIdentity = tuple[int, int]


class ResolutionState(StrEnum):
    """The exhaustive states produced for a canonical reference occurrence."""

    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class ReferenceIndexes:
    """Immutable, collision-preserving exact indexes for one interface."""

    entities_by_key: Mapping[str, InterfaceEntity]
    by_type: Mapping[CanonicalType, tuple[str, ...]]
    by_native_identifier: Mapping[TypeIdentity, tuple[str, ...]]
    by_name: Mapping[TypeIdentity, tuple[str, ...]]
    by_wkn: Mapping[WknIdentity, tuple[str, ...]]
    by_command_identity: Mapping[str, tuple[str, ...]]
    by_stream_function: Mapping[StreamFunctionIdentity, tuple[str, ...]]
    by_standard_designation: Mapping[str, tuple[str, ...]]
    parameter_owner_by_key: Mapping[str, str]

    def __post_init__(self) -> None:
        expected = set(self.entities_by_key)
        for index in (
            self.by_type,
            self.by_native_identifier,
            self.by_name,
            self.by_wkn,
            self.by_command_identity,
            self.by_stream_function,
            self.by_standard_designation,
        ):
            for keys in index.values():
                if tuple(sorted(set(keys))) != keys:
                    raise ModelValidationError("Reference index keys must be unique and sorted")
                if not set(keys) <= expected:
                    raise ModelValidationError("Reference index contains an unknown entity key")


@dataclass(frozen=True, slots=True, kw_only=True)
class Relationship:
    """One source reference and its exact resolution outcome."""

    owner_key: str
    role: str
    reference: EntityReference
    state: ResolutionState
    reason: UnresolvedReason | None = None
    candidate_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.reference) is not EntityReference or type(self.state) is not ResolutionState:
            raise ModelValidationError("Relationship has an invalid reference or state")
        if not self.owner_key or not self.role:
            raise ModelValidationError("Relationship owner and role must be nonempty")
        if tuple(sorted(set(self.candidate_keys))) != self.candidate_keys:
            raise ModelValidationError("Relationship candidates must be unique and sorted")
        if self.state is ResolutionState.RESOLVED:
            if self.reference.target_key is None or self.reason is not None or self.candidate_keys:
                raise ModelValidationError("Resolved relationship has inconsistent state")
        elif self.state is ResolutionState.AMBIGUOUS:
            if (
                self.reference.target_key is not None
                or self.reason is not UnresolvedReason.AMBIGUOUS
                or len(self.candidate_keys) < 2
            ):
                raise ModelValidationError("Ambiguous relationship has inconsistent state")
        elif (
            self.reference.target_key is not None
            or self.reason
            not in {
                UnresolvedReason.NOT_FOUND,
                UnresolvedReason.WRONG_TYPE,
                UnresolvedReason.MISSING_SELECTOR,
                UnresolvedReason.UNSUPPORTED,
            }
            or self.candidate_keys
        ):
            raise ModelValidationError("Unresolved relationship has inconsistent state")


@dataclass(frozen=True, slots=True, kw_only=True)
class RelationshipModel:
    """A resolved canonical interface plus one outcome for every entity reference."""

    interface: EquipmentInterface
    relationships: tuple[Relationship, ...]

    def __post_init__(self) -> None:
        if type(self.interface) is not EquipmentInterface or not isinstance(
            self.relationships, tuple
        ):
            raise ModelValidationError("Invalid relationship model fields")
        if any(type(item) is not Relationship for item in self.relationships):
            raise ModelValidationError("Invalid relationship model entry")
        pairs = [(item.owner_key, item.role) for item in self.relationships]
        if len(set(pairs)) != len(pairs):
            raise ModelValidationError("Duplicate relationship occurrence")
        expected = {
            (owner, role): reference
            for owner, role, reference in _reference_occurrences(self.interface)
        }
        actual = {(item.owner_key, item.role): item.reference for item in self.relationships}
        if actual != expected:
            raise ModelValidationError("Relationship model does not cover every entity reference")
        ledger = {
            (item.owner_key, item.relationship): item
            for item in self.interface.unresolved_references
        }
        if len(ledger) != len(self.interface.unresolved_references):
            raise ModelValidationError("Duplicate unresolved-ledger occurrence")
        nonresolved = {
            (item.owner_key, item.role): item
            for item in self.relationships
            if item.state is not ResolutionState.RESOLVED
        }
        if set(ledger) != set(nonresolved):
            raise ModelValidationError("Relationship states conflict with the unresolved ledger")
        for occurrence, item in nonresolved.items():
            pending = ledger[occurrence]
            if (
                pending.reference != item.reference
                or pending.reason is not item.reason
                or pending.candidate_keys != item.candidate_keys
            ):
                raise ModelValidationError(
                    "Relationship outcome conflicts with the unresolved ledger"
                )


def _frozen_index[K](source: Mapping[K, Iterable[str]]) -> Mapping[K, tuple[str, ...]]:
    ordered = {
        key: tuple(sorted(set(values)))
        for key, values in sorted(source.items(), key=lambda item: repr(item[0]))
    }
    return MappingProxyType(ordered)


def _wkn_key(kind: CanonicalType, wkn: WellKnownName) -> WknIdentity:
    return (kind, wkn.value, wkn.authority, wkn.scope)


def build_reference_indexes(interface: EquipmentInterface) -> ReferenceIndexes:
    """Index exact evidence without normalizing or selecting collision winners."""
    if type(interface) is not EquipmentInterface:
        raise ModelValidationError("Reference indexing requires EquipmentInterface")

    entities = {entity.key: entity for entity in interface.entities()}
    by_type: defaultdict[CanonicalType, list[str]] = defaultdict(list)
    by_native: defaultdict[TypeIdentity, list[str]] = defaultdict(list)
    by_name: defaultdict[TypeIdentity, list[str]] = defaultdict(list)
    by_wkn: defaultdict[WknIdentity, list[str]] = defaultdict(list)
    commands: defaultdict[str, list[str]] = defaultdict(list)
    messages: defaultdict[StreamFunctionIdentity, list[str]] = defaultdict(list)
    standards: defaultdict[str, list[str]] = defaultdict(list)
    parameter_owners = {
        parameter.key: command.key
        for command in interface.remote_commands
        for parameter in command.parameters or ()
    }

    for entity in entities.values():
        kind = entity.canonical_type
        by_type[kind].append(entity.key)
        if entity.implementation_id is not None:
            by_native[(kind, entity.implementation_id)].append(entity.key)
        if entity.name is not None:
            by_name[(kind, entity.name)].append(entity.key)
        if entity.wkn is not None:
            by_wkn[_wkn_key(kind, entity.wkn)].append(entity.key)
        if isinstance(entity, RemoteCommand) and entity.name is not None:
            commands[entity.name].append(entity.key)
        if (
            isinstance(entity, SupportedMessage)
            and entity.stream is not None
            and entity.function is not None
        ):
            messages[(entity.stream, entity.function)].append(entity.key)
        if isinstance(entity, StandardReference) and entity.designation is not None:
            standards[entity.designation].append(entity.key)

    return ReferenceIndexes(
        entities_by_key=MappingProxyType(dict(sorted(entities.items()))),
        by_type=_frozen_index(by_type),
        by_native_identifier=_frozen_index(by_native),
        by_name=_frozen_index(by_name),
        by_wkn=_frozen_index(by_wkn),
        by_command_identity=_frozen_index(commands),
        by_stream_function=_frozen_index(messages),
        by_standard_designation=_frozen_index(standards),
        parameter_owner_by_key=MappingProxyType(dict(sorted(parameter_owners.items()))),
    )


def _reference_occurrences(
    interface: EquipmentInterface,
) -> tuple[tuple[str, str, EntityReference], ...]:
    occurrences = []
    for entity in interface.entities():
        for member in fields(entity):
            value = getattr(entity, member.name)
            if isinstance(value, EntityReference):
                occurrences.append((entity.key, member.name, value))
            elif isinstance(value, tuple):
                occurrences.extend(
                    (entity.key, f"{member.name}[{index}]", item)
                    for index, item in enumerate(value)
                    if isinstance(item, EntityReference)
                )
    return tuple(occurrences)


def _keys_for_types(
    index: Mapping[TypeIdentity, tuple[str, ...]],
    value: str,
    kinds: tuple[CanonicalType, ...],
) -> set[str]:
    return {key for kind in kinds or tuple(CanonicalType) for key in index.get((kind, value), ())}


def _wkn_keys(
    indexes: ReferenceIndexes,
    wkn: WellKnownName,
    kinds: tuple[CanonicalType, ...],
) -> set[str]:
    return {
        key
        for kind in kinds or tuple(CanonicalType)
        for key in indexes.by_wkn.get(_wkn_key(kind, wkn), ())
    }


def _selector_sets(
    reference: EntityReference,
    indexes: ReferenceIndexes,
    kinds: tuple[CanonicalType, ...],
) -> list[set[str]]:
    result = []
    if reference.implementation_id is not None:
        result.append(
            _keys_for_types(indexes.by_native_identifier, reference.implementation_id, kinds)
        )
    if reference.name is not None:
        names = _keys_for_types(indexes.by_name, reference.name, kinds)
        if not kinds or CanonicalType.REMOTE_COMMAND in kinds:
            names.update(indexes.by_command_identity.get(reference.name, ()))
        if not kinds or CanonicalType.STANDARD_REFERENCE in kinds:
            names.update(indexes.by_standard_designation.get(reference.name, ()))
        result.append(names)
    if reference.wkn is not None:
        result.append(_wkn_keys(indexes, reference.wkn, kinds))
    return result


def _candidates(
    reference: EntityReference, indexes: ReferenceIndexes, kinds: tuple[CanonicalType, ...]
) -> set[str] | None:
    selections = _selector_sets(reference, indexes, kinds)
    if not selections:
        return None
    result = selections[0]
    for selection in selections[1:]:
        result &= selection
    if reference.scope_key is not None:
        result = {
            key
            for key in result
            if key not in indexes.parameter_owner_by_key
            or indexes.parameter_owner_by_key[key] == reference.scope_key
        }
    return result


def _resolve_one(
    owner: str, role: str, reference: EntityReference, indexes: ReferenceIndexes
) -> Relationship:
    if reference.target_key is not None:
        return Relationship(
            owner_key=owner,
            role=role,
            reference=reference,
            state=ResolutionState.RESOLVED,
        )

    if all(value is None for value in (reference.implementation_id, reference.name, reference.wkn)):
        return Relationship(
            owner_key=owner,
            role=role,
            reference=reference,
            state=ResolutionState.UNRESOLVED,
            reason=UnresolvedReason.MISSING_SELECTOR,
        )
    if not reference.target_types:
        return Relationship(
            owner_key=owner,
            role=role,
            reference=reference,
            state=ResolutionState.UNRESOLVED,
            reason=UnresolvedReason.UNSUPPORTED,
        )

    candidates = _candidates(reference, indexes, reference.target_types)
    if candidates is None:  # Covered by the selector check above.
        raise ModelValidationError("Reference selector state changed during resolution")
    if len(candidates) == 1:
        target = next(iter(candidates))
        return Relationship(
            owner_key=owner,
            role=role,
            reference=replace(reference, target_key=target),
            state=ResolutionState.RESOLVED,
        )
    if len(candidates) > 1:
        return Relationship(
            owner_key=owner,
            role=role,
            reference=reference,
            state=ResolutionState.AMBIGUOUS,
            reason=UnresolvedReason.AMBIGUOUS,
            candidate_keys=tuple(sorted(candidates)),
        )

    reason = UnresolvedReason.NOT_FOUND
    if reference.target_types:
        untyped = _candidates(reference, indexes, ())
        if untyped:
            reason = UnresolvedReason.WRONG_TYPE
    return Relationship(
        owner_key=owner,
        role=role,
        reference=reference,
        state=ResolutionState.UNRESOLVED,
        reason=reason,
    )


def _replace_entity_references(
    entity: InterfaceEntity, outcomes: Mapping[tuple[str, str], Relationship]
) -> InterfaceEntity:
    changes: dict[str, object] = {}
    for member in fields(entity):
        value = getattr(entity, member.name)
        if isinstance(value, EntityReference):
            changes[member.name] = outcomes[(entity.key, member.name)].reference
        elif isinstance(value, tuple) and any(isinstance(item, EntityReference) for item in value):
            changes[member.name] = tuple(
                outcomes[(entity.key, f"{member.name}[{index}]")].reference
                if isinstance(item, EntityReference)
                else item
                for index, item in enumerate(value)
            )
    return cast(InterfaceEntity, replace(cast(Any, entity), **changes))


def _updated_entities[T: InterfaceEntity](
    entities: tuple[T, ...], updated: Mapping[str, InterfaceEntity]
) -> tuple[T, ...]:
    return tuple(cast(T, updated[entity.key]) for entity in entities)


def resolve_references(
    interface: EquipmentInterface, indexes: ReferenceIndexes | None = None
) -> RelationshipModel:
    """Resolve exact selectors and return an exhaustive relationship model."""
    indexes = indexes or build_reference_indexes(interface)
    if dict(indexes.entities_by_key) != {entity.key: entity for entity in interface.entities()}:
        raise ModelValidationError("Reference indexes belong to a different interface")

    budget = WorkBudget(MAX_CANDIDATE_OCCURRENCES, "Reference candidate occurrences")

    def outcomes_with_budget() -> Iterable[Relationship]:
        for owner, role, reference in _reference_occurrences(interface):
            outcome = _resolve_one(owner, role, reference, indexes)
            budget.consume(len(outcome.candidate_keys))
            yield outcome

    relationships = tuple(
        sorted(
            outcomes_with_budget(),
            key=lambda item: (item.owner_key, item.role),
        )
    )
    outcomes = {(item.owner_key, item.role): item for item in relationships}
    updated = {
        entity.key: _replace_entity_references(entity, outcomes) for entity in interface.entities()
    }

    commands = tuple(
        replace(
            cast(RemoteCommand, updated[command.key]),
            parameters=_updated_entities(command.parameters or (), updated)
            if command.parameters is not None
            else None,
        )
        for command in interface.remote_commands
    )
    unresolved = tuple(
        UnresolvedReference(
            owner_key=item.owner_key,
            relationship=item.role,
            reference=item.reference,
            reason=cast(UnresolvedReason, item.reason),
            candidate_keys=item.candidate_keys,
            provenance=item.reference.provenance,
        )
        for item in relationships
        if item.state is not ResolutionState.RESOLVED
    )
    resolved_interface = replace(
        interface,
        status_variables=_updated_entities(interface.status_variables, updated),
        data_variables=_updated_entities(interface.data_variables, updated),
        equipment_constants=_updated_entities(interface.equipment_constants, updated),
        collection_events=_updated_entities(interface.collection_events, updated),
        alarms=_updated_entities(interface.alarms, updated),
        remote_commands=commands,
        supported_messages=_updated_entities(interface.supported_messages, updated),
        variable_formats=_updated_entities(interface.variable_formats, updated),
        default_reports=_updated_entities(interface.default_reports, updated),
        event_report_links=_updated_entities(interface.event_report_links, updated),
        standard_references=_updated_entities(interface.standard_references, updated),
        unresolved_references=unresolved,
    )
    return RelationshipModel(interface=resolved_interface, relationships=relationships)
