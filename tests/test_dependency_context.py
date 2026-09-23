"""Dependency inclusion, exclusion and evidence on each side of a change."""

from dataclasses import replace
from itertools import permutations

import pytest

from sema_sedd.adapters import load_interface
from sema_sedd.compare import compare_interfaces, to_change_set_dict, to_change_set_json
from sema_sedd.exceptions import ModelValidationError
from sema_sedd.graph import (
    DependencyContext,
    DependencyKind,
    ResolutionState,
    build_dependency_index,
    resolve_references,
)
from sema_sedd.model import (
    Alarm,
    CanonicalType,
    CollectionEvent,
    DataVariable,
    DefaultReport,
    EntityReference,
    EquipmentConstant,
    EquipmentInterface,
    EventReportLink,
    SourceProvenance,
    StandardReference,
    StatusVariable,
    VariableFormat,
    WellKnownName,
    WknAuthority,
)


def ref(kind: CanonicalType, identifier: str) -> EntityReference:
    return EntityReference(
        target_types=(kind,),
        implementation_id=identifier,
        provenance=(SourceProvenance(source_document="synthetic.xml", line=10),),
    )


def fixture() -> EquipmentInterface:
    variable = StatusVariable(key="v", implementation_id="44")
    events = tuple(
        CollectionEvent(
            key=f"e{i}",
            implementation_id=str(i),
            relevant_variables=(ref(CanonicalType.STATUS_VARIABLE, "44"),),
        )
        for i in range(4)
    )
    reports = tuple(
        DefaultReport(
            key=f"r{i}",
            implementation_id=str(i),
            variables=(ref(CanonicalType.STATUS_VARIABLE, "44"),) * (i + 1),
        )
        for i in range(2)
    )
    links = tuple(
        EventReportLink(
            key=f"l{i}",
            event=ref(CanonicalType.COLLECTION_EVENT, str(i)),
            reports=(
                ref(CanonicalType.DEFAULT_REPORT, "0"),
                ref(CanonicalType.DEFAULT_REPORT, "1"),
            ),
        )
        for i in range(2)
    )
    return EquipmentInterface(
        status_variables=(variable, StatusVariable(key="other", implementation_id="99")),
        collection_events=events,
        default_reports=reports,
        event_report_links=links,
        alarms=(
            Alarm(
                key="a",
                implementation_id="72",
                set_event=ref(CanonicalType.COLLECTION_EVENT, "0"),
                clear_event=ref(CanonicalType.COLLECTION_EVENT, "0"),
            ),
            Alarm(
                key="unrelated",
                implementation_id="73",
                set_event=ref(CanonicalType.COLLECTION_EVENT, "3"),
            ),
        ),
    )


def keys(context: DependencyContext, kind: DependencyKind) -> set[str]:
    return {d.entity_key for d in context.dependencies if d.kind is kind}


def test_variable_direct_and_report_mediated_context_are_distinct() -> None:
    graph = resolve_references(fixture())
    context = build_dependency_index(graph).context_for("v")
    assert keys(context, DependencyKind.REFERENCED_BY) == {"e0", "e1", "e2", "e3", "r0", "r1"}
    assert keys(context, DependencyKind.EVENT_VIA_REPORT) == {"e0", "e1"}
    assert context.statements == (
        "Referenced by 4 collection events and 2 default reports.",
        "Linked through containing reports to 2 collection events.",
    )
    # Counts are unique entities, while repeated report members retain their proofs.
    report = next(d for d in context.dependencies if d.entity_key == "r1")
    assert len(report.evidence) == 2
    mediated = next(d for d in context.dependencies if d.kind is DependencyKind.EVENT_VIA_REPORT)
    assert len(mediated.evidence) == 3
    assert all(len(proof.edges) == 3 for proof in mediated.evidence)
    assert not {"a", "unrelated", "other"} & {d.entity_key for d in context.dependencies}
    actual_edges = {
        (r.owner_key, r.role, r.reference.target_key, r.reference)
        for r in graph.relationships
        if r.state is ResolutionState.RESOLVED
    }
    for dependency in context.dependencies:
        for proof in dependency.evidence:
            for edge in proof.edges:
                assert (edge.owner_key, edge.role, edge.target_key, edge.reference) in actual_edges
                assert edge.reference.provenance[0].line == 10


def test_event_links_reports_and_referencing_alarms_with_roles() -> None:
    context = build_dependency_index(resolve_references(fixture())).context_for("e0")
    assert keys(context, DependencyKind.REFERENCED_BY) == {"a", "l0"}
    assert keys(context, DependencyKind.LINKED_REPORT) == {"r0", "r1"}
    alarm = next(d for d in context.dependencies if d.entity_key == "a")
    assert {proof.edges[0].role for proof in alarm.evidence} == {"set_event", "clear_event"}
    assert "Referenced by 1 alarm and 1 event/report link." in context.statements
    assert "Linked to 2 default reports." in context.statements
    assert "unrelated" not in {d.entity_key for d in context.dependencies}


