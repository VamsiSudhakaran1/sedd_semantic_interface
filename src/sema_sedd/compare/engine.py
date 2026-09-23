"""Canonical semantic comparison with matching-aware relationship endpoints."""

from collections import Counter
from dataclasses import fields, replace

from sema_sedd.compare._values import (
    JsonData,
    array,
    dump,
    encode,
    obj,
    requirements,
    semantic,
    structure_annotations,
    token,
)
from sema_sedd.compare.changes import (
    ChangeCategory,
    ChangeKind,
    ChangeSet,
    ChangeSubject,
    ComparisonIssue,
    EntityChange,
    IssueKind,
    PropertyChange,
    RelationshipChange,
)
from sema_sedd.compare.matching import (
    EntityMatch,
    MatchingResult,
    UnmatchedReason,
    match_interfaces,
)
from sema_sedd.exceptions import ModelValidationError
from sema_sedd.graph import RelationshipModel, ResolutionState, resolve_references
from sema_sedd.graph.context import DependencyContext, DependencyIndex, build_dependency_index
from sema_sedd.model import (
    CanonicalType,
    EntityReference,
    EquipmentInterface,
    JsonArray,
    JsonObject,
    RemoteCommandParameter,
    StandardReference,
    WellKnownName,
)
from sema_sedd.model.values import JsonValue

_INVENTORIES = {
    "status_variables",
    "data_variables",
    "equipment_constants",
    "collection_events",
    "alarms",
    "remote_commands",
    "supported_messages",
    "variable_formats",
    "default_reports",
    "event_report_links",
    "standard_references",
    "equipment",
    "unresolved_references",
}
_RELATIONSHIPS = {
    "standards",
    "format",
    "valid_data_variables",
    "relevant_variables",
    "set_event",
    "clear_event",
    "variables",
    "event",
    "reports",
    "parameters",
}
_DOCUMENTATION = {"description", "declared_source", "notes", "created_date"}
_COMMON_KINDS = {
    "implementation_id": ChangeKind.IMPLEMENTATION_ID_CHANGED,
    "wkn": ChangeKind.WELL_KNOWN_NAME_CHANGED,
    "name": ChangeKind.NAME_CHANGED,
    "description": ChangeKind.DESCRIPTION_CHANGED,
    "data_type": ChangeKind.DATA_TYPE_CHANGED,
    "units": ChangeKind.UNIT_CHANGED,
    "minimum": ChangeKind.RANGE_CHANGED,
    "maximum": ChangeKind.RANGE_CHANGED,
    "default": ChangeKind.DEFAULT_CHANGED,
    "state_transition": ChangeKind.STATE_TRANSITION_CHANGED,
}


def _key(entity: ChangeSubject) -> str | None:
    return getattr(entity, "key", None)


def _kind(entity: ChangeSubject, field: str) -> ChangeKind:
    if field in _COMMON_KINDS:
        return _COMMON_KINDS[field]
    if field in _DOCUMENTATION:
        return ChangeKind.DOCUMENTATION_CHANGED
    kind = entity.canonical_type
    if kind is CanonicalType.SUPPORTED_MESSAGE:
        return (
            ChangeKind.MESSAGE_STRUCTURE_CHANGED
            if field == "structure"
            else ChangeKind.SUPPORTED_MESSAGE_CHANGED
        )
    if kind is CanonicalType.VARIABLE_FORMAT and field == "structure":
        return ChangeKind.FORMAT_CHANGED
    if kind is CanonicalType.REMOTE_COMMAND_PARAMETER:
        return ChangeKind.COMMAND_PARAMETER_CHANGED
    if kind is CanonicalType.REMOTE_COMMAND:
        return ChangeKind.COMMAND_CHANGED
    if kind is CanonicalType.STANDARD_REFERENCE:
        return ChangeKind.STANDARD_METADATA_CHANGED
    if kind is CanonicalType.EQUIPMENT_METADATA:
        return ChangeKind.EQUIPMENT_METADATA_CHANGED
    if kind is CanonicalType.EQUIPMENT_INTERFACE:
        return ChangeKind.INTERFACE_METADATA_CHANGED
    if kind is CanonicalType.ALARM:
        return ChangeKind.ALARM_CHANGED
    return ChangeKind.UNKNOWN_CHANGE


