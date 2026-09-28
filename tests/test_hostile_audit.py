"""Adversarial input, resource-exhaustion, and indexing regression coverage."""

from __future__ import annotations

import os
import socket
from collections.abc import Iterator, Mapping
from dataclasses import replace
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import ClassVar

import pytest

from sema_sedd.adapters import load_interface
from sema_sedd.cli.explore import _bounded_distances, _relationships_for
from sema_sedd.cli.inspect import _immediate_relationships
from sema_sedd.cli.report import _write, write_interface_html_report
from sema_sedd.compare import compare_interfaces
from sema_sedd.exceptions import (
    InputError,
    InputTooLargeError,
    InvalidXmlError,
    ReportError,
    ResourceLimitError,
    UnsafeXmlError,
    UnsupportedSeddVersionError,
)
from sema_sedd.graph import (
    Relationship,
    build_dependency_index,
    build_reference_indexes,
    resolve_references,
)
from sema_sedd.graph.adjacency import build_relationship_adjacency
from sema_sedd.graph.resolution import _keys_for_types, _wkn_keys
from sema_sedd.limits import WorkBudget, bounded_join
from sema_sedd.local_files import local_path
from sema_sedd.model import (
    CanonicalType,
    CollectionEvent,
    DefaultReport,
    EntityReference,
    EquipmentInterface,
    EventReportLink,
    StatusVariable,
    WellKnownName,
)
from sema_sedd.parser import load_xml
from sema_sedd.report import ReportSource, render_html_report, render_interface_html
from tools.profile_hostile import synthetic_xml


def write(tmp_path: Path, xml: str | bytes) -> Path:
    path = tmp_path / "attack.xml"
    path.write_bytes(xml.encode() if isinstance(xml, str) else xml)
    return path


@pytest.mark.parametrize(
    "payload",
    [
        '<!DOCTYPE r SYSTEM "https://example.invalid/evil.dtd"><r/>',
        '<!DOCTYPE r [<!ENTITY x SYSTEM "file:///private">]><r>&x;</r>',
        '<!DOCTYPE r [<!ENTITY % x SYSTEM "https://example.invalid/e">%x;]><r/>',
        '<!DOCTYPE r [<!ENTITY a "abcdef"><!ENTITY b "&a;&a;">]><r>&b;</r>',
    ],
)
def test_entities_and_dtd_never_access_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: str
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Network access")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    for encoding in ("utf-8", "utf-16"):
        with pytest.raises(UnsafeXmlError, match="DOCTYPE"):
            load_xml(write(tmp_path, payload.encode(encoding)))


@pytest.mark.parametrize(
    "payload",
    [
        b"<x>\xed\xa0\x80</x>",
        b"<x>\xc0\xaf</x>",
        b"<x>\xf4\x90\x80\x80</x>",
        b"<x>&#0;</x>",
        b"<x>&#xD800;</x>",
        b"<x>\x00</x>",
        b'<?xml version="1.0" encoding="x-unknown"?><x/>',
        b'<?xml version="1.0" encoding="UTF-7"?><x/>',
    ],
)
def test_unicode_and_encoding_failures_are_controlled(tmp_path: Path, payload: bytes) -> None:
    with pytest.raises(InvalidXmlError):
        load_xml(write(tmp_path, payload))


def test_fragmented_text_is_coalesced_once_with_content_order(tmp_path: Path) -> None:
    payload = "<r>" + "&amp;" * 100_000 + "<child/>tail</r>"
    result = load_xml(write(tmp_path, payload))
    assert len(result.root.content) == 3
    assert result.root.content[0] == "&" * 100_000
    assert result.root.content[2] == "tail"


def test_huge_input_and_recursion_are_bounded(tmp_path: Path) -> None:
    path = write(tmp_path, b"x" * (10 * 1024 * 1024 + 1))
    with pytest.raises(InputTooLargeError):
        load_xml(path)
    path = write(tmp_path, "<r>" * 1000 + "</r>" * 1000)
    with pytest.raises(UnsafeXmlError, match="nesting"):
        load_xml(path)
    with pytest.raises(ValueError, match="ceiling"):
        load_xml(path, max_depth=1000)


