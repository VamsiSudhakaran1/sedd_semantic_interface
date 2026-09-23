"""Versioned public JSON report over canonical comparison results."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files

from sema_sedd import __version__
from sema_sedd.compare import ChangeCategory, ChangeKind, ChangeSet
from sema_sedd.compare._values import JsonData, dump, encode
from sema_sedd.compare.matching import MatchingEvidence
from sema_sedd.exceptions import ReportError
from sema_sedd.graph import DependencyContext
from sema_sedd.model import CanonicalType, SourceProvenance
from sema_sedd.model.domain import EquipmentInterface, EquipmentMetadata, InterfaceEntity

REPORT_SCHEMA_VERSION = "1.0"

# Public codes are an explicit versioned registry. No Python class name or
# dynamically generated field name is part of the identifier contract.
_TYPE_PREFIX: dict[CanonicalType, str] = {
    CanonicalType.STATUS_VARIABLE: "SV",
    CanonicalType.DATA_VARIABLE: "DV",
    CanonicalType.EQUIPMENT_CONSTANT: "EC",
    CanonicalType.COLLECTION_EVENT: "CE",
    CanonicalType.ALARM: "AL",
    CanonicalType.REMOTE_COMMAND: "RC",
    CanonicalType.REMOTE_COMMAND_PARAMETER: "RCP",
    CanonicalType.SUPPORTED_MESSAGE: "SM",
    CanonicalType.VARIABLE_FORMAT: "VF",
    CanonicalType.DEFAULT_REPORT: "DR",
    CanonicalType.EVENT_REPORT_LINK: "ERL",
    CanonicalType.STANDARD_REFERENCE: "STD",
    CanonicalType.EQUIPMENT_METADATA: "EQ",
    CanonicalType.EQUIPMENT_INTERFACE: "EI",
}
_KIND_SUFFIX: dict[ChangeKind, str] = {
    ChangeKind.ENTITY_ADDED: "ADDED",
    ChangeKind.ENTITY_REMOVED: "REMOVED",
    ChangeKind.ENTITY_MODIFIED: "MODIFIED",
    ChangeKind.IMPLEMENTATION_ID_CHANGED: "IMPLEMENTATION_ID_CHANGED",
    ChangeKind.WELL_KNOWN_NAME_CHANGED: "WELL_KNOWN_NAME_CHANGED",
    ChangeKind.NAME_CHANGED: "NAME_CHANGED",
    ChangeKind.DESCRIPTION_CHANGED: "DESCRIPTION_CHANGED",
    ChangeKind.DATA_TYPE_CHANGED: "DATA_TYPE_CHANGED",
    ChangeKind.FORMAT_CHANGED: "FORMAT_CHANGED",
    ChangeKind.UNIT_CHANGED: "UNIT_CHANGED",
    ChangeKind.RANGE_CHANGED: "RANGE_CHANGED",
    ChangeKind.DEFAULT_CHANGED: "DEFAULT_CHANGED",
    ChangeKind.RELATIONSHIP_ADDED: "RELATIONSHIP_ADDED",
    ChangeKind.RELATIONSHIP_REMOVED: "RELATIONSHIP_REMOVED",
    ChangeKind.RELATIONSHIP_CHANGED: "RELATIONSHIP_CHANGED",
    ChangeKind.REPORT_CONTENT_CHANGED: "REPORT_CONTENT_CHANGED",
    ChangeKind.EVENT_REPORT_LINK_CHANGED: "EVENT_REPORT_LINK_CHANGED",
    ChangeKind.ALARM_EVENT_LINK_CHANGED: "ALARM_EVENT_LINK_CHANGED",
    ChangeKind.COMMAND_PARAMETER_CHANGED: "COMMAND_PARAMETER_CHANGED",
    ChangeKind.COMMAND_CHANGED: "COMMAND_CHANGED",
    ChangeKind.MESSAGE_STRUCTURE_CHANGED: "MESSAGE_STRUCTURE_CHANGED",
    ChangeKind.SUPPORTED_MESSAGE_CHANGED: "SUPPORTED_MESSAGE_CHANGED",
    ChangeKind.STANDARD_METADATA_CHANGED: "STANDARD_METADATA_CHANGED",
    ChangeKind.STATE_TRANSITION_CHANGED: "STATE_TRANSITION_CHANGED",
    ChangeKind.EQUIPMENT_METADATA_CHANGED: "EQUIPMENT_METADATA_CHANGED",
    ChangeKind.INTERFACE_METADATA_CHANGED: "INTERFACE_METADATA_CHANGED",
    ChangeKind.ALARM_CHANGED: "ALARM_CHANGED",
    ChangeKind.IDENTITY_EVIDENCE_CHANGED: "IDENTITY_EVIDENCE_CHANGED",
    ChangeKind.DOCUMENTATION_CHANGED: "DOCUMENTATION_CHANGED",
    ChangeKind.UNKNOWN_CHANGE: "UNKNOWN_CHANGE",
}


@dataclass(frozen=True, slots=True)
class ReportSource:
    path: str
    revision: str

    def __post_init__(self) -> None:
        if not self.path or not self.revision:
            raise ReportError("Report source path and revision are required")


@dataclass(frozen=True, slots=True)
class ReportDiagnostic:
    code: str
    message: str
    severity: str
    provenance: SourceProvenance | None = None

    def __post_init__(self) -> None:
        if not self.code or self.severity not in {"info", "warning", "error"}:
            raise ReportError("Invalid report diagnostic")


def public_change_id(entity_type: CanonicalType, kind: ChangeKind) -> str:
    """Return a stable taxonomy code; multiple occurrences may share one code."""
    try:
        return f"{_TYPE_PREFIX[entity_type]}_{_KIND_SUFFIX[kind]}"
    except KeyError as error:
        raise ReportError("No public identifier is registered for this change") from error


type ReportEntity = InterfaceEntity | EquipmentMetadata | EquipmentInterface


def _identity(entity: ReportEntity | None) -> dict[str, JsonData] | None:
    if entity is None:
        return None
    return {
        "key": getattr(entity, "key", None),
        "implementation_id": entity.implementation_id,
        "name": entity.name,
        "wkn": {
            "value": entity.wkn.value,
            "authority": entity.wkn.authority,
            "scope": entity.wkn.scope,
            "authority_status": entity.wkn.authority_status.value,
        }
        if entity.wkn is not None
        else None,
    }


def _subject(
    kind: CanonicalType, before: ReportEntity | None, after: ReportEntity | None
) -> dict[str, JsonData]:
    return {
        "entity_type": kind.value,
        "source_a": _identity(before),
        "source_b": _identity(after),
    }


def _issue_side(value: str) -> str:
    if value == "old":
        return "a"
    if value == "new":
        return "b"
    raise ReportError("Comparison issue has no valid source side")


def _change_row(
    change_id: str,
    category: ChangeCategory,
    scope: str,
    subject: dict[str, JsonData],
    field: str | None,
    before: JsonData,
    after: JsonData,
    relationship_delta: JsonData = None,
) -> dict[str, JsonData]:
    return {
        "change_id": change_id,
        "category": category.value,
        "scope": scope,
        "subject": subject,
        "field": field,
        "before": before,
        "after": after,
        "relationship_delta": relationship_delta,
    }


def _ambiguity_evidence(changes: ChangeSet) -> dict[tuple[str, str], JsonData]:
    result: dict[tuple[str, str], JsonData] = {}
    for group in changes.matching.ambiguities:
        detail: JsonData = {
            "reasons": [reason.value for reason in group.reasons],
            "evidence": _evidence(group.evidence),
            "source_a_keys": encode(tuple(sorted(entity.key for entity in group.old_entities))),
            "source_b_keys": encode(tuple(sorted(entity.key for entity in group.new_entities))),
        }
        for side, entities in (("a", group.old_entities), ("b", group.new_entities)):
            for entity in entities:
                result[side, entity.key] = detail
    return result


def _evidence(items: tuple[MatchingEvidence, ...]) -> list[JsonData]:
    return [
        {
            "strategy": item.strategy.value,
            "entity_type": item.entity_type.value,
            "identity": list(item.identity),
            "source_a_keys": list(item.old_keys),
            "source_b_keys": list(item.new_keys),
        }
        for item in items
    ]


def report_from_changes(
    changes: ChangeSet,
    source_a: ReportSource,
    source_b: ReportSource,
    *,
    diagnostics_a: tuple[ReportDiagnostic, ...] = (),
    diagnostics_b: tuple[ReportDiagnostic, ...] = (),
) -> dict[str, JsonData]:
    """Build a source-independent report projection without XML imports or I/O."""
    if (
        type(changes) is not ChangeSet
        or type(source_a) is not ReportSource
        or type(source_b) is not ReportSource
        or any(type(item) is not ReportDiagnostic for item in diagnostics_a + diagnostics_b)
    ):
        raise ReportError("Invalid report inputs")
    matches: list[JsonData] = [
        {
            "subject": _subject(
                match.old_entity.canonical_type, match.old_entity, match.new_entity
            ),
            "strategy": match.strategy.value,
            "confidence": match.confidence.value,
            "evidence": _evidence(match.evidence),
        }
        for match in changes.matching.matches
    ]
    matches.sort(key=dump)
    rows: list[JsonData] = []
    contexts: list[JsonData] = []
    for entity_change in changes.entity_changes:
        before, after = entity_change.old_entity, entity_change.new_entity
        entity_type = entity_change.entity_type
        subject = _subject(entity_type, before, after)
        contexts.append(
            {
                "subject": subject,
                "source_a": _context(entity_change.old_context),
                "source_b": _context(entity_change.new_context),
            }
        )
        if entity_change.kind in {ChangeKind.ENTITY_ADDED, ChangeKind.ENTITY_REMOVED}:
            rows.append(
                _change_row(
                    public_change_id(entity_type, entity_change.kind),
                    ChangeCategory.INTERFACE_CHANGE,
                    "entity",
                    subject,
                    None,
                    encode(before),
                    encode(after),
                )
            )
            continue
        for property_change in entity_change.properties:
            rows.append(
                _change_row(
                    public_change_id(entity_type, property_change.kind),
                    property_change.category,
                    "property",
                    subject,
                    property_change.field,
                    encode(property_change.old_value),
                    encode(property_change.new_value),
                )
            )
        for relationship in entity_change.relationships:
            rows.append(
                _change_row(
                    public_change_id(entity_type, relationship.kind),
                    relationship.category,
                    "relationship",
                    subject,
                    relationship.field,
                    encode(relationship.old_value),
                    encode(relationship.new_value),
                    {
                        "added": encode(relationship.added),
                        "removed": encode(relationship.removed),
                        "order_changed": relationship.order_changed,
                        "presence_changed": relationship.presence_changed,
                    },
                )
            )
    rows.sort(key=dump)
    contexts.sort(key=dump)
    ambiguities = _ambiguity_evidence(changes)
    unresolved: list[JsonData] = [
        {
            "issue_code": issue.kind.value,
            "source": _issue_side(issue.side),
            "entity_type": issue.entity_type.value if issue.entity_type is not None else None,
            "entity_key": issue.entity_key,
            "field": issue.field,
            "detail": issue.detail,
            "identity_ambiguity": ambiguities.get((_issue_side(issue.side), issue.entity_key))
            if issue.entity_key is not None
            else None,
        }
        for issue in changes.issues
    ]
    unresolved.sort(key=dump)
    diagnostics: list[JsonData] = [
        {
            "source": side,
            "code": diagnostic.code,
            "severity": diagnostic.severity,
            "message": diagnostic.message,
            "provenance": encode(diagnostic.provenance),
        }
        for side, records in (("a", diagnostics_a), ("b", diagnostics_b))
        for diagnostic in records
        if diagnostic.code != "REFERENCE_RESOLUTION_PENDING"
    ]
    diagnostics.sort(key=dump)
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "tool_version": __version__,
        "source_a": {"path": source_a.path, "revision": source_a.revision},
        "source_b": {"path": source_b.path, "revision": source_b.revision},
        "summary": {
            "is_complete": changes.is_complete,
            "matched": len(matches),
            "changed_entities": len(changes.entity_changes),
            "added": sum(c.kind is ChangeKind.ENTITY_ADDED for c in changes.entity_changes),
            "removed": sum(c.kind is ChangeKind.ENTITY_REMOVED for c in changes.entity_changes),
            "changes": len(rows),
            "interface_changes": sum(
                isinstance(row, dict) and row["category"] == ChangeCategory.INTERFACE_CHANGE.value
                for row in rows
            ),
            "documentation_changes": sum(
                isinstance(row, dict)
                and row["category"] == ChangeCategory.DOCUMENTATION_CHANGE.value
                for row in rows
            ),
            "unknown_changes": sum(
                isinstance(row, dict) and row["category"] == ChangeCategory.UNKNOWN_CHANGE.value
                for row in rows
            ),
            "unresolved": len(unresolved),
            "diagnostics": len(diagnostics),
        },
        "matches": matches,
        "changes": rows,
        "dependency_context": contexts,
        "unresolved": unresolved,
        "diagnostics": diagnostics,
    }


def _context(value: DependencyContext | None) -> JsonData:
    if value is None:
        return None
    encoded = encode(value)
    assert isinstance(encoded, dict)
    encoded["statements"] = encode(value.statements)
    return encoded


def report_json(report: dict[str, JsonData]) -> str:
    """Stable UTF-8-friendly JSON text with exactly one trailing newline."""
    return dump(report) + "\n"


def report_schema() -> dict[str, JsonData]:
    """Read the schema bundled with the installed wheel, without network access."""
    value = json.loads(files("sema_sedd.report").joinpath("schema_v1.json").read_text("utf-8"))
    if not isinstance(value, dict):
        raise ReportError("Bundled report schema is invalid")
    return value
