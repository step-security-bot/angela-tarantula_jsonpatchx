"""
Demo 3: SRE control plane configs (plain JSON patching).
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import HTTPException, Path

from examples.fastapi.shared import (
    AppendOp,
    ConfigId,
    EnsureObjectOp,
    ExtendOp,
    IncrementOp,
    RemoveNumberOp,
    SetMessageOp,
    SwapOp,
    ToggleBoolOp,
    create_app,
    get_config,
    save_config,
)
from jsonpatchx import JSONValue
from jsonpatchx.fastapi import JsonPatchRoute
from jsonpatchx.pydantic import JsonPatchFor

STRICT_JSON_PATCH = True

type ConfigRegistry = (
    IncrementOp
    | AppendOp
    | ExtendOp
    | ToggleBoolOp
    | SwapOp
    | EnsureObjectOp
    | RemoveNumberOp
    | SetMessageOp
)
ConfigPatch = JsonPatchFor[Literal["ServiceConfig"], ConfigRegistry]
config_patch = JsonPatchRoute(
    ConfigPatch,
    examples={
        "rocket-boost": {
            "summary": "bump max_users and toggle chat",
            "value": [
                {"op": "increment", "path": "/limits/max_users", "value": 50},
                {"op": "toggle", "path": "/features/chat"},
            ],
        },
        "tag-and-seal": {
            "summary": "ensure features and append a tag",
            "value": [
                {"op": "ensure_object", "path": "/features"},
                {"op": "append", "path": "/tags", "value": "beta"},
            ],
        },
        "shuffle-switch": {
            "summary": "swap and then toggle",
            "value": [
                {"op": "swap", "a": "/service_name", "b": "/features/chat"},
                {"op": "toggle", "path": "/features/chat"},
            ],
        },
        "maintenance-note": {
            "summary": "set or clear the service_name message",
            "value": [
                {
                    "op": "set_message",
                    "path": "/service_name",
                    "message": "Atlas maintenance in progress",
                }
            ],
        },
        "oops-expected": {
            "summary": "type-gated remove (expected failure)",
            "value": [
                {"op": "ensure_object", "path": "/features"},
                {"op": "remove_number", "path": "/service_name"},
            ],
        },
    },
    strict_content_type=STRICT_JSON_PATCH,
)

app = create_app(
    title="Demo 3: Control plane configs",
    description="Plain JSON patching for service configs using `JsonPatchFor[Name, Registry]`.",
)


@app.get(
    "/configs/{config_id}",
    response_model=JSONValue,
    tags=["configs"],
    summary="Get a service config",
    description="Fetch a service config by id.",
)
def get_config_endpoint(
    config_id: Annotated[
        ConfigId,
        Path(...),
    ],
) -> JSONValue:
    doc = get_config(config_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="config not found")
    return doc


@app.patch(
    "/configs/{config_id}",
    response_model=JSONValue,
    tags=["configs"],
    summary="Patch a service config",
    description="Apply standard RFC 6902 ops plus custom ops to a service config.",
    **config_patch.route_kwargs(),
)
def patch_config(
    config_id: Annotated[
        ConfigId,
        Path(...),
    ],
    patch: Annotated[ConfigPatch, config_patch.Body()],
) -> JSONValue:
    doc = get_config(config_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="config not found")
    updated = patch.apply(doc)
    save_config(config_id, updated)
    return updated