def test_unsafe_expat_runtime_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sema_sedd.parser.ingest.expat.version_info", (2, 6, 0))
    with pytest.raises(UnsafeXmlError, match="Expat"):
        load_xml(write(tmp_path, "<r/>"))


@pytest.mark.parametrize(
    "payload,reason",
    [
        ("<r " + " ".join(f'xmlns:n{i}="urn:{i}"' for i in range(129)) + "/>", "namespace"),
        ('<r xmlns="' + "x" * 2000 + '"/>', "namespace"),
        ("<" + "x" * 2000 + "/>", "expanded name"),
        ('<r xmlns:n="' + "x" * 900 + '">' + "<n:a/>" * 19000 + "</r>", "expanded content"),
    ],
    ids=["declaration-count", "namespace-size", "name-size", "expanded-size"],
)
def test_namespace_amplification_is_bounded(tmp_path: Path, payload: str, reason: str) -> None:
    with pytest.raises(UnsafeXmlError, match=reason):
        load_xml(write(tmp_path, payload))


def test_namespace_shadowing_and_includes_do_not_establish_semantics(tmp_path: Path) -> None:
    xml = synthetic_xml(1, 0).replace("<StatusVariable>", '<StatusVariable xmlns="urn:impostor">')
    xml = xml.replace(
        "</s:DataDictionary>",
        '<xi:include xmlns:xi="http://www.w3.org/2001/XInclude" href="file:///private"/>'
        "</s:DataDictionary>",
    )
    adapted = load_interface(write(tmp_path, xml))
    assert not adapted.interface.status_variables
    assert sum(d.code == "UNKNOWN_ELEMENT" for d in adapted.diagnostics) == 2
    with pytest.raises(UnsupportedSeddVersionError):
        load_interface(
            write(
                tmp_path, xml.replace('xmlns:s="urn:semi-org:xsd.SEDD"', 'xmlns:s="urn:impostor"')
            )
        )


def test_path_amplification_fails_before_opaque_conversion(tmp_path: Path) -> None:
    # Under the XML expanded-name budget, but duplicated ancestor paths exceed 16 MiB.
    name = "x" * 800
    body = f"<{name}>" * 40 + "<leaf/>" * 600 + f"</{name}>" * 40
    xml = synthetic_xml(1, 0).replace("</s:DataDictionary>", body + "</s:DataDictionary>")
    with pytest.raises(ResourceLimitError, match="provenance"):
        load_interface(write(tmp_path, xml))


