"""Structured ClusterFuzzLite harness for core RFC6902 behavior in jsonpatchx."""

import copy
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import cast

import atheris  # type: ignore[import-not-found]

from fuzzers._fuzz_shared import (
    ByteCursor,
    coerce_patch,
    random_json_value,
    random_rfc6901_path,
)

with atheris.instrument_imports():
    from pydantic import ValidationError

    from jsonpatchx import JsonPatch, JSONPointer, JSONValue, apply_patch
    from jsonpatchx.exceptions import (
        PatchConflictError,
        PatchInputError,
        PatchInternalError,
    )

_KNOWN_OPS: tuple[str, ...] = ("add", "remove", "replace", "move", "copy", "test")
_UNKNOWN_OPS: tuple[str, ...] = ("", "noop", "increment", "ADD", "remove_all")
_ALL_OPS = _KNOWN_OPS + _UNKNOWN_OPS

_EXPECTED_PATCH_EXCEPTIONS = (
    PatchInputError,
    PatchConflictError,
    ValidationError,
    json.JSONDecodeError,
    UnicodeError,
)
_EXPECTED_POINTER_EXCEPTIONS = (
    PatchInputError,
    PatchConflictError,
    ValidationError,
)


@dataclass(frozen=True, slots=True)
class _Outcome:
    value: object | None = None
    error_type: type[BaseException] | None = None

    @property
    def ok(self) -> bool:
        return self.error_type is None


def _error_bucket(error_type: type[BaseException]) -> str:
    if issubclass(error_type, PatchConflictError):
        return "conflict"
    if issubclass(error_type, (PatchInputError, ValidationError)):
        return "input"
    if issubclass(error_type, (json.JSONDecodeError, UnicodeError)):
        return "decode"
    return error_type.__name__


def _assert_equivalent(left: _Outcome, right: _Outcome, *, context: str) -> None:
    if left.ok != right.ok:
        raise AssertionError(
            f"Outcome mismatch in {context}: left={left.error_type}, right={right.error_type}"
        )

    if left.ok:
        if left.value != right.value:
            raise AssertionError(f"Value mismatch in {context}")
        return

    assert left.error_type is not None
    assert right.error_type is not None
    if _error_bucket(left.error_type) != _error_bucket(right.error_type):
        raise AssertionError(
            f"Error bucket mismatch in {context}: "
            f"{left.error_type.__name__} vs {right.error_type.__name__}"
        )


def _random_patch(cursor: ByteCursor) -> list[dict[str, object]]:
    op_count = cursor.int_range(1, 10)
    patch: list[dict[str, object]] = []

    for _ in range(op_count):
        op_name = cursor.choose(_ALL_OPS)
        op: dict[str, object] = {
            "op": op_name,
            "path": random_rfc6901_path(cursor),
        }

        if op_name in {"add", "replace", "test"}:
            op["value"] = random_json_value(cursor)

        if op_name in {"copy", "move"}:
            op["from"] = random_rfc6901_path(cursor)

        # Exercise extra fields and alias ambiguity paths.
        if cursor.int_range(0, 5) == 0:
            op["x-fuzz"] = random_json_value(cursor, max_depth=2)
        if cursor.int_range(0, 9) == 0:
            op["from_"] = random_rfc6901_path(cursor)

        # Sometimes drop required fields to hit validators.
        if cursor.int_range(0, 11) == 0:
            op.pop("path", None)

        patch.append(op)

    return patch


def _run_patch_class_api(
    doc: object, patch: list[dict[str, object]], *, inplace: bool
) -> _Outcome:
    try:
        patch_for_api = cast(Sequence[Mapping[str, JSONValue]], patch)
        doc_for_api = cast(JSONValue, copy.deepcopy(doc))
        result = JsonPatch(patch_for_api).apply(doc_for_api, inplace=inplace)
        return _Outcome(value=result)
    except PatchInternalError:
        raise
    except _EXPECTED_PATCH_EXCEPTIONS as exc:
        return _Outcome(error_type=type(exc))


def _run_patch_function_api(doc: object, patch: list[dict[str, object]]) -> _Outcome:
    try:
        patch_for_api = cast(Sequence[Mapping[str, JSONValue]], patch)
        doc_for_api = cast(JSONValue, copy.deepcopy(doc))
        result = apply_patch(doc_for_api, patch_for_api, inplace=False)
        return _Outcome(value=result)
    except PatchInternalError:
        raise
    except _EXPECTED_PATCH_EXCEPTIONS as exc:
        return _Outcome(error_type=type(exc))


