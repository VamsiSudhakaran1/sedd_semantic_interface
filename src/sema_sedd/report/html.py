"""Self-contained, offline HTML presentation of canonical comparison evidence."""

from __future__ import annotations

import json
from base64 import b64encode
from hashlib import sha256
from html import escape

from sema_sedd.compare import ChangeCategory, ChangeKind, ChangeSet, EntityChange
from sema_sedd.compare._values import JsonData, encode
from sema_sedd.exceptions import ReportError
from sema_sedd.graph import DependencyContext
from sema_sedd.model import SourceProvenance
from sema_sedd.model.domain import EquipmentInterface, EquipmentMetadata, InterfaceEntity
from sema_sedd.report.json_report import (
    ReportDiagnostic,
    ReportSource,
    public_change_id,
    report_from_changes,
)

type ReportEntity = InterfaceEntity | EquipmentMetadata | EquipmentInterface

_CSS = """
:root{color-scheme:light;font-family:system-ui,-apple-system,Segoe UI,sans-serif;
  color:#172336;background:#f5f7fa}*{box-sizing:border-box}body{margin:0}
main{max-width:1120px;margin:auto;padding:2rem 1.25rem 4rem}
h1{font-size:2rem;margin:.25rem 0}.eyebrow{color:#47607d;font-weight:700;letter-spacing:.09em;
  text-transform:uppercase;font-size:.74rem}.lede{color:#465971;margin:.5rem 0 1.5rem}
.sources{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem;margin:1.25rem 0}
.source,.metric,.toolbar,.entity-card,.notice,.plain-card{background:white;border:1px solid #d9e1ec;
  border-radius:10px}.source{padding:1rem;min-width:0}
.source strong{display:block;margin-bottom:.35rem}
.source code{overflow-wrap:anywhere;font-size:.87rem}.source small{display:block;color:#50627b}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:.65rem;
  margin:1.25rem 0}
.metric{padding:.8rem}.metric b{display:block;font-size:1.45rem}
.metric span{color:#4d5e74;font-size:.86rem}
.notice{padding:.9rem 1rem;margin:1rem 0;border-left:4px solid #ab6224}
.toolbar{display:flex;gap:1rem;align-items:end;flex-wrap:wrap;padding:1rem;margin:1rem 0}
.toolbar label{display:grid;gap:.35rem;font-size:.88rem;font-weight:650}.toolbar input[type=search],
.toolbar select{font:inherit;padding:.55rem .65rem;border:1px solid #9baec4;border-radius:6px;
  background:white;min-width:180px}.toolbar input[type=search]{min-width:min(340px,85vw)}
.toolbar .check{display:flex;align-items:center;gap:.5rem;min-height:38px}
.count{margin-left:auto;color:#51637a;font-size:.88rem}h2{margin:2rem 0 .7rem;font-size:1.32rem}
.entity-card{margin:.8rem 0;overflow:hidden}
.entity-card>summary{cursor:pointer;padding:1rem 1.15rem;
  display:flex;gap:.75rem;align-items:center;flex-wrap:wrap;list-style:none}
.entity-card>summary::-webkit-details-marker{display:none}.entity-card>summary:before{content:'▸';color:#48617f}
.entity-card[open]>summary:before{content:'▾'}.entity-card>summary:hover{background:#f2f6fb}
.entity-card>summary strong{font-size:1.02rem}.muted{color:#52657d}.pill{font-size:.76rem;
  border-radius:99px;padding:.25rem .55rem;background:#e8eef6;color:#23405e;font-weight:650}
.pill.doc{background:#f3eaf4;color:#653b6e}.pill.unknown{background:#fff0df;color:#77501a}
.entity-body{padding:0 1.15rem 1.25rem;border-top:1px solid #e6ebf2}
.entity-meta{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem;margin:1rem 0}
.entity-meta section{min-width:0}.entity-meta h3{font-size:.88rem;margin:.25rem 0;color:#455c77}
.entity-meta p,.entity-meta li{font-size:.88rem;overflow-wrap:anywhere}
.change-row{border-top:1px solid #e4eaf1;padding:1rem 0}
.change-row h3{margin:0 0 .65rem;font-size:.98rem}
.change-row code{font-size:.81rem;color:#153b68;background:#eef3f9;padding:.2rem .35rem;
  border-radius:4px;overflow-wrap:anywhere}.change-row .kind{font-size:.82rem;color:#52657d}
.values{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75rem}
.values strong{font-size:.8rem;color:#49617c}.values pre,.proof pre{white-space:pre-wrap;
  overflow-wrap:anywhere;background:#f6f8fb;border:1px solid #e4eaf1;border-radius:6px;
  margin:.3rem 0 0;padding:.65rem;max-height:18rem;overflow:auto;font-size:.81rem}
.subdetails{margin:.85rem 0}.subdetails summary{cursor:pointer;font-size:.86rem;font-weight:650}
.subdetails ul{margin:.55rem 0;padding-left:1.3rem}.subdetails li{margin:.35rem 0;font-size:.86rem}
.plain-card{padding:1rem;margin:.6rem 0;overflow-wrap:anywhere}.plain-card p{margin:.4rem 0}
.empty{padding:1rem;color:#52657d;background:white;border:1px dashed #c5d2e0;border-radius:8px}
[hidden]{display:none!important}:focus-visible{outline:3px solid #316cae;outline-offset:2px}
@media(max-width:650px){main{padding:1.2rem .8rem 3rem}.sources,.entity-meta,.values{
  grid-template-columns:1fr}.count{margin-left:0;width:100%}}
"""

