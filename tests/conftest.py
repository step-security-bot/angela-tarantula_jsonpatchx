from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cached_property
from types import NoneType
from typing import Annotated, Any, Callable, Final, Self

import pytest
from annotated_types import Ge
from typing_extensions import TypeForm, TypeIs

from jsonpatchx.backend import PointerBackend
from jsonpatchx.types import (
    JSONArray,
    JSONBoolean,
    JSONContainer,
    JSONNull,
    JSONNumber,
    JSONObject,
    JSONString,
    JSONValue,
)

# ============================================================================
# 1) Custom Pointer Backends
# ============================================================================


class IncompletePointerBackend:
    """A PointerBackend missing required methods."""

    def __init__(self, pointer: str) -> None:
        self._parts = [] if pointer == "" else pointer.split(".")

    @property
    def parts(self) -> list[str]:
        return self._parts

    @classmethod
    def from_parts(cls, parts: Iterable[Any]) -> Self:
        return cls(".".join(str(p) for p in parts))

    def __str__(self) -> str:
        return ".".join(self._parts)

    def __hash__(self) -> int:
        return hash(tuple(self._parts))


class AnotherIncompletePointerBackend(IncompletePointerBackend, PointerBackend):
    """IncompletePointerBackend but it technically inherits from PointerBackend."""

    pass


class DotPointer(IncompletePointerBackend):
    def __init__(self, pointer: str) -> None:
        if ".." in pointer:
            raise ValueError("invalid dot pointer")
        super().__init__(pointer)

    def resolve(self, data: JSONValue) -> Any:
        cur: Any = data
        for token in self._parts:
            cur = cur[token]
        return cur


class DotPointerSubclass(DotPointer):
    """Narrower DotPointer variant reused across pointer covariance tests."""

    pass


class BadDotPointer(DotPointer):
    """Looks like a valid DotPointer until runtime."""

    def __new__(cls, pointer: str) -> str:
        return "nope"


class PointerMissingParts(PointerBackend):
    __init__ = DotPointer.__init__

    from_parts = DotPointer.from_parts

    __str__ = DotPointer.__str__

    __hash__ = DotPointer.__hash__


# ============================================================================
# 2) Predicate Definitions
# ============================================================================


def _is_bool(v: object) -> TypeIs[JSONBoolean]:
    return isinstance(v, bool)


def _is_number(v: object) -> TypeIs[JSONNumber]:
    if isinstance(v, bool):
        return False
    return isinstance(v, (int, float)) and math.isfinite(v)


def _is_string(v: object) -> TypeIs[JSONString]:
    return isinstance(v, str)


def _is_null(v: object) -> TypeIs[JSONNull]:
    return v is None


def _is_object_any(v: object) -> TypeIs[JSONObject[object]]:
    return isinstance(v, dict) and all(isinstance(k, str) for k in v.keys())


def _is_array_any(v: object) -> TypeIs[JSONArray[object]]:
    return isinstance(v, list)


def _is_json_value(v: object) -> TypeIs[JSONValue]:
    if _is_bool(v) or _is_number(v) or _is_string(v) or _is_null(v):
        return True
    if _is_array_any(v):
        return all(_is_json_value(item) for item in v)
    if _is_object_any(v):
        return all(_is_json_value(val) for val in v.values())
    return False


def _is_array_of[T](pred: Predicate[T]) -> Predicate[JSONArray[T]]:
    def _p(v: object) -> TypeIs[JSONArray[T]]:
        return _is_array_any(v) and all(pred(item) for item in v)

    return _p


def _is_object_of[T](pred: Predicate[T]) -> Predicate[JSONObject[T]]:
    def _p(v: object) -> TypeIs[JSONObject[T]]:
        return _is_object_any(v) and all(pred(val) for val in v.values())

    return _p


# ============================================================================
# 3) Type Suite
# ============================================================================

type Predicate[T] = Callable[[object], TypeIs[T]]
type _TypeInfo = TypeForm[Any] | tuple[_TypeInfo]


@dataclass(frozen=True)
class ExampleValue:
    label: str
    value: object


