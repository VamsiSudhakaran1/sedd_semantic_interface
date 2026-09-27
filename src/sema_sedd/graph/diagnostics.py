"""Factual diagnostics for finalized reference-resolution outcomes."""

from sema_sedd.diagnostics import (
    Diagnostic,
    DiagnosticCode,
    DiagnosticEntityContext,
    DiagnosticSeverity,
)
from sema_sedd.graph.resolution import RelationshipModel, ResolutionState
from sema_sedd.model import CanonicalType


def relationship_diagnostics(graph: RelationshipModel) -> tuple[Diagnostic, ...]:
    """Emit one diagnostic per nonresolved reference, never a guessed target."""
    owners = {entity.key: entity for entity in graph.interface.entities()}
    result: list[Diagnostic] = []
    for relation in graph.relationships:
        if relation.state is ResolutionState.RESOLVED:
            continue
        owner = owners.get(relation.owner_key)
        context = DiagnosticEntityContext(
            owner.canonical_type if owner is not None else CanonicalType.EQUIPMENT_INTERFACE,
            relation.owner_key if owner is not None else None,
        )
        provenance = (
            relation.reference.provenance[0]
            if relation.reference.provenance
            else owner.provenance[0]
            if owner is not None and owner.provenance
            else graph.interface.provenance[0]
            if graph.interface.provenance
            else None
        )
        ambiguous = relation.state is ResolutionState.AMBIGUOUS
        reason = relation.reason.value if relation.reason is not None else "unknown"
        result.append(
            Diagnostic(
                DiagnosticCode.AMBIGUOUS_REFERENCE
                if ambiguous
                else DiagnosticCode.UNRESOLVED_REFERENCE,
                f"Reference {relation.role} has {len(relation.candidate_keys)} possible targets"
                if ambiguous
                else f"Reference {relation.role} target could not be resolved ({reason})",
                DiagnosticSeverity.WARNING,
                provenance,
                context,
            )
        )
    return tuple(result)