_JS = """
(() => {
  const search = document.getElementById('search');
  const filter = document.getElementById('change-filter');
  const docs = document.getElementById('show-docs');
  const count = document.getElementById('visible-count');
  const cards = Array.from(document.querySelectorAll('.entity-card'));
  const text = cards.map(card => card.textContent.toLocaleLowerCase());
  function accepts(row, mode) {
    if (mode === 'all') return true;
    if (mode === 'added' || mode === 'removed') return row.dataset.direction === mode;
    if (mode === 'interface' || mode === 'documentation' || mode === 'unknown')
      return row.dataset.category === mode.toUpperCase() + '_CHANGE';
    return row.dataset.scope === mode;
  }
  function update() {
    const term = search.value.trim().toLocaleLowerCase();
    let visible = 0;
    cards.forEach((card, index) => {
      let rows = 0;
      card.querySelectorAll('.change-row').forEach(row => {
        row.hidden = (!docs.checked && row.dataset.category === 'DOCUMENTATION_CHANGE')
          || !accepts(row, filter.value);
        if (!row.hidden) rows += 1;
      });
      card.hidden = rows === 0 || (term !== '' && !text[index].includes(term));
      if (!card.hidden) visible += 1;
    });
    count.textContent = visible + ' of ' + cards.length + ' changed entities shown';
  }
  search.addEventListener('input', update);
  filter.addEventListener('change', update);
  docs.addEventListener('change', update);
  update();
})();
"""


def _h(value: object) -> str:
    return escape(str(value), quote=True)


def _pretty(value: object) -> str:
    projected = value if isinstance(value, (dict, list)) else encode(value)
    return _h(json.dumps(projected, ensure_ascii=False, sort_keys=True, indent=2))


def _label(entity: ReportEntity) -> str:
    return entity.name or entity.implementation_id or getattr(entity, "key", None) or "Unnamed"


def _location(item: SourceProvenance) -> str:
    parts = [item.source_document]
    if item.source_path:
        parts.append(item.source_path)
    if item.line is not None:
        parts.append(f"line {item.line}" + (f", column {item.column}" if item.column else ""))
    if item.source_identifier:
        parts.append(f"ID {item.source_identifier}")
    return " · ".join(parts)


def _provenance(entity: ReportEntity | None, side: str) -> str:
    if entity is None:
        body = "<p>Entity absent on this side.</p>"
    elif not entity.provenance:
        body = "<p>Source location not recorded.</p>"
    else:
        body = (
            "<ul>"
            + "".join(f"<li>{_h(_location(item))}</li>" for item in entity.provenance)
            + "</ul>"
        )
    return f"<section><h3>Source {side} provenance</h3>{body}</section>"


