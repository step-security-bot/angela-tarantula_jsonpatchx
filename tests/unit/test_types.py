from __future__ import annotations

import copy
from dataclasses import dataclass
from functools import partial
from operator import attrgetter
from typing import Any, Final, Generic

import pytest
from jsonpath import JSONPointer as ExtendedJsonPointer
from jsonpointer import JsonPointer as CustomJsonPointer
from pydantic import BaseModel, TypeAdapter, ValidationError
from pytest import Subtests
from typing_extensions import TypeVar

from jsonpatchx.backend import (
    _DEFAULT_POINTER_CLS,
    PointerBackend,
    TargetState,
    classify_state,
)
from jsonpatchx.exceptions import InvalidJSONPointer, PatchConflictError
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.types import JSONBoolean, JSONNumber, JSONValue
from tests.conftest import (
    AnotherIncompletePointerBackend,
    BadDotPointer,
    DotPointer,
    DotPointerSubclass,
    IncompletePointerBackend,
    PointerMissingParts,
    TypeSuite,
)

# ============================================================================
# 1) JSON alias validations
# ============================================================================


def test_json_type_validations(subtests: Subtests, suite: TypeSuite) -> None:
    """Verify that Pydantic TypeAdapters align with suite predicate logic."""
    for json_type in suite.types:
        adapter = TypeAdapter(json_type)

        for example in suite.examples:
            expected_ok = suite.is_compatible(example.value, json_type)
            label = f"{json_type!r} vs {example.label}"

            with subtests.test(label):
                if expected_ok:
                    adapter.validate_python(example.value, strict=True)
                else:
                    with pytest.raises(ValidationError):
                        adapter.validate_python(example.value, strict=True)


# ============================================================================
# 2) Pointer backend protocol checks
# ============================================================================


def test_pointer_backend(subtests: Subtests) -> None:
    with subtests.test("Custom JsonPointer backend"):
        assert isinstance(CustomJsonPointer(""), PointerBackend)
    with subtests.test("Extended JsonPointer backend"):
        assert isinstance(ExtendedJsonPointer(""), PointerBackend)


# ============================================================================
# 3) classify_state scenarios
# ============================================================================


@dataclass(frozen=True)
class StateScenario:
    label: str
    doc: JSONValue
    path: str
    expected: TargetState


STATE_SCENARIOS: Final[tuple[StateScenario, ...]] = (
    StateScenario("root", {"a": 1}, "", TargetState.ROOT),
    StateScenario(
        "parent-not-found", {"a": {}}, "/a/missing/b", TargetState.PARENT_NOT_FOUND
    ),
    StateScenario(
        "parent-not-container", {"a": 1}, "/a/b", TargetState.PARENT_NOT_CONTAINER
    ),
    StateScenario(
        "object-key-missing", {"a": {}}, "/a/b", TargetState.OBJECT_KEY_MISSING
    ),
    StateScenario(
        "value-present-object", {"a": {"b": 1}}, "/a/b", TargetState.VALUE_PRESENT
    ),
    StateScenario(
        "array-key-invalid", {"a": [1, 2]}, "/a/nope", TargetState.ARRAY_KEY_INVALID
    ),
    StateScenario(
        "array-index-append", {"a": [1, 2]}, "/a/-", TargetState.ARRAY_INDEX_APPEND
    ),
    StateScenario(
        "array-index-at-end", {"a": [1, 2]}, "/a/2", TargetState.ARRAY_INDEX_AT_END
    ),
    StateScenario(
        "array-index-out-of-range",
        {"a": [1, 2]},
        "/a/3",
        TargetState.ARRAY_INDEX_OUT_OF_RANGE,
    ),
    StateScenario(
        "negative-index-present",
        {"a": [1, 2]},
        "/a/-1",
        TargetState.VALUE_PRESENT_AT_NEGATIVE_ARRAY_INDEX,
    ),
)
assert len(STATE_SCENARIOS) == len(TargetState), "STATE_SCENARIOS not set up correctly"


@pytest.mark.parametrize("scenario", STATE_SCENARIOS, ids=attrgetter("label"))
def test_classify_state(scenario: StateScenario) -> None:
    ptr = JSONPointer.parse(scenario.path)
    assert classify_state(ptr.ptr, scenario.doc) is scenario.expected


# ============================================================================
# 4) JSONPointer type gating and method semantics
# ============================================================================


