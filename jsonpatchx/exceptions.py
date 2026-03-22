from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jsonpatchx.schema import OperationSchema


class PatchError(Exception):
    """
    Base class for JSON Patch errors.

    This type is not raised directly; it anchors the error hierarchy for tooling
    and API error mapping.
    """


class PatchInputError(PatchError):
    """
    Patch input is invalid or fails validation.

    Examples:
        - Invalid JSON Pointer syntax in an incoming operation.
        - Operation-specific validation failure (e.g., swap parent/child paths).
        - Model revalidation fails after applying a patch.

    Typical HTTP mapping:
        422 Unprocessable Entity.
    """


class InvalidOperationDefinition(PatchError):
    """
    An OperationSchema definition is invalid (developer error).

    Examples:
        - ``op`` is missing or not declared as ``Literal[...]``.
        - ``op`` is declared as a ClassVar, so it is not a model field.
    """


class OperationValidationError(PatchInputError):
    """
    An OperationSchema instance failed validation (client error).

    Examples:
        - Swap operation rejects parent/child pointers via a model validator.
        - Operation fields violate custom constraints in validators.

    Typical HTTP mapping:
        422 Unprocessable Entity.
    """


class InvalidJSONPointer(PatchInputError):
    """
    A JSON Pointer definition or instance is invalid.

    Examples:
        - Pointer string is malformed or uses an incompatible backend.
        - Pointer backend class fails protocol checks.

    Typical HTTP mapping:
        422 Unprocessable Entity for request input.
    """


class InvalidOperationRegistry(PatchError):
    """
    An OperationRegistry has incompatible OperationSchemas (developer error).

    Examples:
        - Duplicate ``op`` identifiers across schemas.
        - Non-OperationSchema classes provided to the registry.
    """


class OperationNotRecognized(PatchInputError):
    """
    An OperationSchema instance does not belong to the active registry.

    Examples:
        - Passing a StandardRegistry op instance into a custom registry.

    Typical HTTP mapping:
        422 Unprocessable Entity.
    """


class PatchConflictError(PatchError):
    """
    A JSON Patch failed due to a conflict with the current document state.

    Examples:
        - Path does not exist or array index is out of range.
        - Removing a value at a missing or invalid path.

    Typical HTTP mapping:
        409 Conflict (some APIs may prefer 422).
    """


class PatchValidationError(PatchInputError):
    """
    Patched data failed validation against a target schema.

    Examples:
        - Model-aware patching produces a document that violates the target model.

    Typical HTTP mapping:
        422 Unprocessable Entity.
    """


class TestOpFailed(PatchConflictError):
    """
    A test operation failed (RFC 6902).

    Typical HTTP mapping:
        409 Conflict (state mismatch).
    """

    __test__ = False


@dataclass(frozen=True, slots=True)
class PatchFailureDetail:
    """
    Structured failure details for patch application.

    Attributes:
        index: 0-based index of the operation within the patch document.
        op: Best-effort JSON-serializable representation of the failing operation.
            For OperationSchema instances, this is model_dump(mode="json", by_alias=True).
            For mapping-like inputs, this is dict(op).
            As a last resort, {"repr": repr(op)}.
        message: Human-readable error message.
        cause_type: The exception class name of the underlying cause (useful for logging / API error mapping).
    """

    index: int
    op: OperationSchema
    message: str
    cause_type: str | None = None


class PatchInternalError(PatchError):
    """
    Unexpected exception during patch execution wrapped with structured context.

    This is meant for API layers and debuggability:
        - points at the exact op index
        - includes the full op payload (best-effort JSON shape)

    Example:
        A ZeroDivisionError raised inside a custom op implementation that fails
        to catch it.

    Typical HTTP mapping:
        500 Internal Server Error (unexpected failure).
    """

    def __init__(
        self, detail: PatchFailureDetail, *, cause: BaseException | None = None
    ):
        self.detail = detail
        super().__init__(self._format(detail))
        if cause is not None:
            self.__cause__ = cause

    @staticmethod
    def _format(d: PatchFailureDetail) -> str:
        op_name = getattr(d.op, "op")
        return f"Error applying op[{d.index}] ({op_name}): {d.message}"
