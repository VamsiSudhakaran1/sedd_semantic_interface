"""Offline, single-file visual explorer over a resolved canonical interface."""

from __future__ import annotations

from base64 import b64encode
from dataclasses import fields
from hashlib import sha256

from sema_sedd.graph import Relationship, RelationshipModel, ResolutionState
from sema_sedd.model import (
    EntityReference,
    EquipmentInterface,
)
from sema_sedd.model.domain import InterfaceEntity, StandardReference, SupportedMessage
from sema_sedd.report.html import _CSS, _h, _location, _pretty
from sema_sedd.report.json_report import ReportDiagnostic, ReportSource

_EXPLORER_CSS = """
.jump{display:flex;flex-wrap:wrap;gap:.4rem;margin:1rem 0}
.jump a{padding:.4rem .65rem;border-radius:6px;background:#e6eef8;color:#204265;
  text-decoration:none;font-size:.86rem;font-weight:650}.jump a:hover{text-decoration:underline}
.entity-view{background:#fff;border:1px solid #d9e1ec;border-radius:10px;margin:.65rem 0}
.entity-view>summary{cursor:pointer;padding:.85rem 1rem;display:flex;gap:.55rem;
  align-items:center;flex-wrap:wrap;list-style:none}
.entity-view>summary::-webkit-details-marker{display:none}
.entity-view>summary:before{content:'▸';color:#48617f}
.entity-view[open]>summary:before{content:'▾'}
.entity-view>summary:hover{background:#f2f6fb}
.entity-view .body{border-top:1px solid #e6ebf2;padding:1rem}
.entity-view h3{font-size:.9rem;margin:1rem 0 .4rem;color:#455c77}
.entity-view p{margin:.35rem 0;overflow-wrap:anywhere}
.props{width:100%;border-collapse:collapse;font-size:.87rem}
.props th,.props td{text-align:left;vertical-align:top;border-bottom:1px solid #e5ebf2;
  padding:.5rem}.props th{width:175px;color:#4c617c;font-weight:650}
.props pre{white-space:pre-wrap;overflow-wrap:anywhere;margin:0;font-size:.8rem}
.relation-list{padding-left:1.3rem;margin:.4rem 0}.relation-list li{margin:.4rem 0;
  overflow-wrap:anywhere;font-size:.87rem}.relation-list small{display:block;color:#55677e}
.relation-list a,.wkn-list a{color:#205c96}
.wkn-list{padding-left:1.3rem}.wkn-list li{margin:.35rem 0;overflow-wrap:anywhere}
.section-note{color:#4d6079;font-size:.88rem}.search-count{color:#4d6079;font-size:.87rem}
"""

_EXPLORER_JS = """
(() => {
  const input = document.getElementById('entity-search');
  const cards = Array.from(document.querySelectorAll('.entity-view'));
  const count = document.getElementById('entity-count');
  function update() {
    const term = input.value.trim().toLocaleLowerCase();
    let visible = 0;
    cards.forEach(card => {
      card.hidden = !card.dataset.search.includes(term);
      if (!card.hidden) visible += 1;
    });
    count.textContent = visible + ' of ' + cards.length + ' entities shown';
  }
  input.addEventListener('input', update);
  update();
})();
"""

_GROUPS = (
    (
        "variables",
        "Variables",
        ("status_variable", "data_variable", "equipment_constant", "variable_format"),
    ),
    ("events", "Events", ("collection_event",)),
    ("reports", "Reports", ("default_report", "event_report_link")),
    ("alarms", "Alarms", ("alarm",)),
    ("remote-commands", "Remote Commands", ("remote_command", "remote_command_parameter")),
    ("messages", "Messages", ("supported_message",)),
    ("standards-wkn", "Standards/WKN", ("standard_reference",)),
)


def _label(entity: InterfaceEntity) -> str:
    if (
        isinstance(entity, SupportedMessage)
        and entity.stream is not None
        and entity.function is not None
    ):
        return entity.name or f"S{entity.stream}F{entity.function}"
    if isinstance(entity, StandardReference):
        return entity.name or entity.designation or entity.implementation_id or entity.key
    return entity.name or entity.implementation_id or entity.key