def test_jsonpointer_get(subtests: Subtests, suite: TypeSuite) -> None:
    for type_param in suite.types:
        ptr = JSONPointer.parse("/k", type_param=type_param)
        for example in suite.examples:
            value = example.value
            doc: Any = {"k": value}
            expected_get = suite.is_compatible(value, type_param)

            with subtests.test(f"{type_param!r} get / is_gettable ({example.label})"):
                if expected_get:
                    assert ptr.get(doc) == value
                    assert ptr.is_gettable(doc) is True
                else:
                    with pytest.raises(PatchConflictError):
                        ptr.get(doc)
                    assert ptr.is_gettable(doc) is False

            with subtests.test(f"{type_param!r} is_valid_type ({example.label})"):
                assert ptr.is_valid_type(value) is expected_get


def test_jsonpointer_remove(subtests: Subtests, suite: TypeSuite) -> None:
    for type_param in suite.types:
        ptr = JSONPointer.parse("/k", type_param=type_param)
        for example in suite.examples:
            value = example.value
            doc: Any = {"k": value}
            expected_remove = suite.is_compatible(value, type_param)

            with subtests.test(
                f"{type_param!r} remove / is_removable ({example.label})"
            ):
                if expected_remove:
                    assert ptr.is_removable(doc) is True
                    d2 = copy.deepcopy(doc)
                    out = ptr.remove(d2)
                    assert isinstance(out, dict)
                    assert "k" not in out
                    assert ptr.is_removable(d2) is False
                else:
                    assert ptr.is_removable(doc) is False
                    with pytest.raises(PatchConflictError):
                        ptr.remove(copy.deepcopy(doc))


def test_jsonpointer_add(subtests: Subtests, suite: TypeSuite) -> None:
    for type_param in suite.types:
        valid_examples = suite.get_examples(type_param, valid=True)
        valid_T_value = valid_examples[0].value
        alt_valid_T_value = valid_examples[1].value
        ptr = JSONPointer.parse("/k", type_param=type_param)

        for example in suite.examples:
            value = example.value
            doc: Any = {"k": value}
            new_value = alt_valid_T_value

            expected_existing_ok = suite.is_compatible(value, type_param)
            expected_new_ok = suite.is_compatible(new_value, (type_param, JSONValue))
            expected_add = expected_existing_ok and expected_new_ok

            with subtests.test(
                f"{type_param!r} add / is_addable overwrite-object ({example.label})"
            ):
                if expected_add:
                    d2 = copy.deepcopy(doc)
                    assert ptr.is_addable(d2, new_value) is True
                    out = ptr.add(d2, new_value)
                    assert isinstance(out, dict)
                    assert out["k"] == new_value
                else:
                    assert ptr.is_addable(doc, new_value) is False
                    with pytest.raises(PatchConflictError):
                        ptr.add(copy.deepcopy(doc), new_value)

            if (not expected_existing_ok) and expected_new_ok:
                with subtests.test(
                    f"{type_param!r} overwrite blocked when existing wrong type ({example.label})"
                ):
                    assert ptr.is_addable(doc, valid_T_value) is False
                    with pytest.raises(PatchConflictError):
                        ptr.add(copy.deepcopy(doc), valid_T_value)


# ============================================================================
# 5) Non-trivial pointer edge cases
# ============================================================================


def test_jsonpointer_root_semantics(subtests: Subtests) -> None:
    with subtests.test("root semantics"):
        root = JSONPointer.parse("")
        assert root.get({"a": 1}) == {"a": 1}
        assert root.add({"a": 1}, {"b": 2}) == {"b": 2}
        assert root.remove({"a": 1}) is None


def test_jsonpointer_array_index_handling(subtests: Subtests) -> None:
    with subtests.test("get by index"):
        item = JSONPointer.parse("/arr/0")
        assert item.get({"arr": [10, 20]}) == 10

    with subtests.test("append add"):
        doc: JSONValue = {"arr": [10]}
        appended = JSONPointer.parse("/arr/-").add(doc, 30)
        assert appended["arr"] == [10, 30]

    with subtests.test("remove failures"):
        with pytest.raises(PatchConflictError):
            JSONPointer.parse("/arr/-").remove({"arr": [10]})
        with pytest.raises(PatchConflictError):
            JSONPointer.parse("/arr/2").remove({"arr": [10, 20]})
        with pytest.raises(PatchConflictError):
            JSONPointer.parse("/arr/-1").remove({"arr": [10, 20]})
        with pytest.raises(PatchConflictError):
            JSONPointer.parse("/arr/nope").remove({"arr": [10, 20]})
        with pytest.raises(PatchConflictError):
            JSONPointer.parse("/arr/01").remove({"arr": [10, 20]})

    with subtests.test("insert semantics (VALUE_PRESENT)"):
        # /arr/1 with add() inserts (shifts), not overwrite
        doc = {"arr": [10, 20]}
        out = JSONPointer.parse("/arr/1").add(doc, 15)
        assert out["arr"] == [10, 15, 20]


