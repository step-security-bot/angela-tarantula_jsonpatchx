from collections.abc import Sequence
from functools import partial
from inspect import isabstract
from typing import (
    Any,
    Generic,
    Self,
    assert_never,
    cast,
    final,
    get_args,
    override,
)

from pydantic import (
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
    TypeAdapter,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema as cs
from typing_extensions import TypeForm, TypeVar

from jsonpatchx.backend import (
    _DEFAULT_POINTER_CLS,
    PointerBackend,
    TargetState,
    _is_root_ptr,
    _parent_ptr_of,
    _pointer_backend_instance,
    classify_state,
)
from jsonpatchx.exceptions import (
    InvalidJSONPointer,
    PatchConflictError,
)
from jsonpatchx.types import (
    JSONArray,
    JSONBound,
    JSONContainer,
    JSONObject,
    JSONValue,
    _is_array,
    _is_container,
    _is_object,
    _type_adapter_for,
    _validate_JSONValue,
    _validate_typeform,
)

_Nothing = object()
# NOTE: maybe add pydantic_core.MISSING to JSONPointer.get() on failure


T_co = TypeVar("T_co", bound=JSONBound, covariant=True)
P_co = TypeVar(
    "P_co", bound=PointerBackend, covariant=True, default=_DEFAULT_POINTER_CLS
)


@final
class JSONPointer(str, Generic[T_co, P_co]):
    """
    A typed RFC 6901 JSON Pointer with Pydantic integration.

    ``JSONPointer[T]`` (or ``JSONPointer[T, Backend]``) is a string-like value (subclasses ``str``)
    that additionally:

    - stores a parsed pointer backend (see ``PointerBackend``),
    - tracks a covariant type parameter ``T`` used to validate resolved targets,
    - provides convenience methods used by patch operations: ``get``, ``add``, ``remove``.

    ## Important design semantics (intentional)

    **Typed pointers are enforced at runtime.**
    The type parameter ``T`` is not “just typing”; it is enforced whenever a value is read
    through the pointer.

    - ``get(doc)`` always validates the resolved value against ``T``.
    - ``add(doc, value)`` optionally validates the written value against ``T`` (default: True).
    - ``remove(doc)`` is intentionally *type-gated*: it first “reads” the target through the pointer,
      so removal can fail if the current value is not of type ``T``.

    This makes patch semantics explicit:
    - ``JSONPointer[JSONValue]`` is permissive (“remove anything JSON”).
    - ``JSONPointer[JSONBoolean]`` is restrictive (“remove only if it is currently a boolean”).
    - If you want to remove regardless of the current type, use a wider pointer type (e.g. ``JSONValue``)
      or define a dedicated permissive remove operation.

    **Pointer covariance is intentional.**
    ``JSONPointer`` is covariant in ``T``. In practice this means you can often reuse a pointer instance
    (including across composed operations) and preserve stricter guarantees.
    Example: if a custom op carries a ``JSONPointer[JSONBoolean]``, composing that op internally
    using ``AddOp`` should keep the boolean-specific enforcement at runtime.

    ## Backend semantics (advanced)

    - Default backend: ``jsonpointer.JsonPointer``.
    - Custom backend: bound directly via ``JSONPointer[T, Backend]``.
    - Invalid pointer strings raise ``InvalidJSONPointer``.
    - Backend traversal failures in ``get``/``add``/``remove`` are normalized into
      ``PatchConflictError``.

    Mutation semantics:
    - ``add`` and ``remove`` may mutate the document object they are given (or containers reachable
      from it). The root pointer ``""`` is the exception: setting the root returns a new document
      value rather than mutating an existing container. Removing the root sets it to JSONNull (None)
      so that all standard operations are closed over JSONValue. If you want to forbid root removal,
      it's easy to make a custom op!
    - Whether these mutations affect the original caller-owned document is determined by the patch
      engine (see ``_apply_ops(..., inplace=...)``), which may deep-copy the input document.

    ``JSONPointer`` values are intended to be created by Pydantic validation. Direct instantiation
    is not permitted (except when running as ``__main__`` for debugging).
    """

    # Choice: JSONPointer is str subclass, as opposed to Annotated[str, StringConstraints(...)].
    # Why: Cache adapters and pointers where possible, and provide simple primitives like get/add
    #      out-of-the-box, owned by the field, so path.get(doc) just works. Most users don't need
    #      more advanced functionality, so don't require them to reason about the PointerBackend API.
    # Considered: From a mutation point of view, consider reversing ownership to something like doc.get(path).
    #             Downside would be maintaining a JSONDocument wrapper around JSONValues, and taking power
    #             away from the PointerBackend implementation, which should really own the mutation logic.
    # Also considered: Performance drawback (https://docs.pydantic.dev/latest/concepts/performance/?utm_source=chatgpt.com#avoid-extra-information-via-subclasses-of-primitives).
    #                  I may replace str inheritance with a str property that derives from str(self._ptr).
    #                  But I like the idea that users think of JSONPointer[T] as the path string with extra abilities.

    __slots__ = ("_ptr", "_type")

    _ptr: P_co
    _type: TypeForm[T_co]

    @property
    def ptr(self) -> P_co:
        """
        The underlying pointer backend instance.

        This is exposed for advanced users who provide a custom PointerBackend with additional APIs.
        The patch engine relies only on the ``PointerBackend`` protocol.
        """
        # TODO: Somehow 'Any' to the actual JSON Pointer class they pass in.
        # Choice: expose ptr as the user's custom PointerBackend for stronger type inferencing.
        # Why: This library only needs the PointerBackend Protocol, if some users want a custom
        #      PointerBackend, then expose that richer API to those users at type-checker time.
        return self._ptr

    @property
    def parts(self) -> Sequence[str]:
        """A sequence of RFC6901-unescaped pointer components."""
        return self._ptr.parts

    @property
    def type_param(self) -> TypeForm[T_co]:
        """The expected type parameter ``T`` used to validate resolved targets."""
        return self._type

    @property
    def _adapter(self) -> TypeAdapter[T_co]:
        return _type_adapter_for(self._type)

    @property
    def parent_ptr(self) -> P_co:  # NOTE: add parent property for JSONPointer of parent
        # NOTE: make this public
        return _parent_ptr_of(self._ptr)

    def is_root(self, doc: JSONValue) -> bool:
        """Check whether this JSONPointer's target is the root."""
        return _is_root_ptr(self._ptr, doc)

    @classmethod
    def _validator(
        cls,
        path: str | PointerBackend,
        *,
        type_param: TypeForm[Any],
        concrete_backend: type[PointerBackend] | TypeVar,
    ) -> Self:
        """
        Validator function for JSONPointer.

        Assumes ``type_param`` and ``bound_backend`` are already validated.
        """
        resolved_backend = cls._resolve_runtime_backend_param(concrete_backend)
        if isinstance(path, JSONPointer):
            path_str = str(path)
            if resolved_backend is _DEFAULT_POINTER_CLS:
                ptr = path._ptr
            elif isinstance(path._ptr, resolved_backend):
                ptr = path._ptr
            else:
                ptr = _pointer_backend_instance(path_str, pointer_cls=resolved_backend)
        elif isinstance(path, str):
            path_str = path
            ptr = _pointer_backend_instance(
                path_str,
                pointer_cls=resolved_backend,
            )
        elif isinstance(path, PointerBackend):
            if isinstance(path, resolved_backend):
                path_str = str(path)
                ptr = path
            else:
                raise InvalidJSONPointer(
                    "JSONPointer backend mismatch: "
                    f"required backend is {resolved_backend.__name__} but field uses "
                    f"{path.__class__.__name__}"
                )
        else:  # pragma: no cover
            assert_never(path)

        # Build it
        obj: Self = str.__new__(cls, path_str)

        # Try to reuse the type parameters (type checkers already enforce covariance)
        if isinstance(path, JSONPointer):
            obj._type = path._type
        else:
            obj._type = type_param

        # Reuse pointer backends when provided directly or via JSONPointer.
        obj._ptr = cast(P_co, ptr)

        return obj

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: type[Self], handler: GetCoreSchemaHandler
    ) -> cs.CoreSchema:
        type_param, concrete_backend = cls._parse_pointer_type_args(
            *get_args(source_type)
        )
        validator_function = partial(
            cls._validator,
            type_param=type_param,
            concrete_backend=concrete_backend,
        )
        return cs.no_info_after_validator_function(
            function=validator_function,
            schema=cs.union_schema(
                [
                    cs.is_instance_schema(JSONPointer),
                    cs.str_schema(strict=True),
                    cs.is_instance_schema(PointerBackend),
                ]
            ),
            metadata={  # wire to the json_schema
                "type_param": type_param,
                "pointer_backend_param": concrete_backend,  # NOTE: enable customization
            },
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: cs.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        pointer_backend_param = schema["metadata"]["pointer_backend_param"]
        if isinstance(pointer_backend_param, TypeVar):
            pointer_backend = cls._resolve_runtime_backend_param(pointer_backend_param)
        else:
            pointer_backend = pointer_backend_param
        if pointer_backend is _DEFAULT_POINTER_CLS:
            pointer_format = "json-pointer"
            pointer_description = "JSON Pointer (RFC 6901) string"
        else:
            pointer_format = "x-json-pointer"
            pointer_description = "JSON Pointer string (custom backend syntax)"

        json_schema = handler(schema)
        json_schema.update(
            {
                "type": "string",
                "format": pointer_format,
                "description": pointer_description,  # NOTE: let it be overridable
            }
        )

        # enrich with json schema of type param
        type_param = schema["metadata"]["type_param"]
        json_schema["x-pointer-type-schema"] = _type_adapter_for(
            type_param
        ).json_schema()
        return json_schema

    @classmethod
    def _parse_pointer_type_args(
        cls, *args: TypeForm[Any]
    ) -> tuple[TypeForm[Any], type[PointerBackend] | TypeVar]:
        """Validate the JSONPointer's parameter tuple, e.g. ``(JSONValue, DotPointer)`` for ``JSONPointer[JSONValue, DotPointer]``."""
        if not args:
            raise TypeError(f"{cls} requires at least one type parameter")
        unverified_typeform = args[0]
        unverified_bound_backend = args[1] if len(args) > 1 else _DEFAULT_POINTER_CLS

        backend_param = cls._resolve_backend_type_param(unverified_bound_backend)
        type_param = _validate_typeform(unverified_typeform)

        return type_param, backend_param

    @staticmethod
    def _resolve_backend_type_param(
        backend_param: object,
    ) -> type[PointerBackend] | TypeVar:
        if isinstance(backend_param, TypeVar):
            return backend_param
        if not isinstance(backend_param, type):
            raise InvalidJSONPointer(
                f"JSONPointer backend parameter {backend_param!r} must be a class or TypeVar"
            )
        return cast(type[PointerBackend], backend_param)

    @classmethod
    def _resolve_runtime_backend_param(
        cls,
        backend_param: type[PointerBackend] | TypeVar,
    ) -> type[PointerBackend]:
        if not isinstance(backend_param, TypeVar):
            return backend_param
        return cls._resolve_runtime_backend_typevar(backend_param)

    @classmethod
    def _resolve_runtime_backend_typevar(
        cls,
        backend_typevar: TypeVar,
    ) -> type[PointerBackend]:
        # Only TypeVar defaults are used for unspecialized backend TypeVars.
        try:
            has_default = backend_typevar.has_default()
        except AttributeError:  # Py3.12
            has_default = False
        if has_default:
            default_candidate = getattr(backend_typevar, "__default__")
            default_backend = cls._coerce_runtime_backend_candidate(default_candidate)
            if default_backend is not None:
                return default_backend

        raise InvalidJSONPointer(
            "JSONPointer backend TypeVar must define a default backend "
            "or be specialized with a concrete backend type"
        )

    @classmethod
    def _coerce_runtime_backend_candidate(
        cls,
        candidate: object,
    ) -> type[PointerBackend] | None:
        if isinstance(candidate, TypeVar):
            return cls._resolve_runtime_backend_typevar(candidate)
        if not isinstance(candidate, type):
            return None
        if candidate is PointerBackend or isabstract(candidate):
            return None
        return candidate

    def _validate_target(self, target: object) -> T_co:
        """Strictly validate the ``target`` with this JSONPointer's TypeAdapter."""
        try:
            return self._adapter.validate_python(target, strict=True)
        except Exception as e:
            raise PatchConflictError(
                f"expected target type {self.type_param} for pointer {str(self)!r}, got: {type(target)}"
            ) from e

    # Constructor - for convenience

    @classmethod
    def parse(
        cls,
        path: str | Self | PointerBackend,
        *,
        type_param: TypeForm[Any] = JSONValue,
        backend: type[PointerBackend] | None = None,
    ) -> Self:
        """
        Parse a pointer string or instance using Pydantic validation.

        This is a convenience wrapper around ``TypeAdapter(JSONPointer[...])``.
        """
        pointer_args: tuple[TypeForm[Any], ...]
        if backend is None:
            pointer_args = (type_param,)
        else:
            pointer_args = (type_param, backend)
        validated_type, validated_backend = cls._parse_pointer_type_args(*pointer_args)

        if backend is None:
            adapter = _type_adapter_for(
                JSONPointer[validated_type]  # type: ignore[valid-type]
            )
        else:
            adapter = _type_adapter_for(
                JSONPointer[validated_type, validated_backend]  # type: ignore[valid-type]
            )
        return adapter.validate_python(path)

    # Parse-time helpers

    def is_parent_of(self, other: str) -> bool:
        """
        Check whether this pointer is a strict parent of `other`.

        `other` may be a JSONPointer or a pointer string; strings are parsed using this pointer's syntax.

        Root is treated as a parent of all paths except itself.

        Raises InvalidJSONPointer if comparison is called with an `other` pointer with different or invalid syntax.
        """
        if isinstance(other, JSONPointer) and not isinstance(
            other._ptr, type(self._ptr)
        ):
            raise InvalidJSONPointer(
                f"Other pointer {other._ptr!r} has incompatible syntax with {self!r}"
            )
        other_ptr = _pointer_backend_instance(other, pointer_cls=self._ptr.__class__)

        # Strict parentage only
        if self == str(other_ptr):
            return False

        return other_ptr.parts[: len(self.parts)] == self.parts

    def is_child_of(self, other: str) -> bool:
        """
        Check whether this pointer is a strict child of `other`.

        `other` may be a JSONPointer or a pointer string; strings are parsed using this pointer's syntax.

        Root is treated as a parent of all paths except itself.

        Raises InvalidJSONPointer if comparison is called with an `other` pointer with different or invalid syntax.
        """
        # NOTE: Document which of these public helper methods work only with RFC6901
        if isinstance(other, JSONPointer) and not isinstance(
            other._ptr, type(self._ptr)
        ):
            raise InvalidJSONPointer(
                f"Other pointer {other._ptr!r} has incompatible syntax with {self!r}"
            )
        other_ptr = _pointer_backend_instance(other, pointer_cls=self._ptr.__class__)

        # Strict parentage only
        if self == str(other_ptr):
            return False

        return self.parts[: len(other_ptr.parts)] == other_ptr.parts

    # Runtime helpers

    def is_valid_type(self, target: object) -> bool:
        """Validate whether a target conforms to this pointer's type."""
        try:
            self._adapter.validate_python(target, strict=True)
            return True
        except Exception:
            return False

    def get(self, doc: JSONValue) -> T_co:
        """
        Resolve this pointer against ``doc`` and return the target value (type-gated).

        Args:
            doc: Target JSON document.

        Returns:
            The resolved value, validated against ``T``.

        Raises:
            PatchConflictError: If the target does not exist, or it is not type ``T``.
        """
        # Choice: always defer to the PointerBackend implementation for pointer resolution.
        # Why: Don't reinvent the wheel (and maintain it). Plus, give more power to custom PointerBackends.
        try:
            target = self._ptr.resolve(doc)
        except Exception as e:
            raise PatchConflictError(f"path {str(self)!r} not found: {e}") from e
        return self._validate_target(target)

    def is_gettable(self, doc: JSONValue) -> bool:
        """Return True if ``get`` would succeed for this document, else False."""
        try:
            self.get(doc)
        except Exception:
            return False
        else:
            return True

    def add(self, doc: JSONValue, value: object) -> JSONValue:
        """
        RFC 6902 add (type-gated).

        Args:
            doc: Target JSON document.
            value: Value to add at this path, validated against ``T``.

        Returns:
            The updated document.

        Raises:
            PatchConflictError: If the target does not exist, if the target is not type ``T``,
                or if the value being added is not type ``T``.
        """
        # Type errors first
        value_T: T_co = self._validate_target(target=value)
        try:
            target = _validate_JSONValue(value_T)
        except Exception as e:
            raise PatchConflictError(f"value {value!r} is not a valid JSONValue") from e

        match classify_state(self._ptr, doc):
            case TargetState.ROOT:
                self._validate_target(doc)
                return target
            case TargetState.PARENT_NOT_FOUND:
                raise PatchConflictError(
                    f"cannot add value at {str(self)!r} because parent does not exist"
                )
            case TargetState.PARENT_NOT_CONTAINER:
                raise PatchConflictError(
                    f"cannot add value at {str(self)!r} because parent is not a container"
                )
            case TargetState.ARRAY_INDEX_APPEND | TargetState.ARRAY_INDEX_AT_END:
                array = cast(JSONArray[JSONValue], self.parent_ptr.resolve(doc))
                array.append(target)
                return doc
            case TargetState.ARRAY_INDEX_OUT_OF_RANGE:
                raise PatchConflictError(
                    f"cannot add value at {str(self)!r} because array index {self.parts[-1]!r} is out of range"
                )
            case TargetState.OBJECT_KEY_MISSING:
                object = cast(JSONObject[JSONValue], self.parent_ptr.resolve(doc))
                key = self.parts[-1]
                object[key] = target
                return doc
            case (
                TargetState.ARRAY_KEY_INVALID
                | TargetState.VALUE_PRESENT_AT_NEGATIVE_ARRAY_INDEX
            ):
                raise PatchConflictError(
                    f"cannot add value at {str(self)!r} because key {self.parts[-1]!r} is an invalid array index"
                )
            case TargetState.VALUE_PRESENT:
                container = cast(JSONContainer[JSONValue], self.parent_ptr.resolve(doc))
                token = self.parts[-1]
                if _is_object(container):
                    self._validate_target(container[token])
                    container[token] = target
                    return doc
                else:
                    container.insert(int(token), target)
                    return doc
            case _ as unreachable:
                assert_never(unreachable)

    def is_addable(
        self,
        doc: JSONValue,
        value: object = _Nothing,
    ) -> bool:
        """
        Return True if RFC 6902 ``add`` would succeed for this document, else False.
        If ``value`` is provided, it must conform to the pointer's type parameter ``T``.
        """
        if value is not _Nothing:
            try:
                self._validate_target(target=value)
                _validate_JSONValue(value)
            except Exception:
                return False

        match classify_state(self._ptr, doc):
            case TargetState.ROOT:
                return self.is_valid_type(doc)
            case TargetState.VALUE_PRESENT:
                container = self.parent_ptr.resolve(doc)
                token = self.parts[-1]
                if _is_object(container):
                    return self.is_valid_type(container[token])
                return True  # list insert always valid
            case (
                TargetState.ARRAY_INDEX_APPEND
                | TargetState.ARRAY_INDEX_AT_END
                | TargetState.OBJECT_KEY_MISSING
            ):
                return True
            case _:
                return False

    def remove(self, doc: JSONValue) -> JSONValue:
        """
        RFC 6902 remove (type-gated). Removal of the root sets it to null.

        Args:
            doc: Target JSON document.

        Returns:
            The updated document.

        Raises:
            PatchConflictError: If the target does not exist, or it is not type ``T``.
        """
        match classify_state(self._ptr, doc):
            case TargetState.ROOT:
                # Choice: Removal of root sets root to null.
                # Why: Keeps all operations closed over JSONValue. Remove is also more composable this way.
                #      It affects few users, who themselves can circumvent with custom ops.
                self._validate_target(doc)
                return None
            case TargetState.PARENT_NOT_FOUND:
                raise PatchConflictError(
                    f"cannot remove value at {str(self)!r} because parent does not exist"
                )
            case TargetState.PARENT_NOT_CONTAINER:
                raise PatchConflictError(
                    f"cannot remove value at {str(self)!r} because parent is not a container"
                )
            case TargetState.ARRAY_INDEX_APPEND:
                raise PatchConflictError(
                    f"cannot remove value at {str(self)!r} because '-' indicates append position"
                )
            case TargetState.ARRAY_INDEX_OUT_OF_RANGE | TargetState.ARRAY_INDEX_AT_END:
                raise PatchConflictError(
                    f"cannot remove value at {str(self)!r} because array index {self.parts[-1]!r} is out of range"
                )
            case TargetState.OBJECT_KEY_MISSING:
                raise PatchConflictError(
                    f"cannot remove value at {str(self)!r} because key {self.parts[-1]!r} is missing from object"
                )
            case (
                TargetState.ARRAY_KEY_INVALID
                | TargetState.VALUE_PRESENT_AT_NEGATIVE_ARRAY_INDEX
            ):
                raise PatchConflictError(
                    f"cannot remove value at {str(self)!r} because key {self.parts[-1]!r} is an invalid array index"
                )
            case TargetState.VALUE_PRESENT:
                container = self.parent_ptr.resolve(doc)
                assert _is_container(container), (
                    "classify_state regression: VALUE_PRESENT"
                )
                token = self.parts[-1]
                key = int(token) if _is_array(container) else token
                self._validate_target(container[key])  # type: ignore[index]
                del container[key]  # type: ignore[arg-type]
                return doc
            case _ as unreachable:
                assert_never(unreachable)

    def is_removable(self, doc: JSONValue) -> bool:
        """Return True if RFC 6902 ``remove`` would succeed for this document, else False."""
        return self.is_gettable(doc)

    @override
    def __repr__(self) -> str:
        type_repr = (
            self._type.__name__ if isinstance(self._type, type) else repr(self._type)
        )
        return f"{self.__class__.__name__}[{type_repr}]({str(self)!r})"