@dataclass(frozen=True)
class TypeSuite:
    """A registry of JSON types, their predicates, and associated test data."""

    type_map: dict[TypeForm[Any], Predicate[Any]]
    examples: tuple[ExampleValue, ...]

    @cached_property
    def types(self) -> tuple[Any, ...]:
        """Return all registered JSON types."""
        return tuple(self.type_map.keys())

    def get_predicate(self, json_type: Any) -> Predicate[Any]:
        """Return the predicate associated with ``json_type``."""
        if json_type not in self.type_map:
            raise AssertionError("Type {json_type!r} is not registered in {self!r}")
        return self.type_map[json_type]

    def is_compatible(self, value: object, type_or_tuple: _TypeInfo) -> bool:
        """Analogous to `isinstance` but using suite predicates."""
        if not isinstance(type_or_tuple, tuple):
            return self.get_predicate(type_or_tuple)(value)
        return all(self.is_compatible(value, nested) for nested in type_or_tuple)

    def get_examples(
        self, json_type: Any, valid: bool = True
    ) -> Annotated[tuple[ExampleValue, ...], Ge(2)]:
        """Return example values that pass or fail the predicate for ``json_type``."""
        pred = self.get_predicate(json_type)
        matches = [
            ex
            for ex in self.examples
            if (pred(ex.value) if valid else not pred(ex.value))
        ]
        if len(matches) < 2:
            raise AssertionError(
                f"Insufficient {'valid' if valid else 'invalid'} examples for {json_type!r}"
            )
        return tuple(matches)


# ============================================================================
# 4) Global Data
# ============================================================================

EXAMPLE_VALUES: Final = (
    ExampleValue("bool-true", True),
    ExampleValue("bool-false", False),
    ExampleValue("int", 1),
    ExampleValue("float", 1.5),
    ExampleValue("string", "ok"),
    ExampleValue("stringy-number", "1"),
    ExampleValue("null-1", None),
    ExampleValue("null-2", NoneType()),
    ExampleValue("array-simple", [1, {"a": 2}, "ok"]),
    ExampleValue("array-object-item", [object()]),
    ExampleValue("array-bytes-item", [b"bytes"]),
    ExampleValue("array-number", [1, 2, 3]),
    ExampleValue("array-number-float", [1, 2.5]),
    ExampleValue("array-number-null", [1, None]),
    ExampleValue("empty-object", {}),
    ExampleValue("object-simple", {"a": 1, "b": "ok", "c": None, "d": True}),
    ExampleValue("object-any", {"a": 1, "b": object()}),
    ExampleValue("object-strings", {"a": "ok", "b": "yes"}),
    ExampleValue("object-strings-null", {"a": None}),
    ExampleValue("nested", {"a": [1, {"b": [True, None, 3.5]}], "c": {"d": "ok"}}),
    ExampleValue("empty-array", []),
    ExampleValue("nested-obj-array-num", [{"a": 1}, {"b": 2}]),
    ExampleValue("nested-obj-array-num-null", [{"a": 1}, {"b": None}]),
    ExampleValue("poison-bytes", b"bytes"),
    ExampleValue("poison-custom-object", object()),
    ExampleValue("poison-complex", 1 + 2j),
    ExampleValue("poison-tuple", (1, 2)),
    ExampleValue("poison-set", {"a", "b"}),
    ExampleValue("poison-dict-non-str-key", {1: "nope"}),
    ExampleValue("poison-nan", float("nan")),
    ExampleValue("poison-inf", float("inf")),
)

TYPE_MAPPING: Final = {
    JSONBoolean: _is_bool,
    JSONNumber: _is_number,
    JSONString: _is_string,
    JSONNull: _is_null,
    JSONArray[Any]: _is_array_any,
    JSONObject[Any]: _is_object_any,
    JSONContainer[Any]: lambda v: _is_array_any(v) or _is_object_any(v),
    JSONValue: _is_json_value,
    JSONArray[JSONNumber]: _is_array_of(_is_number),
    JSONObject[JSONString]: _is_object_of(_is_string),
    JSONArray[JSONObject[JSONNumber]]: _is_array_of(_is_object_of(_is_number)),
    JSONArray[JSONObject[JSONNumber | JSONNull]]: _is_array_of(
        _is_object_of(lambda x: _is_number(x) or _is_null(x))
    ),
}

# ============================================================================
# 5) Type Suite
# ============================================================================


@pytest.fixture(scope="session")
def suite() -> TypeSuite:
    return TypeSuite(type_map=TYPE_MAPPING, examples=EXAMPLE_VALUES)
