"""
Issue-driven JSON Patch operation recipes.

These operations are intentionally opinionated examples showing how to model
json-patch2-style proposals on top of jsonpatchx extension points.
"""

from __future__ import annotations

import copy
from typing import Any, Literal, Self, assert_never, override

from pydantic import AliasChoices, ConfigDict, Field, model_validator

from jsonpatchx import (
    AddOp,
    JSONPointer,
    JSONValue,
    OperationSchema,
    PatchConflictError,
    RemoveOp,
    ReplaceOp,
    TestOp,
    TestOpFailed,
)
from jsonpatchx.backend import TargetState, classify_state
from jsonpatchx.exceptions import OperationValidationError
from jsonpatchx.types import JSONArray, JSONBoolean, JSONNumber, JSONObject, JSONString


class TestMissingOp(OperationSchema):
    """Supports explicit non-existence preconditions for optimistic workflows.

    Example:
        doc={"users": {"42": {"name": "Ada"}}}
        op={"op": "test_missing", "path": "/users/99"}
        Useful before create flows to assert the target slot is free.
    """

    model_config = ConfigDict(
        title="Test-missing operation",
        json_schema_extra={
            "description": "Assert that a path does not resolve to an existing value."
        },
    )
    op: Literal["test_missing"] = "test_missing"
    path: JSONPointer[JSONValue]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        if self.path.is_gettable(doc):
            raise TestOpFailed(f"expected missing path at {self.path!r}")
        return doc


class AddMissingKeyOp(OperationSchema):
    """AddOp but only for objects missing the target key. Prevents silent overwrite.

    Example:
        doc={"profile": {}}
        op={"op": "add_missing_key", "path": "/profile/email", "value": "a@x.test"}
        If "/profile/email" already exists, this op fails instead of replacing it.
    """

    model_config = ConfigDict(
        title="Add Missing Key Operation",
        json_schema_extra={
            "description": "Add a key-value pair to an object, but only if the key is missing."
        },
    )
    op: Literal["add_missing_key"] = "add_missing_key"
    path: JSONPointer[JSONValue]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        state = classify_state(self.path.ptr, doc)
        if state is TargetState.OBJECT_KEY_MISSING:
            return AddOp(path=self.path, value=self.value).apply(doc)
        if state is TargetState.VALUE_PRESENT:
            raise PatchConflictError(f"path {self.path!r} already exists")
        if state in {
            TargetState.ARRAY_INDEX_APPEND,
            TargetState.ARRAY_INDEX_AT_END,
            TargetState.ARRAY_INDEX_OUT_OF_RANGE,
            TargetState.ARRAY_KEY_INVALID,
            TargetState.VALUE_PRESENT_AT_NEGATIVE_ARRAY_INDEX,
        }:
            raise PatchConflictError(
                f"add_missing_key expects an object member path, got array path {self.path!r}"
            )
        if state is TargetState.PARENT_NOT_FOUND:
            raise PatchConflictError(
                f"cannot add key at {self.path!r} because parent does not exist"
            )
        if state is TargetState.PARENT_NOT_CONTAINER:
            raise PatchConflictError(
                f"cannot add key at {self.path!r} because parent is not a container"
            )
        if state is TargetState.ROOT:
            raise PatchConflictError("add_missing_key does not support root path")
        raise PatchConflictError(f"unsupported path state for {self.path!r}")


def is_sensitive(path: JSONPointer[Any]) -> bool:
    """Check whether a password is sensitive; use to avoid leaking information."""
    markers = ("password", "passwd", "secret", "token", "api_key", "apikey")
    return any(path.parts[-1] == marker for marker in markers)


class SensitiveAwareTestOp(OperationSchema):
    """Blocks test on sensitive paths so probes cannot leak secret matches.

    Example:
        doc={"password": "p@ssw0rd"}
        op={"op": "test_sensitive_aware", "path": "/password", "value": "guess"}
        Always fails on sensitive paths, even if guessed value is correct.
    """

    model_config = ConfigDict(
        title="Sensitive-aware test operation",
        json_schema_extra={
            "description": "Run RFC test except on sensitive paths, where it always fails."
        },
    )
    op: Literal["test_sensitive_aware"] = "test_sensitive_aware"
    path: JSONPointer[JSONValue]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        if is_sensitive(self.path):
            raise TestOpFailed("test is not allowed on sensitive paths")
        return TestOp(path=self.path, value=self.value).apply(doc)


