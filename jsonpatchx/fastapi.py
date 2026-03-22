"""
FastAPI integration helpers for jsonpatch.

Default error mapping:
- 415: Wrong Content-Type for JSON Patch (application/json-patch+json)
- 422: Request validation errors (malformed JSON, invalid operationns or pointers, model revalidation failure)
- 409: Patch is valid but cannot be applied to current resource state
- 500: Server misconfiguration or unexpected failures (e.g., invalid registry/op classes)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.params import Body as BodyParam
from fastapi.params import Depends as DependsParam
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from jsonpatchx.exceptions import (
    PatchConflictError,
    PatchError,
    PatchInputError,
    PatchInternalError,
)
from jsonpatchx.pydantic import JsonPatchFor

JSON_PATCH_MEDIA_TYPE = "application/json-patch+json"


class PatchFailureDetailResponse(BaseModel):
    index: int
    op: dict[str, Any]
    message: str
    cause_type: str | None = None


class PatchErrorResponse(BaseModel):
    detail: str | PatchFailureDetailResponse


# Public helpers


def install_jsonpatch_error_handlers(app: FastAPI) -> None:
    """Register a FastAPI exception handler for PatchError.

    Example:

        app = FastAPI()
        install_jsonpatch_error_handlers(app)

    """

    @app.exception_handler(PatchError)
    def _patch_error_handler(request: Request, exc: PatchError) -> JSONResponse:
        return _patch_error_response_map(exc)


def patch_error_openapi_responses() -> dict[int | str, dict[str, Any]]:
    """Return OpenAPI response schema entries for JSON Patch errors.

    Example:

        @app.patch("/items/{item_id}", responses=patch_error_openapi_responses())
        def patch_item(...):
            ...
    """
    patch_error_schema = {
        "type": "object",
        "properties": {
            "detail": {
                "oneOf": [
                    {"type": "string"},
                    {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer"},
                            "op": {"type": "object"},
                            "message": {"type": "string"},
                            "cause_type": {"type": ["string", "null"]},
                        },
                        "required": ["index", "op", "message"],
                    },
                ]
            }
        },
        "required": ["detail"],
    }
    validation_schema = {"$ref": "#/components/schemas/HTTPValidationError"}
    validation_or_patch_schema = {
        "oneOf": [
            patch_error_schema,
            validation_schema,
        ]
    }
    return {
        409: {
            "description": "Patch cannot be applied to current resource state",
            "content": {"application/json": {"schema": patch_error_schema}},
        },
        422: {
            "description": "Request validation or patch document validation error",
            "content": {"application/json": {"schema": validation_or_patch_schema}},
        },
        415: {
            "description": "Unsupported Media Type",
            "content": {"application/json": {"schema": patch_error_schema}},
        },
        500: {
            "description": "Patch execution error",
            "content": {"application/json": {"schema": patch_error_schema}},
        },
    }


def patch_content_type_dependency(
    enabled: bool, *, media_type: str = JSON_PATCH_MEDIA_TYPE
) -> list[DependsParam]:
    """Return a dependency list that enforces the JSON Patch media type.

    Example:

        @app.patch("/items/{item_id}", dependencies=patch_content_type_dependency(True))
        def patch_item(...):
            ...
    """
    if not enabled:
        return []

    def _dep(request: Request) -> None:
        _enforce_json_patch_content_type(request, media_type=media_type)

    return [Depends(_dep)]


def patch_request_body(
    patch_model: type[JsonPatchFor[Any, Any]],
    examples: dict[str, Any] | None = None,
    *,
    allow_application_json: bool = False,
    media_type: str = JSON_PATCH_MEDIA_TYPE,
    request_body_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an OpenAPI requestBody for JSON Patch with optional examples.

    Convention: JSON Patch requests should use ``application/json-patch+json``.
    This opinionated library advertises only that media type by default.
    Set ``allow_application_json=True`` to also document ``application/json`` for
    compatibility when you choose to accept it.

    ``request_body_overrides`` lets you override top-level requestBody fields and
    shallow-merge the ``content`` map. If you pass ``content``, its entries are
    merged into the generated content; all other keys replace generated values.

    Example:

        @app.patch(
            "/configs/{config_id}",
            openapi_extra=patch_request_body(ConfigPatch, examples={"set": {...}}),
        )
        def patch_config(...):
            ...

        # Add an extra media type and override requestBody.required
        openapi_extra=patch_request_body(
            ConfigPatch,
            request_body_overrides={
                "required": False,
                "content": {"application/merge-patch+json": {"schema": {"type": "object"}}},
            },
        )
    """
    schema_ref = f"#/components/schemas/{patch_model.__name__}"
    content: dict[str, Any] = {
        media_type: {"schema": {"$ref": schema_ref}},
    }
    if examples:
        content[media_type]["examples"] = examples
    if allow_application_json:
        content["application/json"] = {"schema": {"$ref": schema_ref}}
    request_body: dict[str, Any] = {"required": True, "content": content}
    if request_body_overrides:
        override_content = request_body_overrides.get("content")
        if isinstance(override_content, dict):
            content.update(override_content)
        request_body.update(
            {
                key: value
                for key, value in request_body_overrides.items()
                if key != "content"
            }
        )
    return {"requestBody": request_body}