def _search_terms(entity: InterfaceEntity) -> str:
    terms = [
        entity.key,
        entity.implementation_id or "",
        entity.name or "",
        entity.description or "",
    ]
    if entity.wkn is not None:
        terms.append(entity.wkn.value)
    if (
        isinstance(entity, SupportedMessage)
        and entity.stream is not None
        and entity.function is not None
    ):
        terms.append(f"S{entity.stream}F{entity.function}")
    if isinstance(entity, StandardReference):
        terms.append(entity.designation or "")
    return " ".join(terms).lower()


def _property_rows(entity: InterfaceEntity) -> str:
    omitted = {
        "key",
        "name",
        "description",
        "implementation_id",
        "wkn",
        "provenance",
        "unknown_extensions",
        "standards",
        "parameters",
    }
    rows: list[str] = []
    for member in fields(entity):
        if member.name in omitted:
            continue
        value = getattr(entity, member.name)
        if value is None or value == () or isinstance(value, EntityReference):
            continue
        if (
            isinstance(value, tuple)
            and value
            and all(isinstance(item, EntityReference) for item in value)
        ):
            continue
        rows.append(
            f"<tr><th scope='row'>{_h(member.name.replace('_', ' ').title())}</th>"
            f"<td><pre>{_pretty(value)}</pre></td></tr>"
        )
    return (
        "<table class='props'>" + "".join(rows) + "</table>"
        if rows
        else ("<p class='muted'>No additional structured properties recorded.</p>")
    )


def _target(
    relationship: Relationship, entities: dict[str, InterfaceEntity], anchors: dict[str, str]
) -> str:
    target_key = relationship.reference.target_key
    if relationship.state is ResolutionState.RESOLVED and target_key in entities:
        target = entities[target_key]
        return f"<a href='#{anchors[target_key]}'>{_h(_label(target))}</a>"
    selector = relationship.reference
    clues = [
        f"ID {selector.implementation_id}" if selector.implementation_id is not None else "",
        f"name {selector.name}" if selector.name is not None else "",
        f"WKN {selector.wkn.value}" if selector.wkn is not None else "",
    ]
    detail = ", ".join(item for item in clues if item) or "no target selector"
    reason = (
        relationship.reason.value if relationship.reason is not None else relationship.state.value
    )
    if relationship.state is ResolutionState.AMBIGUOUS:
        reason += f"; {len(relationship.candidate_keys)} candidates"
    return f"{_h(detail)} <span class='muted'>({_h(reason)})</span>"


def _reference_location(relationship: Relationship) -> str:
    if not relationship.reference.provenance:
        return ""
    locations = "; ".join(_location(item) for item in relationship.reference.provenance)
    return f"<small>{_h(locations)}</small>"


def _relations(
    entity: InterfaceEntity,
    graph: RelationshipModel,
    entities: dict[str, InterfaceEntity],
    anchors: dict[str, str],
) -> tuple[str, str]:
    outgoing: list[str] = []
    incoming: list[str] = []
    for relationship in graph.relationships:
        if relationship.owner_key == entity.key:
            outgoing.append(
                f"<li><strong>{_h(relationship.role)}</strong> → "
                f"{_target(relationship, entities, anchors)}"
                f"{_reference_location(relationship)}</li>"
            )
        if (
            relationship.state is ResolutionState.RESOLVED
            and relationship.reference.target_key == entity.key
        ):
            owner = entities.get(relationship.owner_key)
            if owner is not None:
                incoming.append(
                    f"<li><a href='#{anchors[owner.key]}'>{_h(_label(owner))}</a> "
                    f"→ <strong>{_h(relationship.role)}</strong>"
                    f"{_reference_location(relationship)}</li>"
                )
    for command in graph.interface.remote_commands:
        for index, parameter in enumerate(command.parameters or ()):
            if command.key == entity.key:
                outgoing.append(
                    f"<li><strong>parameters[{index}]</strong> → "
                    f"<a href='#{anchors[parameter.key]}'>{_h(_label(parameter))}</a> "
                    "<span class='muted'>(contains)</span></li>"
                )
            if parameter.key == entity.key:
                incoming.append(
                    f"<li><a href='#{anchors[command.key]}'>{_h(_label(command))}</a> "
                    f"→ <strong>parameters[{index}]</strong> "
                    "<span class='muted'>(contains)</span></li>"
                )
    outgoing_html = (
        "<ul class='relation-list'>" + "".join(outgoing) + "</ul>"
        if outgoing
        else ("<p class='muted'>No outgoing relationships recorded.</p>")
    )
    incoming_html = (
        "<ul class='relation-list'>" + "".join(incoming) + "</ul>"
        if incoming
        else ("<p class='muted'>No resolved incoming relationships recorded.</p>")
    )
    return incoming_html, outgoing_html