def test_jsonpointer_is_addable_edge_cases(subtests: Subtests) -> None:
    with subtests.test("root is_addable"):
        root_number = JSONPointer.parse("", type_param=JSONNumber)
        assert root_number.is_addable(1) is True
        assert root_number.is_addable("nope") is False

    with subtests.test("array indices"):
        doc = {"arr": [10]}
        assert JSONPointer.parse("/arr/0").is_addable(doc, 5) is True
        assert JSONPointer.parse("/arr/1").is_addable(doc, 5) is True
        assert JSONPointer.parse("/arr/2").is_addable(doc, 5) is False
        assert JSONPointer.parse("/arr/-").is_addable(doc, 5) is True
        assert JSONPointer.parse("/arr/nope").is_addable(doc, 5) is False

    with subtests.test("parent not container"):
        assert JSONPointer.parse("/a/b").is_addable({"a": 1}, 5) is False


def test_jsonpointer_container_type_errors(subtests: Subtests) -> None:
    ptr = JSONPointer.parse("/a/b")
    with subtests.test("add on primitive parent"):
        with pytest.raises(PatchConflictError):
            ptr.add({"a": 1}, "ok")
    with subtests.test("remove on primitive parent"):
        with pytest.raises(PatchConflictError):
            ptr.remove({"a": 1})


def test_jsonpointer_parent_child_edge_cases(subtests: Subtests) -> None:
    parent = JSONPointer.parse("/a")
    child = JSONPointer.parse("/a/b")
    same = JSONPointer.parse("/a")
    with subtests.test("parent/child basics"):
        assert parent.is_parent_of(child) is True
        assert child.is_child_of(parent) is True
        assert parent.is_parent_of(same) is False
        assert parent.is_child_of(child) is False

    with subtests.test("backend mismatch errors"):
        dot_ptr = JSONPointer.parse("a.b", backend=DotPointer)
        with pytest.raises(InvalidJSONPointer):
            parent.is_parent_of(dot_ptr)
        with pytest.raises(InvalidJSONPointer):
            parent.is_child_of(dot_ptr)


# ============================================================================
# 6+) Everything else
# ============================================================================


