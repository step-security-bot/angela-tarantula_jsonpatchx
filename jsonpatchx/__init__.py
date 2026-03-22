"""Typed JSON Patch (RFC 6902) utilities powered by Pydantic."""

from jsonpatchx.builtins import (
    AddOp,
    CopyOp,
    MoveOp,
    RemoveOp,
    ReplaceOp,
    TestOp,
)
from jsonpatchx.exceptions import (
    InvalidJSONPointer,
    InvalidOperationDefinition,
    InvalidOperationRegistry,
    OperationValidationError,
    PatchConflictError,
    PatchError,
    PatchFailureDetail,
    PatchInputError,
    PatchInternalError,
    PatchValidationError,
    TestOpFailed,
)
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.pydantic import JsonPatchFor
from jsonpatchx.registry import (
    STANDARD_OPS,
    StandardRegistry,
)
from jsonpatchx.schema import OperationSchema
from jsonpatchx.standard import JsonPatch, apply_patch
from jsonpatchx.types import JSONValue

__all__ = [
    # exceptions
    "InvalidJSONPointer",
    "InvalidOperationDefinition",
    "InvalidOperationRegistry",
    "OperationValidationError",
    "PatchConflictError",
    "PatchError",
    "PatchInternalError",
    "PatchFailureDetail",
    "PatchInputError",
    "PatchValidationError",
    "TestOpFailed",
    # types
    "JSONPointer",
    "JSONValue",
    # operation specs
    "OperationSchema",
    "StandardRegistry",
    "STANDARD_OPS",
    # pydantic helpers
    "JsonPatchFor",
    # built-ins
    "AddOp",
    "RemoveOp",
    "ReplaceOp",
    "MoveOp",
    "CopyOp",
    "TestOp",
    # classics
    "JsonPatch",
    "apply_patch",
]
