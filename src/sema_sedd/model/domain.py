"""Canonical interface entities. Source adapters own revision-specific extraction."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field, fields
from typing import ClassVar

from sema_sedd.exceptions import ModelValidationError
from sema_sedd.model._base import Record, require_nonempty
from sema_sedd.model.values import (
    CanonicalType,
    DataStructure,
    EntityReference,
    JsonObject,
    MessageDirection,
    Requiredness,
    SourceProvenance,
    StateTransition,
    UnknownExtension,
    UnresolvedReference,
    WellKnownName,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class SemanticRecord(Record):
    name: str | None = None
    description: str | None = None
    implementation_id: str | None = None
    wkn: WellKnownName | None = None
    provenance: tuple[SourceProvenance, ...] = ()
    unknown_extensions: tuple[UnknownExtension, ...] = ()
    extension_metadata: JsonObject = JsonObject()
    declared_source: str | None = None
    standards: tuple[EntityReference, ...] = field(
        default=(), metadata={"target_types": (CanonicalType.STANDARD_REFERENCE,)}
    )

    def __post_init__(self) -> None:
        Record.__post_init__(self)
        for reference, allowed in _references_with_roles(self):
            if allowed and any(kind not in allowed for kind in reference.target_types):
                raise ModelValidationError("Reference target type conflicts with relationship role")


@dataclass(frozen=True, slots=True, kw_only=True)
class Entity(SemanticRecord):
    """Key is local to one interface; native IDs and WKNs are separate evidence."""

    key: str

    def __post_init__(self) -> None:
        SemanticRecord.__post_init__(self)
        require_nonempty(self.key, "entity key")


@dataclass(frozen=True, slots=True, kw_only=True)
class EquipmentMetadata(SemanticRecord):
    canonical_type: ClassVar[CanonicalType] = CanonicalType.EQUIPMENT_METADATA
    model: str | None = None
    software_revision: str | None = None
    supplier: str | None = None
    created_date: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Variable(Entity):
    format: EntityReference | None = field(
        default=None, metadata={"target_types": (CanonicalType.VARIABLE_FORMAT,)}
    )
    data_type: str | None = None
    units: tuple[str, ...] = ()
    minimum: str | None = None
    maximum: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class StatusVariable(Variable):
    canonical_type: ClassVar[CanonicalType] = CanonicalType.STATUS_VARIABLE


@dataclass(frozen=True, slots=True, kw_only=True)
class DataVariable(Variable):
    canonical_type: ClassVar[CanonicalType] = CanonicalType.DATA_VARIABLE


@dataclass(frozen=True, slots=True, kw_only=True)
class EquipmentConstant(Variable):
    canonical_type: ClassVar[CanonicalType] = CanonicalType.EQUIPMENT_CONSTANT
    default: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CollectionEvent(Entity):
    canonical_type: ClassVar[CanonicalType] = CanonicalType.COLLECTION_EVENT
    valid_data_variables: tuple[EntityReference, ...] | None = None
    relevant_variables: tuple[EntityReference, ...] | None = None
    state_transition: StateTransition | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Alarm(Entity):
    canonical_type: ClassVar[CanonicalType] = CanonicalType.ALARM
    code: int | None = None
    text: str | None = None
    set_event: EntityReference | None = field(
        default=None, metadata={"target_types": (CanonicalType.COLLECTION_EVENT,)}
    )
    clear_event: EntityReference | None = field(
        default=None, metadata={"target_types": (CanonicalType.COLLECTION_EVENT,)}
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class RemoteCommandParameter(Entity):
    canonical_type: ClassVar[CanonicalType] = CanonicalType.REMOTE_COMMAND_PARAMETER
    requiredness: Requiredness | None = None
    value_format: tuple[DataStructure, ...] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class RemoteCommand(Entity):
    canonical_type: ClassVar[CanonicalType] = CanonicalType.REMOTE_COMMAND
    parameters: tuple[RemoteCommandParameter, ...] | None = None
    object_specifiers: tuple[str, ...] = ()
    use_s2f21: bool | None = None
    use_s2f41: bool | None = None
    use_s2f49: bool | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SupportedMessage(Entity):
    canonical_type: ClassVar[CanonicalType] = CanonicalType.SUPPORTED_MESSAGE
    stream: int | None = None
    function: int | None = None
    direction: MessageDirection | None = None
    mnemonic: str | None = None
    reply_bit: bool | None = None
    reply_option: str | None = None
    blocking: str | None = None
    transport: str | None = None
    structure: tuple[DataStructure, ...] | None = None
    header: str | None = None
    exceptions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class VariableFormat(Entity):
    canonical_type: ClassVar[CanonicalType] = CanonicalType.VARIABLE_FORMAT
    structure: tuple[DataStructure, ...] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DefaultReport(Entity):
    canonical_type: ClassVar[CanonicalType] = CanonicalType.DEFAULT_REPORT
    variables: tuple[EntityReference, ...] | None = field(
        default=None,
        metadata={
            "target_types": (
                CanonicalType.STATUS_VARIABLE,
                CanonicalType.DATA_VARIABLE,
                CanonicalType.EQUIPMENT_CONSTANT,
            )
        },
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class EventReportLink(Entity):
    canonical_type: ClassVar[CanonicalType] = CanonicalType.EVENT_REPORT_LINK
    event: EntityReference | None = field(
        default=None, metadata={"target_types": (CanonicalType.COLLECTION_EVENT,)}
    )
    reports: tuple[EntityReference, ...] | None = field(
        default=None, metadata={"target_types": (CanonicalType.DEFAULT_REPORT,)}
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class StandardReference(Entity):
    canonical_type: ClassVar[CanonicalType] = CanonicalType.STANDARD_REFERENCE
    designation: str | None = None
    revision: str | None = None
    requirements: tuple[JsonObject, ...] = ()
    notes: tuple[str, ...] = ()


type InterfaceEntity = (
    StatusVariable
    | DataVariable
    | EquipmentConstant
    | CollectionEvent
    | Alarm
    | RemoteCommand
    | RemoteCommandParameter
    | SupportedMessage
    | VariableFormat
    | DefaultReport
    | EventReportLink
    | StandardReference
)


def _records(value: object) -> Iterator[Record]:
    if isinstance(value, Record):
        yield value
        for member in fields(value):
            yield from _records(getattr(value, member.name))
    elif isinstance(value, tuple):
        for item in value:
            yield from _records(item)


def _references_with_roles(
    record: Record,
) -> Iterator[tuple[EntityReference, tuple[CanonicalType, ...]]]:
    for member in fields(record):
        value = getattr(record, member.name)
        allowed = member.metadata.get("target_types", ())
        if isinstance(value, EntityReference):
            yield value, allowed
        elif isinstance(value, tuple):
            for item in value:
                if isinstance(item, EntityReference):
                    yield item, allowed


@dataclass(frozen=True, slots=True, kw_only=True)
class EquipmentInterface(SemanticRecord):
    canonical_type: ClassVar[CanonicalType] = CanonicalType.EQUIPMENT_INTERFACE
    equipment: EquipmentMetadata = EquipmentMetadata()
    status_variables: tuple[StatusVariable, ...] = field(default=(), metadata={"unordered": True})
    data_variables: tuple[DataVariable, ...] = field(default=(), metadata={"unordered": True})
    equipment_constants: tuple[EquipmentConstant, ...] = field(
        default=(), metadata={"unordered": True}
    )
    collection_events: tuple[CollectionEvent, ...] = field(default=(), metadata={"unordered": True})
    alarms: tuple[Alarm, ...] = field(default=(), metadata={"unordered": True})
    remote_commands: tuple[RemoteCommand, ...] = field(default=(), metadata={"unordered": True})
    supported_messages: tuple[SupportedMessage, ...] = field(
        default=(), metadata={"unordered": True}
    )
    variable_formats: tuple[VariableFormat, ...] = field(default=(), metadata={"unordered": True})
    default_reports: tuple[DefaultReport, ...] = field(default=(), metadata={"unordered": True})
    event_report_links: tuple[EventReportLink, ...] = field(
        default=(), metadata={"unordered": True}
    )
    standard_references: tuple[StandardReference, ...] = field(
        default=(), metadata={"unordered": True}
    )
    unresolved_references: tuple[UnresolvedReference, ...] = field(
        default=(), metadata={"unordered": True}
    )
    reports_can_be_deleted: bool | None = None
    event_report_links_can_be_deleted: bool | None = None

    def entities(self) -> tuple[InterfaceEntity, ...]:
        """Return all records, including scoped command parameters, without merging."""
        parameters = tuple(
            parameter for command in self.remote_commands for parameter in command.parameters or ()
        )
        return (
            *self.status_variables,
            *self.data_variables,
            *self.equipment_constants,
            *self.collection_events,
            *self.alarms,
            *self.remote_commands,
            *parameters,
            *self.supported_messages,
            *self.variable_formats,
            *self.default_reports,
            *self.event_report_links,
            *self.standard_references,
        )

    def __post_init__(self) -> None:
        SemanticRecord.__post_init__(self)
        entities = self.entities()
        catalogue = {entity.key: entity for entity in entities}
        if len(catalogue) != len(entities):
            raise ModelValidationError("Duplicate document-local entity key")
        parameter_owners = {
            parameter.key: command.key
            for command in self.remote_commands
            for parameter in command.parameters or ()
        }
        for record in _records(self):
            for reference, allowed in _references_with_roles(record):
                if reference.scope_key is not None and reference.scope_key not in catalogue:
                    raise ModelValidationError("Unknown reference scope key")
                if reference.target_key is not None:
                    self._check_target(reference, reference.target_key, catalogue, parameter_owners)
                    if allowed and catalogue[reference.target_key].canonical_type not in allowed:
                        raise ModelValidationError(
                            "Resolved target conflicts with relationship role"
                        )
            if isinstance(record, UnresolvedReference):
                if record.owner_key not in catalogue:
                    raise ModelValidationError("Unknown unresolved reference owner key")
                for key in record.candidate_keys:
                    self._check_target(record.reference, key, catalogue, parameter_owners)

    @staticmethod
    def _check_target(
        reference: EntityReference,
        key: str,
        catalogue: dict[str, InterfaceEntity],
        parameter_owners: dict[str, str],
    ) -> None:
        if key not in catalogue:
            raise ModelValidationError("Unknown reference target or candidate key")
        if reference.target_types and catalogue[key].canonical_type not in reference.target_types:
            raise ModelValidationError("Target conflicts with reference target types")
        if reference.scope_key is not None and key in parameter_owners:
            if parameter_owners[key] != reference.scope_key:
                raise ModelValidationError("Parameter target conflicts with command scope")


# The contract's name and Prompt 4's name designate one model, not two layers.
CanonicalEquipmentInterface = EquipmentInterface
