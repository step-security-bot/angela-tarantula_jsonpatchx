"""
Opinionated catalog of custom JSON Patch operations for demos and prototypes.

This API is **UNSTABLE** and is just for demonstration purposes.
"""

from __future__ import annotations

import json
from typing import Literal, override

from pydantic import ConfigDict, Field, model_validator

from jsonpatchx import (
    AddOp,
    JSONPointer,
    JSONValue,
    OperationSchema,
    OperationValidationError,
    PatchConflictError,
    RemoveOp,
    ReplaceOp,
)
from jsonpatchx.types import JSONArray, JSONBoolean, JSONNumber, JSONObject, JSONString


class ToggleOp(OperationSchema):
    """Invert a boolean value at the target path."""

    model_config = ConfigDict(title="Toggle operation")
    op: Literal["toggle"] = "toggle"
    path: JSONPointer[JSONBoolean]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=not current).apply(doc)


class EnableOp(OperationSchema):
    """Set a boolean value to true."""

    model_config = ConfigDict(title="Enable operation")
    op: Literal["enable"] = "enable"
    path: JSONPointer[JSONBoolean]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return ReplaceOp(path=self.path, value=True).apply(doc)


class DisableOp(OperationSchema):
    """Set a boolean value to false."""

    model_config = ConfigDict(title="Disable operation")
    op: Literal["disable"] = "disable"
    path: JSONPointer[JSONBoolean]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return ReplaceOp(path=self.path, value=False).apply(doc)


class IncrementOp(OperationSchema):
    """Increase a numeric value by an amount."""

    model_config = ConfigDict(title="Increment operation")
    op: Literal["increment"] = "increment"
    path: JSONPointer[JSONNumber]
    amount: JSONNumber = Field(default=1, gt=0)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=current + self.amount).apply(doc)


class DecrementOp(OperationSchema):
    """Decrease a numeric value by an amount."""

    model_config = ConfigDict(title="Decrement operation")
    op: Literal["decrement"] = "decrement"
    path: JSONPointer[JSONNumber]
    amount: JSONNumber = Field(default=1, gt=0)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=current - self.amount).apply(doc)


class ClampOp(OperationSchema):
    """Clamp a numeric value to an inclusive range."""

    model_config = ConfigDict(title="Clamp operation")
    op: Literal["clamp"] = "clamp"
    path: JSONPointer[JSONNumber]
    min: JSONNumber
    max: JSONNumber

    @model_validator(mode="after")
    def _validate_bounds(self) -> "ClampOp":
        if self.min > self.max:
            raise OperationValidationError("clamp requires min <= max")
        return self

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(
            path=self.path, value=max(self.min, min(self.max, current))
        ).apply(doc)


class AppendOp(OperationSchema):
    """Append a value to an array."""

    model_config = ConfigDict(title="Append operation")
    op: Literal["append"] = "append"
    path: JSONPointer[JSONArray[JSONValue]]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        current.append(self.value)
        return doc


class PrependOp(OperationSchema):
    """Prepend a value to an array."""

    model_config = ConfigDict(title="Prepend operation")
    op: Literal["prepend"] = "prepend"
    path: JSONPointer[JSONArray[JSONValue]]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        current.insert(0, self.value)
        return doc


class InsertAtOp(OperationSchema):
    """Insert a value into an array at a specific index."""

    model_config = ConfigDict(title="Insert-at operation")
    op: Literal["insert_at"] = "insert_at"
    path: JSONPointer[JSONArray[JSONValue]]
    index: int = Field(ge=0)
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.index > len(current):
            raise PatchConflictError("index out of range")
        current.insert(self.index, self.value)
        return doc


class RemoveWhereOp(OperationSchema):
    """Remove objects from an array where a field matches a value."""

    model_config = ConfigDict(title="Remove-where operation")
    op: Literal["remove_where"] = "remove_where"
    path: JSONPointer[JSONArray[JSONObject[JSONValue]]]
    field: str
    equals: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        original_len = len(current)
        current[:] = [item for item in current if item.get(self.field) != self.equals]
        if len(current) == original_len:
            raise PatchConflictError("no matching item found")
        return doc


