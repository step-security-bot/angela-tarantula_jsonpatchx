import copy
from typing import Generic, Literal, Self, override

from pydantic import ConfigDict, Field, model_validator
from typing_extensions import TypeVar

from jsonpatchx.exceptions import OperationValidationError, TestOpFailed
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import (
    JSONBound,
    JSONValue,
)

# Advanced: RFC ops are actually generic: AddOp[T], RemoveOp[T], ReplaceOp[T], MoveOp[T], CopyOp[T], TestOp[T] (default T=JSONValue).
# This lets custom ops use precise pointer targets like JSONPointer[JSONArray[JSONNumber]] and still compose safely.
# Users don't need to make their own ops generic unless for advanced use case they intend to commpose them with type-safety.
# So RFC ops are not advertised as generic in order to lower the barrier to entry.


T = TypeVar("T", default=JSONValue, bound=JSONBound)


class AddOp(OperationSchema, Generic[T]):
    """RFC 6902 add operation."""

    model_config = ConfigDict(
        title="Add operation",
        json_schema_extra={"description": "RFC 6902 add operation."},
    )

    op: Literal["add"] = "add"
    path: JSONPointer[T]
    value: T

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return self.path.add(doc, self.value)


class RemoveOp(OperationSchema, Generic[T]):
    """RFC 6902 remove operation. Removal of the root sets it to null."""

    model_config = ConfigDict(
        title="Remove operation",
        json_schema_extra={
            "description": "RFC 6902 remove operation. Removal of the root sets it to null."
        },
    )

    op: Literal["remove"] = "remove"
    path: JSONPointer[T]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return self.path.remove(doc)


class ReplaceOp(OperationSchema, Generic[T]):
    """RFC 6902 replace operation."""

    model_config = ConfigDict(
        title="Replace operation",
        json_schema_extra={"description": "RFC 6902 replace operation."},
    )

    op: Literal["replace"] = "replace"
    path: JSONPointer[T]
    value: T

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        doc = RemoveOp[T](path=self.path).apply(doc)
        return AddOp[T](path=self.path, value=self.value).apply(doc)


class MoveOp(OperationSchema, Generic[T]):
    """RFC 6902 move operation."""

    model_config = ConfigDict(
        title="Move operation",
        json_schema_extra={"description": "RFC 6902 move operation."},
    )

    op: Literal["move"] = "move"
    from_: JSONPointer[T] = Field(alias="from")
    path: JSONPointer[T]

    @model_validator(mode="after")
    def _reject_proper_prefixes(self) -> Self:
        if self.from_.is_parent_of(self.path):
            raise OperationValidationError(
                "pointer 'path' cannot be a child of pointer 'from'"
            )
        return self

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        value = self.from_.get(doc)
        doc = RemoveOp[T](path=self.from_).apply(doc)
        return AddOp[T](path=self.path, value=value).apply(doc)


class CopyOp(OperationSchema, Generic[T]):
    """RFC 6902 copy operation."""

    model_config = ConfigDict(
        title="Copy operation",
        json_schema_extra={"description": "RFC 6902 copy operation."},
    )

    op: Literal["copy"] = "copy"
    from_: JSONPointer[T] = Field(alias="from")
    path: JSONPointer[T]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        value = self.from_.get(doc)
        duplicate = copy.deepcopy(value)
        return AddOp[T](path=self.path, value=duplicate).apply(doc)


class TestOp(OperationSchema, Generic[T]):
    """RFC 6902 test operation."""

    __test__ = False  # Suppress pytest warning

    model_config = ConfigDict(
        title="Test operation",
        json_schema_extra={"description": "RFC 6902 test operation."},
    )

    op: Literal["test"] = "test"
    path: JSONPointer[T]
    value: T

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        actual = self.path.get(doc)
        if actual != self.value:
            raise TestOpFailed(
                f"test at path {self.path!r} failed, got {actual!r} but expected {self.value!r}"
            )
        return doc
