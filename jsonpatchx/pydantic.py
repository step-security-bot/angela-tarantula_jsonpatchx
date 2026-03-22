from __future__ import annotations

from inspect import isclass
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    Generic,
    Literal,
    TypeAliasType,
    cast,
    get_args,
    get_origin,
    overload,
    override,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    ValidationError,
    create_model,
)
from pydantic_core import PydanticUndefined, PydanticUndefinedType
from typing_extensions import TypeVar

from jsonpatchx.exceptions import PatchValidationError
from jsonpatchx.registry import _RegistrySpec
from jsonpatchx.schema import OperationSchema
from jsonpatchx.standard import _apply_ops
from jsonpatchx.types import JSONValue, _validate_JSONValue


class _RegistryBoundPatchRoot(RootModel[Any]):
    """
    Internal base for registry-backed JSON Patch RootModels.

    Notes:
        - ``root`` is a JSON Patch document: ``list[registry.union_type]`` built dynamically via
          ``create_model``.
        - ``__registry__`` is set on subclasses.
    """

    # Choice: This base intentionally uses RootModel[Any].
    # Why: The concrete root type (list[registry.union]) is supplied dynamically
    #      by factories via create_model(). Making this generic would either lie
    #      to the type checker or require pervasive casting with no real benefit.
    #      (``registry.union_type`` in current implementation.)

    model_config = ConfigDict(frozen=True, strict=True)

    __registry__: ClassVar[_RegistrySpec | PydanticUndefinedType] = PydanticUndefined

    @property
    def ops(self) -> list[OperationSchema]:
        # Assumption: subclasses will set root to list[registry.union_type]
        return cast(list[OperationSchema], self.root)


ModelT = TypeVar("ModelT", bound=BaseModel)


class _BasePatchModel(_RegistryBoundPatchRoot, Generic[ModelT]):
    """
    Internal patch RootModel for model-aware patching (Pydantic BaseModel targets).

    Notes:
        - ``apply(target)`` patches ``target.model_dump()`` using the shared engine.
        - The patched output is validated back into ``__target_model__`` via ``model_validate``.
        - The input model instance is not mutated.
    """

    # Normally, ClassVars can't be generic (https://github.com/python/typing/discussions/1424#discussioncomment-7989934)
    # But in this case, the _BasePatchModel class is never used directly. It is just a __base__ for create_model,
    # where each subclass is tied a a single type[ModelT].
    __target_model__: ClassVar[type[ModelT]]

    def apply(self, target: ModelT) -> ModelT:
        if not isinstance(target, BaseModel):
            raise TypeError(
                f"{self.__class__.__name__}.apply() expects a Pydantic BaseModel instance, "
                f"got {type(target).__name__}"
            )
        try:
            data = _validate_JSONValue(target.model_dump())
        except Exception as e:
            raise PatchValidationError(
                f"Target model produced non-JSON data for patching: {e}"
            ) from e
        patched = _apply_ops(self.ops, data, inplace=True)
        try:
            return self.__target_model__.model_validate(patched)
        except ValidationError as e:
            raise PatchValidationError(
                f"Patched data failed validation for {self.__target_model__.__name__}: {e}"
            ) from e


class _BasePatchBody(_RegistryBoundPatchRoot):
    """
    Internal patch RootModel for typed operations applied to an untyped JSON document.

    Notes:
        - ``apply(doc, inplace=...)`` delegates to ``_apply_ops`` (engine defines copy and mutation semantics).
    """

    def apply(
        self,
        doc: JSONValue,
        *,
        inplace: bool = False,
    ) -> JSONValue:
        try:
            _validate_JSONValue(doc)
        except Exception as e:
            raise PatchValidationError(f"Invalid JSON document: {e}") from e
        return _apply_ops(self.ops, doc, inplace=inplace)


TargetT = TypeVar("TargetT", bound=BaseModel | str)
RegistryT = TypeVar("RegistryT", bound=OperationSchema)


def _coerce_schema_name(target: object) -> str | None:
    # Limitation: target is either str or Literal["..."]
    if isinstance(target, str):
        return target
    origin = get_origin(target)
    if origin is Literal:
        args = get_args(target)
        if len(args) == 1 and isinstance(args[0], str):
            return args[0]
    return None