def _relationship_kind(entity: ChangeSubject, field: str) -> ChangeKind:
    if field == "format":
        return ChangeKind.FORMAT_CHANGED
    if field == "standards":
        return ChangeKind.STANDARD_METADATA_CHANGED
    if field == "parameters":
        return ChangeKind.COMMAND_PARAMETER_CHANGED
    if entity.canonical_type is CanonicalType.ALARM:
        return ChangeKind.ALARM_EVENT_LINK_CHANGED
    if entity.canonical_type is CanonicalType.DEFAULT_REPORT:
        return ChangeKind.REPORT_CONTENT_CHANGED
    if entity.canonical_type is CanonicalType.EVENT_REPORT_LINK:
        return ChangeKind.EVENT_REPORT_LINK_CHANGED
    return ChangeKind.RELATIONSHIP_CHANGED


class _Side:
    def __init__(
        self,
        side: str,
        model: RelationshipModel,
        matching: MatchingResult,
        certain_unmatched: set[str],
        issues: list[ComparisonIssue],
    ) -> None:
        self.side = side
        self.model = model
        self.entities = {entity.key: entity for entity in model.interface.entities()}
        self.relationships = {(item.owner_key, item.role): item for item in model.relationships}
        self.pairs = {
            (m.old_entity.key if side == "old" else m.new_entity.key): (
                m.old_entity.key,
                m.new_entity.key,
            )
            for m in matching.matches
        }
        self.certain_unmatched = certain_unmatched
        self.issues = issues

    def issue(self, kind: IssueKind, entity: ChangeSubject, field: str, detail: str) -> None:
        self.issues.append(
            ComparisonIssue(
                kind=kind,
                side=self.side,
                entity_key=_key(entity),
                entity_type=entity.canonical_type,
                field=field,
                detail=detail,
            )
        )

    def target(self, key: str, owner: ChangeSubject, field: str) -> tuple[JsonValue, bool]:
        entity = self.entities[key]
        if key in self.pairs:
            old_key, new_key = self.pairs[key]
            return obj(
                state="matched",
                entity_type=entity.canonical_type.value,
                old_key=old_key,
                new_key=new_key,
            ), True
        if key in self.certain_unmatched:
            return obj(
                state="unmatched", side=self.side, entity_type=entity.canonical_type.value, key=key
            ), True
        self.issue(
            IssueKind.UNCERTAIN_TARGET_IDENTITY,
            owner,
            field,
            "Target has no confirmed cross-version identity",
        )
        return obj(
            state="uncertain",
            entity_type=entity.canonical_type.value,
            implementation_id=entity.implementation_id,
            name=entity.name,
            wkn=semantic(entity.wkn),
        ), False

    def reference(
        self,
        reference: EntityReference,
        owner: ChangeSubject,
        role: str,
    ) -> tuple[JsonValue, bool]:
        if reference.target_key is not None:
            return self.target(reference.target_key, owner, role)
        owner_key = _key(owner)
        outcome = self.relationships.get((owner_key, role)) if owner_key is not None else None
        self.issue(
            IssueKind.UNRESOLVED_REFERENCE,
            owner,
            role,
            "Reference endpoint is not uniquely resolved",
        )
        scope = None
        if reference.scope_key is not None:
            scope, _ = self.target(reference.scope_key, owner, role)
        return obj(
            state=outcome.state.value if outcome is not None else "unresolved",
            reason=outcome.reason.value
            if outcome is not None and outcome.reason is not None
            else "not_attempted",
            target_types=array(tuple(sorted(kind.value for kind in reference.target_types))),
            implementation_id=reference.implementation_id,
            name=reference.name,
            wkn=semantic(reference.wkn),
            scope=scope,
        ), False

    def role(self, entity: ChangeSubject, field: str) -> tuple[JsonValue, bool, JsonValue]:
        value = getattr(entity, field)
        if value is None:
            return None, True, None
        items = value if isinstance(value, tuple) else (value,)
        results: list[JsonValue] = []
        annotations: list[JsonValue] = []
        certain = True
        for index, item in enumerate(items):
            role = f"{field}[{index}]" if isinstance(value, tuple) else field
            if isinstance(item, RemoteCommandParameter):
                projected, known = self.target(item.key, entity, role)
            elif isinstance(item, EntityReference):
                projected, known = self.reference(item, entity, role)
                if item.unknown_extensions or item.metadata.entries:
                    self.issue(
                        IssueKind.UNKNOWN_CONTENT, entity, role, "Reference has opaque metadata"
                    )
                    annotations.append(
                        obj(
                            position=projected if field == "standards" else index,
                            extensions=semantic(item.unknown_extensions),
                            metadata=semantic(item.metadata),
                        )
                    )
            else:
                raise ModelValidationError("Unexpected canonical relationship member")
            results.append(projected)
            certain = certain and known
        projected_value = (
            array(tuple(results), unordered=field == "standards")
            if isinstance(value, tuple)
            else results[0]
        )
        return projected_value, certain, array(tuple(annotations), unordered=field == "standards")


