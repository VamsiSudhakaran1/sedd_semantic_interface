"""Deterministic inspect-command projection and rendering."""

from __future__ import annotations

import os
from dataclasses import fields
from enum import StrEnum
from pathlib import Path
from typing import cast

from sema_sedd.adapters import AdapterDiagnostic, AdapterResult, load_interface
from sema_sedd.diagnostics import context_data
from sema_sedd.graph import (
    Relationship,
    ResolutionState,
    relationship_diagnostics,
    resolve_references,
)
from sema_sedd.graph.adjacency import RelationshipAdjacency, build_relationship_adjacency
from sema_sedd.limits import bounded_json
from sema_sedd.model import CanonicalType, JsonArray, JsonObject, UnknownExtension
from sema_sedd.model._base import Record
from sema_sedd.model.domain import InterfaceEntity, RemoteCommand, RemoteCommandParameter

INSPECTION_SCHEMA_VERSION = "2.0"
_PENDING_DIAGNOSTIC = "REFERENCE_RESOLUTION_PENDING"
_ENTITY_TYPES = (
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
)
ENTITY_TYPE_NAMES = tuple(kind.value for kind in _ENTITY_TYPES)

type JsonData = None | str | int | float | bool | list["JsonData"] | dict[str, "JsonData"]


def _dump(value: JsonData, *, pretty: bool = False) -> str:
    return bounded_json(value, pretty=pretty)


def _encode(value: object) -> JsonData:
    if isinstance(value, StrEnum):
        return value.value
    if value is None or type(value) in (str, int, float, bool):
        return value  # type: ignore[return-value]
    if isinstance(value, JsonObject):
        return {key: _encode(item) for key, item in sorted(value.entries)}
    if isinstance(value, JsonArray):
        return [_encode(item) for item in value.items]
    if isinstance(value, tuple):
        return [_encode(item) for item in value]
    if isinstance(value, Record):
        canonical_type = getattr(value, "canonical_type", None)
        if not isinstance(canonical_type, CanonicalType):
            raise TypeError("Inspection record has no canonical type")
        result: dict[str, JsonData] = {"canonical_type": canonical_type.value}
        for member in fields(value):
            encoded = _encode(getattr(value, member.name))
            if member.metadata.get("unordered") and isinstance(encoded, list):
                encoded.sort(key=_dump)
            result[member.name] = encoded
        return result
    raise TypeError(f"Unsupported inspection value: {type(value).__name__}")


def _relationship_data(relationship: Relationship, direction: str | None = None) -> JsonData:
    result: dict[str, JsonData] = {
        "owner_key": relationship.owner_key,
        "role": relationship.role,
        "state": relationship.state.value,
        "reason": relationship.reason.value if relationship.reason is not None else None,
        "target_key": relationship.reference.target_key,
        "candidate_keys": list(relationship.candidate_keys),
        "selector": _encode(relationship.reference),
    }
    if direction is not None:
        result["direction"] = direction
    return result


def _diagnostic_data(diagnostic: AdapterDiagnostic) -> JsonData:
    return {
        "code": diagnostic.code,
        "message": diagnostic.message,
        "severity": diagnostic.severity.value,
        "provenance": _encode(diagnostic.provenance),
        "source": diagnostic.source,
        "source_line": diagnostic.source_line,
        "entity_context": cast(JsonData, context_data(diagnostic.entity_context)),
    }


def _unsupported_data(extension: UnknownExtension) -> JsonData:
    provenance = extension.provenance[0] if extension.provenance else None
    return {
        "name": extension.name,
        "namespace": extension.namespace,
        "reason": extension.reason,
        "source_path": provenance.source_path if provenance is not None else None,
        "line": provenance.line if provenance is not None else None,
        "column": provenance.column if provenance is not None else None,
    }


def _entity_sort_key(entity: InterfaceEntity) -> tuple[str, str, str, str, str]:
    return (
        entity.canonical_type.value,
        entity.implementation_id or "",
        entity.wkn.value if entity.wkn is not None else "",
        entity.name or "",
        entity.key,
    )