def _matching(change: EntityChange) -> str:
    if change.match is None:
        return "No confirmed counterpart; this is a definite addition or removal."
    match = change.match
    tokens = "; ".join(" / ".join(item.identity) for item in match.evidence)
    return (
        f"Matched by {_h(match.strategy.value.replace('_', ' ').lower())} "
        f"({_h(match.confidence.value.replace('_', ' ').lower())}). "
        f"Exact identity evidence: {_h(tokens)}."
    )


def _dependencies(context: DependencyContext | None, side: str) -> str:
    if context is None:
        return (
            f"<section><h3>Source {side} dependencies</h3>"
            "<p>Entity absent on this side.</p></section>"
        )
    statements = "".join(f"<li>{_h(item)}</li>" for item in context.statements)
    proofs = "".join(
        "<li>"
        + _h(dependency.kind.value.replace("_", " ").title())
        + ": "
        + _h(dependency.entity_type.value.replace("_", " "))
        + " "
        + _h(dependency.implementation_id or dependency.name or dependency.entity_key)
        + f" ({len(dependency.evidence)} proof(s))</li>"
        for dependency in context.dependencies
    )
    evidence = (
        "<details class='subdetails'><summary>Dependency evidence "
        f"({len(context.dependencies)})</summary>"
        f"<ul>{proofs}</ul></details>"
        if proofs
        else ""
    )
    excluded = (
        f"<p class='muted'>{context.excluded_unresolved_graph_relationships} unresolved graph "
        "relationship(s) excluded from dependency counts.</p>"
        if context.excluded_unresolved_graph_relationships
        else ""
    )
    return (
        f"<section><h3>Source {side} dependencies</h3>"
        f"<ul>{statements}</ul>{evidence}{excluded}</section>"
    )


def _values(before: object, after: object) -> str:
    return (
        "<div class='values'><div><strong>Before · source A</strong><pre>"
        + _pretty(before)
        + "</pre></div><div><strong>After · source B</strong><pre>"
        + _pretty(after)
        + "</pre></div></div>"
    )


def _row(
    change_id: str,
    category: ChangeCategory,
    scope: str,
    field: str | None,
    before: object,
    after: object,
    *,
    direction: str = "",
    delta: str = "",
) -> str:
    title = field.replace("_", " ").title() if field else scope.title()
    return (
        f"<section class='change-row' data-category='{_h(category.value)}' "
        f"data-scope='{_h(scope)}' data-direction='{_h(direction)}'>"
        f"<h3>{_h(title)} <code>{_h(change_id)}</code> "
        f"<span class='kind'>{_h(category.value.replace('_', ' ').lower())}</span></h3>"
        + _values(before, after)
        + delta
        + "</section>"
    )


