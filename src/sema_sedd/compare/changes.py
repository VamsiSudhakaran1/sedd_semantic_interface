"""Immutable semantic change records and explicit comparison uncertainty."""

from dataclasses import dataclass
from enum import StrEnum

from sema_sedd.compare._values import token
from sema_sedd.compare.matching import EntityMatch, MatchingResult
from sema_sedd.exceptions import ModelValidationError
from sema_sedd.model import CanonicalType, EquipmentInterface, EquipmentMetadata
from sema_sedd.model._base import Record
from sema_sedd.model.domain import InterfaceEntity
from sema_sedd.model.values import JsonValue


class ChangeCategory(StrEnum):
    INTERFACE_CHANGE = "INTERFACE_CHANGE"
    DOCUMENTATION_CHANGE = "DOCUMENTATION_CHANGE"
    UNKNOWN_CHANGE = "UNKNOWN_CHANGE"


class ChangeKind(StrEnum):
    ENTITY_ADDED = "ENTITY_ADDED"
    ENTITY_REMOVED = "ENTITY_REMOVED"
    ENTITY_MODIFIED = "ENTITY_MODIFIED"
    IMPLEMENTATION_ID_CHANGED = "IMPLEMENTATION_ID_CHANGED"
    WELL_KNOWN_NAME_CHANGED = "WELL_KNOWN_NAME_CHANGED"
    NAME_CHANGED = "NAME_CHANGED"
    DESCRIPTION_CHANGED = "DESCRIPTION_CHANGED"
    DATA_TYPE_CHANGED = "DATA_TYPE_CHANGED"
    FORMAT_CHANGED = "FORMAT_CHANGED"
    UNIT_CHANGED = "UNIT_CHANGED"
    RANGE_CHANGED = "RANGE_CHANGED"
    DEFAULT_CHANGED = "DEFAULT_CHANGED"
    RELATIONSHIP_ADDED = "RELATIONSHIP_ADDED"
    RELATIONSHIP_REMOVED = "RELATIONSHIP_REMOVED"
    RELATIONSHIP_CHANGED = "RELATIONSHIP_CHANGED"
    REPORT_CONTENT_CHANGED = "REPORT_CONTENT_CHANGED"
    EVENT_REPORT_LINK_CHANGED = "EVENT_REPORT_LINK_CHANGED"
    ALARM_EVENT_LINK_CHANGED = "ALARM_EVENT_LINK_CHANGED"
    COMMAND_PARAMETER_CHANGED = "COMMAND_PARAMETER_CHANGED"
    COMMAND_CHANGED = "COMMAND_CHANGED"
    MESSAGE_STRUCTURE_CHANGED = "MESSAGE_STRUCTURE_CHANGED"
    SUPPORTED_MESSAGE_CHANGED = "SUPPORTED_MESSAGE_CHANGED"
    STANDARD_METADATA_CHANGED = "STANDARD_METADATA_CHANGED"
    STATE_TRANSITION_CHANGED = "STATE_TRANSITION_CHANGED"
    EQUIPMENT_METADATA_CHANGED = "EQUIPMENT_METADATA_CHANGED"
    INTERFACE_METADATA_CHANGED = "INTERFACE_METADATA_CHANGED"
    ALARM_CHANGED = "ALARM_CHANGED"
    IDENTITY_EVIDENCE_CHANGED = "IDENTITY_EVIDENCE_CHANGED"
    DOCUMENTATION_CHANGED = "DOCUMENTATION_CHANGED"
    UNKNOWN_CHANGE = "UNKNOWN_CHANGE"


class IssueKind(StrEnum):
    AMBIGUOUS_IDENTITY = "AMBIGUOUS_IDENTITY"
    INSUFFICIENT_IDENTITY = "INSUFFICIENT_IDENTITY"
    UNRESOLVED_REFERENCE = "UNRESOLVED_REFERENCE"
    UNCERTAIN_TARGET_IDENTITY = "UNCERTAIN_TARGET_IDENTITY"
    UNKNOWN_CONTENT = "UNKNOWN_CONTENT"


@dataclass(frozen=True, slots=True, kw_only=True)
class ComparisonIssue(Record):
    kind: IssueKind
    side: str
    entity_key: str | None
    entity_type: CanonicalType | None = None
    field: str | None = None
    detail: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PropertyChange(Record):
    field: str
    kind: ChangeKind
    category: ChangeCategory
    old_value: JsonValue
    new_value: JsonValue

    def __post_init__(self) -> None:
        Record.__post_init__(self)
        if not self.field or token(self.old_value) == token(self.new_value):
            raise ModelValidationError("Property change requires a field and distinct values")


