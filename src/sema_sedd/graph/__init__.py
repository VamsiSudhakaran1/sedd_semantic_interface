"""Revision-neutral reference indexes and relationship resolution."""

from sema_sedd.graph.context import (
    Dependency,
    DependencyContext,
    DependencyEdge,
    DependencyEvidence,
    DependencyIndex,
    DependencyKind,
    build_dependency_index,
)
from sema_sedd.graph.diagnostics import relationship_diagnostics
from sema_sedd.graph.resolution import (
    ReferenceIndexes,
    Relationship,
    RelationshipModel,
    ResolutionState,
    build_reference_indexes,
    resolve_references,
)

__all__ = [
    "Dependency",
    "DependencyContext",
    "DependencyEdge",
    "DependencyEvidence",
    "DependencyIndex",
    "DependencyKind",
    "build_dependency_index",
    "ReferenceIndexes",
    "Relationship",
    "RelationshipModel",
    "ResolutionState",
    "build_reference_indexes",
    "resolve_references",
    "relationship_diagnostics",
]
