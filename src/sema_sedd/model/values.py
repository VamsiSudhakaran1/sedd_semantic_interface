"""XML-independent value objects and explicit evidence/unknown states."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar

from sema_sedd.exceptions import ModelValidationError
from sema_sedd.model._base import Record, require_nonempty


class CanonicalType(StrEnum):
    EQUIPMENT_INTERFACE = "equipment_interface"
    EQUIPMENT_METADATA = "equipment_metadata"
    STATUS_VARIABLE = "status_variable"
    DATA_VARIABLE = "data_variable"
    EQUIPMENT_CONSTANT = "equipment_constant"
    COLLECTION_EVENT = "collection_event"
    ALARM = "alarm"
    REMOTE_COMMAND = "remote_command"
    REMOTE_COMMAND_PARAMETER = "remote_command_parameter"
    SUPPORTED_MESSAGE = "supported_message"
    VARIABLE_FORMAT = "variable_format"
    DEFAULT_REPORT = "default_report"
    EVENT_REPORT_LINK = "event_report_link"
    STANDARD_REFERENCE = "standard_reference"
    WELL_KNOWN_NAME = "well_known_name"
    ENTITY_REFERENCE = "entity_reference"
    SOURCE_PROVENANCE = "source_provenance"
    UNRESOLVED_REFERENCE = "unresolved_reference"
    UNKNOWN_EXTENSION = "unknown_extension"
    DATA_STRUCTURE = "data_structure"
    STATE_TRANSITION = "state_transition"


class WknAuthority(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"


class Requiredness(StrEnum):
    YES = "yes"
    NO = "no"
    CONDITIONAL = "conditional"
    UNKNOWN = "unknown"


class MessageDirection(StrEnum):
    HOST_TO_EQUIPMENT = "host_to_equipment"
    EQUIPMENT_TO_HOST = "equipment_to_host"
    BOTH = "both"
    UNKNOWN = "unknown"


class UnresolvedReason(StrEnum):
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    MISSING_SELECTOR = "missing_selector"
    UNSUPPORTED = "unsupported"
    NOT_ATTEMPTED = "not_attempted"


@dataclass(frozen=True, slots=True, kw_only=True)
class JsonObject(Record):
    """Immutable JSON object; repeated member names are rejected, not overwritten."""

    entries: tuple[tuple[str, JsonValue], ...] = ()

    def __post_init__(self) -> None:
        Record.__post_init__(self)
        keys = [key for key, _ in self.entries]
        if len(set(keys)) != len(keys):
            raise ModelValidationError("Duplicate JSON object member")


@dataclass(frozen=True, slots=True, kw_only=True)
class JsonArray(Record):
    items: tuple[JsonValue, ...] = ()


type JsonValue = str | int | float | bool | None | JsonObject | JsonArray


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceProvenance(Record):
    canonical_type: ClassVar[CanonicalType] = CanonicalType.SOURCE_PROVENANCE
    source_document: str
    source_revision: str | None = None
    source_path: str | None = None
    path_kind: str | None = None
    source_identifier: str | None = None
    line: int | None = None
    column: int | None = None

    def __post_init__(self) -> None:
        Record.__post_init__(self)
        require_nonempty(self.source_document, "source_document")
        if any(value is not None and value < 1 for value in (self.line, self.column)):
            raise ModelValidationError("Source positions must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class WellKnownName(Record):
    canonical_type: ClassVar[CanonicalType] = CanonicalType.WELL_KNOWN_NAME
    value: str
    authority: str | None = None
    scope: str | None = None
    authority_status: WknAuthority = WknAuthority.UNVERIFIED
    provenance: tuple[SourceProvenance, ...] = ()

    def __post_init__(self) -> None:
        Record.__post_init__(self)
        if self.authority_status is WknAuthority.VERIFIED:
            if not self.authority or not self.scope or not self.provenance:
                raise ModelValidationError("Verified WKN needs authority, scope, and provenance")
            require_nonempty(self.value, "verified WKN value")
            require_nonempty(self.authority, "WKN authority")
            require_nonempty(self.scope, "WKN scope")


@dataclass(frozen=True, slots=True, kw_only=True)
class UnknownExtension(Record):
    """Opaque source content; preservation makes no claim of schema validity."""

    canonical_type: ClassVar[CanonicalType] = CanonicalType.UNKNOWN_EXTENSION
    name: str
    namespace: str | None = None
    reason: str = "unsupported"
    attributes: JsonObject = JsonObject()
    content: tuple[str | UnknownExtension, ...] = ()
    metadata: JsonObject = JsonObject()
    provenance: tuple[SourceProvenance, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class EntityReference(Record):
    """An explicit selector and optional local target; no implicit resolution."""

    canonical_type: ClassVar[CanonicalType] = CanonicalType.ENTITY_REFERENCE
    target_types: tuple[CanonicalType, ...] = field(default=(), metadata={"unordered": True})
    implementation_id: str | None = None
    name: str | None = None
    wkn: WellKnownName | None = None
    scope_key: str | None = None
    target_key: str | None = None
    provenance: tuple[SourceProvenance, ...] = ()
    unknown_extensions: tuple[UnknownExtension, ...] = ()
    metadata: JsonObject = JsonObject()

    def __post_init__(self) -> None:
        Record.__post_init__(self)
        if len(set(self.target_types)) != len(self.target_types):
            raise ModelValidationError("Duplicate reference target type")
        for key in (self.scope_key, self.target_key):
            if key is not None:
                require_nonempty(key, "reference key")


@dataclass(frozen=True, slots=True, kw_only=True)
class UnresolvedReference(Record):
    canonical_type: ClassVar[CanonicalType] = CanonicalType.UNRESOLVED_REFERENCE
    owner_key: str
    relationship: str
    reference: EntityReference
    reason: UnresolvedReason = UnresolvedReason.NOT_ATTEMPTED
    candidate_keys: tuple[str, ...] = field(default=(), metadata={"unordered": True})
    provenance: tuple[SourceProvenance, ...] = ()
    detail: str | None = None

    def __post_init__(self) -> None:
        Record.__post_init__(self)
        require_nonempty(self.owner_key, "owner_key")
        require_nonempty(self.relationship, "relationship")
        if self.reference.target_key is not None:
            raise ModelValidationError("An unresolved reference cannot have a resolved target")
        if len(set(self.candidate_keys)) != len(self.candidate_keys):
            raise ModelValidationError("Duplicate unresolved candidate key")
        if self.reason is UnresolvedReason.AMBIGUOUS and len(self.candidate_keys) < 2:
            raise ModelValidationError("Ambiguity requires at least two candidate keys")
        if self.reason is not UnresolvedReason.AMBIGUOUS and self.candidate_keys:
            raise ModelValidationError("Candidate keys require ambiguous status")
        for key in self.candidate_keys:
            require_nonempty(key, "candidate key")


@dataclass(frozen=True, slots=True, kw_only=True)
class DataStructure(Record):
    """An ordered data shape, with open kind labels for future encodings."""

    canonical_type: ClassVar[CanonicalType] = CanonicalType.DATA_STRUCTURE
    kind: str
    name: str | None = None
    description: str | None = None
    value: str | None = None
    attributes: JsonObject = JsonObject()
    children: tuple[DataStructure, ...] = ()
    provenance: tuple[SourceProvenance, ...] = ()
    unknown_extensions: tuple[UnknownExtension, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class StateTransition(Record):
    canonical_type: ClassVar[CanonicalType] = CanonicalType.STATE_TRANSITION
    state_model: str | None = None
    transition_id: str | None = None
    previous_state: str | None = None
    new_state: str | None = None
    provenance: tuple[SourceProvenance, ...] = ()
    unknown_extensions: tuple[UnknownExtension, ...] = ()
