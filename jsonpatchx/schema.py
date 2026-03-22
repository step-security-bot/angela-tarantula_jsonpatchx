from abc import ABC, abstractmethod
from typing import (
    ClassVar,
    Literal,
    Unpack,
    get_args,
    get_origin,
    get_type_hints,  # NOTE: For Py3.14+, this is enhanced for deferred annotations
    override,
)

from pydantic import BaseModel, ConfigDict, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema as cs

from jsonpatchx.exceptions import InvalidOperationDefinition
from jsonpatchx.types import JSONValue


class OperationSchema(BaseModel, ABC):
    """
    Base class for typed JSON Patch operations.

    An ``OperationSchema`` is a Pydantic model representing one JSON Patch operation:
    standard RFC 6902 operations (``add``/``remove``/``replace``/...) and custom domain operations.

    The library's workflow is:

    - Define operations as Pydantic models.
    - Register them in an ``OperationRegistry``.
    - Parse incoming patch documents into concrete operation instances via a discriminated union
      keyed by ``op``.
    - Apply operations sequentially by calling ``apply``.

    Example:
        Required ``op`` field:

        ``class ReplaceOp(OperationSchema):``
        ``    op: Literal["replace"] = "replace"``
        ``    path: JSONPointer[JSONValue]``
        ``    value: JSONValue``

        Multiple identifiers (aliases):

        ``class CreateOp(OperationSchema):``
        ``    op: Literal["create", "add"] = "create"``

    Notes:
        - ``op`` must be a normal annotated attribute, not a ``ClassVar``. ``ClassVar`` values are not
          Pydantic fields and cannot participate in discriminated-union dispatch.
        - Instances are frozen and strict by default.
        - Instances are revalidated when parsed, which matters for fields that depend on validation
          context (for example, registry-scoped pointer backends).
        - Subclasses are validated at class-definition time. If ``op`` is not declared correctly, the
          class raises ``InvalidOperationDefinition`` during import.
    """

    model_config = ConfigDict(
        frozen=True,  # Patch operations are not stateful
        strict=True,  # Flexible validation can still be provided per field as desired
        extra="allow",  # Standard JSON Patch allows extras
        validate_by_alias=True,  # Some JSON Patch keys are protected keywords in Python, such as 'from', and require aliases to bypass.
        serialize_by_alias=True,  # Consistent with validation
        loc_by_alias=True,  #  So error messages also use alias. For example, when 'from' is an alias of 'from_', errors should say, "error at: from".
        validate_default=True,  # Validate default values against their intended type annotations
        validate_return=True,  # For extra correctness. Also ensures that 'apply()' always results in valid JSON.
        use_enum_values=True,  # For consistent serialization when values are Enums
        allow_inf_nan=False,  # infinite values are not valid JSON
        validation_error_cause=False,  # Consider enabling when Pydantic guarantees a stable error structure. Useful to flip when debugging locally.
    )

    _op_literals: ClassVar[tuple[str, ...]]
    """
    Internal: cached tuple of string op identifiers declared by the subclass' ``op: Literal[...]``.

    This is populated during subclass creation and is used by OperationRegistry to build the mapping
    from operation name to schema type.
    """

    @override
    def __init_subclass__(cls, **kwargs: Unpack[ConfigDict]) -> None:
        """
        Hook that validates subclasses at definition time.

        Public subclasses normally do not need to call this directly. The base class ensures that
        every OperationSchema has a properly declared ``op`` field, and caches the allowed op
        identifiers for registry dispatch.
        """
        super().__init_subclass__(**kwargs)
        cls._op_literals = cls._get_op_literals()

    @classmethod
    def _get_op_literals(cls) -> tuple[str, ...]:
        """
        Internal: extract the string literal values from the subclass' ``op`` annotation.

        Supported forms:

        - ``op: Literal["add"]``
        - ``op: Literal["add", "create"]``

        Raises ``InvalidOperationDefinition`` if the subclass does not declare a valid ``Literal[str, ...]``
        annotation for ``op``.
        """
        if (
            (annotations := get_type_hints(cls, include_extras=True))
            and (op_annotation := annotations.get("op"))
            and (get_origin(op_annotation) is Literal)
            and (op_literals := get_args(op_annotation))
            and all(isinstance(v, str) for v in op_literals)
        ):
            return op_literals
        else:
            raise InvalidOperationDefinition(
                f"OperationSchema '{cls.__name__}' is missing valid type hints for required 'op' field. "
                "'op' must be an instance field annotated as a Literal[...] of strings."
            )

    @abstractmethod
    def apply(self, doc: JSONValue) -> JSONValue:
        """
        Apply this operation to ``doc`` and return the updated document.

        Notes:
            - Implementations may mutate the provided ``doc`` object in-place and should return the
              updated document (often the same object).
            - Raise ``PatchError`` subclasses for expected patch failures. Unexpected exceptions will
              be wrapped by the patch engine.
            - Whether the caller-owned document is mutated is controlled by the patch engine
              (see ``_apply_ops(..., inplace=...)``), not by this method.
        """

    @classmethod
    @override
    def __get_pydantic_json_schema__(
        cls, schema: cs.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(schema)

        # Allow users to set "op" defaults, but tell OpenAPI it's required
        required = set(json_schema.get("required", []))
        required.add("op")
        json_schema["required"] = sorted(required)

        # Add description to 'op' for consistency across models
        json_schema["properties"]["op"].setdefault(
            "description", "The operation to perform."
        )
        return json_schema