class ReplaceWithPriorOp(OperationSchema):
    """Captures previous value checks for auditable and reversible replace flows.

    Example:
        doc={"status": "draft"}
        op={
          "op": "replace_with_prior",
          "path": "/status",
          "priorValue": "draft",
          "value": "published"
        }
        The operation fails if current value is not "draft".
    """

    model_config = ConfigDict(
        title="Replace-with-prior operation",
        json_schema_extra={
            "description": "Replace only when the current value matches priorValue."
        },
    )
    op: Literal["replace_with_prior", "replace with prior"] = "replace_with_prior"
    path: JSONPointer[JSONValue]
    prior_value: JSONValue = Field(
        validation_alias=AliasChoices("prior value", "priorValue"),
        serialization_alias="priorValue",  # openapi requires ^[a-zA-Z0-9\.\-_]+$ but for parsing json 'prior value' is also accepted
    )
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if current != self.prior_value:
            raise TestOpFailed(
                f"prior value mismatch at {self.path!r}: "
                f"expected {self.prior_value!r}, got {current!r}"
            )
        return ReplaceOp(path=self.path, value=self.value).apply(doc)


class RemoveWithOldValueOp(OperationSchema):
    """Makes remove invertible by carrying and validating old value.

    Example:
        doc={"nickname": "max"}
        op={"op": "remove_with_old", "path": "/nickname", "oldValue": "max"}
        The remove fails unless oldValue matches the current document value.
    """

    model_config = ConfigDict(
        title="Remove-with-old-value operation",
        json_schema_extra={
            "description": "Remove only when current value matches oldValue."
        },
    )
    op: Literal["remove_with_old"] = "remove_with_old"
    path: JSONPointer[JSONValue]
    old_value: JSONValue = Field(
        validation_alias=AliasChoices("old value", "oldValue"),
        serialization_alias="oldValue",
    )

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if current != self.old_value:
            raise TestOpFailed(
                f"old value mismatch at {self.path!r}: "
                f"expected {self.old_value!r}, got {current!r}"
            )
        return RemoveOp(path=self.path).apply(doc)


def _deep_merge_object(
    base: JSONObject[JSONValue], incoming: JSONObject[JSONValue]
) -> JSONObject[JSONValue]:
    """Recursively merge nested objects without dropping unrelated sibling keys.

    Example:
        base={"attributes": {"age": 15, "city": "Rome"}}
        incoming={"attributes": {"continent": "Europe"}}
        result={"attributes": {"age": 15, "city": "Rome", "continent": "Europe"}}
    """
    merged: JSONObject[JSONValue] = copy.deepcopy(base)
    for key, value in incoming.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _deep_merge_object(current, value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


class MergeObjectOp(OperationSchema):
    """Preserves sibling fields when independent patches target one object key.

    Example:
        doc={"attributes": {"age": 15}}
        op={"op": "merge_object", "path": "/attributes", "value": {"continent": "EU"}}
        Result keeps "age" and adds "continent".
    """

    model_config = ConfigDict(
        title="Merge-object operation",
        json_schema_extra={
            "description": "Merge object fields at path; optionally merge nested objects recursively."
        },
    )
    op: Literal["merge_object"] = "merge_object"
    path: JSONPointer[JSONObject[JSONValue]]
    value: JSONObject[JSONValue]
    deep: JSONBoolean = False

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        merged = (
            _deep_merge_object(current, self.value)
            if self.deep
            else {**current, **self.value}
        )
        return ReplaceOp(path=self.path, value=merged).apply(doc)


class IncrementByOp(OperationSchema):
    """Avoids read-modify-write races for simple counters.

    Example:
        doc={"votes": 10}
        op={"op": "increment_by", "path": "/votes", "amount": 1}
        Result is {"votes": 11} without a separate client read step.
    """

    model_config = ConfigDict(
        title="Increment-by operation",
        json_schema_extra={
            "description": "Increase a numeric value by amount in one patch step."
        },
    )
    op: Literal["increment_by"] = "increment_by"
    path: JSONPointer[JSONNumber]
    amount: JSONNumber

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=current + self.amount).apply(doc)


