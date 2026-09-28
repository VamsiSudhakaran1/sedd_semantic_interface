"""Bounded, deterministic exploration over canonical relationships."""

from __future__ import annotations

import os
from collections import deque
from dataclasses import fields
from pathlib import Path

from sema_sedd.adapters import load_interface
from sema_sedd.cli.inspect import JsonData, _display, _dump, _encode, _relationship_data
from sema_sedd.exceptions import EntitySelectionError
from sema_sedd.graph import RelationshipModel, ResolutionState, resolve_references
from sema_sedd.graph.adjacency import RelationshipAdjacency, build_relationship_adjacency
from sema_sedd.model import CanonicalType, EntityReference
from sema_sedd.model.domain import InterfaceEntity, RemoteCommand, RemoteCommandParameter

EXPLORATION_SCHEMA_VERSION = "1.0"
DEFAULT_EXPLORE_DEPTH = 1
MAX_EXPLORE_DEPTH = 8

_SELECTOR_TYPES = {
    "event": CanonicalType.COLLECTION_EVENT,
    "alarm": CanonicalType.ALARM,
    "status-variable": CanonicalType.STATUS_VARIABLE,
}
_IDENTITY_FIELDS = {
    "canonical_type",
    "key",
    "implementation_id",
    "name",
    "description",
    "wkn",
}
_RELATIONSHIP_FIELDS = {
    "standards",
    "format",
    "valid_data_variables",
    "relevant_variables",
    "set_event",
    "clear_event",
    "parameters",
    "variables",
    "event",
    "reports",
}


def parse_selector(selector: str) -> tuple[str, str]:
    """Parse one documented exact selector without normalizing its value."""
    kind, separator, value = selector.partition(":")
    if not separator or kind not in (*_SELECTOR_TYPES, "wkn") or not value:
        choices = ", ".join((*_SELECTOR_TYPES, "wkn"))
        raise EntitySelectionError(
            f"Invalid entity selector {selector!r}; expected <kind>:<value> where kind is {choices}"
        )
    return kind, value


def _select_entity(entities: tuple[InterfaceEntity, ...], selector: str) -> InterfaceEntity:
    kind, value = parse_selector(selector)
    if kind == "wkn":
        matches = tuple(
            entity for entity in entities if entity.wkn is not None and entity.wkn.value == value
        )
    else:
        canonical_type = _SELECTOR_TYPES[kind]
        matches = tuple(
            entity
            for entity in entities
            if entity.canonical_type is canonical_type and entity.implementation_id == value
        )
    if not matches:
        raise EntitySelectionError(f"Entity selector {selector!r} matched no entities")
    if len(matches) > 1:
        raise EntitySelectionError(
            f"Entity selector {selector!r} is ambiguous; it matched {len(matches)} entities"
        )
    return matches[0]


def _containment_relationships(
    entity: InterfaceEntity, adjacency: RelationshipAdjacency
) -> tuple[list[JsonData], list[JsonData]]:
    incoming: list[JsonData] = []
    outgoing: list[JsonData] = []
    if isinstance(entity, RemoteCommand):
        outgoing.extend(
            {
                "kind": "containment",
                "role": f"parameters[{index}]",
                "owner_key": entity.key,
                "target_key": parameter.key,
            }
            for index, parameter in enumerate(entity.parameters or ())
        )
    elif isinstance(entity, RemoteCommandParameter):
        incoming.extend(
            {
                "kind": "containment",
                "role": f"parameters[{index}]",
                "owner_key": owner,
                "target_key": entity.key,
            }
            for owner, index in [adjacency.contained_by[entity.key]]
        )
    return incoming, outgoing


def _relationships_for(
    entity: InterfaceEntity, adjacency: RelationshipAdjacency
) -> tuple[list[JsonData], list[JsonData]]:
    incoming: list[JsonData] = []
    outgoing = [
        _relationship_data(relationship) for relationship in adjacency.outgoing.get(entity.key, ())
    ]
    for relationship in (
        *adjacency.incoming.get(entity.key, ()),
        *adjacency.candidates.get(entity.key, ()),
    ):
        if relationship.reference.target_key == entity.key:
            incoming.append(_relationship_data(relationship))
        elif entity.key in relationship.candidate_keys:
            candidate = _relationship_data(relationship)
            if not isinstance(candidate, dict):
                raise TypeError("Relationship projection must be an object")
            candidate["candidate"] = True
            incoming.append(candidate)
    containment_incoming, containment_outgoing = _containment_relationships(entity, adjacency)
    incoming.extend(containment_incoming)
    outgoing.extend(containment_outgoing)
    incoming.sort(key=_dump)
    outgoing.sort(key=_dump)
    return incoming, outgoing


def _entity_identity(entity: InterfaceEntity) -> dict[str, JsonData]:
    return {
        "canonical_type": entity.canonical_type.value,
        "key": entity.key,
        "implementation_id": entity.implementation_id,
        "name": entity.name,
        "description": entity.description,
        "wkn": _encode(entity.wkn),
    }


def _entity_properties(entity: InterfaceEntity) -> dict[str, JsonData]:
    properties: dict[str, JsonData] = {}
    for member in fields(entity):
        if member.name in _IDENTITY_FIELDS or member.name in _RELATIONSHIP_FIELDS:
            continue
        value = getattr(entity, member.name)
        if isinstance(value, EntityReference):
            continue
        if isinstance(value, tuple) and any(isinstance(item, EntityReference) for item in value):
            continue
        if isinstance(entity, RemoteCommand) and member.name == "parameters":
            continue
        properties[member.name] = _encode(value)
    return properties