def test_report_context_includes_only_linked_events_not_its_variables() -> None:
    context = build_dependency_index(resolve_references(fixture())).context_for("r0")
    assert keys(context, DependencyKind.LINKED_EVENT) == {"e0", "e1"}
    assert keys(context, DependencyKind.REFERENCED_BY) == {"l0", "l1"}
    assert "Linked from 2 collection events." in context.statements
    assert not {"v", "e2", "e3", "a"} & {d.entity_key for d in context.dependencies}


def test_shared_event_does_not_make_sibling_report_a_variable_dependency() -> None:
    model = fixture()
    assert model.event_report_links[0].reports is not None
    sibling = DefaultReport(
        key="sibling", implementation_id="90", variables=(ref(CanonicalType.STATUS_VARIABLE, "99"),)
    )
    model = replace(
        model,
        default_reports=(*model.default_reports, sibling),
        event_report_links=(
            replace(
                model.event_report_links[0],
                reports=(
                    *model.event_report_links[0].reports,
                    ref(CanonicalType.DEFAULT_REPORT, "90"),
                ),
            ),
            model.event_report_links[1],
        ),
    )
    context = build_dependency_index(resolve_references(model)).context_for("v")
    assert "sibling" not in {d.entity_key for d in context.dependencies}
    assert keys(context, DependencyKind.EVENT_VIA_REPORT) == {"e0", "e1"}


def test_direct_event_roles_and_multiple_links_count_each_event_once() -> None:
    model = fixture()
    event = replace(
        model.collection_events[0], valid_data_variables=(ref(CanonicalType.STATUS_VARIABLE, "44"),)
    )
    model = replace(
        model,
        collection_events=(event, *model.collection_events[1:]),
        event_report_links=(
            *model.event_report_links,
            replace(model.event_report_links[0], key="second-link"),
        ),
    )
    context = build_dependency_index(resolve_references(model)).context_for("v")
    direct = next(
        d
        for d in context.dependencies
        if d.kind is DependencyKind.REFERENCED_BY and d.entity_key == "e0"
    )
    assert {proof.edges[0].role for proof in direct.evidence} == {
        "relevant_variables[0]",
        "valid_data_variables[0]",
    }
    assert keys(context, DependencyKind.EVENT_VIA_REPORT) == {"e0", "e1"}
    assert context.statements[1] == "Linked through containing reports to 2 collection events."


def test_resolved_cycles_do_not_trigger_transitive_context_expansion() -> None:
    # A canonical graph can represent these edges without establishing variable semantics.
    first = CollectionEvent(
        key="a",
        implementation_id="1",
        relevant_variables=(ref(CanonicalType.COLLECTION_EVENT, "2"),),
    )
    second = CollectionEvent(
        key="b",
        implementation_id="2",
        relevant_variables=(ref(CanonicalType.COLLECTION_EVENT, "1"),),
    )
    third = CollectionEvent(
        key="c",
        implementation_id="3",
        relevant_variables=(ref(CanonicalType.COLLECTION_EVENT, "2"),),
    )
    model = EquipmentInterface(collection_events=(first, second, third))
    context = build_dependency_index(resolve_references(model)).context_for("a")
    assert keys(context, DependencyKind.REFERENCED_BY) == {"b"}
    assert "c" not in {d.entity_key for d in context.dependencies}


def test_synthetic_xml_context_uses_adapter_and_resolver_evidence() -> None:
    from pathlib import Path

    path = Path(__file__).parent / "fixtures" / "relationships" / "e172-complete.xml"
    old = load_interface(path, revision="E172-0225").interface
    variable = old.status_variables[0]
    new = replace(
        old,
        status_variables=(
            replace(variable, description="New documentation"),
            *old.status_variables[1:],
        ),
    )
    change = next(
        c
        for c in compare_interfaces(old, new).entity_changes
        if c.entity_type is CanonicalType.STATUS_VARIABLE
    )
    assert change.new_context is not None
    assert any(
        d.entity_type is CanonicalType.DEFAULT_REPORT for d in change.new_context.dependencies
    )
    assert any(d.kind is DependencyKind.EVENT_VIA_REPORT for d in change.new_context.dependencies)
    # The adapter preserves unknown target kinds for event variable lists.
    # Those unresolved direct references must not masquerade as event usage.
    assert not any(
        d.entity_type is CanonicalType.COLLECTION_EVENT and d.kind is DependencyKind.REFERENCED_BY
        for d in change.new_context.dependencies
    )
    assert change.new_context.excluded_unresolved_graph_relationships > 0