def _items(value: JsonValue) -> tuple[JsonValue, ...]:
    if value is None:
        return ()
    return value.items if isinstance(value, JsonArray) else (value,)


def _relationship_change(
    owner: ChangeSubject,
    field: str,
    before: JsonValue,
    after: JsonValue,
    certain: bool,
) -> RelationshipChange | None:
    if token(before) == token(after):
        return None
    old_items, new_items = _items(before), _items(after)
    old_counts, new_counts = Counter(map(token, old_items)), Counter(map(token, new_items))
    representatives = {token(item): item for item in old_items + new_items}
    added = tuple(
        representatives[k] for k, n in sorted((new_counts - old_counts).items()) for _ in range(n)
    )
    removed = tuple(
        representatives[k] for k, n in sorted((old_counts - new_counts).items()) for _ in range(n)
    )
    kind = _relationship_kind(owner, field)
    if kind is ChangeKind.RELATIONSHIP_CHANGED:
        if added and not old_items:
            kind = ChangeKind.RELATIONSHIP_ADDED
        elif removed and not new_items:
            kind = ChangeKind.RELATIONSHIP_REMOVED
    return RelationshipChange(
        field=field,
        kind=kind,
        category=ChangeCategory.INTERFACE_CHANGE if certain else ChangeCategory.UNKNOWN_CHANGE,
        old_value=before,
        new_value=after,
        added=added,
        removed=removed,
        order_changed=old_counts == new_counts
        and token(array(old_items)) != token(array(new_items)),
        presence_changed=(before is None) != (after is None),
    )


def _property(
    output: list[PropertyChange],
    field: str,
    kind: ChangeKind,
    category: ChangeCategory,
    before: JsonValue,
    after: JsonValue,
) -> None:
    if token(before) != token(after):
        output.append(
            PropertyChange(
                field=field, kind=kind, category=category, old_value=before, new_value=after
            )
        )