def _entity_card(change: EntityChange) -> str:
    entity = change.new_entity or change.old_entity
    assert entity is not None
    old, new = change.old_entity, change.new_entity
    rows: list[str] = []
    if change.kind in {ChangeKind.ENTITY_ADDED, ChangeKind.ENTITY_REMOVED}:
        direction = "added" if change.kind is ChangeKind.ENTITY_ADDED else "removed"
        rows.append(
            _row(
                public_change_id(change.entity_type, change.kind),
                ChangeCategory.INTERFACE_CHANGE,
                "entity",
                None,
                old,
                new,
                direction=direction,
            )
        )
    for property_change in change.properties:
        rows.append(
            _row(
                public_change_id(change.entity_type, property_change.kind),
                property_change.category,
                "property",
                property_change.field,
                property_change.old_value,
                property_change.new_value,
            )
        )
    for relationship in change.relationships:
        delta = (
            "<details class='subdetails'><summary>Relationship delta</summary><div class='values'>"
            f"<div><strong>Added</strong><pre>{_pretty(relationship.added)}</pre></div>"
            f"<div><strong>Removed</strong><pre>{_pretty(relationship.removed)}</pre></div></div>"
            f"<p>Order changed: {_h(relationship.order_changed)} · Presence changed: "
            f"{_h(relationship.presence_changed)}</p></details>"
        )
        rows.append(
            _row(
                public_change_id(change.entity_type, relationship.kind),
                relationship.category,
                "relationship",
                relationship.field,
                relationship.old_value,
                relationship.new_value,
                delta=delta,
            )
        )
    count = len(rows)
    categories = ""
    for category in change.categories:
        color = (
            "doc"
            if category is ChangeCategory.DOCUMENTATION_CHANGE
            else "unknown"
            if category is ChangeCategory.UNKNOWN_CHANGE
            else ""
        )
        categories += (
            f"<span class='pill {color}'>{_h(category.value.replace('_', ' ').title())}</span>"
        )
    identity = (
        f"ID {_h(old.implementation_id if old else '—')} → "
        f"{_h(new.implementation_id if new else '—')}"
    )
    return (
        "<details class='entity-card'><summary>"
        f"<strong>{_h(change.entity_type.value.replace('_', ' ').title())}: "
        f"{_h(_label(entity))}</strong>"
        f"<span class='muted'>{identity}</span><span class='pill'>{count} change(s)</span>"
        f"{categories}</summary><div class='entity-body'>"
        f"<p><strong>Matching reason:</strong> {_matching(change)}</p>"
        "<div class='entity-meta'>"
        + _provenance(old, "A")
        + _provenance(new, "B")
        + _dependencies(change.old_context, "A")
        + _dependencies(change.new_context, "B")
        + "</div>"
        + "".join(rows)
        + "</div></details>"
    )


def _records(report: dict[str, JsonData], key: str) -> list[dict[str, JsonData]]:
    value = report[key]
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ReportError(f"Invalid {key} report section")
    return [item for item in value if isinstance(item, dict)]


def _summary(report: dict[str, JsonData]) -> dict[str, JsonData]:
    value = report["summary"]
    if not isinstance(value, dict):
        raise ReportError("Invalid report summary")
    return value


def _issue(item: dict[str, JsonData]) -> str:
    code = item.get("issue_code", "UNKNOWN")
    side = item.get("source", "?")
    detail = item.get("detail", "")
    identity = item.get("identity_ambiguity")
    evidence = (
        f"<details class='subdetails'><summary>Identity evidence</summary>"
        f"<pre>{_pretty(identity)}</pre></details>"
        if identity is not None
        else ""
    )
    return (
        "<article class='plain-card'>"
        f"<strong>{_h(code)}</strong> <span class='muted'>· source {_h(str(side).upper())}</span>"
        f"<p>{_h(detail)}</p>{evidence}</article>"
    )


def _diagnostic(item: dict[str, JsonData]) -> str:
    source = str(item.get("source", "?")).upper()
    provenance = item.get("provenance")
    location = (
        f"<details class='subdetails'><summary>Source location</summary>"
        f"<pre>{_pretty(provenance)}</pre></details>"
        if provenance is not None
        else ""
    )
    return (
        "<article class='plain-card'>"
        f"<strong>{_h(item.get('code', 'UNKNOWN'))}</strong> "
        f"<span class='muted'>· {_h(item.get('severity', '?'))} · source {_h(source)}</span>"
        f"<p>{_h(item.get('message', ''))}</p>{location}</article>"
    )


