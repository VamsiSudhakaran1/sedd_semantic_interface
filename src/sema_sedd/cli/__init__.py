"""Command-line entry point."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from sema_sedd import __version__
from sema_sedd.cli.inspect import ENTITY_TYPE_NAMES, build_inspection, render_json, render_text
from sema_sedd.exceptions import SeddError


def main(argv: Sequence[str] | None = None) -> int:
    """Run a CLI command; argparse rejects unsupported arguments."""
    parser = argparse.ArgumentParser(
        prog="sedd",
        description="Local-first semantic explorer for SEDD equipment interfaces.",
        epilog="Explore, compare, and report are planned commands.",
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
    parser.error("unsupported command")