class DeduplicateOp(OperationSchema):
    """Remove duplicate values from an array, preserving order."""

    model_config = ConfigDict(title="Deduplicate operation")
    op: Literal["deduplicate"] = "deduplicate"
    path: JSONPointer[JSONArray[JSONValue]]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        encoded = dict.fromkeys(
            # treat dict as ordered set
            json.dumps(item, sort_keys=True)
            for item in current
        )
        current[:] = [json.loads(item) for item in encoded]
        return doc


class ReplaceSubstringOp(OperationSchema):
    """Replace a substring within a string field."""

    model_config = ConfigDict(title="Replace-substring operation")
    op: Literal["replace_substring"] = "replace_substring"
    path: JSONPointer[JSONString]
    old: JSONString
    new: JSONString

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(
            path=self.path, value=current.replace(self.old, self.new)
        ).apply(doc)


class MergeOp(OperationSchema):
    """Merge an object into a target object."""

    model_config = ConfigDict(title="Merge operation")
    op: Literal["merge"] = "merge"
    path: JSONPointer[JSONObject[JSONValue]]
    value: JSONObject[JSONValue]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        current.update(self.value)
        return doc


class RenameKeyOp(OperationSchema):
    """Rename a key inside an object."""

    model_config = ConfigDict(title="Rename-key operation")
    op: Literal["rename"] = "rename"
    path: JSONPointer[JSONObject[JSONValue]]
    from_: JSONString = Field(alias="from")
    to: JSONString

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.from_ not in current:
            raise PatchConflictError("source key does not exist")
        if self.to in current:
            raise PatchConflictError("destination key already exists")
        current[self.to] = current.pop(self.from_)
        return doc


class MoveOnlyIfExistsOp(OperationSchema):
    """Move a value if the source path exists."""

    model_config = ConfigDict(title="Move-if-exists operation")
    op: Literal["moveonlyifexists"] = "moveonlyifexists"
    from_: JSONPointer[JSONValue] = Field(alias="from")
    path: JSONPointer[JSONValue]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        if not self.from_.is_gettable(doc):
            return doc
        value = self.from_.get(doc)
        doc = AddOp(path=self.path, value=value).apply(doc)
        return RemoveOp(path=self.from_).apply(doc)


class SortNumbersOp(OperationSchema):
    """Sort a numeric array ascending or descending."""

    model_config = ConfigDict(title="Sort numbers operation")
    op: Literal["sort_numbers"] = "sort_numbers"
    path: JSONPointer[JSONArray[JSONNumber]]
    order: Literal["asc", "desc"] = "asc"

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        new = sorted(current, reverse=self.order == "desc")
        return ReplaceOp(path=self.path, value=new).apply(doc)


class BitSetOp(OperationSchema):
    """Set or clear a bit in a numeric bitfield."""

    model_config = ConfigDict(
        title="Bit operation",
        json_schema_extra={
            "description": "Set or clear a specific bit in a numeric bitfield.",
        },
    )
    op: Literal["bit_set"] = "bit_set"
    path: JSONPointer[JSONNumber]
    index: int = Field(ge=0)
    value: JSONBoolean

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = int(self.path.get(doc))
        mask = 1 << self.index
        next_val = (current | mask) if self.value else (current & ~mask)
        return ReplaceOp(path=self.path, value=next_val).apply(doc)


class MapOp(OperationSchema):
    """Replace a value based on a mapping table."""

    model_config = ConfigDict(title="Map operation")
    op: Literal["map"] = "map"
    path: JSONPointer[JSONString]
    mapping: JSONObject[JSONValue]
    strict: JSONBoolean

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if current not in self.mapping:
            if self.strict:
                raise PatchConflictError(f"missing map entry for {current!r}")
            return doc
        return ReplaceOp(path=self.path, value=self.mapping[current]).apply(doc)


CUSTOM_OP_RECIPES = [
    ToggleOp,
    EnableOp,
    DisableOp,
    IncrementOp,
    DecrementOp,
    ClampOp,
    AppendOp,
    PrependOp,
    InsertAtOp,
    RemoveWhereOp,
    DeduplicateOp,
    ReplaceSubstringOp,
    MergeOp,
    RenameKeyOp,
    MoveOnlyIfExistsOp,
    SortNumbersOp,
    BitSetOp,
    MapOp,
]
