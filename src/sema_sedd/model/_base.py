"""Strict, immutable model boundary; no parser types or mutable containers."""

from dataclasses import dataclass, fields
from functools import cache
from math import isfinite
from types import UnionType
from typing import TypeAliasType, Union, get_args, get_origin, get_type_hints

from sema_sedd.exceptions import ModelValidationError

_HINTS: dict[type[object], dict[str, object]] = {}


def _hints(cls: type[object]) -> dict[str, object]:
    if cls not in _HINTS:
        _HINTS[cls] = get_type_hints(cls)
    return _HINTS[cls]


@cache
def _shape(annotation: object) -> tuple[object, tuple[object, ...]]:
    return get_origin(annotation), get_args(annotation)


def _matches(value: object, annotation: object) -> bool:
    # Primitive and record checks do not require typing introspection.
    if annotation is str:
        if type(value) is not str:
            return False
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            return False
        return True
    if annotation in (int, float, bool, type(None)):
        return type(value) is annotation and (not isinstance(value, float) or isfinite(value))
    if isinstance(annotation, type):
        return type(value) is annotation
    if isinstance(annotation, TypeAliasType):
        return _matches(value, annotation.__value__)
    origin, args = _shape(annotation)
    if origin in (Union, UnionType):
        return any(_matches(value, arg) for arg in args)
    if origin is tuple:
        if not isinstance(value, tuple):
            return False
        if len(args) == 2 and args[1] is Ellipsis:
            return all(_matches(item, args[0]) for item in value)
        return len(value) == len(args) and all(
            _matches(item, arg) for item, arg in zip(value, args, strict=True)
        )
    return False


@dataclass(frozen=True, slots=True, kw_only=True)
class Record:
    """Validate declared field types even when callers bypass static checking."""

    def __post_init__(self) -> None:
        hints = _hints(type(self))
        for field in fields(self):
            if not _matches(getattr(self, field.name), hints[field.name]):
                raise ModelValidationError(
                    f"Invalid model field: {type(self).__name__}.{field.name}"
                )


def require_nonempty(value: str, field: str) -> None:
    if not value.strip():
        raise ModelValidationError(f"{field} must be nonempty")
