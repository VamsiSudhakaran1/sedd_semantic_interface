"""Command-line entry point for the repository foundation."""

import argparse
from collections.abc import Sequence

from sema_sedd import __version__


def main(argv: Sequence[str] | None = None) -> int:
    """Display help or version; argparse rejects unsupported arguments."""
    parser = argparse.ArgumentParser(
        prog="sedd",
        description="Local-first semantic explorer for SEDD equipment interfaces.",
        epilog="Foundation only: inspect, explore, compare, and report are not yet implemented.",
        allow_abbrev=False,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.parse_args(argv)
    parser.print_help()
    return 0
