"""Factual dependency context from resolved edges and explicit bounded joins."""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from sema_sedd.exceptions import ModelValidationError
from sema_sedd.graph.resolution import RelationshipModel, ResolutionState
from sema_sedd.limits import MAX_DEPENDENCY_PATHS, WorkBudget
from sema_sedd.model import CanonicalType, EntityReference
from sema_sedd.model._base import Record
from sema_sedd.model.domain import InterfaceEntity


class DependencyKind(StrEnum):
    REFERENCED_BY = "REFERENCED_BY"
    LINKED_REPORT = "LINKED_REPORT"
    LINKED_EVENT = "LINKED_EVENT"
    EVENT_VIA_REPORT = "EVENT_VIA_REPORT"


@dataclass(frozen=True, slots=True, kw_only=True)
class DependencyEdge(Record):
    """One resolved reference occurrence, retaining selectors and provenance."""

    owner_key: str
    target_key: str
    role: str
    reference: EntityReference

    def __post_init__(self) -> None:
        Record.__post_init__(self)
        if not self.owner_key or not self.role or self.reference.target_key != self.target_key:
            raise ModelValidationError("Dependency evidence requires a resolved reference")


@dataclass(frozen=True, slots=True, kw_only=True)
class DependencyEvidence(Record):
    # Edges retain their original direction; a link join is not a directed path.
    edges: tuple[DependencyEdge, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Dependency(Record):
    kind: DependencyKind
    entity_key: str
    entity_type: CanonicalType
    implementation_id: str | None
    name: str | None
    evidence: tuple[DependencyEvidence, ...]


_LABELS = {
    CanonicalType.STATUS_VARIABLE: ("status variable", "status variables"),
    CanonicalType.DATA_VARIABLE: ("data variable", "data variables"),
    CanonicalType.EQUIPMENT_CONSTANT: ("equipment constant", "equipment constants"),
    CanonicalType.COLLECTION_EVENT: ("collection event", "collection events"),
    CanonicalType.ALARM: ("alarm", "alarms"),
    CanonicalType.REMOTE_COMMAND: ("remote command", "remote commands"),
    CanonicalType.REMOTE_COMMAND_PARAMETER: ("command parameter", "command parameters"),
    CanonicalType.SUPPORTED_MESSAGE: ("supported message", "supported messages"),
    CanonicalType.VARIABLE_FORMAT: ("variable format", "variable formats"),
    CanonicalType.DEFAULT_REPORT: ("default report", "default reports"),
    CanonicalType.EVENT_REPORT_LINK: ("event/report link", "event/report links"),
    CanonicalType.STANDARD_REFERENCE: ("standard reference", "standard references"),
}


@dataclass(frozen=True, slots=True, kw_only=True)
class DependencyContext(Record):
    subject_key: str | None
    subject_type: CanonicalType
    dependencies: tuple[Dependency, ...] = ()
    # Graph-wide count, not a count of possible dependencies of this subject.
    excluded_unresolved_graph_relationships: int = 0

    @property
    def statements(self) -> tuple[str, ...]:
        if self.subject_key is None:
            return ("This change has no catalogued entity in the reference graph.",)
        statements = []
        prefixes = {
            DependencyKind.REFERENCED_BY: "Referenced by",
            DependencyKind.LINKED_REPORT: "Linked to",
            DependencyKind.LINKED_EVENT: "Linked from",
            DependencyKind.EVENT_VIA_REPORT: "Linked through containing reports to",
        }
        for kind, prefix in prefixes.items():
            counts: dict[CanonicalType, set[str]] = defaultdict(set)
            for dependency in self.dependencies:
                if dependency.kind is kind:
                    counts[dependency.entity_type].add(dependency.entity_key)
            parts = [
                f"{len(keys)} {_LABELS[entity_type][len(keys) != 1]}"
                for entity_type, keys in sorted(counts.items())
            ]
            if parts:
                phrase = ", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0]
                statements.append(f"{prefix} {phrase}.")
        return tuple(statements) or (
            "No dependencies found in the supported resolved graph paths.",
        )


def _edge_key(edge: DependencyEdge) -> tuple[str, str, str]:
    return edge.owner_key, edge.role, edge.target_key


_VARIABLES = {
    CanonicalType.STATUS_VARIABLE,
    CanonicalType.DATA_VARIABLE,
    CanonicalType.EQUIPMENT_CONSTANT,
}


@dataclass(frozen=True, slots=True)
class DependencyIndex:
    """Shared adjacency for a single graph; context uses at most three edges."""

    entities: Mapping[str, InterfaceEntity]
    incoming: Mapping[str, tuple[DependencyEdge, ...]]
    outgoing: Mapping[str, tuple[DependencyEdge, ...]]
    link_event_edges: Mapping[str, tuple[DependencyEdge, ...]]
    excluded_unresolved_graph_relationships: int
    budget: WorkBudget

    def context_for(self, key: str) -> DependencyContext:
        if key not in self.entities:
            raise ModelValidationError("Dependency subject is not in this graph")
        subject = self.entities[key]
        proofs: dict[tuple[DependencyKind, str], set[tuple[DependencyEdge, ...]]] = defaultdict(set)

        def add(kind: DependencyKind, target: str, *edges: DependencyEdge) -> None:
            self.budget.consume()
            proofs[kind, target].add(tuple(sorted(edges, key=_edge_key)))

        def link_events(report_key: str) -> Iterable[tuple[DependencyEdge, DependencyEdge]]:
            return (
                (report_edge, event_edge)
                for report_edge in self.incoming.get(report_key, ())
                if self.entities[report_edge.owner_key].canonical_type
                is CanonicalType.EVENT_REPORT_LINK
                and report_edge.role.startswith("reports[")
                for event_edge in self.link_event_edges.get(report_edge.owner_key, ())
                if event_edge.role == "event"
                and self.entities[event_edge.target_key].canonical_type
                is CanonicalType.COLLECTION_EVENT
            )

        for edge in self.incoming.get(key, ()):
            add(DependencyKind.REFERENCED_BY, edge.owner_key, edge)
            if (
                subject.canonical_type in _VARIABLES
                and self.entities[edge.owner_key].canonical_type is CanonicalType.DEFAULT_REPORT
                and edge.role.startswith("variables[")
            ):
                for report_edge, event_edge in link_events(edge.owner_key):
                    add(
                        DependencyKind.EVENT_VIA_REPORT,
                        event_edge.target_key,
                        edge,
                        report_edge,
                        event_edge,
                    )
            if (
                subject.canonical_type is CanonicalType.COLLECTION_EVENT
                and self.entities[edge.owner_key].canonical_type is CanonicalType.EVENT_REPORT_LINK
                and edge.role == "event"
            ):
                for report_edge in self.outgoing.get(edge.owner_key, ()):
                    if (
                        report_edge.role.startswith("reports[")
                        and self.entities[report_edge.target_key].canonical_type
                        is CanonicalType.DEFAULT_REPORT
                    ):
                        add(DependencyKind.LINKED_REPORT, report_edge.target_key, edge, report_edge)
        if subject.canonical_type is CanonicalType.DEFAULT_REPORT:
            for report_edge, event_edge in link_events(key):
                add(DependencyKind.LINKED_EVENT, event_edge.target_key, report_edge, event_edge)
        return DependencyContext(
            subject_key=key,
            subject_type=subject.canonical_type,
            excluded_unresolved_graph_relationships=self.excluded_unresolved_graph_relationships,
            dependencies=tuple(
                Dependency(
                    kind=kind,
                    entity_key=entity_key,
                    entity_type=self.entities[entity_key].canonical_type,
                    implementation_id=self.entities[entity_key].implementation_id,
                    name=self.entities[entity_key].name,
                    evidence=tuple(
                        DependencyEvidence(edges=edges)
                        for edges in sorted(paths, key=lambda path: tuple(map(_edge_key, path)))
                    ),
                )
                for (kind, entity_key), paths in sorted(proofs.items())
            ),
        )


def build_dependency_index(model: RelationshipModel) -> DependencyIndex:
    """Only RESOLVED graph edges can establish a dependency; never use candidates."""
    if type(model) is not RelationshipModel:
        raise ModelValidationError("Dependency context requires a RelationshipModel")
    incoming: dict[str, list[DependencyEdge]] = defaultdict(list)
    outgoing: dict[str, list[DependencyEdge]] = defaultdict(list)
    excluded = 0
    for relationship in model.relationships:
        if relationship.state is not ResolutionState.RESOLVED:
            excluded += 1
            continue
        target = relationship.reference.target_key
        assert target is not None
        edge = DependencyEdge(
            owner_key=relationship.owner_key,
            role=relationship.role,
            target_key=target,
            reference=relationship.reference,
        )
        incoming[target].append(edge)
        outgoing[edge.owner_key].append(edge)
    return DependencyIndex(
        entities=MappingProxyType({entity.key: entity for entity in model.interface.entities()}),
        incoming=MappingProxyType(
            {key: tuple(sorted(edges, key=_edge_key)) for key, edges in incoming.items()}
        ),
        outgoing=MappingProxyType(
            {key: tuple(sorted(edges, key=_edge_key)) for key, edges in outgoing.items()}
        ),
        link_event_edges=MappingProxyType(
            {
                key: tuple(edge for edge in edges if edge.role == "event")
                for key, edges in outgoing.items()
            }
        ),
        excluded_unresolved_graph_relationships=excluded,
        budget=WorkBudget(MAX_DEPENDENCY_PATHS, "Dependency evidence paths"),
    )