@pytest.mark.parametrize(
    (
        "custom_pointer_cls",
        "path",
        "parent_path",
        "child_path",
        "missing_path",
        "add_path",
        "parts",
    ),
    [
        (None, "/a/b", "/a", "/a/b/c", "/a/b/missing", "/a/new", ["a", "b"]),
        (DotPointer, "a.b", "a", "a.b.c", "a.b.missing", "a.new", ["a", "b"]),
    ],
)
def test_jsonpointer_public_methods_are_backend_agnostic(
    subtests: Subtests,
    custom_pointer_cls: type[PointerBackend] | None,
    path: str,
    parent_path: str,
    child_path: str,
    missing_path: str,
    add_path: str,
    parts: list[str],
) -> None:
    doc = {"a": {"b": 1, "c": {"d": 2}}, "arr": [10, 20]}

    if custom_pointer_cls is None:
        parse = JSONPointer.parse
    else:
        parse = partial(JSONPointer.parse, backend=DotPointer)

    ptr = parse(path)
    parent = parse(parent_path)
    child = parse(child_path)

    with subtests.test("ptr"):
        assert ptr.ptr is not None

    with subtests.test("parts"):
        assert list(ptr.parts) == parts

    with subtests.test("type_param"):
        assert ptr.type_param is JSONValue

    with subtests.test("is_root"):
        assert ptr.is_root(doc) is False
        root = parse("")
        assert root.is_root(doc) is True
        missing = parse(missing_path)
        assert missing.is_root(doc) is False

    with subtests.test("is_parent_of"):
        assert parent.is_parent_of(ptr) is True
        assert ptr.is_parent_of(parent) is False
        if custom_pointer_cls is None:
            with pytest.raises(InvalidJSONPointer):
                ptr.is_parent_of(DotPointer("a.b"))
        else:
            with pytest.raises(InvalidJSONPointer):
                ptr.is_parent_of(CustomJsonPointer("/a/b"))

    with subtests.test("is_child_of"):
        assert child.is_child_of(ptr) is True
        assert ptr.is_child_of(child) is False
        assert ptr.is_child_of(ptr) is False
        if custom_pointer_cls is None:
            with pytest.raises(InvalidJSONPointer):
                ptr.is_child_of(DotPointer("a.b"))
        else:
            with pytest.raises(InvalidJSONPointer):
                ptr.is_child_of(CustomJsonPointer("/a/b"))

    with subtests.test("is_valid_type"):
        bool_ptr = parse(parent_path, type_param=JSONBoolean)
        assert bool_ptr.is_valid_type(True) is True
        assert bool_ptr.is_valid_type(1) is False

    with subtests.test("get"):
        assert ptr.get(doc) == 1

    with subtests.test("is_gettable"):
        assert ptr.is_gettable(doc) is True
        missing = parse(missing_path)
        assert missing.is_gettable(doc) is False

    with subtests.test("is_removable"):
        assert ptr.is_removable(doc) is True
        missing = parse(missing_path)
        assert missing.is_removable(doc) is False

    with subtests.test("add"):
        add_ptr = parse(add_path)
        updated = add_ptr.add({"a": {"b": 1}}, "ok")
        assert updated["a"]["new"] == "ok"

    with subtests.test("is_addable"):
        add_ptr = parse(add_path)
        assert add_ptr.is_addable({"a": {"b": 1}}, "ok") is True
        assert child.is_addable(doc, "ok") is False

    with subtests.test("remove"):
        remove_ptr = parse(path)
        removed = remove_ptr.remove({"a": {"b": 1}})
        assert "b" not in removed["a"]

    with subtests.test("__str__"):
        assert str(ptr) == path


def test_pointer_backend_binding(subtests: Subtests) -> None:
    class BoundPointer(DotPointer):
        pass

    with subtests.test("no backends"):
        ptr = JSONPointer.parse("/a", backend=None)
        assert isinstance(ptr.ptr, _DEFAULT_POINTER_CLS)

    with subtests.test("bound backend"):
        ptr = JSONPointer.parse("a.b", backend=BoundPointer)
        assert isinstance(ptr.ptr, BoundPointer)

    with subtests.test("explicit default backend class behaves like omitted backend"):
        ptr = JSONPointer.parse("/a", backend=_DEFAULT_POINTER_CLS)
        assert isinstance(ptr.ptr, _DEFAULT_POINTER_CLS)

    with subtests.test("bound PointerBackend is invalid"):
        with pytest.raises(InvalidJSONPointer):
            JSONPointer.parse("/a", backend=PointerBackend)


def test_jsonpointer_backend_reuse(subtests: Subtests) -> None:
    ptr1a = JSONPointer.parse("a.b", backend=DotPointer)
    ptr1b = JSONPointer.parse(ptr1a, backend=DotPointer)
    ptr2a = JSONPointer.parse(DotPointer("a.b"), backend=DotPointer)
    ptr2b = JSONPointer.parse(ptr2a, backend=DotPointer)
    ptr3a = JSONPointer.parse(DotPointerSubclass("c.d"), backend=DotPointer)
    ptr3b = JSONPointer.parse(ptr3a, backend=DotPointer)

    with subtests.test("reuse compatible backend instances"):
        assert ptr1a.ptr is ptr1b.ptr
        assert ptr2a.ptr is ptr2b.ptr
        assert ptr3a.ptr is ptr3b.ptr

    with subtests.test("don't coerce backend superclass instances"):
        with pytest.raises(InvalidJSONPointer):
            JSONPointer.parse(DotPointer("e.f"), backend=DotPointerSubclass)

    with subtests.test("reject incompatible backend instances"):
        with pytest.raises(InvalidJSONPointer):
            JSONPointer.parse(CustomJsonPointer("/hello"), backend=DotPointer)

    with subtests.test(
        "reparse JSONPointer into different but compatible-syntax backend"
    ):
        reparsed = JSONPointer.parse(ptr1a, backend=DotPointerSubclass)
        assert isinstance(reparsed.ptr, DotPointerSubclass)
        assert reparsed.ptr is not ptr1a.ptr


