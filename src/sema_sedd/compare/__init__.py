"""Revision-neutral, evidence-based cross-version identity matching."""

from sema_sedd.compare.changes import (
    ChangeCategory,
    ChangeKind,
    ChangeSet,
    ComparisonIssue,
    EntityChange,
    IssueKind,
    PropertyChange,
    RelationshipChange,
)
from sema_sedd.compare.engine import compare_interfaces, to_change_set_dict, to_change_set_json
from sema_sedd.compare.matching import (
    AmbiguityReason,
    EntityMatch,
    IdentityChange,
    IdentityChangeKind,
    MatchAmbiguity,
    MatchConfidence,
    MatchingEvidence,
    MatchingResult,
    MatchStrategy,
    UnmatchedEntity,
    UnmatchedReason,
    match_interfaces,
)

__all__ = [
    "ChangeCategory",
    "ChangeKind",
    "ChangeSet",
    "ComparisonIssue",
    "EntityChange",
    "IssueKind",
    "PropertyChange",
    "RelationshipChange",
    "compare_interfaces",
    "to_change_set_dict",
    "to_change_set_json",
    "AmbiguityReason",
    "EntityMatch",
    "IdentityChange",
    "IdentityChangeKind",
    "MatchAmbiguity",
    "MatchConfidence",
    "MatchStrategy",
    "MatchingEvidence",
    "MatchingResult",
    "UnmatchedEntity",
    "UnmatchedReason",
    "match_interfaces",
]
