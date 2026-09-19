"""Versioned deterministic JSON, with inventory order separated from sequence order."""

import json
from dataclasses import fields
from enum import StrEnum

from sema_sedd.exceptions import ModelValidationError
from sema_sedd.model._base import Record
from sema_sedd.model.domain import EquipmentInterface
from sema_sedd.model.values import JsonArray, JsonObject

MODEL_SCHEMA_VERSION = "1.0"
type JsonData = None | str | int | float | bool | list["JsonData"] | dict[str, "JsonData"]


def _dump(value: JsonData) -> str:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    )


def _encode(value: object) -> JsonData:
    if isinstance(value, StrEnum):
        return value.value
    if value is None or type(value) in (str, int, float, bool):
        # The runtime model validator has already checked scalar types and finite floats.
        if isinstance(value, (str, int, float)) or value is None:
            return value
    if isinstance(value, JsonObject):
        return {key: _encode(item) for key, item in sorted(value.entries)}
    if isinstance(value, JsonArray):
        return [_encode(item) for item in value.items]
    if isinstance(value, tuple):
        return [_encode(item) for item in value]
    if isinstance(value, Record):
        canonical_type = getattr(value, "canonical_type", None)
        if canonical_type is None:
            raise ModelValidationError("Internal model base cannot be serialized")
        result: dict[str, JsonData] = {"canonical_type": _encode(canonical_type)}
        for member in fields(value):
            encoded = _encode(getattr(value, member.name))
            if member.metadata.get("unordered") and isinstance(encoded, list):
                encoded.sort(key=_dump)
            result[member.name] = encoded
        return result
    raise ModelValidationError("Unsupported canonical JSON value")


def to_canonical_dict(interface: EquipmentInterface) -> dict[str, JsonData]:
    """Return a fresh JSON-compatible snapshot; no source I/O or identity matching."""
    if type(interface) is not EquipmentInterface:
        raise ModelValidationError("Canonical serialization requires EquipmentInterface")
    return {"model_schema_version": MODEL_SCHEMA_VERSION, "interface": _encode(interface)}


def to_canonical_json(interface: EquipmentInterface) -> str:
    """Stable compact Unicode JSON; encode the returned string as UTF-8 for storage."""
    return _dump(to_canonical_dict(interface))