def _select_entities(
    interface_entities: tuple[InterfaceEntity, ...],
    *,
    entity_type: str | None,
    implementation_id: str | None,
    wkn: str | None,
) -> tuple[InterfaceEntity, ...]:
    return tuple(
        sorted(
            (
                entity
                for entity in interface_entities
                if (entity_type is None or entity.canonical_type.value == entity_type)
                and (implementation_id is None or entity.implementation_id == implementation_id)
                and (wkn is None or (entity.wkn is not None and entity.wkn.value == wkn))
            ),
            key=_entity_sort_key,
        )
    )


def _containment_data(entity: InterfaceEntity, adjacency: RelationshipAdjacency) -> list[JsonData]:
    relationships: list[JsonData] = []
    if isinstance(entity, RemoteCommand):
        relationships.extend(
            {
                "direction": "outgoing",
                "kind": "containment",
                "role": f"parameters[{index}]",
                "target_key": parameter.key,
            }
            for index, parameter in enumerate(entity.parameters or ())
        )
    elif isinstance(entity, RemoteCommandParameter):
        relationships.extend(
            {
                "direction": "incoming",
                "kind": "containment",
                "role": f"parameters[{index}]",
                "owner_key": owner,
            }
            for owner, index in [adjacency.contained_by[entity.key]]
        )
    return relationships


def _immediate_relationships(
    entity: InterfaceEntity, adjacency: RelationshipAdjacency
) -> list[JsonData]:
    result = [
        _relationship_data(relationship, "outgoing")
        for relationship in adjacency.outgoing.get(entity.key, ())
    ]
    for relationship in (
        *adjacency.incoming.get(entity.key, ()),
        *adjacency.candidates.get(entity.key, ()),
    ):
        if relationship.reference.target_key == entity.key:
            result.append(_relationship_data(relationship, "incoming"))
        elif entity.key in relationship.candidate_keys:
            result.append(_relationship_data(relationship, "incoming_candidate"))
    result.extend(_containment_data(entity, adjacency))
    result.sort(key=_dump)
    return result


def build_inspection(
    path: str | os.PathLike[str],
    *,
    entity_type: str | None = None,
    implementation_id: str | None = None,
    wkn: str | None = None,
) -> dict[str, JsonData]:
    """Load, resolve, and project a SEDD document without mutating the input."""
    adapted: AdapterResult = load_interface(path)
    relationship_model = resolve_references(adapted.interface)
    interface = relationship_model.interface
    entities = interface.entities()
    counts: dict[str, JsonData] = {
        kind.value: sum(entity.canonical_type is kind for entity in entities)
        for kind in _ENTITY_TYPES
    }
    unresolved = [
        _relationship_data(relationship)
        for relationship in relationship_model.relationships
        if relationship.state is not ResolutionState.RESOLVED
    ]
    unresolved.sort(key=_dump)
    unsupported = [_unsupported_data(extension) for extension in interface.unknown_extensions]
    unsupported.sort(key=_dump)
    diagnostics = [
        _diagnostic_data(diagnostic)
        for diagnostic in (*adapted.diagnostics, *relationship_diagnostics(relationship_model))
        if diagnostic.code != _PENDING_DIAGNOSTIC
    ]
    diagnostics.sort(key=_dump)

    filtered = any(value is not None for value in (entity_type, implementation_id, wkn))
    selection: JsonData = None
    if filtered:
        adjacency = build_relationship_adjacency(relationship_model)
        selected = _select_entities(
            entities,
            entity_type=entity_type,
            implementation_id=implementation_id,
            wkn=wkn,
        )
        selection = {
            "filters": {"type": entity_type, "id": implementation_id, "wkn": wkn},
            "count": len(selected),
            "entities": [
                {
                    "entity": _encode(entity),
                    "immediate_relationships": _immediate_relationships(entity, adjacency),
                }
                for entity in selected
            ],
        }

    return {
        "inspection_schema_version": INSPECTION_SCHEMA_VERSION,
        "source": str(Path(path).resolve()),
        "sedd_revision": adapted.revision,
        "equipment": _encode(interface.equipment),
        "entity_counts": counts,
        "unresolved_references": unresolved,
        "unsupported_sections": unsupported,
        "diagnostics": diagnostics,
        "selection": selection,
    }


def render_json(inspection: dict[str, JsonData]) -> str:
    """Return stable compact Unicode JSON with one trailing newline."""
    return _dump(inspection) + "\n"