def test_jsonpointer_type_args_validation(subtests: Subtests) -> None:
    with subtests.test("invalid type param"):
        with pytest.raises(InvalidJSONPointer):
            TypeAdapter(JSONPointer[int()])

    with subtests.test("not enough args"):
        with pytest.raises(TypeError):
            TypeAdapter(JSONPointer)

    with subtests.test("too many args"):
        with pytest.raises(TypeError):
            TypeAdapter(JSONPointer[JSONValue, DotPointer, int])

    with subtests.test("invalid backend"):
        for invalid_backend in [
            object,
            object(),
            JSONValue,
            str,
            IncompletePointerBackend,
            AnotherIncompletePointerBackend,
            PointerMissingParts,
            PointerBackend,
            BadDotPointer,
            DotPointer(""),
            "DotPointer",  # forward references disallowed for predictability
        ]:
            with pytest.raises(InvalidJSONPointer):
                adapter = TypeAdapter(JSONPointer[JSONValue, invalid_backend])
                adapter.validate_python("")

    with subtests.test("valid backend"):
        for valid_backend in [
            _DEFAULT_POINTER_CLS,
            DotPointer,
            CustomJsonPointer,
        ]:
            adapter = TypeAdapter(JSONPointer[JSONValue, valid_backend])
            adapter.validate_python("")

    with subtests.test(
        "backend typevar bound to PointerBackend requires specialization or default"
    ):
        P_backend = TypeVar("P_backend", bound=PointerBackend)
        adapter = TypeAdapter(JSONPointer[JSONValue, P_backend])
        with pytest.raises(InvalidJSONPointer):
            adapter.validate_python("")

    with subtests.test("backend typevar constraints require specialization or default"):
        P_constrained = TypeVar("P_constrained", DotPointer, CustomJsonPointer)
        adapter = TypeAdapter(JSONPointer[JSONValue, P_constrained])
        with pytest.raises(InvalidJSONPointer):
            adapter.validate_python("")

    with subtests.test("backend typevar non-backend bound fails at runtime"):
        P_invalid_bound = TypeVar("P_invalid_bound", bound=str)
        adapter = TypeAdapter(JSONPointer[JSONValue, P_invalid_bound])
        with pytest.raises(InvalidJSONPointer):
            adapter.validate_python("")

    with subtests.test("backend typevar without constraints or bound is rejected"):
        P_unbound = TypeVar("P_unbound")
        adapter = TypeAdapter(JSONPointer[JSONValue, P_unbound])
        with pytest.raises(InvalidJSONPointer):
            adapter.validate_python("")

    with subtests.test("backend typevar default is honored at runtime"):

        class DefaultDotPointer(DotPointer):
            pass

        P_default = TypeVar(
            "P_default", bound=PointerBackend, default=DefaultDotPointer
        )
        adapter = TypeAdapter(JSONPointer[JSONValue, P_default])
        ptr = adapter.validate_python("a.b")
        assert isinstance(ptr.ptr, DefaultDotPointer)

    with subtests.test("backend typevar nested default typevar is resolved"):
        P_inner = TypeVar("P_inner", bound=PointerBackend, default=DotPointer)
        P_outer = TypeVar("P_outer", bound=PointerBackend, default=P_inner)
        adapter = TypeAdapter(JSONPointer[JSONValue, P_outer])
        ptr = adapter.validate_python("a.b")
        assert isinstance(ptr.ptr, DotPointer)

    with subtests.test("backend typevar non-type default is rejected"):
        P_non_type_default = TypeVar(
            "P_non_type_default", bound=PointerBackend, default=123
        )
        adapter = TypeAdapter(JSONPointer[JSONValue, P_non_type_default])
        with pytest.raises(InvalidJSONPointer):
            adapter.validate_python("/a/b")

    with subtests.test("backend typevar PointerBackend default is rejected"):
        P_protocol_default = TypeVar(
            "P_protocol_default", bound=PointerBackend, default=PointerBackend
        )
        adapter = TypeAdapter(JSONPointer[JSONValue, P_protocol_default])
        with pytest.raises(InvalidJSONPointer):
            adapter.validate_python("/a/b")

    with subtests.test("TypeVar without default works in Python 3.12 and below"):
        import typing

        P_backend = typing.TypeVar("P_backend", bound=PointerBackend)
        adapter = TypeAdapter(JSONPointer[JSONValue, P_backend])
        with pytest.raises(InvalidJSONPointer):
            adapter.validate_python("/a/b")

    with subtests.test("reject invalid default backend string syntax"):
        adapter = TypeAdapter(JSONPointer[JSONValue])
        with pytest.raises(InvalidJSONPointer):
            adapter.validate_python("a.b")

    with subtests.test("reject invalid custom backend string syntax"):
        adapter = TypeAdapter(JSONPointer[JSONValue, DotPointer])
        with pytest.raises(InvalidJSONPointer):
            adapter.validate_python("a..b")