def render_html_report(
    changes: ChangeSet,
    source_a: ReportSource,
    source_b: ReportSource,
    *,
    diagnostics_a: tuple[ReportDiagnostic, ...] = (),
    diagnostics_b: tuple[ReportDiagnostic, ...] = (),
) -> str:
    """Render complete local HTML; controls enhance an otherwise readable document."""
    report = report_from_changes(
        changes,
        source_a,
        source_b,
        diagnostics_a=diagnostics_a,
        diagnostics_b=diagnostics_b,
    )
    summary = _summary(report)
    issues = _records(report, "unresolved")
    diagnostics = _records(report, "diagnostics")
    cards = "".join(_entity_card(change) for change in changes.entity_changes)
    if not cards:
        message = (
            "No confirmed changes. Unresolved items prevent a complete equivalence conclusion."
            if summary["is_complete"] is False
            else "No semantic changes found in the supported comparison scope."
        )
        cards = f"<p class='empty'>{_h(message)}</p>"
    notice = (
        "<div class='notice'><strong>Comparison is incomplete.</strong> "
        "Unresolved evidence limits what can be concluded from the confirmed changes.</div>"
        if summary["is_complete"] is False
        else ""
    )
    metrics = (
        ("Matched", "matched"),
        ("Changed entities", "changed_entities"),
        ("Added", "added"),
        ("Removed", "removed"),
        ("Total changes", "changes"),
        ("Interface changes", "interface_changes"),
        ("Documentation changes", "documentation_changes"),
        ("Unknown changes", "unknown_changes"),
        ("Unresolved", "unresolved"),
        ("Diagnostics", "diagnostics"),
    )
    metric_html = "".join(
        f"<div class='metric'><b>{_h(summary[key])}</b><span>{_h(label)}</span></div>"
        for label, key in metrics
    )
    issues_html = "".join(_issue(item) for item in issues) or (
        "<p class='empty'>No unresolved items recorded.</p>"
    )
    diagnostics_html = "".join(_diagnostic(item) for item in diagnostics) or (
        "<p class='empty'>No diagnostics recorded.</p>"
    )
    script_hash = b64encode(sha256(_JS.encode("utf-8")).digest()).decode("ascii")
    return (
        "<!doctype html>\n<html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; "
        f"style-src 'unsafe-inline'; script-src 'sha256-{script_hash}'; base-uri 'none'; "
        "form-action 'none'; connect-src 'none'\">"
        "<title>SEDD semantic comparison</title><style>" + _CSS + "</style></head><body><main>"
        "<p class='eyebrow'>Local semantic comparison</p><h1>SEDD comparison report</h1>"
        "<p class='lede'>Confirmed interface changes and supporting evidence. "
        "Dependency statements describe references, not application impact.</p>"
        "<div class='sources'>"
        f"<div class='source'><strong>Source A · Before</strong><code>{_h(source_a.path)}</code>"
        f"<small>Revision {_h(source_a.revision)}</small></div>"
        f"<div class='source'><strong>Source B · After</strong><code>{_h(source_b.path)}</code>"
        f"<small>Revision {_h(source_b.revision)}</small></div></div>"
        + notice
        + "<section aria-labelledby='summary-title'><h2 id='summary-title'>Summary</h2>"
        f"<div class='metrics'>{metric_html}</div></section>"
        "<section aria-labelledby='changes-title'><h2 id='changes-title'>Changes</h2>"
        "<div class='toolbar'>"
        "<label for='search'>Search changed entities<input id='search' type='search' "
        "placeholder='Name, ID, code, or evidence'></label>"
        "<label for='change-filter'>Change filter<select id='change-filter'>"
        "<option value='all'>All changes</option><option value='added'>Added</option>"
        "<option value='removed'>Removed</option><option value='interface'>Interface</option>"
        "<option value='property'>Property</option>"
        "<option value='relationship'>Relationship</option>"
        "<option value='documentation'>Documentation</option>"
        "<option value='unknown'>Unknown</option>"
        "</select></label>"
        "<label class='check' for='show-docs'><input id='show-docs' type='checkbox' checked>"
        "Show documentation changes</label>"
        "<span class='count' id='visible-count' aria-live='polite'></span></div>"
        + cards
        + "</section><section aria-labelledby='unresolved-title'><h2 id='unresolved-title'>"
        "Unresolved items</h2>"
        + issues_html
        + "</section><section aria-labelledby='diagnostics-title'><h2 id='diagnostics-title'>"
        "Diagnostics</h2>"
        + diagnostics_html
        + "</section><footer><p class='muted'>Generated locally by sema-sedd "
        f"{_h(report['tool_version'])} · report schema {_h(report['report_schema_version'])}. "
        "No network resources or telemetry are used.</p></footer></main><script>"
        + _JS
        + "</script></body></html>\n"
    )
