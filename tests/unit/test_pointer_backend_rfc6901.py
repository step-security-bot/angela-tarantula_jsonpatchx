from operator import attrgetter
from typing import Final, Self

import pytest
from jsonpath import JSONPointer as CustomJsonPointer
from pydantic import BaseModel, model_validator

from jsonpatchx import JSONPointer


class URIJsonPointer(CustomJsonPointer):
    # NOTE: investigate functools.partial feasibility
    # Then make a test for partial compatibility, but remove this URIJsonPointer test
    # since it's not RFC 6901 related, and this URIJsonPointer fails the last 3 cases of POINTER_CASES.
    def __init__(self, pointer) -> None:
        super().__init__(pointer, uri_decode=True, unicode_escape=False)


MISSING = "__MISSING__"


class Case(BaseModel):
    pointer: str
    expected: object = MISSING
    fail: str = MISSING

    @model_validator(mode="after")
    def _ensure_expected_or_fail(self) -> Self:
        if self.expected == MISSING and self.fail == MISSING:
            raise ValueError("case must include expected or set fail message")
        return self

    @property
    def id(self) -> str:
        return self.fail if self.fail != MISSING else repr(self.expected)


DOC: Final = {
    "arr": ["array-item-1", "array-item-2"],
    "": "empty-key",
    "slash/key": "has-slash",
    "tilde~key": "has-tilde",
    "space key": "has-space",
    'quote"key': "has-quote",
    r"backsl\ash": "has-backslash",
    "pct%key": "has-percent",
    "caret^key": "has-caret",
    "pipe|key": "has-pipe",
    r"tab\tkey": "has-tab",
}

# Core RFC 6901 semantics
POINTER_CASES = [
    Case(pointer="", expected=DOC),
    Case(pointer="/arr", expected=["array-item-1", "array-item-2"]),
    Case(pointer="/arr/", fail="invalid pointer"),
    Case(pointer="/nope", fail="missing key"),
    Case(pointer="/pct%key/0", fail="strings are not indexable"),
    Case(pointer="/slash~1key/x", fail="missing key"),
    Case(pointer="/arr/0", expected="array-item-1"),
    Case(pointer="/arr/00", fail="invalid index"),
    Case(pointer="/arr/01", fail="invalid index"),
    Case(pointer="/arr/1", expected="array-item-2"),
    Case(pointer="/arr/2", fail="index out of range"),
    Case(pointer="/arr/-1", fail="invalid index"),
    Case(pointer="/arr/nope", fail="invalid index"),
    Case(pointer="/", expected="empty-key"),
    Case(pointer="/slash~1key", expected="has-slash"),
    Case(pointer="/tilde~0key", expected="has-tilde"),
    Case(pointer="/tilde~2key", fail="invalid escape"),
    Case(pointer="/space key", expected="has-space"),
    Case(pointer='/quote"key', expected="has-quote"),
    Case(pointer="/backsl\\ash", expected="has-backslash"),
    Case(pointer="/tab\\tkey", expected="has-tab"),
    Case(pointer="/pct%key", expected="has-percent"),
    Case(pointer="/caret^key", expected="has-caret"),
    Case(pointer="/pipe|key", expected="has-pipe"),
    Case(pointer="/~arr", fail="non-standard selector"),
    Case(pointer="/#arr", fail="non-standard selector"),
    Case(pointer="/arr/#1", fail="non-standard selector"),
]


URI_CASES: Final = [
    Case(pointer="/space%20key", expected="has-space"),
    Case(pointer="/quote%22key", expected="has-quote"),
    Case(pointer="/backsl%5Cash", expected="has-backslash"),
    Case(pointer="/pct%25key", expected="has-percent"),
    Case(pointer="/caret%5Ekey", expected="has-caret"),
    Case(pointer="/pipe%7Ckey", expected="has-pipe"),
]


@pytest.mark.parametrize("case", POINTER_CASES, ids=attrgetter("id"))
def test_json_pointer_core(case: Case) -> None:
    if case.fail == MISSING:
        ptr = JSONPointer.parse(case.pointer)
        assert ptr.get(DOC) == case.expected
    else:
        with pytest.raises(Exception):
            ptr = JSONPointer.parse(case.pointer)
            print(ptr.get(DOC))


@pytest.mark.parametrize("case", URI_CASES, ids=attrgetter("id"))
def test_json_pointer_with_uri_decoding(case: Case) -> None:
    if case.fail == MISSING:
        ptr = JSONPointer.parse(case.pointer, backend=URIJsonPointer)
        assert ptr.get(DOC) == case.expected
    else:
        with pytest.raises(Exception):
            ptr = JSONPointer.parse(case.pointer, backend=URIJsonPointer)
            print(ptr.get(DOC))
