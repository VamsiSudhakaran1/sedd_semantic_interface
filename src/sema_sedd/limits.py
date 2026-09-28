"""Explicit work budgets for adversarial graph fanout and rendered output."""

import json
from collections.abc import Iterable
from dataclasses import dataclass

from sema_sedd.exceptions import ResourceLimitError

MAX_CANDIDATE_OCCURRENCES = 250_000
MAX_DEPENDENCY_PATHS = 250_000
MAX_HTML_CHARACTERS = 64 * 1024 * 1024


@dataclass(slots=True)
class WorkBudget:
    limit: int
    label: str
    used: int = 0

    def consume(self, count: int = 1) -> None:
        self.used += count
        if self.used > self.limit:
            raise ResourceLimitError(f"{self.label} limit exceeded ({self.limit})")


def bounded_join(parts: Iterable[str], separator: str = "") -> str:
    """Bound accumulated strings before joining; never return a truncated report."""
    budget = WorkBudget(MAX_HTML_CHARACTERS, "HTML output")
    collected: list[str] = []
    for part in parts:
        budget.consume(len(part) + (len(separator) if collected else 0))
        collected.append(part)
    return separator.join(collected)


class BoundedParts(list[str]):
    """Bound accumulation before final string assembly."""

    def __init__(self) -> None:
        super().__init__()
        self.budget = WorkBudget(MAX_HTML_CHARACTERS, "HTML output")

    def append(self, value: str) -> None:
        self.budget.consume(len(value))
        super().append(value)


MAX_JSON_CHARACTERS = 64 * 1024 * 1024


def bounded_json(value: object, *, pretty: bool = False) -> str:
    """Serialize incrementally, flushing small tokens to bounded chunks."""
    encoder = json.JSONEncoder(
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    )
    budget = WorkBudget(MAX_JSON_CHARACTERS, "JSON output")
    chunks: list[str] = []
    pending: list[str] = []
    size = 0
    for part in encoder.iterencode(value):
        budget.consume(len(part))
        pending.append(part)
        size += len(part)
        if size >= 65536:
            chunks.append("".join(pending))
            pending.clear()
            size = 0
    chunks.append("".join(pending))
    return "".join(chunks)


def check_html(value: str) -> str:
    WorkBudget(MAX_HTML_CHARACTERS, "HTML output").consume(len(value))
    return value
