"""Revision-neutral, evidence-based cross-version identity matching."""

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
