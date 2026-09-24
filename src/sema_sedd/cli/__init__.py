"""Command-line entry point."""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from sema_sedd import __version__
from sema_sedd.cli.compare import (
    COMPARISON_TYPE_NAMES,
    build_comparison,
)
from sema_sedd.cli.compare import render_json as render_comparison_json
from sema_sedd.cli.compare import render_text as render_comparison_text
from sema_sedd.cli.explore import (
    DEFAULT_EXPLORE_DEPTH,
    MAX_EXPLORE_DEPTH,
    build_exploration,
)
from sema_sedd.cli.explore import render_json as render_exploration_json
from sema_sedd.cli.explore import render_text as render_exploration_text
from sema_sedd.cli.inspect import ENTITY_TYPE_NAMES, build_inspection, render_json, render_text
from sema_sedd.cli.report import write_html_report, write_interface_html_report
from sema_sedd.exceptions import SeddError


def _bounded_depth(value: str) -> int:
    try:
        depth = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("depth must be an integer") from error
    if not 0 <= depth <= MAX_EXPLORE_DEPTH:
        raise argparse.ArgumentTypeError(f"depth must be between 0 and {MAX_EXPLORE_DEPTH}")
    return depth


def main(argv: Sequence[str] | None = None) -> int:
    """Run a CLI command; argparse rejects unsupported arguments."""
    parser = argparse.ArgumentParser(
        prog="sedd",
        description="Local-first semantic explorer for SEDD equipment interfaces.",
        allow_abbrev=False,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command")
    inspect_parser = commands.add_parser(
        "inspect", help="inspect one SEDD document", allow_abbrev=False
    )
    inspect_parser.add_argument("file", type=Path, metavar="FILE")
    inspect_parser.add_argument("--json", action="store_true", help="emit deterministic JSON")
    inspect_parser.add_argument(
        "--type", dest="entity_type", choices=ENTITY_TYPE_NAMES, help="filter by canonical type"
    )
    inspect_parser.add_argument("--id", dest="implementation_id", help="filter by exact native ID")
    inspect_parser.add_argument("--wkn", help="filter by exact Well-Known Name")
    explore_parser = commands.add_parser(
        "explore", help="explore a bounded entity neighborhood", allow_abbrev=False
    )
    explore_parser.add_argument("file", type=Path, metavar="FILE")
    explore_parser.add_argument(
        "entity",
        metavar="ENTITY",
        help="exact selector: event:ID, alarm:ID, status-variable:ID, or wkn:VALUE",
    )
    explore_parser.add_argument(
        "--depth",
        type=_bounded_depth,
        default=DEFAULT_EXPLORE_DEPTH,
        metavar="N",
        help=f"traversal depth from 0 to {MAX_EXPLORE_DEPTH} (default: %(default)s)",
    )
    explore_parser.add_argument("--json", action="store_true", help="emit deterministic JSON")
    compare_parser = commands.add_parser(
        "compare", help="compare two SEDD documents", allow_abbrev=False
    )
    compare_parser.add_argument("old", type=Path, metavar="OLD")
    compare_parser.add_argument("new", type=Path, metavar="NEW")
    compare_parser.add_argument("--json", action="store_true", help="emit deterministic JSON")
    compare_parser.add_argument(
        "--type",
        dest="entity_type",
        choices=COMPARISON_TYPE_NAMES,
        help="filter findings by exact canonical type",
    )
    compare_parser.add_argument(
        "--only-changed", action="store_true", help="hide unchanged confirmed matches"
    )
    compare_parser.add_argument(
        "--include-documentation", action="store_true", help="include documentation changes"
    )
    compare_parser.add_argument(
        "--no-color", action="store_true", help="disable ANSI heading colors"
    )
    report_parser = commands.add_parser(
        "report",
        help="write a self-contained local HTML explorer or comparison",
        allow_abbrev=False,
    )
    report_parser.add_argument("old", type=Path, metavar="FILE_OR_OLD")
    report_parser.add_argument("new", type=Path, nargs="?", metavar="NEW")
    report_parser.add_argument("--html", type=Path, required=True, metavar="FILE")

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "inspect":
        try:
            inspection = build_inspection(
                args.file,
                entity_type=args.entity_type,
                implementation_id=args.implementation_id,
                wkn=args.wkn,
            )
        except SeddError as error:
            inspect_parser.error(str(error))
        sys.stdout.write(render_json(inspection) if args.json else render_text(inspection))
        return 0
    if args.command == "explore":
        try:
            exploration = build_exploration(args.file, args.entity, depth=args.depth)
        except SeddError as error:
            explore_parser.error(str(error))
        sys.stdout.write(
            render_exploration_json(exploration)
            if args.json
            else render_exploration_text(exploration)
        )
        return 0
    if args.command == "compare":
        try:
            comparison = build_comparison(
                args.old,
                args.new,
                entity_type=args.entity_type,
                only_changed=args.only_changed,
                include_documentation=args.include_documentation,
            )
        except SeddError as error:
            compare_parser.error(str(error))
        color = (
            not args.no_color
            and not args.json
            and sys.stdout.isatty()
            and "NO_COLOR" not in os.environ
        )
        sys.stdout.write(
            render_comparison_json(comparison)
            if args.json
            else render_comparison_text(comparison, color=color)
        )
        return 0
    if args.command == "report":
        try:
            destination = (
                write_interface_html_report(args.old, args.html)
                if args.new is None
                else write_html_report(args.old, args.new, args.html)
            )
        except SeddError as error:
            report_parser.error(str(error))
        sys.stdout.write(f"Wrote HTML report to {destination}\n")
        return 0
    parser.error("unsupported command")
