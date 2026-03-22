from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Annotated, Any, cast, get_args

from pydantic import Field, TypeAdapter
from pydantic_core import core_schema
from typing_extensions import TypeForm, TypeIs

from jsonpatchx.exceptions import InvalidJSONPointer

# TypeAdapter helpers


@lru_cache(maxsize=512)
def _cached_type_adapter[T](expected: TypeForm[T]) -> TypeAdapter[T]:
    # https://docs.pydantic.dev/latest/concepts/performance/#typeadapter-instantiated-once
    return TypeAdapter(expected)


def _type_adapter_for[T](expected: TypeForm[T]) -> TypeAdapter[T]:
    """
    Internal: return a (usually cached) Pydantic TypeAdapter for a TypeForm.

    JSONPointer uses adapters at apply-time to validate that the resolved target
    conforms to the pointer's type parameter.

    Adapters are cached for performance when possible. Unhashable TypeForms are supported
    but cannot be cached.
    """
    try:
        try:
            return _cached_type_adapter(expected)  # type: ignore[arg-type]
        except TypeError:
            # Choice: Don't forbid unhashable typeforms, but don't break an arm supporting them either.
            # Why: Most TypeForms are hashable, even Annotated[int, json_schema_extra={"dict here": "still hashable"})].
            #      It's really just cases like Annotated[int, {"dict":"unhashable"}] that are too rare to support for now.
            return TypeAdapter(expected)
    except Exception as e:
        raise InvalidJSONPointer(
            f"Invalid type parameter for JSON Pointer: {expected!r}. Cannot create TypeAdapter. Did you implement __get_pydantic_core_schema__?"
        ) from e


# Pydantic-aware JSON types (type-checking aliases + runtime classes)


def _strict_validator(typeform: TypeForm[Any]) -> core_schema.CoreSchema:
    """
    Build a strict validator for a TypeForm using a cached TypeAdapter.

    This is used to keep validation strict while avoiding automatic OpenAPI
    component generation for internal helper types (e.g., JSONValue internals).
    """
    adapter = _type_adapter_for(typeform)

    def _validate(value: object) -> object:
        return adapter.validate_python(value, strict=True)

    return core_schema.no_info_plain_validator_function(_validate)


if TYPE_CHECKING:
    type JSONBoolean = bool
    type JSONNumber = int | float
    type JSONString = str
    type JSONNull = None
    type JSONArray[T] = list[T]
    type JSONObject[T] = dict[str, T]
else:

    class JSONBoolean:
        @classmethod
        def __get_pydantic_core_schema__(
            cls, _source_type: object, _handler: core_schema.GetCoreSchemaHandler
        ) -> core_schema.CoreSchema:
            return _strict_validator(Annotated[bool, Field(strict=True)])

        @classmethod
        def __get_pydantic_json_schema__(
            cls,
            _core_schema: core_schema.CoreSchema,
            _handler: core_schema.GetJsonSchemaHandler,
        ) -> dict[str, object]:
            return {"type": "boolean"}

    class JSONNumber:
        @classmethod
        def __get_pydantic_core_schema__(
            cls, _source_type: object, _handler: core_schema.GetCoreSchemaHandler
        ) -> core_schema.CoreSchema:
            type _JSONNumberInternal = Annotated[  # NOTE: document the necessity of field strictness. adapters strict too for preventing "2" -> 2 for JSONBoolean and int/float
                Annotated[int, Field(strict=True)]
                | Annotated[float, Field(strict=True, allow_inf_nan=False)],
                Field(
                    description="integer or finite float (no NaN/Infinity).",
                ),
            ]
            return _strict_validator(_JSONNumberInternal)

        @classmethod
        def __get_pydantic_json_schema__(
            cls,
            _core_schema: core_schema.CoreSchema,
            _handler: core_schema.GetJsonSchemaHandler,
        ) -> dict[str, object]:
            return {"type": "number"}

    class JSONString:
        @classmethod
        def __get_pydantic_core_schema__(
            cls, _source_type: object, _handler: core_schema.GetCoreSchemaHandler
        ) -> core_schema.CoreSchema:
            return _strict_validator(Annotated[str, Field(strict=True)])

        @classmethod
        def __get_pydantic_json_schema__(
            cls,
            _core_schema: core_schema.CoreSchema,
            _handler: core_schema.GetJsonSchemaHandler,
        ) -> dict[str, object]:
            return {"type": "string"}

    class JSONNull:
        @classmethod
        def __get_pydantic_core_schema__(
            cls, _source_type: object, _handler: core_schema.GetCoreSchemaHandler
        ) -> core_schema.CoreSchema:
            return _strict_validator(Annotated[None, Field()])

        @classmethod
        def __get_pydantic_json_schema__(
            cls,
            _core_schema: core_schema.CoreSchema,
            _handler: core_schema.GetJsonSchemaHandler,
        ) -> dict[str, object]:
            return {"type": "null"}

    class JSONArray[T]:
        @classmethod
        def __get_pydantic_core_schema__(
            cls, source_type: object, handler: core_schema.GetCoreSchemaHandler
        ) -> core_schema.CoreSchema:
            (item_type,) = get_args(source_type) or (Any,)
            item_schema = handler.generate_schema(item_type)
            return core_schema.list_schema(item_schema, strict=True)

        @classmethod
        def __get_pydantic_json_schema__(
            cls,
            _core_schema: core_schema.CoreSchema,
            handler: core_schema.GetJsonSchemaHandler,
        ) -> dict[str, object]:
            return handler(_core_schema)

    class JSONObject[T]:
        @classmethod
        def __get_pydantic_core_schema__(
            cls, source_type: object, handler: core_schema.GetCoreSchemaHandler
        ) -> core_schema.CoreSchema:
            (value_type,) = get_args(source_type) or (Any,)
            value_schema = handler.generate_schema(value_type)
            return core_schema.dict_schema(
                core_schema.str_schema(), value_schema, strict=True
            )

        @classmethod
        def __get_pydantic_json_schema__(
            cls,
            _core_schema: core_schema.CoreSchema,
            handler: core_schema.GetJsonSchemaHandler,
        ) -> dict[str, object]:
            return handler(_core_schema)


