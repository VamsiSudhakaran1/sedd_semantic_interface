"""Read-only presentation of canonical semantic changes between two SEDD files."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path

from sema_sedd.adapters import AdapterDiagnostic, AdapterResult, load_interface
from sema_sedd.cli.inspect import ENTITY_TYPE_NAMES, _diagnostic_data
from sema_sedd.compare import (
    ChangeCategory,
    ChangeKind,
    ChangeSet,
    ComparisonIssue,
    EntityChange,
    EntityMatch,
    PropertyChange,
    RelationshipChange,
    compare_interfaces,
)
from sema_sedd.compare._values import JsonData, dump, encode
from sema_sedd.model import CanonicalType

COMPARISON_SCHEMA_VERSION = "1.0"
COMPARISON_TYPE_NAMES = (
    CanonicalType.EQUIPMENT_INTERFACE.value,
    CanonicalType.EQUIPMENT_METADATA.value,
    *ENTITY_TYPE_NAMES,
)
_PENDING_DIAGNOSTIC = "REFERENCE_RESOLUTION_PENDING"


@dataclass(frozen=True, slots=True)
class ComparisonView:
    """A selection over one complete ChangeSet; filters never change the findings."""

    old_source: str
    new_source: str
    old_revision: str
    new_revision: str
    changes: ChangeSet
    entity_type: str | None
    only_changed: bool
    include_documentation: bool
    added: tuple[EntityChange, ...]
    removed: tuple[EntityChange, ...]
    identity_preserving: tuple[EntityChange, ...]
    documentation_only: tuple[EntityChange, ...]
    hidden_documentation_only: int
    unchanged_matches: tuple[EntityMatch, ...]
    issues: tuple[ComparisonIssue, ...]
    diagnostics: tuple[tuple[str, AdapterDiagnostic], ...]

    @property
    def displayed_changes(self) -> tuple[EntityChange, ...]:
        return self.added + self.removed + self.identity_preserving + self.documentation_only

    @property
    def properties(self) -> tuple[tuple[EntityChange, PropertyChange], ...]:
        return tuple(
            (entity, item)
            for entity in self.identity_preserving + self.documentation_only
            for item in entity.properties
        )

    @property
    def relationships(self) -> tuple[tuple[EntityChange, RelationshipChange], ...]:
        return tuple(
            (entity, item)
            for entity in self.identity_preserving + self.documentation_only
            for item in entity.relationships
        )


def _select_change(change: EntityChange, *, include_documentation: bool) -> EntityChange | None:
    if include_documentation or change.kind is not ChangeKind.ENTITY_MODIFIED:
        return change
    properties = tuple(
        item
        for item in change.properties
        if item.category is not ChangeCategory.DOCUMENTATION_CHANGE
    )
    relationships = tuple(
        item
        for item in change.relationships
        if item.category is not ChangeCategory.DOCUMENTATION_CHANGE
    )
    if not properties and not relationships:
        return None
    return replace(change, properties=properties, relationships=relationships)


def build_comparison(
    old_path: str | os.PathLike[str],
    new_path: str | os.PathLike[str],
    *,
    entity_type: str | None = None,
    only_changed: bool = False,
    include_documentation: bool = False,
) -> ComparisonView:
    """Load both sources and select a view without changing semantic outcomes."""
    if entity_type is not None and entity_type not in COMPARISON_TYPE_NAMES:
        raise ValueError(f"Unknown canonical type: {entity_type}")
    old: AdapterResult = load_interface(old_path)
    new: AdapterResult = load_interface(new_path)
    changes = compare_interfaces(old.interface, new.interface)
    selected_all = tuple(
        entity
        for entity in changes.entity_changes
        if entity_type is None or entity.entity_type.value == entity_type
    )
    selected = tuple(
        visible
        for entity in selected_all
        if (visible := _select_change(entity, include_documentation=include_documentation))
        is not None
    )
    added = tuple(entity for entity in selected if entity.kind is ChangeKind.ENTITY_ADDED)
    removed = tuple(entity for entity in selected if entity.kind is ChangeKind.ENTITY_REMOVED)
    documentation_only = tuple(
        entity
        for entity in selected
        if entity.kind is ChangeKind.ENTITY_MODIFIED
        and entity.categories == (ChangeCategory.DOCUMENTATION_CHANGE,)
    )
    identity_preserving = tuple(
        entity
        for entity in selected
        if entity.kind is ChangeKind.ENTITY_MODIFIED and entity not in documentation_only
    )
    changed_matches = {
        (entity.match.old_entity.key, entity.match.new_entity.key)
        for entity in selected_all
        if entity.match is not None
    }
    unchanged_matches = (
        ()
        if only_changed
        else tuple(
            match
            for match in changes.matching.matches
            if (entity_type is None or match.old_entity.canonical_type.value == entity_type)
            and (match.old_entity.key, match.new_entity.key) not in changed_matches
        )
    )
    issues = tuple(
        item
        for item in changes.issues
        if entity_type is None
        or (item.entity_type is not None and item.entity_type.value == entity_type)
    )
    diagnostics = tuple(
        sorted(
            (
                (side, item)
                for side, adapted in (("old", old), ("new", new))
                for item in adapted.diagnostics
                if item.code != _PENDING_DIAGNOSTIC
            ),
            key=lambda pair: (pair[0], pair[1].severity.value, pair[1].code, pair[1].message),
        )
    )
    return ComparisonView(
        old_source=str(Path(old_path).resolve()),
        new_source=str(Path(new_path).resolve()),
        old_revision=old.revision,
        new_revision=new.revision,
        changes=changes,
        entity_type=entity_type,
        only_changed=only_changed,
        include_documentation=include_documentation,
        added=added,
        removed=removed,
        identity_preserving=identity_preserving,
        documentation_only=documentation_only,
        hidden_documentation_only=sum(
            entity.categories == (ChangeCategory.DOCUMENTATION_CHANGE,) for entity in selected_all
        )
        if not include_documentation
        else 0,
        unchanged_matches=unchanged_matches,
        issues=issues,
        diagnostics=diagnostics,
    )


def _subject(change: EntityChange) -> dict[str, JsonData]:
    old, new = change.old_entity, change.new_entity
    subject = new if new is not None else old
    assert subject is not None
    return {
        "type": change.entity_type.value,
        "old_key": getattr(old, "key", None),
        "new_key": getattr(new, "key", None),
        "old_id": old.implementation_id if old is not None else None,
        "new_id": new.implementation_id if new is not None else None,
        "name": subject.name,
    }


def _change_data(changes: tuple[EntityChange, ...]) -> list[JsonData]:
    result: list[JsonData] = []
    for change in changes:
        encoded = encode(change)
        assert isinstance(encoded, dict)
        encoded["change_kinds"] = encode(change.kinds)
        encoded["categories"] = encode(change.categories)
        for side in ("old_context", "new_context"):
            context = getattr(change, side)
            context_data = encoded[side]
            if context is not None and isinstance(context_data, dict):
                context_data["statements"] = encode(context.statements)
        result.append(encoded)
    return result


def to_comparison_dict(view: ComparisonView) -> dict[str, JsonData]:
    """Deterministic, versioned JSON view with sections and source diagnostics."""
    properties: list[JsonData] = [
        {"subject": _subject(entity), "change": encode(item)} for entity, item in view.properties
    ]
    relationships: list[JsonData] = [
        {"subject": _subject(entity), "change": encode(item)} for entity, item in view.relationships
    ]
    return {
        "comparison_schema_version": COMPARISON_SCHEMA_VERSION,
        "old_source": view.old_source,
        "new_source": view.new_source,
        "old_revision": view.old_revision,
        "new_revision": view.new_revision,
        "selection": {
            "type": view.entity_type,
            "only_changed": view.only_changed,
            "include_documentation": view.include_documentation,
        },
        "summary": {
            "is_complete": view.changes.is_complete,
            "matched": sum(
                view.entity_type is None or item.old_entity.canonical_type.value == view.entity_type
                for item in view.changes.matching.matches
            ),
            "added": len(view.added),
            "removed": len(view.removed),
            "identity_preserving_changes": len(view.identity_preserving),
            "property_changes": len(properties),
            "relationship_changes": len(relationships),
            "documentation_only_changes": len(view.documentation_only),
            "hidden_documentation_only_changes": view.hidden_documentation_only,
            "unchanged_matches_displayed": len(view.unchanged_matches),
            "unresolved_items": len(view.issues),
            "diagnostics": len(view.diagnostics),
        },
        "added": _change_data(view.added),
        "removed": _change_data(view.removed),
        "identity_preserving_changes": _change_data(view.identity_preserving),
        "property_changes": properties,
        "relationship_changes": relationships,
        "documentation_only_changes": _change_data(view.documentation_only),
        "unchanged_matches": [encode(item) for item in view.unchanged_matches],
        "unresolved_items": [encode(item) for item in view.issues],
        "diagnostics": [
            {"side": side, "diagnostic": _diagnostic_data(item)} for side, item in view.diagnostics
        ],
    }


def render_json(view: ComparisonView) -> str:
    return dump(to_comparison_dict(view)) + "\n"


def _display(value: object) -> str:
    if isinstance(value, str):
        # Keep source text on one report line, including XML-legal newlines/tabs.
        return (
            json.dumps(value, ensure_ascii=False)[1:-1]
            if any(ord(character) < 32 or ord(character) == 127 for character in value)
            else value
        )
    return (
        "-"
        if value is None
        else str(value)
        if isinstance(value, (str, int, float))
        else dump(encode(value))
    )


def _entity_line(change: EntityChange) -> str:
    subject = _subject(change)
    old_id, new_id = subject["old_id"], subject["new_id"]
    if old_id == new_id and old_id is not None:
        identity = f"id {old_id}"
    elif old_id is not None or new_id is not None:
        identity = f"id {_display(old_id)} -> {_display(new_id)}"
    elif subject["old_key"] is not None or subject["new_key"] is not None:
        identity = f"key {_display(subject['old_key'])} -> {_display(subject['new_key'])}"
    else:
        identity = ""
    suffix = f" via {change.match.strategy.value}" if change.match is not None else ""
    return (
        f"  {subject['type']}{' ' + identity if identity else ''} "
        f"[{_display(subject['name'])}]{suffix}"
    )


def _contexts(change: EntityChange) -> list[str]:
    lines: list[str] = []
    for side, context in (("old", change.old_context), ("new", change.new_context)):
        if context is not None:
            lines.extend(f"    {side}: {statement}" for statement in context.statements)
    return lines


def render_text(view: ComparisonView, *, color: bool = False) -> str:
    """Human-readable sections; optional ANSI affects headings only."""
    data = to_comparison_dict(view)
    summary = data["summary"]
    assert isinstance(summary, dict)

    def heading(title: str) -> str:
        return f"\x1b[36m{title}\x1b[0m" if color else title

    lines = [
        heading("Summary"),
        f"  Old: {_display(view.old_source)} ({view.old_revision})",
        f"  New: {_display(view.new_source)} ({view.new_revision})",
        f"  Complete: {'yes' if view.changes.is_complete else 'no'}",
        f"  Matched: {summary['matched']}",
        f"  Type: {view.entity_type or 'all'}",
    ]
    for title, entities in (
        ("Added", view.added),
        ("Removed", view.removed),
        ("Identity-preserving changes", view.identity_preserving),
    ):
        lines.append(heading(f"{title} ({len(entities)})"))
        for entity in entities:
            lines.append(_entity_line(entity))
            lines.extend(_contexts(entity))
    lines.append(heading(f"Property changes ({len(view.properties)})"))
    for entity, property_change in view.properties:
        lines.append(
            f"  {_subject(entity)['type']} {_display(_subject(entity)['old_id'])} "
            f"{property_change.field}: {_display(property_change.old_value)} -> "
            f"{_display(property_change.new_value)} [{property_change.kind.value}]"
        )
    lines.append(heading(f"Relationship changes ({len(view.relationships)})"))
    for entity, relationship_change in view.relationships:
        lines.append(
            f"  {_subject(entity)['type']} {_display(_subject(entity)['old_id'])} "
            f"{relationship_change.field}: {_display(relationship_change.old_value)} -> "
            f"{_display(relationship_change.new_value)} "
            f"[{relationship_change.kind.value}; +{len(relationship_change.added)}"
            f"/-{len(relationship_change.removed)}"
            f"; order_changed={str(relationship_change.order_changed).lower()}]"
        )
    lines.append(heading(f"Documentation-only changes ({len(view.documentation_only)})"))
    if view.hidden_documentation_only:
        lines.append(
            f"  {view.hidden_documentation_only} hidden; use --include-documentation to show them."
        )
    for entity in view.documentation_only:
        lines.append(_entity_line(entity))
        for documentation_change in entity.properties:
            lines.append(
                f"    {documentation_change.field}: "
                f"{_display(documentation_change.old_value)} -> "
                f"{_display(documentation_change.new_value)}"
            )
        lines.extend(_contexts(entity))
    if not view.only_changed:
        lines.append(heading(f"Unchanged matched entities ({len(view.unchanged_matches)})"))
        for match in view.unchanged_matches:
            lines.append(
                f"  {match.old_entity.canonical_type.value} "
                f"{_display(match.old_entity.implementation_id)} "
                f"[{_display(match.old_entity.name)}]"
            )
    lines.append(heading(f"Unresolved items ({len(view.issues)})"))
    for issue in view.issues:
        lines.append(
            f"  {issue.side} {issue.kind.value}: "
            f"{issue.entity_type.value if issue.entity_type is not None else '-'} "
            f"{_display(issue.entity_key)} {issue.field or ''} {issue.detail}".rstrip()
        )
    lines.append(heading(f"Diagnostics ({len(view.diagnostics)})"))
    for side, diagnostic in view.diagnostics:
        lines.append(
            f"  {side} {diagnostic.severity.value.upper()} "
            f"{diagnostic.code}: {_display(diagnostic.message)}"
        )
    return "\n".join(lines) + "\n"
