from typing import Literal, override

import pytest
from pydantic import BaseModel, ConfigDict

from jsonpatchx.exceptions import InvalidOperationRegistry
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.pydantic import JsonPatchFor
from jsonpatchx.registry import StandardRegistry
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import JSONValue


class User(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    name: str


def test_jsonpatchfor_requires_basemodel_type() -> None:
    with pytest.raises(TypeError):
        JsonPatchFor[int, StandardRegistry]  # type: ignore[type-var]


def test_jsonpatchfor_requires_model_type() -> None:
    with pytest.raises(TypeError):
        JsonPatchFor[int, StandardRegistry]  # type: ignore[type-var]

    with pytest.raises(InvalidOperationRegistry):
        JsonPatchFor[Literal["Config"], int]  # type: ignore[type-var]


def test_jsonpatchfor_with_custom_registry() -> None:
    class EchoOp(OperationSchema):
        op: Literal["echo"] = "echo"
        path: JSONPointer[JSONValue]
        value: JSONValue

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    type Registry = EchoOp
    PatchBody = JsonPatchFor[User, Registry]
    patch = PatchBody.model_validate([{"op": "echo", "path": "/name", "value": "ok"}])
    assert patch.ops


def test_jsonpatchfor_accepts_registry_type_aliases() -> None:
    class EchoOp(OperationSchema):
        op: Literal["echo-alias"] = "echo-alias"
        path: JSONPointer[JSONValue]
        value: JSONValue

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    class StampOp(OperationSchema):
        op: Literal["stamp"] = "stamp"
        path: JSONPointer[JSONValue]
        value: JSONValue

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    type EchoRegistry = EchoOp
    type StampRegistry = StampOp
    type EchoRegistryAlias = EchoRegistry
    type CombinedRegistry = EchoRegistryAlias | StampRegistry

    PatchFromAlias = JsonPatchFor[User, EchoRegistryAlias]
    parsed_from_alias = PatchFromAlias.model_validate(
        [{"op": "echo-alias", "path": "/name", "value": "ok"}]
    )
    assert type(parsed_from_alias.ops[0]) is EchoOp

    PatchFromUnionAlias = JsonPatchFor[Literal["Config"], CombinedRegistry]
    parsed_from_union_alias = PatchFromUnionAlias.model_validate(
        [{"op": "stamp", "path": "/name", "value": "ok"}]
    )
    assert type(parsed_from_union_alias.ops[0]) is StampOp
