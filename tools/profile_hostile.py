"""Reproducible offline synthetic pipeline profile (no downloaded fixtures)."""

from __future__ import annotations

import argparse
import cProfile
import json
import time
import tracemalloc
from dataclasses import replace
from pathlib import Path

from sema_sedd.adapters import load_interface
from sema_sedd.compare import compare_interfaces
from sema_sedd.graph import resolve_references
from sema_sedd.report import ReportSource, render_interface_html


def synthetic_xml(
    entities: int, relationships: int, description: int = 32, message_items: int = 0
) -> str:
    variables = "".join(
        f"<StatusVariable><SVID>{i}</SVID><SVNAME>Variable {i}</SVNAME>"
        f"<Description>{'d' * description}</Description></StatusVariable>"
        for i in range(entities)
    )
    references = "".join(f"<VID>{i % entities}</VID>" for i in range(relationships))
    message = (
        (
            '<SECSMessages><m:SECSMessage s="99" f="1" direction="H to E">'
            "<m:SECSData><m:LST>"
            + "<m:UI4/>" * message_items
            + "</m:LST></m:SECSData></m:SECSMessage></SECSMessages>"
        )
        if message_items
        else ""
    )
    return (
        '<s:DataDictionary xmlns:s="urn:semi-org:xsd.SEDD" '
        'xmlns:m="urn:semi-org:xsd.SMN" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="urn:semi-org:xsd.SEDD E172-0225-SEDD-Schema.xsd">'
        "<SEDDHeader><MDLN>Synthetic</MDLN><SOFTREV>1</SOFTREV></SEDDHeader>"
        "<CollectionEvents/><DataVariables/><EquipmentConstants/><Alarms/>"
        "<VariableFormats/><StatusVariables>" + variables + "</StatusVariables>"
        "<DefaultReportDefinitions><DefaultReportDefinition><RPTID>1</RPTID>"
        "<DefaultReportName>Repeated references</DefaultReportName><VIDList>"
        + references
        + "</VIDList></DefaultReportDefinition></DefaultReportDefinitions>"
        + message
        + "</s:DataDictionary>"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entities", type=int, default=1000)
    parser.add_argument("--relationships", type=int, default=5000)
    parser.add_argument("--description", type=int, default=32)
    parser.add_argument("--message-items", type=int, default=0)
    parser.add_argument("--memory", action="store_true")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--changed", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source = args.output / "synthetic.xml"
    source.write_text(
        synthetic_xml(args.entities, args.relationships, args.description, args.message_items),
        encoding="utf-8",
    )
    if args.memory:
        tracemalloc.start()
    profile = cProfile.Profile()
    if args.profile:
        profile.enable()
    times: dict[str, float | int] = {"input_bytes": source.stat().st_size}
    start = time.perf_counter()
    adapted = load_interface(source)
    times["parse_seconds"] = time.perf_counter() - start
    start = time.perf_counter()
    graph = resolve_references(adapted.interface)
    times["resolve_seconds"] = time.perf_counter() - start
    times["entities"] = len(graph.interface.entities())
    times["relationships"] = len(graph.relationships)
    if args.compare:
        start = time.perf_counter()
        after = (
            replace(
                adapted.interface,
                status_variables=tuple(
                    replace(variable, data_type="synthetic-new-type")
                    for variable in adapted.interface.status_variables
                ),
            )
            if args.changed
            else adapted.interface
        )
        changes = compare_interfaces(adapted.interface, after)
        times["compare_seconds"] = time.perf_counter() - start
        times["changes"] = len(changes.entity_changes)
    if args.html:
        start = time.perf_counter()
        html = render_interface_html(graph, ReportSource(str(source), adapted.revision))
        times["html_seconds"] = time.perf_counter() - start
        times["html_bytes"] = len(html.encode())
    if args.profile:
        profile.disable()
        profile.dump_stats(str(args.output / "profile.pstats"))
    if args.memory:
        times["peak_mib"] = tracemalloc.get_traced_memory()[1] / (1024 * 1024)
        tracemalloc.stop()
    result = json.dumps(times, indent=2, sort_keys=True)
    (args.output / "results.json").write_text(result + "\n", encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