def _entity_view(
    entity: InterfaceEntity,
    graph: RelationshipModel,
    entities: dict[str, InterfaceEntity],
    anchors: dict[str, str],
) -> str:
    incoming, outgoing = _relations(entity, graph, entities, anchors)
    locations = "".join(f"<li>{_h(_location(item))}</li>" for item in entity.provenance)
    provenance = (
        f"<ul>{locations}</ul>"
        if locations
        else ("<p class='muted'>Source location not recorded.</p>")
    )
    wkn = (
        f"{_h(entity.wkn.value)} "
        f"<span class='muted'>({_h(entity.wkn.authority_status.value)})</span>"
        if entity.wkn is not None
        else "Not recorded"
    )
    return (
        f"<details class='entity-view' id='{anchors[entity.key]}' "
        f"data-search='{_h(_search_terms(entity))}'><summary>"
        f"<strong>{_h(_label(entity))}</strong>"
        f"<span class='pill'>{_h(entity.canonical_type.value.replace('_', ' ').title())}</span>"
        f"<span class='muted'>Source ID: {_h(entity.implementation_id or 'not recorded')}</span>"
        "</summary><div class='body'>"
        f"<p><strong>Description:</strong> {_h(entity.description or 'Not recorded')}</p>"
        f"<p><strong>WKN:</strong> {wkn}</p>"
        "<h3>Properties</h3>"
        + _property_rows(entity)
        + "<h3>Incoming relationships</h3>"
        + incoming
        + "<h3>Outgoing relationships</h3>"
        + outgoing
        + "<h3>Provenance</h3>"
        + provenance
        + "</div></details>"
    )


def _wkn_directory(entities: tuple[InterfaceEntity, ...], anchors: dict[str, str]) -> str:
    entries = sorted(
        (entity for entity in entities if entity.wkn is not None),
        key=lambda entity: (entity.wkn.value if entity.wkn else "", entity.key),
    )
    if not entries:
        return "<p class='empty'>No WKN values recorded.</p>"
    return (
        "<ul class='wkn-list'>"
        + "".join(
            f"<li><strong>{_h(entity.wkn.value if entity.wkn else '')}</strong> → "
            f"<a href='#{anchors[entity.key]}'>{_h(_label(entity))}</a> "
            f"<span class='muted'>({_h(entity.canonical_type.value.replace('_', ' '))}; "
            f"{_h(entity.wkn.authority_status.value if entity.wkn else '')})</span></li>"
            for entity in entries
        )
        + "</ul>"
    )


def _diagnostics(graph: RelationshipModel, diagnostics: tuple[ReportDiagnostic, ...]) -> str:
    entries: list[str] = []
    for item in diagnostics:
        if item.code == "REFERENCE_RESOLUTION_PENDING":
            continue
        location = f" · {_h(_location(item.provenance))}" if item.provenance else ""
        entries.append(
            f"<article class='plain-card'><strong>{_h(item.code)}</strong> "
            f"<span class='muted'>({_h(item.severity)}){location}</span>"
            f"<p>{_h(item.message)}</p></article>"
        )
    for relation in graph.relationships:
        if relation.state is ResolutionState.RESOLVED:
            continue
        reason = relation.reason.value if relation.reason is not None else relation.state.value
        entries.append(
            "<article class='plain-card'><strong>REFERENCE_"
            f"{_h(relation.state.value.upper())}</strong> "
            f"<span class='muted'>{_h(relation.owner_key)} · {_h(relation.role)}</span>"
            f"<p>{_h(reason)}; {_h(len(relation.candidate_keys))} candidate(s).</p></article>"
        )
    source = (graph.interface, graph.interface.equipment, *graph.interface.entities())
    for entity in source:
        for extension in entity.unknown_extensions:
            location = (
                _location(extension.provenance[0]) if extension.provenance else "Not recorded"
            )
            entries.append(
                f"<article class='plain-card'><strong>UNKNOWN_EXTENSION</strong> "
                f"<span class='muted'>{_h(extension.name)} · {_h(location)}</span>"
                f"<p>{_h(extension.reason)}</p></article>"
            )
    return "".join(entries) or "<p class='empty'>No diagnostics recorded.</p>"