def _traversable_adjacency(
    relationship_model: RelationshipModel,
) -> dict[str, tuple[str, ...]]:
    entities = relationship_model.interface.entities()
    adjacent: dict[str, set[str]] = {entity.key: set() for entity in entities}
    for relationship in relationship_model.relationships:
        target = relationship.reference.target_key
        if relationship.state is ResolutionState.RESOLVED and target is not None:
            adjacent[relationship.owner_key].add(target)
            adjacent[target].add(relationship.owner_key)
    for command in relationship_model.interface.remote_commands:
        for parameter in command.parameters or ():
            adjacent[command.key].add(parameter.key)
            adjacent[parameter.key].add(command.key)
    return {key: tuple(sorted(neighbors)) for key, neighbors in sorted(adjacent.items())}


def _bounded_distances(
    root_key: str, adjacency: dict[str, tuple[str, ...]], max_depth: int
) -> dict[str, int]:
    distances = {root_key: 0}
    pending = deque([root_key])
    while pending:
        current = pending.popleft()
        distance = distances[current]
        if distance >= max_depth:
            continue
        for neighbor in adjacency[current]:
            if neighbor not in distances:
                distances[neighbor] = distance + 1
                pending.append(neighbor)
    return distances


def build_exploration(
    path: str | os.PathLike[str], selector: str, *, depth: int = DEFAULT_EXPLORE_DEPTH
) -> dict[str, JsonData]:
    """Load and explore a canonical relationship neighborhood up to ``depth`` edges."""
    if not 0 <= depth <= MAX_EXPLORE_DEPTH:
        raise ValueError(f"depth must be between 0 and {MAX_EXPLORE_DEPTH}")
    adapted = load_interface(path)
    relationship_model = resolve_references(adapted.interface)
    entities = relationship_model.interface.entities()
    root = _select_entity(entities, selector)
    by_key = {entity.key: entity for entity in entities}
    adjacency = build_relationship_adjacency(relationship_model)
    distances = _bounded_distances(root.key, _traversable_adjacency(relationship_model), depth)
    explored: list[JsonData] = []
    for key, distance in sorted(
        distances.items(),
        key=lambda item: (
            item[1],
            by_key[item[0]].canonical_type.value,
            by_key[item[0]].implementation_id or "",
            item[0],
        ),
    ):
        entity = by_key[key]
        incoming, outgoing = _relationships_for(entity, adjacency)
        explored.append(
            {
                "depth": distance,
                "entity": _entity_identity(entity),
                "properties": _entity_properties(entity),
                "incoming_relationships": incoming,
                "outgoing_relationships": outgoing,
            }
        )
    kind, value = parse_selector(selector)
    return {
        "exploration_schema_version": EXPLORATION_SCHEMA_VERSION,
        "source": str(Path(path).resolve()),
        "sedd_revision": adapted.revision,
        "selector": {"kind": kind, "value": value},
        "max_depth": depth,
        "root_key": root.key,
        "entities": explored,
    }


def render_json(exploration: dict[str, JsonData]) -> str:
    """Return stable compact Unicode JSON with one trailing newline."""
    return _dump(exploration) + "\n"


def _relationship_text(value: JsonData, direction: str) -> str:
    if not isinstance(value, dict):
        raise TypeError("Relationship projection must be an object")
    if value.get("kind") == "containment":
        peer = value["owner_key"] if direction == "incoming" else value["target_key"]
        return f"{value['role']} -> {_display(peer)} [CONTAINED]"
    target = value.get("target_key")
    candidates = value.get("candidate_keys")
    destination = target if target is not None else candidates if candidates else "-"
    reason = f"/{value['reason']}" if value.get("reason") is not None else ""
    marker = " candidate" if value.get("candidate") else ""
    peer = value["owner_key"] if direction == "incoming" else destination
    return f"{value['role']} -> {_display(peer)} [{str(value['state']).upper()}{reason}{marker}]"


def render_text(exploration: dict[str, JsonData]) -> str:
    """Return a deterministic human-readable exploration report."""
    lines = [
        f"SEDD revision: {_display(exploration['sedd_revision'])}",
        f"Source: {_display(exploration['source'])}",
        (
            f"Selector: {_display(exploration['selector'])} "
            f"(maximum depth {_display(exploration['max_depth'])})"
        ),
    ]
    entities = exploration["entities"]
    if not isinstance(entities, list):
        raise TypeError("Explored entities projection must be an array")
    for item in entities:
        if not isinstance(item, dict) or not isinstance(item["entity"], dict):
            raise TypeError("Explored entity projection must be an object")
        entity = item["entity"]
        lines.extend(
            (
                f"Entity (depth {item['depth']}): {entity['canonical_type']}",
                f"  key: {entity['key']}",
                f"  id: {_display(entity['implementation_id'])}",
                f"  name: {_display(entity['name'])}",
                f"  description: {_display(entity['description'])}",
                f"  wkn: {_display(entity['wkn'])}",
                f"  Properties: {_dump(item['properties'])}",
            )
        )
        for label, direction in (
            ("Incoming relationships", "incoming"),
            ("Outgoing relationships", "outgoing"),
        ):
            relationships = item[f"{direction}_relationships"]
            if not isinstance(relationships, list):
                raise TypeError("Relationship projection must be an array")
            lines.append(f"  {label}: {len(relationships)}")
            lines.extend(
                f"    {_relationship_text(relationship, direction)}"
                for relationship in relationships
            )
    return "\n".join(lines) + "\n"