def _display(value: JsonData) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (str, int, float)):
        return str(value)
    return _dump(value)


def _relationship_text(value: JsonData) -> str:
    if not isinstance(value, dict):
        raise TypeError("Relationship projection must be an object")
    direction = f"{value['direction']} " if "direction" in value else ""
    if value.get("kind") == "containment":
        peer = value.get("target_key", value.get("owner_key"))
        return f"{direction}{value['role']} -> {_display(peer)} [contained]"
    target = value.get("target_key")
    candidates = value.get("candidate_keys")
    destination = target if target is not None else candidates if candidates else "-"
    reason = f"/{value['reason']}" if value.get("reason") is not None else ""
    return (
        f"{direction}{value['owner_key']}:{value['role']} -> {_display(destination)} "
        f"[{str(value['state']).upper()}{reason}]"
    )


def render_text(inspection: dict[str, JsonData]) -> str:
    """Return a deterministic human-readable inspection report."""
    equipment = inspection["equipment"]
    if not isinstance(equipment, dict):
        raise TypeError("Equipment projection must be an object")
    lines = [
        f"SEDD revision: {_display(inspection['sedd_revision'])}",
        f"Source: {_display(inspection['source'])}",
        "Equipment metadata:",
    ]
    for key in (
        "implementation_id",
        "model",
        "software_revision",
        "supplier",
        "created_date",
        "name",
        "description",
    ):
        lines.append(f"  {key}: {_display(equipment.get(key))}")

    counts = inspection["entity_counts"]
    if not isinstance(counts, dict):
        raise TypeError("Entity counts projection must be an object")
    lines.append("Entity counts:")
    lines.extend(f"  {kind}: {_display(counts[kind])}" for kind in ENTITY_TYPE_NAMES)

    unresolved = inspection["unresolved_references"]
    if not isinstance(unresolved, list):
        raise TypeError("Unresolved projection must be an array")
    lines.append(f"Unresolved references: {len(unresolved)}")
    lines.extend(f"  {_relationship_text(item)}" for item in unresolved)

    unsupported = inspection["unsupported_sections"]
    if not isinstance(unsupported, list):
        raise TypeError("Unsupported projection must be an array")
    lines.append(f"Unsupported sections: {len(unsupported)}")
    for item in unsupported:
        if not isinstance(item, dict):
            raise TypeError("Unsupported section projection must be an object")
        lines.append(f"  {item['name']} [{item['reason']}] at {_display(item['source_path'])}")

    diagnostics = inspection["diagnostics"]
    if not isinstance(diagnostics, list):
        raise TypeError("Diagnostic projection must be an array")
    lines.append(f"Diagnostics: {len(diagnostics)}")
    for item in diagnostics:
        if not isinstance(item, dict):
            raise TypeError("Diagnostic projection must be an object")
        context = item.get("entity_context")
        owner = (
            f"{context['canonical_type']} {context['key']}"
            if isinstance(context, dict)
            else "unknown entity"
        )
        lines.append(
            f"  {item['severity']} {item['code']}: {item['message']} "
            f"[{item.get('source')}:{item.get('source_line') or '?'} · {owner}]"
        )

    selection = inspection["selection"]
    if selection is not None:
        if not isinstance(selection, dict) or not isinstance(selection["entities"], list):
            raise TypeError("Selection projection must be an object")
        lines.append(f"Selected entities: {selection['count']}")
        for selected in selection["entities"]:
            if not isinstance(selected, dict) or not isinstance(selected["entity"], dict):
                raise TypeError("Selected entity projection must be an object")
            entity = selected["entity"]
            lines.extend(
                (
                    f"  Entity: {entity['canonical_type']}",
                    f"    key: {entity['key']}",
                    f"    id: {_display(entity['implementation_id'])}",
                    f"    name: {_display(entity['name'])}",
                    f"    wkn: {_display(entity['wkn'])}",
                    f"    data: {_dump(entity)}",
                )
            )
            immediate = selected["immediate_relationships"]
            if not isinstance(immediate, list):
                raise TypeError("Immediate relationships projection must be an array")
            lines.append(f"    immediate relationships: {len(immediate)}")
            lines.extend(f"      {_relationship_text(item)}" for item in immediate)
    return "\n".join(lines) + "\n"
