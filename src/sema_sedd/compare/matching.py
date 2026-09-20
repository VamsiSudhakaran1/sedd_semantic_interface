"""Conservative cross-version matching; no XML, I/O, scoring, or fuzzy identity."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum

from sema_sedd.exceptions import ModelValidationError
from sema_sedd.model import (
    CanonicalType,
    EquipmentInterface,
    EventReportLink,
    RemoteCommand,
    RemoteCommandParameter,
    StandardReference,
    SupportedMessage,
    VariableFormat,
    WknAuthority,
)
from sema_sedd.model._base import Record
from sema_sedd.model.domain import InterfaceEntity


class MatchStrategy(StrEnum):
    NATIVE_ID = "NATIVE_ID"
    WELL_KNOWN_NAME = "WELL_KNOWN_NAME"
    COMMAND_NAME = "COMMAND_NAME"
    PARAMETER_NAME = "PARAMETER_NAME"
    FORMAT_NAME = "FORMAT_NAME"
    STANDARD_DESIGNATION = "STANDARD_DESIGNATION"
    EVENT_IDENTITY = "EVENT_IDENTITY"
    STREAM_FUNCTION = "STREAM_FUNCTION"


class MatchConfidence(StrEnum):
    """Evidence categories, never probabilities or claims of certification."""

    CORROBORATED = "CORROBORATED"
    VERIFIED_WKN = "VERIFIED_WKN"
    EXACT_IDENTITY = "EXACT_IDENTITY"


class AmbiguityReason(StrEnum):
    IDENTITY_COLLISION = "IDENTITY_COLLISION"
    CONFLICTING_SIGNALS = "CONFLICTING_SIGNALS"


class UnmatchedReason(StrEnum):
    NO_COUNTERPART = "NO_COUNTERPART"
    NO_USABLE_IDENTITY = "NO_USABLE_IDENTITY"
    NO_CONFIRMED_COMMAND_SCOPE = "NO_CONFIRMED_COMMAND_SCOPE"


class IdentityChangeKind(StrEnum):
    IMPLEMENTATION_ID_CHANGED = "IMPLEMENTATION_ID_CHANGED"


@dataclass(frozen=True, slots=True, kw_only=True)
class MatchingEvidence(Record):
    """An exact identity token and every occurrence on each side.

    Scoped tokens contain both confirmed scope keys. Keys address input records;
    their equality across documents is never evidence of identity.
    """

    strategy: MatchStrategy
    entity_type: CanonicalType
    identity: tuple[str, ...]
    old_keys: tuple[str, ...]
    new_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        Record.__post_init__(self)
        if not self.identity or not (self.old_keys or self.new_keys):
            raise ModelValidationError("Matching evidence requires identity and occurrences")
        for keys in (self.old_keys, self.new_keys):
            if keys != tuple(sorted(set(keys))):
                raise ModelValidationError("Matching evidence keys must be unique and sorted")


@dataclass(frozen=True, slots=True, kw_only=True)
class IdentityChange(Record):
    kind: IdentityChangeKind
    old_value: str | None
    new_value: str | None

    def __post_init__(self) -> None:
        Record.__post_init__(self)
        if self.old_value == self.new_value:
            raise ModelValidationError("Identity change requires different field values")


@dataclass(frozen=True, slots=True, kw_only=True)
class EntityMatch(Record):
    old_entity: InterfaceEntity
    new_entity: InterfaceEntity
    strategy: MatchStrategy
    evidence: tuple[MatchingEvidence, ...]
    confidence: MatchConfidence
    changes: tuple[IdentityChange, ...] = ()

    def __post_init__(self) -> None:
        Record.__post_init__(self)
        if self.old_entity.canonical_type is not self.new_entity.canonical_type:
            raise ModelValidationError("Cross-type entity matching is unsupported")
        if not self.evidence or self.strategy not in {item.strategy for item in self.evidence}:
            raise ModelValidationError("Match requires supporting strategy evidence")
        for item in self.evidence:
            if (
                item.entity_type is not self.old_entity.canonical_type
                or item.old_keys != (self.old_entity.key,)
                or item.new_keys != (self.new_entity.key,)
            ):
                raise ModelValidationError("Match evidence must identify exactly this pair")


@dataclass(frozen=True, slots=True, kw_only=True)
class MatchAmbiguity(Record):
    """A whole conflicting component, including one-sided duplicate identities."""

    old_entities: tuple[InterfaceEntity, ...]
    new_entities: tuple[InterfaceEntity, ...]
    reasons: tuple[AmbiguityReason, ...]
    evidence: tuple[MatchingEvidence, ...]

    def __post_init__(self) -> None:
        Record.__post_init__(self)
        if len(self.old_entities) + len(self.new_entities) < 2 or not self.reasons:
            raise ModelValidationError("Ambiguity requires conflicting entities and reasons")
        if not self.evidence:
            raise ModelValidationError("Ambiguity requires recorded evidence")
        old_keys = {entity.key for entity in self.old_entities}
        new_keys = {entity.key for entity in self.new_entities}
        for item in self.evidence:
            if not set(item.old_keys) <= old_keys or not set(item.new_keys) <= new_keys:
                raise ModelValidationError("Ambiguity evidence refers outside its component")


@dataclass(frozen=True, slots=True, kw_only=True)
class UnmatchedEntity(Record):
    """No accepted match; this alone does not prove addition or removal."""

    entity: InterfaceEntity
    reason: UnmatchedReason
    evidence: tuple[MatchingEvidence, ...] = ()
    dependency_key: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class MatchingResult(Record):
    matches: tuple[EntityMatch, ...] = ()
    ambiguities: tuple[MatchAmbiguity, ...] = ()
    unmatched_old: tuple[UnmatchedEntity, ...] = ()
    unmatched_new: tuple[UnmatchedEntity, ...] = ()

    def __post_init__(self) -> None:
        Record.__post_init__(self)
        old_keys = [item.old_entity.key for item in self.matches]
        new_keys = [item.new_entity.key for item in self.matches]
        old_keys.extend(e.key for group in self.ambiguities for e in group.old_entities)
        new_keys.extend(e.key for group in self.ambiguities for e in group.new_entities)
        old_keys.extend(item.entity.key for item in self.unmatched_old)
        new_keys.extend(item.entity.key for item in self.unmatched_new)
        if len(old_keys) != len(set(old_keys)) or len(new_keys) != len(set(new_keys)):
            raise ModelValidationError("Each input entity must have exactly one matching outcome")


# These categories have native identity fields in X04, X06, X07, X11.
# Common implementation_id fields on other types are not automatically identities.
_NATIVE_TYPES = frozenset(
    {
        CanonicalType.STATUS_VARIABLE,
        CanonicalType.DATA_VARIABLE,
        CanonicalType.EQUIPMENT_CONSTANT,
        CanonicalType.COLLECTION_EVENT,
        CanonicalType.ALARM,
        CanonicalType.DEFAULT_REPORT,
    }
)
# Explanation precedence only, AFTER collision/conflict checks. No greedy consumption.
_PRIORITY = {strategy: index for index, strategy in enumerate(MatchStrategy)}


@dataclass(frozen=True, slots=True)
class _Token:
    strategy: MatchStrategy
    kind: CanonicalType
    value: tuple[str, ...]


type _Node = tuple[str, str]  # Side and document-local key.
type _Signals = dict[str, tuple[_Token, ...]]


def _token_order(token: _Token) -> tuple[int, str, tuple[str, ...]]:
    return _PRIORITY[token.strategy], token.kind.value, token.value


def _nonblank(value: str | None) -> bool:
    # Blank identities provide no continuity evidence; other lexical forms stay exact.
    return value is not None and bool(value.strip())


def _signals(entity: InterfaceEntity, scope: tuple[str, ...] = ()) -> tuple[_Token, ...]:
    result: list[_Token] = []

    def add(strategy: MatchStrategy, *values: str) -> None:
        result.append(_Token(strategy, entity.canonical_type, (*scope, *values)))

    if entity.canonical_type in _NATIVE_TYPES and _nonblank(entity.implementation_id):
        assert entity.implementation_id is not None
        add(MatchStrategy.NATIVE_ID, entity.implementation_id)
    wkn = entity.wkn
    if wkn is not None and wkn.authority_status is WknAuthority.VERIFIED:
        assert wkn.authority is not None and wkn.scope is not None
        add(MatchStrategy.WELL_KNOWN_NAME, wkn.authority, wkn.scope, wkn.value)
    name_strategy = None
    if isinstance(entity, RemoteCommand):
        name_strategy = MatchStrategy.COMMAND_NAME
    elif isinstance(entity, RemoteCommandParameter):
        name_strategy = MatchStrategy.PARAMETER_NAME
    elif isinstance(entity, VariableFormat):
        name_strategy = MatchStrategy.FORMAT_NAME
    if name_strategy is not None and _nonblank(entity.name):
        assert entity.name is not None
        add(name_strategy, entity.name)
    if isinstance(entity, StandardReference) and _nonblank(entity.designation):
        assert entity.designation is not None
        add(MatchStrategy.STANDARD_DESIGNATION, entity.designation)
    if (
        isinstance(entity, SupportedMessage)
        and entity.stream is not None
        and entity.function is not None
    ):
        # S05 shows that direction cannot safely disambiguate repeated S/F entries.
        add(MatchStrategy.STREAM_FUNCTION, str(entity.stream), str(entity.function))
    return tuple(result)


def _evidence(token: _Token, nodes: tuple[_Node, ...]) -> MatchingEvidence:
    return MatchingEvidence(
        strategy=token.strategy,
        entity_type=token.kind,
        identity=token.value,
        old_keys=tuple(key for side, key in nodes if side == "old"),
        new_keys=tuple(key for side, key in nodes if side == "new"),
    )


def _conflicting_pair(old: tuple[_Token, ...], new: tuple[_Token, ...]) -> bool:
    old_by_strategy = {token.strategy: token for token in old}
    new_by_strategy = {token.strategy: token for token in new}
    for strategy in old_by_strategy.keys() & new_by_strategy.keys():
        if strategy is MatchStrategy.NATIVE_ID:
            # WKN continuity may span an ID change. Competing ID candidates are
            # already in the full connected component and cannot be discarded.
            continue
        if old_by_strategy[strategy] != new_by_strategy[strategy]:
            return True
    return False


def _make_match(
    old: InterfaceEntity, new: InterfaceEntity, evidence: tuple[MatchingEvidence, ...]
) -> EntityMatch:
    strategies = {item.strategy for item in evidence}
    confidence = (
        MatchConfidence.CORROBORATED
        if len(strategies) > 1
        else MatchConfidence.VERIFIED_WKN
        if MatchStrategy.WELL_KNOWN_NAME in strategies
        else MatchConfidence.EXACT_IDENTITY
    )
    changes: tuple[IdentityChange, ...] = ()
    if old.implementation_id != new.implementation_id:
        changes = (
            IdentityChange(
                kind=IdentityChangeKind.IMPLEMENTATION_ID_CHANGED,
                old_value=old.implementation_id,
                new_value=new.implementation_id,
            ),
        )
    return EntityMatch(
        old_entity=old,
        new_entity=new,
        strategy=evidence[0].strategy,
        evidence=evidence,
        confidence=confidence,
        changes=changes,
    )


def _match_stage(
    old: tuple[InterfaceEntity, ...],
    new: tuple[InterfaceEntity, ...],
    old_signals: _Signals,
    new_signals: _Signals,
) -> MatchingResult:
    entities = {
        (side, entity.key): entity
        for side, source in (("old", old), ("new", new))
        for entity in source
    }
    by_node = {
        (side, key): tokens
        for side, source in (("old", old_signals), ("new", new_signals))
        for key, tokens in source.items()
    }
    groups: defaultdict[_Token, list[_Node]] = defaultdict(list)
    for node, node_tokens in sorted(by_node.items()):
        for token in node_tokens:
            groups[token].append(node)
    evidence_by_token = {token: _evidence(token, tuple(nodes)) for token, nodes in groups.items()}
    matches: list[EntityMatch] = []
    ambiguities: list[MatchAmbiguity] = []
    unmatched: dict[str, list[UnmatchedEntity]] = {"old": [], "new": []}
    seen: set[_Node] = set()
    for start in sorted(entities):
        if start in seen:
            continue
        # Entity -> token -> entity traversal avoids a quadratic candidate-pair
        # expansion for duplicates. No recursion, and every token is visited once.
        pending = [start]
        component: set[_Node] = set()
        tokens: set[_Token] = set()
        seen.add(start)
        while pending:
            node = pending.pop()
            component.add(node)
            for token in by_node[node]:
                if token in tokens:
                    continue
                tokens.add(token)
                for neighbor in groups[token]:
                    if neighbor not in seen:
                        seen.add(neighbor)
                        pending.append(neighbor)
        old_entities = tuple(entities[node] for node in sorted(component) if node[0] == "old")
        new_entities = tuple(entities[node] for node in sorted(component) if node[0] == "new")
        evidence = tuple(evidence_by_token[token] for token in sorted(tokens, key=_token_order))
        shared = tuple(item for item in evidence if item.old_keys and item.new_keys)
        collision = any(len(item.old_keys) > 1 or len(item.new_keys) > 1 for item in evidence)
        pair_conflict = len(old_entities) == len(new_entities) == 1 and _conflicting_pair(
            old_signals[old_entities[0].key], new_signals[new_entities[0].key]
        )
        if len(old_entities) == len(new_entities) == 1 and not pair_conflict and not collision:
            matches.append(_make_match(old_entities[0], new_entities[0], shared))
        elif len(component) > 1:
            reasons = []
            if collision:
                reasons.append(AmbiguityReason.IDENTITY_COLLISION)
            competing_groups = len({(item.old_keys, item.new_keys) for item in shared}) > 1
            if pair_conflict or (competing_groups and len({e.strategy for e in shared}) > 1):
                reasons.append(AmbiguityReason.CONFLICTING_SIGNALS)
            ambiguities.append(
                MatchAmbiguity(
                    old_entities=old_entities,
                    new_entities=new_entities,
                    reasons=tuple(reasons),
                    evidence=evidence,
                )
            )
        else:
            side, _ = start
            unmatched[side].append(
                UnmatchedEntity(
                    entity=entities[start],
                    reason=UnmatchedReason.NO_COUNTERPART
                    if tokens
                    else UnmatchedReason.NO_USABLE_IDENTITY,
                    evidence=evidence,
                )
            )
    return MatchingResult(
        matches=tuple(matches),
        ambiguities=tuple(ambiguities),
        unmatched_old=tuple(unmatched["old"]),
        unmatched_new=tuple(unmatched["new"]),
    )


def _link_signals(
    entity: EventReportLink, confirmed_events: dict[str, tuple[str, str]]
) -> tuple[_Token, ...]:
    result = _signals(entity)
    target = entity.event.target_key if entity.event is not None else None
    if target is not None and target in confirmed_events:
        result += (
            _Token(MatchStrategy.EVENT_IDENTITY, entity.canonical_type, confirmed_events[target]),
        )
    return result


def match_interfaces(old: EquipmentInterface, new: EquipmentInterface) -> MatchingResult:
    """Match versions of the same equipment lineage using exact canonical evidence.

    All signals participate before any match is accepted. Collision components
    remain ambiguous even if a greedy or maximum matching could select pairs.
    Parameters require confirmed command scope; event-link identity requires a
    resolved event reference and a confirmed event match. Inputs are never mutated.
    """
    if type(old) is not EquipmentInterface or type(new) is not EquipmentInterface:
        raise ModelValidationError("Matching requires two canonical EquipmentInterface models")
    old_entities, new_entities = old.entities(), new.entities()
    base_old = tuple(
        entity
        for entity in old_entities
        if not isinstance(entity, (RemoteCommandParameter, EventReportLink))
    )
    base_new = tuple(
        entity
        for entity in new_entities
        if not isinstance(entity, (RemoteCommandParameter, EventReportLink))
    )
    base = _match_stage(
        base_old,
        base_new,
        {entity.key: _signals(entity) for entity in base_old},
        {entity.key: _signals(entity) for entity in base_new},
    )
    stages = [base]
    old_events: dict[str, tuple[str, str]] = {}
    new_events: dict[str, tuple[str, str]] = {}
    old_commands: dict[str, tuple[str, str]] = {}
    new_commands: dict[str, tuple[str, str]] = {}
    for match in base.matches:
        pair = (match.old_entity.key, match.new_entity.key)
        if match.old_entity.canonical_type is CanonicalType.COLLECTION_EVENT:
            old_events[pair[0]] = new_events[pair[1]] = pair
        elif match.old_entity.canonical_type is CanonicalType.REMOTE_COMMAND:
            old_commands[pair[0]] = new_commands[pair[1]] = pair
    stages.append(
        _match_stage(
            old.event_report_links,
            new.event_report_links,
            {entity.key: _link_signals(entity, old_events) for entity in old.event_report_links},
            {entity.key: _link_signals(entity, new_events) for entity in new.event_report_links},
        )
    )
    parameters: dict[str, list[InterfaceEntity]] = {"old": [], "new": []}
    parameter_signals: dict[str, _Signals] = {"old": {}, "new": {}}
    deferred: dict[str, list[UnmatchedEntity]] = {"old": [], "new": []}
    for side, interface, confirmed in (
        ("old", old, old_commands),
        ("new", new, new_commands),
    ):
        for command in interface.remote_commands:
            for parameter in command.parameters or ():
                if command.key not in confirmed:
                    deferred[side].append(
                        UnmatchedEntity(
                            entity=parameter,
                            reason=UnmatchedReason.NO_CONFIRMED_COMMAND_SCOPE,
                            dependency_key=command.key,
                        )
                    )
                else:
                    parameters[side].append(parameter)
                    parameter_signals[side][parameter.key] = _signals(
                        parameter, confirmed[command.key]
                    )
    stages.append(
        _match_stage(
            tuple(parameters["old"]),
            tuple(parameters["new"]),
            parameter_signals["old"],
            parameter_signals["new"],
        )
    )
    result = MatchingResult(
        matches=tuple(
            sorted(
                (item for stage in stages for item in stage.matches),
                key=lambda item: (item.old_entity.key, item.new_entity.key),
            )
        ),
        ambiguities=tuple(
            sorted(
                (item for stage in stages for item in stage.ambiguities),
                key=lambda item: (
                    tuple(entity.key for entity in item.old_entities),
                    tuple(entity.key for entity in item.new_entities),
                ),
            )
        ),
        unmatched_old=tuple(
            sorted(
                [item for stage in stages for item in stage.unmatched_old] + deferred["old"],
                key=lambda item: item.entity.key,
            )
        ),
        unmatched_new=tuple(
            sorted(
                [item for stage in stages for item in stage.unmatched_new] + deferred["new"],
                key=lambda item: item.entity.key,
            )
        ),
    )
    for entities, matched, ambiguous, unmatched in (
        (
            old_entities,
            [item.old_entity for item in result.matches],
            [entity for group in result.ambiguities for entity in group.old_entities],
            result.unmatched_old,
        ),
        (
            new_entities,
            [item.new_entity for item in result.matches],
            [entity for group in result.ambiguities for entity in group.new_entities],
            result.unmatched_new,
        ),
    ):
        covered = {entity.key for entity in (*matched, *ambiguous)}
        covered.update(item.entity.key for item in unmatched)
        if covered != {entity.key for entity in entities}:
            raise ModelValidationError("Matching did not cover every input entity")
    return result