class RemoveArrayValueOp(OperationSchema):
    """Removes by value so callers are not forced to discover unstable indexes.

    Example:
        doc={"roles": ["admin", "viewer", "editor"]}
        op={"op": "remove_array_value", "path": "/roles", "value": "viewer"}
        Removes "viewer" even if indexes shifted since the client last read.
    """

    model_config = ConfigDict(
        title="Remove-array-value operation",
        json_schema_extra={
            "description": "Remove matching array members by value (first or all)."
        },
    )
    op: Literal["remove_array_value"] = "remove_array_value"
    path: JSONPointer[JSONArray[JSONValue]]
    value: JSONValue
    mode: Literal["first", "all"] = "first"

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.value not in current:
            raise PatchConflictError("array value not found")
        match self.mode:
            case "first":
                current.remove(self.value)
            case "all":
                current[:] = [item for item in current if item != self.value]
            case _ as unreachable:
                assert_never(unreachable)
        return doc


class ReplaceArrayValueOp(OperationSchema):
    """Replaces by value to support set-like arrays without index coupling.

    Example:
        doc={"tags": ["alpha", "beta", "beta"]}
        op={
          "op": "replace_array_value",
          "path": "/tags",
          "oldValue": "beta",
          "value": "stable",
          "mode": "first"
        }
        Replaces a matching value without requiring an index.
    """

    model_config = ConfigDict(
        title="Replace-array-value operation",
        json_schema_extra={
            "description": "Replace matching array members by value (first or all)."
        },
    )
    op: Literal["replace_array_value"] = "replace_array_value"
    path: JSONPointer[JSONArray[JSONValue]]
    old_value: JSONValue = Field(alias="oldValue")
    value: JSONValue
    mode: Literal["first", "all"] = "first"

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.value not in current:
            raise PatchConflictError("array value to replace not found")
        match self.mode:
            case "first":
                for index, item in enumerate(current):
                    if item == self.old_value:
                        current[index] = self.value
                        break
            case "all":
                current[:] = [
                    item if item != self.old_value else self.value for item in current
                ]
            case _ as unreachable:
                assert_never(unreachable)
        return doc


class SetUnionOp(OperationSchema):
    """Adds missing members only, matching set-style collection semantics.

    Example:
        doc={"features": ["chat"]}
        op={"op": "set_union", "path": "/features", "values": ["chat", "audit"]}
        Result is ["chat", "audit"] (no duplicate "chat").
    """

    model_config = ConfigDict(
        title="Set-union operation",
        json_schema_extra={
            "description": "Append only values that are not already present in an array."
        },
    )
    op: Literal["set_union"] = "set_union"
    path: JSONPointer[JSONArray[JSONValue]]
    values: JSONArray[JSONValue]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        for item in self.values:
            if item not in current:
                current.append(copy.deepcopy(item))
        return doc


class ReplaceTextSliceOp(OperationSchema):
    """Changes large strings surgically without replacing the full field value.

    Example:
        doc={"title": "Hello world"}
        op={
          "op": "replace_text_slice",
          "path": "/title",
          "start": 6,
          "end": 11,
          "text": "team"
        }
        Result is {"title": "Hello team"}.
    """

    model_config = ConfigDict(
        title="Replace-text-slice operation",
        json_schema_extra={
            "description": "Replace a substring by start/end offsets instead of replacing full text."
        },
    )
    op: Literal["replace_text_slice"] = "replace_text_slice"
    path: JSONPointer[JSONString]
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: JSONString

    @model_validator(mode="after")
    def _validate_range(self) -> Self:
        if self.start > self.end:
            raise OperationValidationError("replace_text_slice requires start <= end")
        return self

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.end > len(current):
            raise PatchConflictError("text slice end is out of range")
        updated = current[: self.start] + self.text + current[self.end :]
        return ReplaceOp(path=self.path, value=updated).apply(doc)