@pytest.mark.parametrize("variable_type", [StatusVariable, DataVariable, EquipmentConstant])
def test_each_variable_category_has_report_and_event_context(
    variable_type: type[StatusVariable] | type[DataVariable] | type[EquipmentConstant],
) -> None:
    variable = variable_type(key="v", implementation_id="44")
    model = EquipmentInterface(
        status_variables=(variable,) if isinstance(variable, StatusVariable) else (),
        data_variables=(variable,) if isinstance(variable, DataVariable) else (),
        equipment_constants=(variable,) if isinstance(variable, EquipmentConstant) else (),
        collection_events=(CollectionEvent(key="e", implementation_id="1"),),
        default_reports=(
            DefaultReport(
                key="r", implementation_id="1", variables=(ref(variable.canonical_type, "44"),)
            ),
        ),
        event_report_links=(
            EventReportLink(
                key="l",
                event=ref(CanonicalType.COLLECTION_EVENT, "1"),
                reports=(ref(CanonicalType.DEFAULT_REPORT, "1"),),
            ),
        ),
    )
    context = build_dependency_index(resolve_references(model)).context_for("v")
    assert keys(context, DependencyKind.REFERENCED_BY) == {"r"}
    assert keys(context, DependencyKind.EVENT_VIA_REPORT) == {"e"}


@pytest.mark.parametrize("broken", ["event", "report", "variable"])
def test_incomplete_path_cannot_establish_indirect_dependency(broken: str) -> None:
    model = fixture()
    if broken == "event":
        model = replace(model, collection_events=())
    elif broken == "report":
        model = replace(model, default_reports=())
    else:
        model = replace(
            model,
            default_reports=tuple(
                replace(r, variables=(ref(CanonicalType.STATUS_VARIABLE, "missing"),))
                for r in model.default_reports
            ),
        )
    context = build_dependency_index(resolve_references(model)).context_for("v")
    assert not keys(context, DependencyKind.EVENT_VIA_REPORT)
    assert context.excluded_unresolved_graph_relationships > 0


def test_ambiguous_wrong_type_untyped_and_missing_references_are_excluded() -> None:
    variable = StatusVariable(key="v", implementation_id="44")
    refs = (
        ref(CanonicalType.STATUS_VARIABLE, "44"),  # Ambiguous.
        ref(CanonicalType.DATA_VARIABLE, "44"),  # Wrong type.
        EntityReference(implementation_id="44"),  # Unsupported target type.
        ref(CanonicalType.STATUS_VARIABLE, "missing"),
    )
    model = EquipmentInterface(
        status_variables=(variable, replace(variable, key="duplicate")),
        default_reports=(DefaultReport(key="r", implementation_id="1", variables=refs),),
    )
    index = build_dependency_index(resolve_references(model))
    for key in ("v", "duplicate"):
        context = index.context_for(key)
        assert context.dependencies == ()
        assert context.excluded_unresolved_graph_relationships == 4
        assert context.statements == (
            "No dependencies found in the supported resolved graph paths.",
        )


def test_ambiguous_event_link_excludes_each_candidate_event() -> None:
    model = fixture()
    model = replace(
        model,
        collection_events=(
            *model.collection_events,
            replace(model.collection_events[0], key="duplicate"),
        ),
    )
    index = build_dependency_index(resolve_references(model))
    assert keys(index.context_for("r0"), DependencyKind.LINKED_EVENT) == {"e1"}
    assert not keys(index.context_for("e0"), DependencyKind.LINKED_REPORT)
    assert not keys(index.context_for("duplicate"), DependencyKind.LINKED_REPORT)


def test_names_ids_and_prose_never_establish_dependency_without_edges() -> None:
    model = EquipmentInterface(
        status_variables=(StatusVariable(key="v", implementation_id="1", name="Shared"),),
        collection_events=(
            CollectionEvent(
                key="e", implementation_id="1", name="Shared", description="Uses variable 1"
            ),
        ),
        default_reports=(DefaultReport(key="r", implementation_id="1", name="Shared"),),
    )
    index = build_dependency_index(resolve_references(model))
    assert all(not index.context_for(key).dependencies for key in ("v", "e", "r"))


def test_generic_incoming_reference_context_for_format_and_standard() -> None:
    model = EquipmentInterface(
        variable_formats=(VariableFormat(key="f", name="U4"),),
        standard_references=(StandardReference(key="s", designation="Synthetic"),),
        status_variables=(
            StatusVariable(
                key="v",
                implementation_id="1",
                format=EntityReference(target_types=(CanonicalType.VARIABLE_FORMAT,), name="U4"),
                standards=(
                    EntityReference(
                        target_types=(CanonicalType.STANDARD_REFERENCE,), name="Synthetic"
                    ),
                ),
            ),
        ),
    )
    index = build_dependency_index(resolve_references(model))
    assert keys(index.context_for("f"), DependencyKind.REFERENCED_BY) == {"v"}
    assert keys(index.context_for("s"), DependencyKind.REFERENCED_BY) == {"v"}