def render_interface_html(
    graph: RelationshipModel,
    source: ReportSource,
    *,
    diagnostics: tuple[ReportDiagnostic, ...] = (),
) -> str:
    """Render one revision-neutral interface as a self-contained local document."""
    interface: EquipmentInterface = graph.interface
    ordered = tuple(
        sorted(
            interface.entities(),
            key=lambda e: (e.canonical_type.value, e.implementation_id or "", e.name or "", e.key),
        )
    )
    entities = {entity.key: entity for entity in ordered}
    anchors = {entity.key: f"entity-{index}" for index, entity in enumerate(ordered)}
    groups: list[str] = []
    for section_id, title, types in _GROUPS:
        selected = tuple(entity for entity in ordered if entity.canonical_type.value in types)
        cards = "".join(_entity_view(entity, graph, entities, anchors) for entity in selected)
        if not cards:
            cards = "<p class='empty'>No entries recorded.</p>"
        directory = (
            "<h3>Well-Known Name directory</h3>" + _wkn_directory(ordered, anchors)
            if section_id == "standards-wkn"
            else ""
        )
        groups.append(
            f"<section id='{section_id}'><h2>{_h(title)}</h2>"
            f"<p class='section-note'>{len(selected)} entity record(s)</p>"
            f"{cards}{directory}</section>"
        )
    equipment = interface.equipment
    metadata = (
        ("Model", equipment.model),
        ("Software revision", equipment.software_revision),
        ("Supplier", equipment.supplier),
        ("Created", equipment.created_date),
        ("Description", equipment.description),
    )
    metadata_html = "".join(
        f"<tr><th scope='row'>{_h(label)}</th><td>{_h(value or 'Not recorded')}</td></tr>"
        for label, value in metadata
    )
    equipment_locations = "; ".join(_location(item) for item in equipment.provenance)
    unresolved = sum(
        relation.state is not ResolutionState.RESOLVED for relation in graph.relationships
    )
    nav = "".join(f"<a href='#{section_id}'>{_h(title)}</a>" for section_id, title, _ in _GROUPS)
    script_hash = b64encode(sha256(_EXPLORER_JS.encode("utf-8")).digest()).decode("ascii")
    return (
        "<!doctype html>\n<html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; "
        f"style-src 'unsafe-inline'; script-src 'sha256-{script_hash}'; "
        "base-uri 'none'; form-action 'none'; connect-src 'none'\">"
        "<title>SEDD interface explorer</title><style>"
        + _CSS
        + _EXPLORER_CSS
        + "</style></head><body><main>"
        "<p class='eyebrow'>Local interface explorer</p><h1>SEDD interface</h1>"
        f"<p class='lede'><code>{_h(source.path)}</code> · revision {_h(source.revision)}</p>"
        "<nav class='jump' aria-label='Report sections'><a href='#overview'>Overview</a>"
        + nav
        + "<a href='#diagnostics'>Diagnostics</a></nav>"
        "<section id='overview'><h2>Overview</h2>"
        "<div class='metrics'>"
        f"<div class='metric'><b>{len(ordered)}</b><span>Entities</span></div>"
        f"<div class='metric'><b>{len(graph.relationships)}</b><span>References</span></div>"
        f"<div class='metric'><b>{unresolved}</b>"
        "<span>Unresolved or ambiguous references</span></div>"
        "</div><div class='plain-card'><h3>Equipment metadata</h3>"
        f"<table class='props'>{metadata_html}</table>"
        f"<p><strong>Provenance:</strong> {_h(equipment_locations or 'Not recorded')}</p>"
        "</div></section>"
        "<div class='toolbar'><label for='entity-search'>"
        "Search identifier, name, WKN, or description"
        "<input id='entity-search' type='search' placeholder='Search entities'></label>"
        "<span id='entity-count' class='search-count' aria-live='polite'></span></div>"
        + "".join(groups)
        + "<section id='diagnostics'><h2>Diagnostics</h2>"
        + _diagnostics(graph, diagnostics)
        + "</section><footer><p class='muted'>Generated locally by sema-sedd. "
        "No network resources or telemetry are used.</p></footer></main><script>"
        + _EXPLORER_JS
        + "</script></body></html>\n"
    )
