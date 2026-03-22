"""Demo 6: registry backend scoped to operations generic in pointer backend type P."""

from __future__ import annotations

from typing import Annotated, Generic, Literal, override

from fastapi import HTTPException, Path
from pydantic import ConfigDict
from typing_extensions import TypeVar

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

P = TypeVar("P", bound=RunePointer, covariant=True, default=RunePointer)


class RunePointerV2(RunePointer):
    """Marker subclass used when specializing generic backend parameter P."""


class GenericIncrementOp(OperationSchema, Generic[P]):
    model_config = ConfigDict(
        title="Increment operation",
        json_schema_extra={
            "description": "Increments a numeric field using a pointer backend generic type parameter."
        },
    )

    op: Literal["generic_increment"] = "generic_increment"
    path: JSONPointer[JSONNumber, P]
    value: JSONNumber

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return self.path.add(doc, current + self.value)


class GenericAppendOp(OperationSchema, Generic[P]):
    model_config = ConfigDict(
        title="Append operation",
        json_schema_extra={
            "description": "Appends a value to an array using a pointer backend generic type parameter."
        },
    )

    op: Literal["generic_append"] = "generic_append"
    path: JSONPointer[JSONArray[JSONValue], P]
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
    | GenericIncrementOp[RunePointerV2]
    | GenericAppendOp[RunePointerV2]
)
ApprenticePatch = JsonPatchFor[Apprentice, ApprenticeRegistry]
apprentice_patch = JsonPatchRoute(
    ApprenticePatch,
    examples={
        "generic-runes": {
            "summary": "increment mana and append a sigil via ops generic in P",
            "value": [
                {"op": "generic_increment", "path": "mana", "value": 15},
                {"op": "generic_append", "path": "sigils", "value": "flare"},
            ],
        }
    },
    strict_content_type=STRICT_JSON_PATCH,
)

app = create_app(
    title="Demo 6: Generic backend-parameterized ops",
    description=(
        "Rune-pointer operations authored as "
        "JSONPointer[..., P] where P is a backend TypeVar."
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
    summary="Patch apprentice (generic P ops)",
    description="Apply ops authored with a generic pointer backend type parameter.",
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
