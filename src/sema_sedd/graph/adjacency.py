"""One-pass adjacency including uncertain candidates and command containment."""

from collections import defaultdict
from dataclasses import dataclass

from sema_sedd.graph.resolution import Relationship, RelationshipModel
from sema_sedd.limits import MAX_CANDIDATE_OCCURRENCES, WorkBudget


@dataclass(slots=True)
class RelationshipAdjacency:
    incoming: dict[str, list[Relationship]]
    outgoing: dict[str, list[Relationship]]
    candidates: dict[str, list[Relationship]]
    contained_by: dict[str, tuple[str, int]]
    contains: dict[str, list[tuple[str, int]]]


def build_relationship_adjacency(model: RelationshipModel) -> RelationshipAdjacency:
    incoming: dict[str, list[Relationship]] = defaultdict(list)
    outgoing: dict[str, list[Relationship]] = defaultdict(list)
    candidates: dict[str, list[Relationship]] = defaultdict(list)
    contained_by = {}
    contains: dict[str, list[tuple[str, int]]] = defaultdict(list)
    budget = WorkBudget(MAX_CANDIDATE_OCCURRENCES, "Candidate adjacency projection")
    for relation in model.relationships:
        budget.consume(len(relation.candidate_keys) ** 2)
        outgoing[relation.owner_key].append(relation)
        if relation.reference.target_key is not None:
            incoming[relation.reference.target_key].append(relation)
        for candidate in relation.candidate_keys:
            candidates[candidate].append(relation)
    for command in model.interface.remote_commands:
        for index, parameter in enumerate(command.parameters or ()):
            contained_by[parameter.key] = command.key, index
            contains[command.key].append((parameter.key, index))
    return RelationshipAdjacency(incoming, outgoing, candidates, contained_by, contains)
