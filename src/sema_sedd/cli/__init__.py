"""Command-line entry point."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from sema_sedd import __version__
from sema_sedd.cli.explore import (
    DEFAULT_EXPLORE_DEPTH,
    MAX_EXPLORE_DEPTH,
    build_exploration,
)
from sema_sedd.cli.explore import render_json as render_exploration_json
from sema_sedd.cli.explore import render_text as render_exploration_text
from sema_sedd.cli.inspect import ENTITY_TYPE_NAMES, build_inspection, render_json, render_text
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
        epilog="Compare and report are planned commands.",
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
    parser.error("unsupported command")