def _compare_entity(
    old: ChangeSubject,
    new: ChangeSubject,
    left: _Side,
    right: _Side,
    match: EntityMatch | None = None,
) -> EntityChange | None:
    properties: list[PropertyChange] = []
    relationships: list[RelationshipChange] = []
    for member in fields(old):
        field = member.name
        if field in {"key", "provenance"} or (
            isinstance(old, EquipmentInterface) and field in _INVENTORIES
        ):
            continue
        before, after = getattr(old, field), getattr(new, field)
        if field in _RELATIONSHIPS:
            old_role, old_certain, old_metadata = left.role(old, field)
            new_role, new_certain, new_metadata = right.role(new, field)
            changed = _relationship_change(
                old, field, old_role, new_role, old_certain and new_certain
            )
            if changed is not None:
                relationships.append(changed)
            # Missing and empty metadata are equivalent; role presence is above.
            _property(
                properties,
                f"{field}.metadata",
                ChangeKind.UNKNOWN_CHANGE,
                ChangeCategory.UNKNOWN_CHANGE,
                old_metadata or array(()),
                new_metadata or array(()),
            )
            continue
        kind = _kind(old, field)
        category = (
            ChangeCategory.DOCUMENTATION_CHANGE
            if field in _DOCUMENTATION
            else ChangeCategory.INTERFACE_CHANGE
        )
        if field in {"unknown_extensions", "extension_metadata"}:
            kind, category = ChangeKind.UNKNOWN_CHANGE, ChangeCategory.UNKNOWN_CHANGE
            for side, entity, value in ((left, old, before), (right, new, after)):
                if (isinstance(value, tuple) and value) or (
                    isinstance(value, JsonObject) and value.entries
                ):
                    side.issue(
                        IssueKind.UNKNOWN_CONTENT,
                        entity,
                        field,
                        "Opaque content cannot establish semantic equivalence",
                    )
        elif (
            field == "wkn"
            and isinstance(before, WellKnownName)
            and isinstance(after, WellKnownName)
        ):
            if (before.value, before.authority, before.scope) == (
                after.value,
                after.authority,
                after.scope,
            ) and before.authority_status != after.authority_status:
                kind, category = ChangeKind.IDENTITY_EVIDENCE_CHANGED, ChangeCategory.UNKNOWN_CHANGE
        elif field == "state_transition":
            _property(
                properties,
                field,
                kind,
                category,
                semantic(before, structural=True),
                semantic(after, structural=True),
            )
            _property(
                properties,
                field + ".extensions",
                ChangeKind.UNKNOWN_CHANGE,
                ChangeCategory.UNKNOWN_CHANGE,
                semantic(getattr(before, "unknown_extensions", ())),
                semantic(getattr(after, "unknown_extensions", ())),
            )
            continue
        elif field in {"structure", "value_format"}:
            _property(
                properties,
                field,
                kind,
                category,
                semantic(before, structural=True),
                semantic(after, structural=True),
            )
            _property(
                properties,
                field + ".documentation",
                ChangeKind.DESCRIPTION_CHANGED,
                ChangeCategory.DOCUMENTATION_CHANGE,
                structure_annotations(before),
                structure_annotations(after),
            )
            old_unknown, new_unknown = (
                structure_annotations(before, opaque=True),
                structure_annotations(after, opaque=True),
            )
            _property(
                properties,
                field + ".extensions",
                ChangeKind.UNKNOWN_CHANGE,
                ChangeCategory.UNKNOWN_CHANGE,
                old_unknown,
                new_unknown,
            )
            for side, entity, unknown in ((left, old, old_unknown), (right, new, new_unknown)):
                if _items(unknown):
                    side.issue(
                        IssueKind.UNKNOWN_CONTENT,
                        entity,
                        field,
                        "Data shape contains opaque extensions",
                    )
            continue
        elif field == "requirements" and isinstance(old, StandardReference):
            assert isinstance(new, StandardReference)
            _property(
                properties,
                field,
                kind,
                category,
                requirements(old.requirements),
                requirements(new.requirements),
            )
            _property(
                properties,
                field + ".documentation",
                ChangeKind.DOCUMENTATION_CHANGED,
                ChangeCategory.DOCUMENTATION_CHANGE,
                requirements(old.requirements, documentation=True),
                requirements(new.requirements, documentation=True),
            )
            continue
        if kind is ChangeKind.UNKNOWN_CHANGE:
            category = ChangeCategory.UNKNOWN_CHANGE
        _property(properties, field, kind, category, semantic(before), semantic(after))
    if not properties and not relationships:
        return None
    return EntityChange(
        kind=ChangeKind.ENTITY_MODIFIED,
        old_entity=old,
        new_entity=new,
        match=match,
        properties=tuple(sorted(properties, key=lambda p: p.field)),
        relationships=tuple(sorted(relationships, key=lambda r: r.field)),
    )


