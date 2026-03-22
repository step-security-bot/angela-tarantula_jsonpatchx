"""Shared structured data generators for jsonpatchx fuzz targets."""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")

_MAX_STRING_LEN = 32
_MAX_ARRAY_ITEMS = 5
_MAX_OBJECT_ITEMS = 5

_STRING_EDGE_CASES: tuple[str, ...] = (
    "",
    "0",
    "-",
    "~",
    "~0",
    "~1",
    "a/b",
    "a~b",
    "../",
    "nul\\x00",
    "true",
    "false",
    "null",
)

_POINTER_TOKEN_EDGE_CASES: tuple[str, ...] = (
    "",
    "0",
    "00",
    "-",
    "~",
    "~0",
    "~1",
    "a/b",
    "a~b",
    "path",
    "array",
    "key",
)

_RFC6901_EDGE_PATHS: tuple[str, ...] = (
    "",
    "/",
    "/-",
    "/0",
    "/00",
    "/~0",
    "/~1",
    "/a~1b",
    "/a~0b",
    "/nested/key",
)

_DOT_EDGE_PATHS: tuple[str, ...] = (
    "",
    "root",
    "root.value",
    "arr.0",
    "arr.00",
    "arr.-1",
    "a..b",
    "x.y.z",
)


@dataclass(slots=True)
class ByteCursor:
    """Deterministic byte consumer for structured fuzz input generation."""

    data: bytes
    offset: int = 0

    @property
    def remaining(self) -> int:
        return max(0, len(self.data) - self.offset)

    def take(self, n: int) -> bytes:
        if n <= 0 or self.offset >= len(self.data):
            return b""
        end = min(len(self.data), self.offset + n)
        chunk = self.data[self.offset : end]
        self.offset = end
        return chunk

    def u8(self) -> int:
        chunk = self.take(1)
        return chunk[0] if chunk else 0

    def u32(self) -> int:
        chunk = self.take(4)
        if len(chunk) < 4:
            chunk = chunk.ljust(4, b"\x00")
        return int.from_bytes(chunk, byteorder="little", signed=False)

    def i32(self) -> int:
        chunk = self.take(4)
        if len(chunk) < 4:
            chunk = chunk.ljust(4, b"\x00")
        return int.from_bytes(chunk, byteorder="little", signed=True)

    def bool(self) -> bool:
        return bool(self.u8() & 1)

    def int_range(self, low: int, high: int) -> int:
        if low > high:
            raise ValueError("low must be <= high")
        span = high - low + 1
        return low + (self.u32() % span)

    def choose(self, values: tuple[T, ...]) -> T:
        if not values:
            raise ValueError("values cannot be empty")
        return values[self.u32() % len(values)]

    def take_bytes(self, max_len: int) -> bytes:
        if max_len <= 0:
            return b""
        length = self.int_range(0, max_len)
        return self.take(length)

    def take_text(self, max_len: int = _MAX_STRING_LEN) -> str:
        return self.take_bytes(max_len).decode("latin-1", errors="ignore")

    def finite_float(self) -> float:
        chunk = self.take(8)
        if len(chunk) < 8:
            return float(self.int_range(-1000, 1000))
        value = float(struct.unpack("<d", chunk)[0])
        if not math.isfinite(value):
            return float(self.int_range(-1000, 1000))
        return value


JSONLike = None | bool | int | float | str | list["JSONLike"] | dict[str, "JSONLike"]


def _random_string(cursor: ByteCursor) -> str:
    if cursor.bool():
        return cursor.choose(_STRING_EDGE_CASES)
    return cursor.take_text(_MAX_STRING_LEN)


def _random_object_key(cursor: ByteCursor, fallback_index: int) -> str:
    if cursor.bool():
        key = cursor.choose(_POINTER_TOKEN_EDGE_CASES)
    else:
        key = cursor.take_text(16)
    if key == "":
        return f"k{fallback_index}"
    return key


def random_json_value(
    cursor: ByteCursor, *, depth: int = 0, max_depth: int = 4
) -> JSONLike:
    """Generate a JSON-like value with bounded depth and size."""
    if depth >= max_depth:
        kind = cursor.int_range(0, 4)
    else:
        kind = cursor.int_range(0, 6)

    if kind == 0:
        return None
    if kind == 1:
        return cursor.bool()
    if kind == 2:
        return cursor.i32()
    if kind == 3:
        return cursor.finite_float()
    if kind == 4:
        return _random_string(cursor)
    if kind == 5:
        size = cursor.int_range(0, _MAX_ARRAY_ITEMS)
        return [
            random_json_value(cursor, depth=depth + 1, max_depth=max_depth)
            for _ in range(size)
        ]

    size = cursor.int_range(0, _MAX_OBJECT_ITEMS)
    result: dict[str, JSONLike] = {}
    for i in range(size):
        key = _random_object_key(cursor, i)
        result[key] = random_json_value(cursor, depth=depth + 1, max_depth=max_depth)
    return result


def escape_rfc6901_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def random_rfc6901_path(cursor: ByteCursor, *, max_tokens: int = 5) -> str:
    """Generate valid and invalid RFC6901-like paths."""
    if cursor.bool():
        return cursor.choose(_RFC6901_EDGE_PATHS)

    token_count = cursor.int_range(0, max_tokens)
    if token_count == 0:
        return "" if cursor.bool() else "/"

    rendered_tokens: list[str] = []
    for _ in range(token_count):
        if cursor.bool():
            token = cursor.choose(_POINTER_TOKEN_EDGE_CASES)
        else:
            token = cursor.take_text(12)

        # Mostly valid escaping, with occasional intentionally invalid raw tokens.
        if cursor.int_range(0, 9) == 0:
            rendered_tokens.append(token)
        else:
            rendered_tokens.append(escape_rfc6901_token(token))

    return "/" + "/".join(rendered_tokens)


def random_dot_path(cursor: ByteCursor, *, max_tokens: int = 5) -> str:
    """Generate valid and invalid dot-separated paths."""
    if cursor.bool():
        return cursor.choose(_DOT_EDGE_PATHS)

    token_count = cursor.int_range(0, max_tokens)
    if token_count == 0:
        return ""

    tokens: list[str] = []
    for _ in range(token_count):
        if cursor.bool():
            token = cursor.choose(_POINTER_TOKEN_EDGE_CASES)
        else:
            token = cursor.take_text(12)
        tokens.append(token)

    if cursor.int_range(0, 11) == 0:
        # Inject malformed empty segments occasionally.
        return ".".join(tokens[:1] + [""] + tokens[1:])

    return ".".join(tokens)


def coerce_patch(value: object, *, max_ops: int = 10) -> list[dict[str, object]] | None:
    """Coerce unknown payloads into list[dict[str, object]] for patch execution."""
    if not isinstance(value, list):
        return None

    patch: list[dict[str, object]] = []
    for raw_op in value[:max_ops]:
        if not isinstance(raw_op, dict):
            continue
        op: dict[str, object] = {}
        for key, item in raw_op.items():
            if isinstance(key, str):
                op[key] = item
        if op:
            patch.append(op)

    return patch or None
