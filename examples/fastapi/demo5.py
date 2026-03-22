"""Demo 5: registry backend scoped to ops with explicit custom backend annotations."""

from __future__ import annotations

from typing import Annotated, Literal, override

from fastapi import HTTPException, Path
from pydantic import ConfigDict

from examples.fastapi.shared import (
    Apprentice,
    ApprenticeId,
    RunePointer,
    create_app,
    get_apprentice,
    save_apprentice,
)
from jsonpatchx import (
    AddOp,
    CopyOp,
    JSONValue,
    MoveOp,
    RemoveOp,
    ReplaceOp,
    TestOp,
)
from jsonpatchx.fastapi import JsonPatchRoute
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.pydantic import JsonPatchFor
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import JSONArray, JSONNumber

STRICT_JSON_PATCH = True


class ExplicitRuneIncrementOp(OperationSchema):
    model_config = ConfigDict(
        title="Explicit rune increment operation",
        json_schema_extra={
            "description": "Increments a numeric field using an explicit rune pointer backend."
        },
    )

    op: Literal["explicit_increment"] = "explicit_increment"
    path: JSONPointer[JSONNumber, RunePointer]
    value: JSONNumber

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return self.path.add(doc, current + self.value)


class ExplicitRuneAppendOp(OperationSchema):
    model_config = ConfigDict(
        title="Explicit rune append operation",
        json_schema_extra={
            "description": "Appends a value to an array using an explicit rune pointer backend."
        },
    )

    op: Literal["explicit_append"] = "explicit_append"
    path: JSONPointer[JSONArray[JSONValue], RunePointer]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return self.path.add(doc, [*current, self.value])


type ApprenticeRegistry = (
    AddOp
    | CopyOp
    | MoveOp
    | RemoveOp
    | ReplaceOp
    | TestOp
    | ExplicitRuneIncrementOp
    | ExplicitRuneAppendOp
)
ApprenticePatch = JsonPatchFor[Apprentice, ApprenticeRegistry]
apprentice_patch = JsonPatchRoute(
    ApprenticePatch,
    examples={
        "explicit-runes": {
            "summary": "increment mana and append a sigil via explicit rune-backend ops",
            "value": [
                {"op": "explicit_increment", "path": "mana", "value": 10},
                {"op": "explicit_append", "path": "sigils", "value": "glint"},
            ],
        }
    },
    strict_content_type=STRICT_JSON_PATCH,
)

app = create_app(
    title="Demo 5: Explicit custom backend ops",
    description=(
        "Rune-pointer ops that already declare "
        "an explicit custom backend in their path annotations."
    ),
)


@app.get(
    "/apprentices/{apprentice_id}",
    response_model=Apprentice,
    tags=["apprentices"],
    summary="Get an apprentice",
    description="Fetch an apprentice by id.",
)
def get_apprentice_endpoint(
    apprentice_id: Annotated[
        ApprenticeId,
        Path(...),
    ],
) -> Apprentice:
    apprentice = get_apprentice(apprentice_id)
    if apprentice is None:
        raise HTTPException(status_code=404, detail="apprentice not found")
    return apprentice


@app.patch(
    "/apprentices/{apprentice_id}",
    response_model=Apprentice,
    tags=["apprentices"],
    summary="Patch apprentice (explicit custom backend ops)",
    description="Apply ops that explicitly annotate RunePointer-backed paths.",
    **apprentice_patch.route_kwargs(),
)
def patch_apprentice(
    apprentice_id: Annotated[
        ApprenticeId,
        Path(...),
    ],
    patch: Annotated[ApprenticePatch, apprentice_patch.Body()],
) -> Apprentice:
    apprentice = get_apprentice(apprentice_id)
    if apprentice is None:
        raise HTTPException(status_code=404, detail="apprentice not found")
    updated = patch.apply(apprentice)
    save_apprentice(apprentice_id, updated)
    return updated