@pytest.mark.parametrize(
    "path",
    [
        "\\\\server\\share\\file.xml",
        "//server/share/file.xml",
        "/\\server/share/file.xml",
        "https://example.invalid/a",
        "file:///etc/passwd",
        "nul\x00.xml",
        "bad\ud800.xml",
    ],
)
def test_path_abuse_is_rejected_before_filesystem_access(
    path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Filesystem probe")

    monkeypatch.setattr(Path, "lstat", forbidden)
    with pytest.raises(InputError):
        local_path(path)


@pytest.mark.skipif(os.name != "nt", reason="Windows device/stream paths")
@pytest.mark.parametrize(
    "path",
    [
        "NUL",
        "CON.txt",
        "CONIN$",
        "dir/COM1",
        "file.xml:secret",
        "C:relative.xml",
        "file.xml.",
        "file.xml ",
    ],
)
def test_windows_device_and_stream_paths_are_rejected(path: str) -> None:
    with pytest.raises(InputError):
        local_path(path)


@pytest.mark.skipif(os.name != "nt", reason="Windows mapped network drives")
def test_mapped_network_drive_rejected_before_stat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sema_sedd.local_files._remote_drive", lambda anchor: True)
    with pytest.raises(InputError):
        local_path("Z:/remote.xml")


def test_symlink_ancestor_and_report_destination_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    source = real / "input.xml"
    source.write_text(synthetic_xml(1, 0))
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("Host does not allow symlink creation")
    with pytest.raises(InputError):
        load_xml(link / "input.xml")
    with pytest.raises(ReportError):
        write_interface_html_report(source, link / "report.html")


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX named pipes")
def test_fifo_is_rejected_before_open(tmp_path: Path) -> None:
    path = tmp_path / "fifo"
    vars(os)["mkfifo"](path)
    with pytest.raises(InputError, match="regular"):
        load_xml(path)


def test_hard_link_output_cannot_overwrite_input(tmp_path: Path) -> None:
    source = write(tmp_path, synthetic_xml(1, 0))
    destination = tmp_path / "alias.html"
    os.link(source, destination)
    before = source.read_bytes()
    with pytest.raises(ReportError, match="differ"):
        write_interface_html_report(source, destination)
    assert source.read_bytes() == before


def test_failed_atomic_write_preserves_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "report.html"
    output.write_text("previous")

    def fail(*args: object) -> None:
        raise OSError("simulated failure")

    monkeypatch.setattr("sema_sedd.cli.report.os.replace", fail)
    with pytest.raises(ReportError):
        _write(output, "new")
    assert output.read_text() == "previous"
    assert not list(tmp_path.glob(".sedd-*.tmp"))


class NoScan[K](Mapping[K, tuple[str, ...]]):
    def __init__(self, values: Mapping[K, tuple[str, ...]]) -> None:
        self.values_map = values
        self.lookups = 0

    def __getitem__(self, key: K) -> tuple[str, ...]:
        self.lookups += 1
        return self.values_map[key]

    def __len__(self) -> int:
        return len(self.values_map)

    def __iter__(self) -> Iterator[K]:
        raise AssertionError("Full index scan")


def test_native_and_wkn_selectors_use_constant_time_index_lookups() -> None:
    index = NoScan({(CanonicalType.STATUS_VARIABLE, str(i)): (str(i),) for i in range(10000)})
    assert _keys_for_types(index, "99", (CanonicalType.STATUS_VARIABLE,)) == {"99"}
    assert index.lookups == 1
    assert _keys_for_types(index, "99", ()) == {"99"}
    assert index.lookups == 1 + len(CanonicalType)
    interface = EquipmentInterface(
        status_variables=(
            StatusVariable(key="v", implementation_id="1", wkn=WellKnownName(value="exact")),
        )
    )
    indexes = build_reference_indexes(interface)
    wkn_index = NoScan(indexes.by_wkn)
    # Swap only after validated construction so validation is not counted as lookup work.
    object.__setattr__(indexes, "by_wkn", wkn_index)
    assert _wkn_keys(indexes, WellKnownName(value="exact"), (CanonicalType.STATUS_VARIABLE,)) == {
        "v"
    }
    assert wkn_index.lookups == 1


class CountedRelationships(tuple[Relationship, ...]):
    visits: ClassVar[int] = 0

    def __iter__(self) -> Iterator[Relationship]:
        for item in super().__iter__():
            type(self).visits += 1
            yield item


def test_rendering_and_cli_relationships_use_one_shared_adjacency(tmp_path: Path) -> None:
    graph = resolve_references(load_interface(write(tmp_path, synthetic_xml(200, 1000))).interface)
    object.__setattr__(graph, "relationships", CountedRelationships(graph.relationships))
    CountedRelationships.visits = 0
    adjacency = build_relationship_adjacency(graph)
    for entity in graph.interface.entities():
        _relationships_for(entity, adjacency)
        _immediate_relationships(entity, adjacency)
    assert CountedRelationships.visits == len(graph.relationships)
    CountedRelationships.visits = 0
    render_interface_html(graph, ReportSource("synthetic", "E172-0225"))
    assert CountedRelationships.visits <= 4 * len(graph.relationships)
    assert len(adjacency.outgoing[graph.interface.default_reports[0].key]) == 1000


def reference(kind: CanonicalType, identifier: str) -> EntityReference:
    return EntityReference(target_types=(kind,), implementation_id=identifier)


def test_collision_fanout_fails_explicitly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sema_sedd.graph.resolution.MAX_CANDIDATE_OCCURRENCES", 100)
    interface = EquipmentInterface(
        status_variables=tuple(
            StatusVariable(key=str(i), implementation_id="1") for i in range(20)
        ),
        default_reports=(
            DefaultReport(key="r", variables=(reference(CanonicalType.STATUS_VARIABLE, "1"),) * 6),
        ),
    )
    with pytest.raises(ResourceLimitError, match="candidate"):
        resolve_references(interface)


def test_candidate_projection_fanout_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    interface = EquipmentInterface(
        status_variables=tuple(
            StatusVariable(key=str(i), implementation_id="1") for i in range(20)
        ),
        default_reports=(
            DefaultReport(key="r", variables=(reference(CanonicalType.STATUS_VARIABLE, "1"),)),
        ),
    )
    graph = resolve_references(interface)
    monkeypatch.setattr("sema_sedd.graph.adjacency.MAX_CANDIDATE_OCCURRENCES", 100)
    with pytest.raises(ResourceLimitError, match="adjacency"):
        build_relationship_adjacency(graph)


def test_dependency_join_fanout_is_bounded() -> None:
    interface = EquipmentInterface(
        status_variables=(StatusVariable(key="v", implementation_id="1"),),
        collection_events=(CollectionEvent(key="e", implementation_id="2"),),
        default_reports=(
            DefaultReport(
                key="r",
                implementation_id="3",
                variables=(reference(CanonicalType.STATUS_VARIABLE, "1"),) * 20,
            ),
        ),
        event_report_links=(
            EventReportLink(
                key="l",
                event=reference(CanonicalType.COLLECTION_EVENT, "2"),
                reports=(reference(CanonicalType.DEFAULT_REPORT, "3"),) * 20,
            ),
        ),
    )
    index = build_dependency_index(resolve_references(interface))
    object.__setattr__(index, "budget", WorkBudget(100, "Dependency evidence paths"))
    with pytest.raises(ResourceLimitError, match="Dependency"):
        index.context_for("v")


def test_cycles_and_repeated_neighbors_terminate_at_requested_depth() -> None:
    graph = {"a": ("b", "b"), "b": ("a", "c"), "c": ("b", "d"), "d": ("c",)}
    assert _bounded_distances("a", graph, 0) == {"a": 0}
    assert _bounded_distances("a", graph, 2) == {"a": 0, "b": 1, "c": 2}


def test_html_output_budget_rejects_without_silent_truncation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sema_sedd.limits.MAX_HTML_CHARACTERS", 10)
    with pytest.raises(ResourceLimitError, match="HTML output"):
        bounded_join(iter(["12345", "67890", "x"]))


class Tags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))