def test_backend_typevar_explicit_policy_cases(subtests: Subtests) -> None:
    with subtests.test("explicit PointerBackend parameter is rejected at runtime"):
        adapter = TypeAdapter(JSONPointer[JSONValue, PointerBackend])
        with pytest.raises(InvalidJSONPointer):
            adapter.validate_python("/a/b")

    with subtests.test("direct specialization uses explicit backend"):

        class OtherDotPointer(DotPointer):
            pass

        P_backend = TypeVar("P_backend", bound=PointerBackend, default=DotPointer)

        class GenericModel(BaseModel, Generic[P_backend]):
            path: JSONPointer[JSONValue, P_backend]

        model = GenericModel[OtherDotPointer].model_validate({"path": "a.b"})
        assert isinstance(model.path.ptr, OtherDotPointer)


def test_jsonpointer_json_schema_backend_resolution(subtests: Subtests) -> None:
    with subtests.test("default backend reports RFC json-pointer format"):
        schema = TypeAdapter(JSONPointer[JSONValue]).json_schema()
        assert schema["format"] == "json-pointer"

    with subtests.test("concrete custom backend reports custom format"):
        schema = TypeAdapter(JSONPointer[JSONValue, DotPointer]).json_schema()
        assert schema["format"] == "x-json-pointer"

    with subtests.test("backend TypeVar without default cannot produce JSON schema"):
        P_backend = TypeVar("P_backend", bound=PointerBackend)
        with pytest.raises(InvalidJSONPointer):
            TypeAdapter(JSONPointer[JSONValue, P_backend]).json_schema()

    with subtests.test("backend TypeVar defaulting to RFC backend reports RFC format"):
        P_default_default_ptr = TypeVar(
            "P_default_default_ptr",
            bound=PointerBackend,
            default=_DEFAULT_POINTER_CLS,
        )
        schema = TypeAdapter(
            JSONPointer[JSONValue, P_default_default_ptr]
        ).json_schema()
        assert schema["format"] == "json-pointer"

    with subtests.test(
        "backend TypeVar defaulting to custom backend reports custom format"
    ):
        P_default_custom_ptr = TypeVar(
            "P_default_custom_ptr",
            bound=PointerBackend,
            default=DotPointer,
        )
        schema = TypeAdapter(JSONPointer[JSONValue, P_default_custom_ptr]).json_schema()
        assert schema["format"] == "x-json-pointer"


def test_jsonpointer_path_validation(subtests: Subtests) -> None:
    with subtests.test("accept strings"):
        JSONPointer.parse("a.b", backend=DotPointer)
    with subtests.test("accept compatible PointerBackend instances"):
        JSONPointer.parse(DotPointer("a.b"), backend=DotPointer)
    with subtests.test("accept other JSONPointers"):
        ptr = JSONPointer.parse(DotPointer("a.b"), backend=DotPointer)
        JSONPointer.parse(ptr, backend=DotPointer)
    with subtests.test("reject incompatible PointerBackends"):
        with pytest.raises(InvalidJSONPointer):
            JSONPointer.parse(CustomJsonPointer("/a/b"), backend=DotPointer)
        with pytest.raises(InvalidJSONPointer):
            JSONPointer.parse(ExtendedJsonPointer("/hello"), backend=DotPointer)
    with subtests.test("accepts narrower PointerBackends"):
        JSONPointer.parse(DotPointerSubclass("a.b"), backend=DotPointer)


def test_jsonpointer_covariance_narrow_to_wide(subtests: Subtests) -> None:
    with subtests.test("narrow to wide passes"):
        p_bool = JSONPointer.parse("/x", type_param=bool)
        assert JSONPointer.parse(p_bool, type_param=int) == p_bool
        assert JSONPointer.parse(p_bool, type_param=JSONNumber) == p_bool
        assert JSONPointer.parse(p_bool, type_param=JSONValue) == p_bool
    # currently wide-to-narrow is also allowed, but that's not guaranteed in the future
    # type hints already forbid non-covariant assignment
    # NOTE: add tests that simply showcase that ``type: ignore`` is required to disobey the documentation