def _run_patch_string_api(doc: object, patch: list[dict[str, object]]) -> _Outcome:
    try:
        encoded_patch = json.dumps(patch, separators=(",", ":"), ensure_ascii=False)
        doc_for_api = cast(JSONValue, copy.deepcopy(doc))
        result = JsonPatch.from_string(encoded_patch).apply(doc_for_api, inplace=False)
        return _Outcome(value=result)
    except PatchInternalError:
        raise
    except _EXPECTED_PATCH_EXCEPTIONS as exc:
        return _Outcome(error_type=type(exc))


def _run_pointer_call(fn: Callable[[], object]) -> _Outcome:
    try:
        return _Outcome(value=fn())
    except PatchInternalError:
        raise
    except _EXPECTED_POINTER_EXCEPTIONS as exc:
        return _Outcome(error_type=type(exc))


def _exercise_pointer(pointer_text: str, *, source: bytes) -> None:
    try:
        ptr: JSONPointer[JSONValue] = JSONPointer.parse(pointer_text)
    except _EXPECTED_POINTER_EXCEPTIONS:
        return

    # Parsing should be stable under canonical stringification.
    round_trip: JSONPointer[JSONValue] = JSONPointer.parse(str(ptr))
    if tuple(ptr.parts) != tuple(round_trip.parts):
        raise AssertionError(
            "JSONPointer parse/string round-trip changed pointer parts"
        )

    cursor = ByteCursor(source)
    doc = random_json_value(cursor)
    value = random_json_value(cursor)

    gettable = ptr.is_gettable(copy.deepcopy(doc))
    get_outcome = _run_pointer_call(lambda: ptr.get(copy.deepcopy(doc)))
    if gettable != get_outcome.ok:
        raise AssertionError("JSONPointer.is_gettable disagrees with JSONPointer.get")

    addable = ptr.is_addable(copy.deepcopy(doc), value)
    add_outcome = _run_pointer_call(lambda: ptr.add(copy.deepcopy(doc), value))
    if addable != add_outcome.ok:
        raise AssertionError("JSONPointer.is_addable disagrees with JSONPointer.add")

    removable = ptr.is_removable(copy.deepcopy(doc))
    remove_outcome = _run_pointer_call(lambda: ptr.remove(copy.deepcopy(doc)))
    if removable != remove_outcome.ok:
        raise AssertionError(
            "JSONPointer.is_removable disagrees with JSONPointer.remove"
        )


def _exercise_patch(doc: object, patch: list[dict[str, object]]) -> None:
    class_copy = _run_patch_class_api(doc, patch, inplace=False)
    function_copy = _run_patch_function_api(doc, patch)
    string_copy = _run_patch_string_api(doc, patch)
    class_inplace = _run_patch_class_api(doc, patch, inplace=True)

    _assert_equivalent(
        class_copy, function_copy, context="JsonPatch.apply vs apply_patch"
    )
    _assert_equivalent(
        class_copy, string_copy, context="JsonPatch() vs JsonPatch.from_string"
    )
    _assert_equivalent(
        class_copy, class_inplace, context="inplace=False vs inplace=True"
    )


def TestOneInput(data: bytes) -> None:
    if not data:
        return

    cursor = ByteCursor(data)
    generated_doc = random_json_value(cursor)
    generated_patch = _random_patch(cursor)

    # Directly consume raw bytes as pointer text to preserve entropy.
    pointer_text = data[:96].decode("latin-1")
    _exercise_pointer(pointer_text, source=data)
    _exercise_pointer(random_rfc6901_path(cursor), source=data[::-1])

    _exercise_patch(generated_doc, generated_patch)

    # Also exercise externally supplied JSON payload shape:
    #   {"doc": ..., "patch": [...]} or a plain patch array.
    try:
        payload = json.loads(data)
    except (json.JSONDecodeError, UnicodeError):
        return

    if isinstance(payload, str):
        _exercise_pointer(payload[:96], source=data)
        return

    if isinstance(payload, dict):
        payload_patch = coerce_patch(payload.get("patch"))
        if payload_patch:
            _exercise_patch(payload.get("doc", generated_doc), payload_patch)
        return

    payload_patch = coerce_patch(payload)
    if payload_patch:
        _exercise_patch(generated_doc, payload_patch)


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