@dataclass(frozen=True, slots=True, kw_only=True)
class RelationshipChange(Record):
    """One relationship role, including ordered contents and multiset deltas."""

    field: str
    kind: ChangeKind
    category: ChangeCategory
    old_value: JsonValue
    new_value: JsonValue
    added: tuple[JsonValue, ...] = ()
    removed: tuple[JsonValue, ...] = ()
    order_changed: bool = False
    presence_changed: bool = False

    def __post_init__(self) -> None:
        Record.__post_init__(self)
        if not self.field or token(self.old_value) == token(self.new_value):
            raise ModelValidationError("Relationship change requires distinct role values")


type ChangeSubject = InterfaceEntity | EquipmentMetadata | EquipmentInterface

_DOMAIN_KINDS = {
    CanonicalType.REMOTE_COMMAND_PARAMETER: ChangeKind.COMMAND_PARAMETER_CHANGED,
    CanonicalType.SUPPORTED_MESSAGE: ChangeKind.SUPPORTED_MESSAGE_CHANGED,
    CanonicalType.EVENT_REPORT_LINK: ChangeKind.EVENT_REPORT_LINK_CHANGED,
    CanonicalType.STANDARD_REFERENCE: ChangeKind.STANDARD_METADATA_CHANGED,
    CanonicalType.DEFAULT_REPORT: ChangeKind.REPORT_CONTENT_CHANGED,
}


@dataclass(frozen=True, slots=True, kw_only=True)
class EntityChange(Record):
    kind: ChangeKind
    old_entity: ChangeSubject | None
    new_entity: ChangeSubject | None
    match: EntityMatch | None = None
    properties: tuple[PropertyChange, ...] = ()
    relationships: tuple[RelationshipChange, ...] = ()

    def __post_init__(self) -> None:
        Record.__post_init__(self)
        if self.kind is ChangeKind.ENTITY_ADDED:
            valid = self.old_entity is None and self.new_entity is not None and self.match is None
        elif self.kind is ChangeKind.ENTITY_REMOVED:
            valid = self.old_entity is not None and self.new_entity is None and self.match is None
        elif self.kind is ChangeKind.ENTITY_MODIFIED:
            valid = (
                self.old_entity is not None
                and self.new_entity is not None
                and self.old_entity.canonical_type is self.new_entity.canonical_type
                and bool(self.properties or self.relationships)
            )
        else:
            valid = False
        if not valid:
            raise ModelValidationError("Entity change has inconsistent presence or kind")
        if self.match is not None and (
            self.match.old_entity != self.old_entity or self.match.new_entity != self.new_entity
        ):
            raise ModelValidationError("Entity change match belongs to different entities")

    @property
    def entity_type(self) -> CanonicalType:
        entity = self.new_entity if self.new_entity is not None else self.old_entity
        assert entity is not None
        return entity.canonical_type

    @property
    def kinds(self) -> tuple[ChangeKind, ...]:
        result = {self.kind, *(item.kind for item in self.properties + self.relationships)}
        for relationship in self.relationships:
            if relationship.category is ChangeCategory.INTERFACE_CHANGE:
                if relationship.added:
                    result.add(ChangeKind.RELATIONSHIP_ADDED)
                if relationship.removed:
                    result.add(ChangeKind.RELATIONSHIP_REMOVED)
        if self.kind is not ChangeKind.ENTITY_MODIFIED and self.entity_type in _DOMAIN_KINDS:
            result.add(_DOMAIN_KINDS[self.entity_type])
        return tuple(sorted(result))

    @property
    def categories(self) -> tuple[ChangeCategory, ...]:
        if self.kind is not ChangeKind.ENTITY_MODIFIED:
            return (ChangeCategory.INTERFACE_CHANGE,)
        return tuple(sorted({item.category for item in self.properties + self.relationships}))


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangeSet(Record):
    matching: MatchingResult
    entity_changes: tuple[EntityChange, ...] = ()
    issues: tuple[ComparisonIssue, ...] = ()

    @property
    def is_complete(self) -> bool:
        """False means an empty change list is not proof of equivalence."""
        return not self.issues and not any(
            ChangeCategory.UNKNOWN_CHANGE in entity.categories for entity in self.entity_changes
        )

    @property
    def has_interface_changes(self) -> bool:
        return any(ChangeCategory.INTERFACE_CHANGE in e.categories for e in self.entity_changes)

    @property
    def has_documentation_changes(self) -> bool:
        return any(ChangeCategory.DOCUMENTATION_CHANGE in e.categories for e in self.entity_changes)