type JSONScalar = JSONBoolean | JSONNumber | JSONString | JSONNull
type JSONContainer[T] = JSONArray[T] | JSONObject[T]

# type-narrowing helpers
# NOTE: consider making public type-narrowing helpers


def _is_container(value: JSONValue) -> TypeIs[JSONContainer[JSONValue]]:
    """Internal: runtime check for JSON containers (dict/list)."""
    return isinstance(value, (list, dict))


def _is_object(value: JSONValue) -> TypeIs[JSONObject[JSONValue]]:
    return isinstance(value, dict)


def _is_array(value: JSONValue) -> TypeIs[JSONArray[JSONValue]]:
    return isinstance(value, list)


if TYPE_CHECKING:
    # Static typing: keep JSONValue as a strict JSON union.
    type JSONValue = Annotated[
        JSONScalar | JSONContainer[JSONValue],
        Field(),
    ]  # NOTE: document somewhere that you can't do isinstance because these are type aliases
    """
    Pydantic-friendly type representing a strict JSON value.

    Notes:
        - The standard JSON Patch operation schemas use it for ``value`` fields.
        - ``JSONPointer`` uses it as the document type for ``get``/``add``/``remove``.
        - Patch application helpers can optionally validate that inputs are legitimate JSON.
        - Containers are restricted to ``list`` and ``dict[str, ...]``.
        - Numeric values are restricted to ``int`` or finite ``float`` (no NaN/Infinity).
        - Pydantic validation is strict (no implicit coercions).
    """
else:

    class JSONValue:
        """
        Runtime JSON value type with strict validation and minimal OpenAPI schema.

        Validation delegates to the strict JSON union, while
        JSON schema is deliberately inlined as ``{}`` to avoid a named component.
        """

        @classmethod
        def __get_pydantic_core_schema__(
            cls, _source_type: object, _handler: core_schema.GetCoreSchemaHandler
        ) -> core_schema.CoreSchema:
            type _JSONValueInternal = Annotated[
                JSONBoolean
                | JSONNumber
                | JSONString
                | JSONNull
                | JSONArray[_JSONValueInternal]
                | JSONObject[_JSONValueInternal],
                Field(),
            ]
            return _strict_validator(_JSONValueInternal)

        @classmethod
        def __get_pydantic_json_schema__(
            cls,
            _core_schema: core_schema.CoreSchema,
            _handler: core_schema.GetJsonSchemaHandler,
        ) -> dict[str, object]:
            return {}


def _validate_JSONValue(obj: object) -> JSONValue:
    return _type_adapter_for(JSONValue).validate_python(obj, strict=True)


def _validate_typeform(unverified: object) -> TypeForm[Any]:
    """Validate a TypeForm parameter."""  # NOTE: move to JSONPointer if it's gonna raise InvalidJSONPointer
    try:
        _type_adapter_for(unverified)  # type: ignore[arg-type]
    except Exception as e:
        raise InvalidJSONPointer(
            f"JSONPointer type parameter {unverified!r} must be a valid TypeForm"
        ) from e
    return cast(TypeForm[Any], unverified)


type JSONBound = (
    JSONScalar | JSONContainer[Any]
)  # Bound for all recursively JSON-ish types.
# Use it like ``T = TypeVar("T", default=JSONValue, bound=JSONBound)``

# NOTE: Ideally we'd accept JSON containers parameterized by *any* JSON element type:
#   type JSONBound = JSONScalar | JSONContainer[T]  where  T <: JSONValue
# This is an existential ("there exists some T") constraint. Writing
#   type JSONBound = JSONScalar | JSONContainer[JSONValue]
# is too narrow when JSONContainer is invariant (e.g., mutable), because it would reject
# JSONContainer[JSONNumber], etc.
#
# Python typing can't currently express this existential constraint for invariant recursive
# containers in type aliases/annotations, so we use `Any` in the container branch as a
# pragmatic approximation. (Consequence: static checkers may not reject non-JSON element
# types inside containers.)
#
# My proposed syntax (not supported today):
#   type JSONBound = JSONScalar | JSONContainer[T: JSONValue]