class AddByValueOp(OperationSchema):
    """Insert relative to a matched value when index position is not reliable.

    Example:
        doc={"items": ["a", "c", "e", "z"]}
        op={"op": "add_by_value", "path": "/items", "value": "b", "before": "c"}
        Result is {"items": ["a", "b", "c", "e", "z"]}.
    """

    model_config = ConfigDict(
        title="Add-by-value operation",
        json_schema_extra={
            "description": "Insert array value before/after a matched anchor value."
        },
    )
    op: Literal["add_by_value"] = "add_by_value"
    path: JSONPointer[JSONArray[JSONValue]]
    value: JSONValue
    before: JSONValue | None = None
    after: JSONValue | None = None

    @model_validator(mode="after")
    def _validate_anchor(self) -> Self:
        if (self.before is None) == (self.after is None):
            raise OperationValidationError(
                "add_by_value requires exactly one of 'before' or 'after'"
            )
        return self

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        anchor = self.before if self.before is not None else self.after
        assert anchor is not None  # validated above
        for index, item in enumerate(current):
            if item == anchor:
                insert_at = index if self.before is not None else index + 1
                current.insert(insert_at, self.value)
                return doc
        raise PatchConflictError("anchor value not found")


class ReplaceByValueOp(OperationSchema):
    """Replace matched array values without depending on current index positions.

    Example:
        doc={"items": ["a", "c", "e", "z"]}
        op={"op": "replace_by_value", "path": "/items", "replace": "e", "value": "d"}
        Result is {"items": ["a", "c", "d", "z"]}.
    """

    model_config = ConfigDict(
        title="Replace-by-value operation",
        json_schema_extra={
            "description": "Replace first/all matched array values by value."
        },
    )
    op: Literal["replace_by_value"] = "replace_by_value"
    path: JSONPointer[JSONArray[JSONValue]]
    replace: JSONValue
    value: JSONValue
    mode: Literal["first", "all"] = "first"

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        replaced = False
        for index, item in enumerate(current):
            if item == self.replace:
                current[index] = self.value
                replaced = True
                if self.mode == "first":
                    return doc
        if not replaced:
            raise PatchConflictError("replace target value not found")
        return doc


class RemoveByValueOp(OperationSchema):
    """Remove first/all matched array values to avoid index-race removals.

    Example:
        doc={"items": ["a", "b", "c", "d"]}
        op={"op": "remove_by_value", "path": "/items", "value": "d"}
        Result is {"items": ["a", "b", "c"]}.
    """

    model_config = ConfigDict(
        title="Remove-by-value operation",
        json_schema_extra={
            "description": "Remove first/all matched array values by value."
        },
    )
    op: Literal["remove_by_value"] = "remove_by_value"
    path: JSONPointer[JSONArray[JSONValue]]
    value: JSONValue
    mode: Literal["first", "all"] = "first"

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        if self.mode == "first":
            for index, item in enumerate(current):
                if item == self.value:
                    del current[index]
                    return doc
            raise PatchConflictError("remove target value not found")

        filtered = [item for item in current if item != self.value]
        if len(filtered) == len(current):
            raise PatchConflictError("remove target value not found")
        current[:] = filtered
        return doc


ISSUE_DRIVEN_RECIPES = [
    AddMissingKeyOp,
    TestMissingOp,
    ReplaceWithPriorOp,
    RemoveWithOldValueOp,
    MergeObjectOp,
    SensitiveAwareTestOp,
    IncrementByOp,
    RemoveArrayValueOp,
    ReplaceArrayValueOp,
    SetUnionOp,
    ReplaceTextSliceOp,
    AddByValueOp,
    ReplaceByValueOp,
    RemoveByValueOp,
]