class JsonPatchFor(_RegistryBoundPatchRoot, Generic[TargetT, RegistryT]):
    """
    Factory for creating typed JSON Patch models bound to a registry declaration.

    ``JsonPatchFor[Target, Registry]`` produces a patch model.
    ``Target`` is either a Pydantic model or a string name for JSON documents.
    ``Registry`` is a union of concrete OperationSchemas (``OpA | OpB | ...``).
    """

    if TYPE_CHECKING:
        # At runtime, JsonPatchFor[X] returns either a _BasePatchBody or a BasePatchModel, each with their own apply().
        # Tell type checkers that JsonPatchFor[X] has an apply() to expose this.

        @overload
        def apply[TargetModelM: BaseModel](
            self: JsonPatchFor[TargetModelM, RegistryT], target: TargetModelM
        ) -> TargetModelM:
            """
            Apply this patch to ``target`` and return the patched Model.

            Args:
                target: The target BaseModel.

            Returns:
                patched: The patched BaseModel.

            Raises:
                PatchValidationError: Patched data fails validation for the target model.
                PatchError: Any patch-domain error raised by operations, including conflicts.
                    ``PatchInternalError`` is a ``PatchError`` raised for unexpected failures.
            """
            ...

        @overload
        def apply[TargetNameN: str](
            self: JsonPatchFor[TargetNameN, RegistryT],
            doc: JSONValue,
            *,
            inplace: bool = False,
        ) -> JSONValue:
            """
            Apply this patch to ``doc`` and return the patched document.

            Args:
                doc: The target JSON document.
                inplace: Controls whether ``doc`` is deep-copied before application.

            Return:
                patched: The patched JSON document.

            Raises:
                ValidationError: If the input is not a mutable ``JSONValue``.
                PatchError: Any patch-domain error raised by operations, including conflicts.
                    ``PatchInternalError`` is a ``PatchError`` raised for unexpected failures.
            """
            ...

        def apply(self, *args: Any, **kwargs: Any) -> Any:
            """
            Apply a JSON Patch document.

            Raises:
                TypeError: Model variant expects a Pydantic BaseModel instance.
                ValidationError: If the input is not a mutable ``JSONValue``.
                PatchValidationError: Patched data fails validation for the target model.
                PatchError: Any patch-domain error raised by operations, including conflicts.
                    ``PatchInternalError`` is a ``PatchError`` raised for unexpected failures.
            """
            ...

    @override
    def __class_getitem__(cls, params: object) -> type[_RegistryBoundPatchRoot]:
        if not isinstance(params, tuple) or len(params) != 2:
            raise TypeError(
                "JsonPatchFor expects JsonPatchFor[Target, Registry] where "
                "Target is a BaseModel subclass or schema name string and "
                "Registry is a union of concrete OperationSchemas. "
                f"Got: {params!r}."
            )

        target, registry = params
        registry = _RegistrySpec.from_typeform(registry)

        schema_name = _coerce_schema_name(target)
        if schema_name is not None:
            return cls._create_json_patch_body(schema_name, registry)

        if not isclass(target) or not issubclass(target, BaseModel):
            raise TypeError(
                "JsonPatchFor[...] expects a Pydantic BaseModel subclass or schema name string, "
                f"got {target!r}"
            )

        return cls._create_model_patch_body(target, registry)

    @staticmethod
    def _create_json_patch_body(
        schema_name: str,
        registry: _RegistrySpec,
    ) -> type[_BasePatchBody]:
        BodyPatchOperation = TypeAliasType(  # type: ignore[misc]
            f"{schema_name}PatchOperation",
            Annotated[
                registry.union_type,
                Field(
                    title=f"{schema_name} Patch Operation",
                    description=(
                        f"Discriminated union of patch operations for {schema_name}."
                    ),
                ),
            ],
        )  # NOTE: can't use type keyword because otherwise OpenAPI title binds to "BodyPatchOperation" instead

        PatchBody = create_model(
            f"{schema_name}PatchRequest",
            __base__=_BasePatchBody,
            __config__=ConfigDict(
                title=f"{schema_name} Patch Request",
                json_schema_extra={
                    "description": f"Array of patch operations for {schema_name}.",
                },
            ),
            root=(list[BodyPatchOperation], ...),  # type: ignore[valid-type]
        )

        PatchBody.__registry__ = registry
        PatchBody.__doc__ = (
            f"Discriminated union of patch operations for {schema_name}."
        )
        return PatchBody

    @staticmethod
    def _create_model_patch_body(
        model: type[ModelT],
        registry: _RegistrySpec,
    ) -> type[_BasePatchModel[ModelT]]:
        ModelPatchOperation = TypeAliasType(  # type: ignore[misc]
            f"{model.__name__}PatchOperation",
            Annotated[
                registry.union_type,
                Field(
                    title=f"{model.__name__} Patch Operation",
                    description=f"Discriminated union of patch operations for {model.__name__}.",
                ),
            ],
        )  # NOTE: can't use type keyword because otherwise OpenAPI title binds to "ModelPatchOperation" instead

        PatchModel = create_model(
            f"{model.__name__}PatchRequest",
            __base__=_BasePatchModel,
            __config__=ConfigDict(
                title=f"{model.__name__} Patch Request",
                json_schema_extra={
                    "description": (
                        f"Array of patch operations for {model.__name__}. "
                        "Applied to model_dump() and re-validated against the model schema."
                    ),
                    "x-target-model": model.__name__,
                },
            ),
            root=(list[ModelPatchOperation], ...),  # type: ignore[valid-type]
        )

        PatchModel.__target_model__ = model
        PatchModel.__registry__ = registry
        PatchModel.__doc__ = f"Array of patch operations for {model.__name__}."
        return PatchModel