@pytest.mark.parametrize(
    "attack",
    [
        "</script><script>alert(1)</script>",
        '" onmouseover="alert(1)',
        "'><img src=x onerror=alert(1)>",
        "<svg/onload=alert(1)>",
        "javascript:alert(1)",
        '<iframe src="https://example.invalid/"/>',
    ],
)
def test_html_and_crafted_identifiers_never_create_executable_markup(
    tmp_path: Path, attack: str
) -> None:
    xml = synthetic_xml(1, 1).replace("<SVID>0</SVID>", "<SVID>" + escape(attack) + "</SVID>")
    xml = xml.replace("<VID>0</VID>", "<VID>" + escape(attack) + "</VID>")
    xml = xml.replace("Variable 0", escape(attack))
    adapted = load_interface(write(tmp_path, xml))
    graph = resolve_references(adapted.interface)
    assert graph.relationships[0].reference.target_key == graph.interface.status_variables[0].key
    changed = replace(
        adapted.interface,
        status_variables=(replace(adapted.interface.status_variables[0], description=attack),),
    )
    reports = (
        render_interface_html(graph, ReportSource(attack, "E172-0225")),
        render_html_report(
            compare_interfaces(adapted.interface, changed),
            ReportSource(attack, "E172-0225"),
            ReportSource(attack, "E172-0225"),
        ),
    )
    for report in reports:
        tags = Tags()
        tags.feed(report)
        assert sum(tag == "script" for tag, attrs in tags.tags) == 1
        assert not any(
            tag in {"img", "iframe", "svg", "object", "embed"} for tag, attrs in tags.tags
        )
        assert not any(
            key.startswith("on") or key == "src" for tag, attrs in tags.tags for key in attrs
        )
        assert not any(
            (attrs.get("href") or "").startswith("javascript:") for tag, attrs in tags.tags
        )
        assert "default-src" in report and "connect-src" in report