def patch_route_kwargs(
    patch_model: type[JsonPatchFor[Any, Any]] | None = None,
    examples: dict[str, Any] | None = None,
    *,
    allow_application_json: bool = False,
    media_type: str = JSON_PATCH_MEDIA_TYPE,
    request_body_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return FastAPI decorator kwargs that keep docs and enforcement aligned.

    This opinionated helper adds:
    - ``responses`` for JSON Patch errors
    - ``dependencies`` that enforce JSON Patch media type by default
    - ``openapi_extra`` for the request body when ``patch_model`` is provided

    If ``allow_application_json`` is True, ``application/json`` is documented
    and enforcement is disabled to allow both.
    """
    kwargs: dict[str, Any] = {
        "responses": patch_error_openapi_responses(),
        "dependencies": patch_content_type_dependency(
            not allow_application_json,
            media_type=media_type,
        ),
    }
    if patch_model is not None:
        kwargs["openapi_extra"] = patch_request_body(
            patch_model,
            examples,
            allow_application_json=allow_application_json,
            media_type=media_type,
            request_body_overrides=request_body_overrides,
        )
    return kwargs


@dataclass(frozen=True)
class JsonPatchRoute:
    """Configure JSON Patch routes with a single source of truth."""

    patch_model: type[JsonPatchFor[Any, Any]]
    examples: dict[str, Any] | None = None
    strict_content_type: bool = True
    media_type: str = JSON_PATCH_MEDIA_TYPE
    request_body_overrides: dict[str, Any] | None = None
    request_param_overrides: dict[str, Any] | None = None

    def route_kwargs(self) -> dict[str, Any]:
        return patch_route_kwargs(
            self.patch_model,
            examples=self.examples,
            allow_application_json=not self.strict_content_type,
            media_type=self.media_type,
            request_body_overrides=self.request_body_overrides,
        )

    def Body(self) -> BodyParam:
        body_kwargs = dict(self.request_param_overrides or {})
        if self.strict_content_type:
            body_kwargs.setdefault("media_type", self.media_type)
        return cast(BodyParam, Body(..., **body_kwargs))


def _patch_error_response_map(exc: PatchError) -> JSONResponse:
    """Map a PatchError to a JSONResponse for FastAPI exception handlers."""
    if isinstance(exc, PatchInternalError):
        detail = exc.detail
        payload = PatchFailureDetailResponse(
            index=detail.index,
            op=detail.op.model_dump(mode="json", by_alias=True),
            message=detail.message,
            cause_type=detail.cause_type,
        )
        return JSONResponse(
            status_code=500, content=PatchErrorResponse(detail=payload).model_dump()
        )

    if isinstance(exc, PatchInputError):
        return JSONResponse(
            status_code=422, content=PatchErrorResponse(detail=str(exc)).model_dump()
        )

    if isinstance(exc, PatchConflictError):
        return JSONResponse(
            status_code=409, content=PatchErrorResponse(detail=str(exc)).model_dump()
        )

    return JSONResponse(
        status_code=500, content=PatchErrorResponse(detail=str(exc)).model_dump()
    )


def _enforce_json_patch_content_type(
    request: Request, *, media_type: str = JSON_PATCH_MEDIA_TYPE
) -> None:
    content_type = request.headers.get("content-type", "")
    if not content_type.lower().startswith(media_type.lower()):
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported Media Type. Use {media_type} for JSON Patch requests."
            ),
        )
