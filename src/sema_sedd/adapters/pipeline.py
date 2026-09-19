"""Filesystem -> secure loader -> registry -> revision adapter -> canonical model."""

import os

from sema_sedd.adapters.base import AdapterResult
from sema_sedd.adapters.defaults import default_registry
from sema_sedd.adapters.registry import AdapterRegistry
from sema_sedd.parser import load_sedd
from sema_sedd.parser.ingest import (
    DEFAULT_MAX_ATTRIBUTES,
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_ELEMENTS,
)


def load_interface(
    path: str | os.PathLike[str],
    *,
    registry: AdapterRegistry | None = None,
    revision: str | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_elements: int = DEFAULT_MAX_ELEMENTS,
    max_attributes: int = DEFAULT_MAX_ATTRIBUTES,
) -> AdapterResult:
    document = load_sedd(
        path,
        max_bytes=max_bytes,
        max_depth=max_depth,
        max_elements=max_elements,
        max_attributes=max_attributes,
    )
    active = registry if registry is not None else default_registry()
    return active.adapt(document, revision=revision)