def test_fragmented_text_callback_work_is_bounded_by_chunks(tmp_path: Path) -> None:
    import cProfile
    import pstats

    profile = cProfile.Profile()
    path = write(tmp_path, "<r>" + "&amp;" * 100_000 + "</r>")
    profile.runcall(load_xml, path)
    stats = pstats.Stats(profile)
    callbacks = int(stats.get_stats_profile().func_profiles["characters"].ncalls)
    assert 0 < callbacks < 30


def test_reparse_ancestor_is_rejected_without_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace
    from typing import Any

    real_stat = Path.lstat
    ancestor = tmp_path / "redirect"

    def lstat(path: Path, **kwargs: object) -> Any:
        if path == ancestor:
            return SimpleNamespace(st_mode=0o040755, st_file_attributes=0x400)
        return real_stat(path)

    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(InputError, match="reparse"):
        local_path(ancestor / "input.xml")


def test_retained_mixed_message_tree_has_work_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sema_sedd.adapters._e172_0225_xml.MAX_RETAINED_XML_NODES", 100)
    body = "<m:LST>text" * 15 + "<m:UI4/>" * 20 + "</m:LST>" * 15
    xml = synthetic_xml(1, 0, message_items=1).replace("<m:UI4/>", body)
    with pytest.raises(ResourceLimitError, match="Retained XML"):
        load_interface(write(tmp_path, xml))


def test_permitted_deep_message_structure_survives_entire_pipeline(tmp_path: Path) -> None:
    body = "<m:LST>" * 55 + "<m:UI4/>" + "</m:LST>" * 55
    xml = synthetic_xml(1, 0, message_items=1).replace("<m:UI4/>", body)
    adapted = load_interface(write(tmp_path, xml))
    assert not compare_interfaces(adapted.interface, adapted.interface).entity_changes
    html = render_interface_html(
        resolve_references(adapted.interface), ReportSource("deep", "E172-0225")
    )
    assert "Messages" in html


def test_dependency_report_join_uses_event_index() -> None:
    from sema_sedd.graph.context import DependencyEdge

    class ForbiddenOutgoing(Mapping[str, tuple[DependencyEdge, ...]]):
        def __getitem__(self, key: str) -> tuple[DependencyEdge, ...]:
            raise AssertionError("Report join scanned all outgoing link edges")

        def __iter__(self) -> Iterator[str]:
            raise AssertionError("Outgoing scan")

        def __len__(self) -> int:
            return 0

    interface = EquipmentInterface(
        collection_events=(CollectionEvent(key="e", implementation_id="1"),),
        default_reports=(DefaultReport(key="r", implementation_id="2"),),
        event_report_links=(
            EventReportLink(
                key="l",
                event=reference(CanonicalType.COLLECTION_EVENT, "1"),
                reports=(reference(CanonicalType.DEFAULT_REPORT, "2"),) * 100,
            ),
        ),
    )
    index = build_dependency_index(resolve_references(interface))
    object.__setattr__(index, "outgoing", ForbiddenOutgoing())
    assert any(d.entity_key == "e" for d in index.context_for("r").dependencies)


def test_json_budget_fails_through_controlled_cli_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from sema_sedd.cli import main
    from sema_sedd.limits import bounded_json

    monkeypatch.setattr("sema_sedd.limits.MAX_JSON_CHARACTERS", 10)
    with pytest.raises(ResourceLimitError, match="JSON output"):
        bounded_json({"large": "x" * 100})
    source = write(tmp_path, synthetic_xml(1, 0))
    with pytest.raises(SystemExit) as error:
        main(["inspect", str(source), "--json"])
    assert error.value.code == 2
    output = capsys.readouterr()
    assert not output.out
    assert "JSON output limit exceeded" in output.err
    assert "Traceback" not in output.err


def test_report_cleanup_failure_is_controlled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(path: Path, **kwargs: object) -> None:
        raise OSError("simulated cleanup failure")

    monkeypatch.setattr(Path, "unlink", fail)
    with pytest.raises(ReportError, match="clean temporary"):
        _write(tmp_path / "report.html", "complete report")
    assert (tmp_path / "report.html").read_text() == "complete report"
