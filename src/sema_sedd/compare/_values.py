"""Semantic value projections; exact scalar text and ordered protocol sequences."""

import json
from dataclasses import fields
from enum import StrEnum

from sema_sedd.model import DataStructure, JsonArray, JsonObject
from sema_sedd.model._base import Record
from sema_sedd.model.values import JsonValue

type JsonData = None | str | int | float | bool | list["JsonData"] | dict[str, "JsonData"]


def encode(value: object) -> JsonData:
    """Lossless JSON encoding for change records and retained canonical evidence."""
    if isinstance(value, StrEnum):
        return value.value
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, JsonObject):
        return {key: encode(item) for key, item in sorted(value.entries)}
    if isinstance(value, JsonArray):
        return [encode(item) for item in value.items]
    if isinstance(value, tuple):
        return [encode(item) for item in value]
    if isinstance(value, Record):
        result = {}
        kind = getattr(value, "canonical_type", None)
        if kind is not None:
            result["canonical_type"] = encode(kind)
        for member in fields(value):
            item = encode(getattr(value, member.name))
            if member.metadata.get("unordered") and isinstance(item, list):
                item.sort(key=dump)
            result[member.name] = item
        return result
    raise TypeError(f"Unsupported comparison value: {type(value).__name__}")


def dump(value: JsonData) -> str:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    )


def token(value: JsonValue) -> str:
    return dump(encode(value))


def obj(**values: JsonValue) -> JsonObject:
    return JsonObject(entries=tuple(sorted(values.items())))


def array(values: tuple[JsonValue, ...], *, unordered: bool = False) -> JsonArray:
    return JsonArray(items=tuple(sorted(values, key=token)) if unordered else values)


def semantic(value: object, *, structural: bool = False) -> JsonValue:
    """Ignore source coordinates, never normalize arbitrary scalar strings."""
    if isinstance(value, StrEnum):
        return value.value
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, JsonObject):
        return JsonObject(
            entries=tuple(sorted((k, semantic(v, structural=structural)) for k, v in value.entries))
        )
    if isinstance(value, JsonArray):
        return array(tuple(semantic(v, structural=structural) for v in value.items))
    if isinstance(value, tuple):
        return array(tuple(semantic(v, structural=structural) for v in value))
    if isinstance(value, Record):
        result: dict[str, JsonValue] = {}
        canonical_type = getattr(value, "canonical_type", None)
        if canonical_type is not None:
            result["canonical_type"] = canonical_type.value
        for member in fields(value):
            if member.name in {"key", "provenance"}:
                continue
            if structural and member.name in {"description", "unknown_extensions"}:
                continue
            item = getattr(value, member.name)
            if structural and isinstance(value, DataStructure) and member.name == "attributes":
                item = JsonObject(
                    entries=tuple((k, v) for k, v in value.attributes.entries if k != "description")
                )
            result[member.name] = semantic(item, structural=structural)
        return obj(**result)
    raise TypeError(f"Unsupported semantic value: {type(value).__name__}")


def structure_annotations(value: object, *, opaque: bool = False) -> JsonValue:
    """Retain annotation paths without mistaking annotations for data shape."""
    entries: list[JsonValue] = []

    def visit(item: object, path: str) -> None:
        if isinstance(item, DataStructure):
            annotation = (
                semantic(item.unknown_extensions)
                if opaque
                else obj(
                    description=item.description,
                    attribute_description=dict(item.attributes.entries).get("description"),
                )
            )
            if (opaque and item.unknown_extensions) or (
                not opaque
                and (item.description is not None or "description" in dict(item.attributes.entries))
            ):
                entries.append(obj(path=path, value=annotation))
            visit(item.children, path + "/children")
        elif isinstance(item, tuple):
            for index, child in enumerate(item):
                visit(child, f"{path}/{index}")

    visit(value, "")
    return array(tuple(entries))


def requirements(value: tuple[JsonObject, ...], *, documentation: bool = False) -> JsonValue:
    """Canonical requirement groups reserve location keys at group/member level.

    Other nested JSON is opaque and retains every key. Inventories preserve
    multiplicity but not occurrence order; sections and arbitrary arrays stay ordered.
    """
    groups: list[JsonValue] = []
    for group in value:
        group_values = dict(group.entries)
        if group_values.get("kind") != "requirement_group":
            if not documentation:
                groups.append(semantic(group))
            continue
        members = group_values.get("requirements")
        cleaned: list[JsonValue] = []
        for member in members.items if isinstance(members, JsonArray) else ():
            if not isinstance(member, JsonObject):
                if not documentation:
                    cleaned.append(semantic(member))
                continue
            fields_ = dict(member.entries)
            if documentation:
                notes = fields_.get("notes")
                if notes is not None and (not isinstance(notes, JsonArray) or notes.items):
                    cleaned.append(
                        obj(
                            requirement_id=fields_.get("requirement_id"),
                            name=fields_.get("name"),
                            notes=semantic(fields_["notes"]),
                        )
                    )
            else:
                cleaned.append(
                    obj(
                        **{
                            k: semantic(v)
                            for k, v in fields_.items()
                            if k not in {"source_path", "line", "column", "notes"}
                        }
                    )
                )
        if documentation:
            if cleaned:
                groups.append(
                    obj(
                        name=group_values.get("name"),
                        requirements=array(tuple(cleaned), unordered=True),
                    )
                )
        else:
            values = {
                k: semantic(v)
                for k, v in group_values.items()
                if k not in {"source_path", "line", "column", "requirements"}
            }
            values["requirements"] = (
                array(tuple(cleaned), unordered=True)
                if isinstance(members, JsonArray)
                else semantic(members)
            )
            groups.append(obj(**values))
    return array(tuple(groups), unordered=True)