def test_comparison_attaches_separate_before_and_after_context_and_json() -> None:
    old = fixture()
    new = replace(
        old,
        status_variables=(
            replace(old.status_variables[0], description="Revised"),
            old.status_variables[1],
        ),
        default_reports=tuple(
            replace(r, variables=(ref(CanonicalType.STATUS_VARIABLE, "99"),))
            for r in old.default_reports
        ),
    )
    changes = compare_interfaces(old, new)
    variable_change = next(
        c for c in changes.entity_changes if c.entity_type is CanonicalType.STATUS_VARIABLE
    )
    assert variable_change.old_context is not None and variable_change.new_context is not None
    assert {"r0", "r1"} <= keys(variable_change.old_context, DependencyKind.REFERENCED_BY)
    assert not {"r0", "r1"} & keys(variable_change.new_context, DependencyKind.REFERENCED_BY)
    assert all(
        c.old_context is not None and c.new_context is not None for c in changes.entity_changes
    )
    data = to_change_set_dict(changes)
    assert "Referenced by 4 collection events and 2 default reports." in to_change_set_json(changes)
    assert data["change_schema_version"] == "1.0"  # Additive context fields.


def test_added_and_removed_entities_have_only_existing_side_context() -> None:
    populated = fixture()
    for old, new, side in (
        (EquipmentInterface(), populated, "new"),
        (populated, EquipmentInterface(), "old"),
    ):
        changes = compare_interfaces(old, new)
        assert changes.entity_changes
        for change in changes.entity_changes:
            assert getattr(change, f"{side}_context") is not None
            absent = "old" if side == "new" else "new"
            assert getattr(change, f"{absent}_context") is None


def test_verified_id_change_uses_the_graph_from_each_revision() -> None:
    wkn = WellKnownName(
        value="fixture.variable",
        authority="fictional-registry",
        scope="fixture",
        authority_status=WknAuthority.VERIFIED,
        provenance=(SourceProvenance(source_document="registry.json"),),
    )
    old = EquipmentInterface(
        status_variables=(StatusVariable(key="old-v", implementation_id="44", wkn=wkn),),
        default_reports=(
            DefaultReport(
                key="old-r",
                implementation_id="1",
                variables=(ref(CanonicalType.STATUS_VARIABLE, "44"),),
            ),
        ),
    )
    new = replace(
        old,
        status_variables=(replace(old.status_variables[0], key="new-v", implementation_id="8044"),),
        default_reports=(
            replace(
                old.default_reports[0],
                key="new-r",
                variables=(ref(CanonicalType.STATUS_VARIABLE, "8044"),),
            ),
        ),
    )
    changes = compare_interfaces(old, new)
    assert len(changes.entity_changes) == 1
    change = changes.entity_changes[0]
    assert change.old_context is not None and change.new_context is not None
    assert keys(change.old_context, DependencyKind.REFERENCED_BY) == {"old-r"}
    assert keys(change.new_context, DependencyKind.REFERENCED_BY) == {"new-r"}


def test_context_output_is_deterministic_across_inventory_permutations() -> None:
    old = fixture()
    new = replace(
        old,
        status_variables=(replace(old.status_variables[0], units=("C",)), old.status_variables[1]),
    )
    expected = to_change_set_json(compare_interfaces(old, new))
    for events in permutations(old.collection_events):
        permuted_old = replace(
            old, collection_events=events, default_reports=tuple(reversed(old.default_reports))
        )
        permuted_new = replace(
            new,
            collection_events=tuple(reversed(events)),
            event_report_links=tuple(reversed(new.event_report_links)),
        )
        assert to_change_set_json(compare_interfaces(permuted_old, permuted_new)) == expected


def test_singleton_metadata_and_invalid_graph_boundaries() -> None:
    old = EquipmentInterface()
    new = replace(old, equipment=replace(old.equipment, supplier="Supplier"))
    context = compare_interfaces(old, new).entity_changes[0].new_context
    assert context is not None and context.subject_key is None
    assert context.statements == ("This change has no catalogued entity in the reference graph.",)
    index = build_dependency_index(resolve_references(old))
    with pytest.raises(ModelValidationError):
        index.context_for("not-in-graph")
    with pytest.raises(ModelValidationError):
        build_dependency_index(old)  # type: ignore[arg-type]
    change = compare_interfaces(old, new).entity_changes[0]
    with pytest.raises(ModelValidationError):
        replace(
            change,
            new_context=DependencyContext(
                subject_key="wrong", subject_type=CanonicalType.STATUS_VARIABLE
            ),
        )
