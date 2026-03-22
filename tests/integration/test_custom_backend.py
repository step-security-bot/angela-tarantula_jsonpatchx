from typing import Literal, override

from jsonpatchx.pointer import JSONPointer
from jsonpatchx.schema import OperationSchema
from jsonpatchx.standard import JsonPatch
from jsonpatchx.types import JSONValue
from tests.conftest import DotPointer


def test_custom_backend_with_registry() -> None:
    class DotRemoveOp(OperationSchema):
        op: Literal["dot-remove"] = "dot-remove"
        path: JSONPointer[JSONValue, DotPointer]

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return self.path.remove(doc)

    type Registry = DotRemoveOp
    patch = JsonPatch([{"op": "dot-remove", "path": "a.b"}], registry=Registry)
    result = patch.apply({"a": {"b": 1}})
    assert result == {"a": {}}