def _certain_unmatched(matching: MatchingResult, *, old: bool) -> set[str]:
    unmatched = matching.unmatched_old if old else matching.unmatched_new
    opposite = matching.unmatched_new if old else matching.unmatched_old
    uncertain_types = {
        item.entity.canonical_type
        for item in opposite
        if item.reason is not UnmatchedReason.NO_COUNTERPART
    }
    uncertain_types.update(
        entity.canonical_type
        for group in matching.ambiguities
        for entity in (group.new_entities if old else group.old_entities)
    )
    result = {
        item.entity.key
        for item in unmatched
        if item.reason is UnmatchedReason.NO_COUNTERPART
        and item.entity.canonical_type not in uncertain_types
    }
    # A parameter disappears/appears with its conclusively removed/added command.
    result.update(item.entity.key for item in unmatched if item.dependency_key in result)
    return result


def compare_interfaces(old: EquipmentInterface, new: EquipmentInterface) -> ChangeSet:
    """Resolve, match, and compare canonical interfaces without source-layer I/O."""
    if type(old) is not EquipmentInterface or type(new) is not EquipmentInterface:
        raise ModelValidationError("Comparison requires two canonical EquipmentInterface models")
    old_model, new_model = resolve_references(old), resolve_references(new)
    matching = match_interfaces(old_model.interface, new_model.interface)
    issues: list[ComparisonIssue] = []
    old_certain = _certain_unmatched(matching, old=True)
    new_certain = _certain_unmatched(matching, old=False)
    left, right = (
        _Side("old", old_model, matching, old_certain, issues),
        _Side("new", new_model, matching, new_certain, issues),
    )
    changes: list[EntityChange] = []
    for match in matching.matches:
        changed = _compare_entity(match.old_entity, match.new_entity, left, right, match)
        if changed is not None:
            changes.append(changed)
    for before, after in (
        (old_model.interface.equipment, new_model.interface.equipment),
        (old_model.interface, new_model.interface),
    ):
        changed = _compare_entity(before, after, left, right)
        if changed is not None:
            changes.append(changed)
    for side, unmatched, certain, kind in (
        (left, matching.unmatched_old, old_certain, ChangeKind.ENTITY_REMOVED),
        (right, matching.unmatched_new, new_certain, ChangeKind.ENTITY_ADDED),
    ):
        for item in unmatched:
            if item.entity.key in certain:
                changes.append(
                    EntityChange(
                        kind=kind,
                        old_entity=item.entity if side is left else None,
                        new_entity=item.entity if side is right else None,
                    )
                )
            else:
                issues.append(
                    ComparisonIssue(
                        kind=IssueKind.INSUFFICIENT_IDENTITY,
                        side=side.side,
                        entity_key=item.entity.key,
                        entity_type=item.entity.canonical_type,
                        detail=item.reason.value
                        if item.reason is not UnmatchedReason.NO_COUNTERPART
                        else "Opposite inventory has uncertain identities of this type",
                    )
                )
    for ambiguity in matching.ambiguities:
        for side, entities in ((left, ambiguity.old_entities), (right, ambiguity.new_entities)):
            for entity in entities:
                issues.append(
                    ComparisonIssue(
                        kind=IssueKind.AMBIGUOUS_IDENTITY,
                        side=side.side,
                        entity_key=entity.key,
                        entity_type=entity.canonical_type,
                        detail=",".join(reason.value for reason in ambiguity.reasons),
                    )
                )
    # Reference uncertainty exists even on an added/removed/ambiguous owner.
    for side in (left, right):
        for subject in (
            *side.model.interface.entities(),
            side.model.interface.equipment,
            side.model.interface,
        ):
            for field in (
                "unknown_extensions",
                "extension_metadata",
                "structure",
                "value_format",
                "state_transition",
            ):
                value = getattr(subject, field, None)
                opaque = (
                    bool(value)
                    if field == "unknown_extensions"
                    else bool(value.entries)
                    if isinstance(value, JsonObject)
                    else bool(_items(structure_annotations(value, opaque=True)))
                    if field in {"structure", "value_format"}
                    else bool(getattr(value, "unknown_extensions", ()))
                )
                if opaque:
                    side.issue(
                        IssueKind.UNKNOWN_CONTENT,
                        subject,
                        field,
                        "Opaque content cannot establish semantic equivalence",
                    )
        for relationship in side.model.relationships:
            if relationship.reference.unknown_extensions or relationship.reference.metadata.entries:
                side.issue(
                    IssueKind.UNKNOWN_CONTENT,
                    side.entities[relationship.owner_key],
                    relationship.role,
                    "Reference has opaque metadata",
                )
            if relationship.state is not ResolutionState.RESOLVED:
                side.issue(
                    IssueKind.UNRESOLVED_REFERENCE,
                    side.entities[relationship.owner_key],
                    relationship.role,
                    "Reference endpoint is not uniquely resolved",
                )
    old_context_index = build_dependency_index(old_model)
    new_context_index = build_dependency_index(new_model)

    def context(index: DependencyIndex, subject: ChangeSubject | None) -> DependencyContext | None:
        if subject is None:
            return None
        key = _key(subject)
        if key is not None:
            return index.context_for(key)
        return DependencyContext(
            subject_key=None,
            subject_type=subject.canonical_type,
            excluded_unresolved_graph_relationships=index.excluded_unresolved_graph_relationships,
        )

    changes = [
        replace(
            change,
            old_context=context(old_context_index, change.old_entity),
            new_context=context(new_context_index, change.new_entity),
        )
        for change in changes
    ]
    return ChangeSet(
        matching=matching,
        entity_changes=tuple(
            sorted(
                changes,
                key=lambda c: (
                    c.entity_type.value,
                    _key(c.old_entity) or "" if c.old_entity is not None else "",
                    _key(c.new_entity) or "" if c.new_entity is not None else "",
                    c.kind.value,
                ),
            )
        ),
        issues=tuple(
            sorted(
                set(issues),
                key=lambda i: (
                    i.side,
                    i.entity_type.value if i.entity_type else "",
                    i.entity_key or "",
                    i.field or "",
                    i.kind.value,
                    i.detail,
                ),
            )
        ),
    )


def to_change_set_dict(changes: ChangeSet) -> dict[str, JsonData]:
    """Versioned JSON projection retains match evidence and original provenance."""
    if type(changes) is not ChangeSet:
        raise ModelValidationError("Change serialization requires ChangeSet")
    encoded = encode(changes)
    assert isinstance(encoded, dict)
    entities = encoded["entity_changes"]
    assert isinstance(entities, list)
    for item, change in zip(entities, changes.entity_changes, strict=True):
        assert isinstance(item, dict)
        item["change_kinds"] = encode(change.kinds)
        item["categories"] = encode(change.categories)
        for side in ("old_context", "new_context"):
            context_value = getattr(change, side)
            encoded_context = item[side]
            if context_value is not None and isinstance(encoded_context, dict):
                encoded_context["statements"] = encode(context_value.statements)
    return {
        "change_schema_version": "1.0",
        "is_complete": changes.is_complete,
        "has_interface_changes": changes.has_interface_changes,
        "has_documentation_changes": changes.has_documentation_changes,
        "change_set": encoded,
    }


def to_change_set_json(changes: ChangeSet) -> str:
    return dump(to_change_set_dict(changes)) + "\n"
