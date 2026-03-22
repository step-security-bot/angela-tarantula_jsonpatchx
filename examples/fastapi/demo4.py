"""Demo 4: spellbook dot-runes pointer backend."""

from __future__ import annotations

from typing import Annotated, Literal, override

from fastapi import HTTPException, Path
from pydantic import ConfigDict, Field

from examples.fastapi.shared import (
    Apprentice,
    ApprenticeId,
    RunePointer,
    SpellbookId,
    create_app,
    get_apprentice,
    get_spellbook,
    save_apprentice,
    save_spellbook,
)
from jsonpatchx import (
    JSONValue,
    OperationSchema,
)
from jsonpatchx.fastapi import JsonPatchRoute
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.pydantic import JsonPatchFor
from jsonpatchx.registry import StandardRegistry
from jsonpatchx.types import JSONNumber

STRICT_JSON_PATCH = True

app = create_app(
    title="Demo 4: Spellbook rune pointers",
    description=(
        "Mixed pointer backends in one registry: RFC6901 slash-pointer built-ins "
        "plus rune-pointer custom ops. "
        "Uses `JsonPatchRoute` to align OpenAPI and runtime validation."
    ),
)


class RuneIncrementOp(OperationSchema):
    model_config = ConfigDict(
        title="Rune increment operation",
        json_schema_extra={"description": "Increments a numeric field by a value."},
    )

    op: Literal["increment"] = "increment"
    path: JSONPointer[JSONNumber, RunePointer]
    value: JSONNumber = Field(gt=0, multiple_of=5)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        total = current + self.value
        return self.path.add(doc, total)


class RuneAppendOp(OperationSchema):
    model_config = ConfigDict(
        title="Rune append operation",
        json_schema_extra={"description": "Appends a value to an array."},
    )

    op: Literal["append"] = "append"
    path: JSONPointer[list[JSONValue], RunePointer]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return self.path.add(doc, [*current, self.value])


type RuneRegistry = RuneIncrementOp | RuneAppendOp
SpellbookPatch = JsonPatchFor[Literal["Spellbook"], StandardRegistry | RuneRegistry]
ApprenticePatch = JsonPatchFor[Apprentice, StandardRegistry | RuneRegistry]
spellbook_patch = JsonPatchRoute(
    SpellbookPatch,
    examples={
        "midnight-runes": {
            "summary": "slash replace + rune increment in one patch",
            "value": [
                {"op": "replace", "path": "/rituals/summon/enabled", "value": True},
                {"op": "increment", "path": "ingredients.moon_salt", "value": 5},
            ],
        }
    },
    strict_content_type=STRICT_JSON_PATCH,
)
apprentice_patch = JsonPatchRoute(
    ApprenticePatch,
    examples={
        "sparkle-sprint": {
            "summary": "slash replace + rune increment + rune append",
            "value": [
                {"op": "replace", "path": "/name", "value": "Morgan Vale"},
                {"op": "increment", "path": "mana", "value": 20},
                {"op": "append", "path": "sigils", "value": "aurora"},
            ],
        },
        "lantern-lesson": {
            "summary": "slash replace + rune append",
            "value": [
                {"op": "replace", "path": "/name", "value": "Nova"},
                {"op": "append", "path": "sigils", "value": "ember"},
            ],
        },
    },
    strict_content_type=STRICT_JSON_PATCH,
)


@app.get(
    "/spellbooks/{spellbook_id}",
    response_model=JSONValue,
    tags=["spellbooks"],
    summary="Get a spellbook",
    description="Fetch a spellbook by id.",
)
def get_spellbook_endpoint(
    spellbook_id: Annotated[
        SpellbookId,
        Path(...),
    ],
) -> JSONValue:
    doc = get_spellbook(spellbook_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="spellbook not found")
    return doc


@app.patch(
    "/spellbooks/{spellbook_id}",
    response_model=JSONValue,
    tags=["spellbooks"],
    summary="Patch a spellbook (mixed pointer backends)",
    description="Use slash pointers for built-ins and rune pointers for custom ops.",
    **spellbook_patch.route_kwargs(),
)
def patch_spellbook(
    spellbook_id: Annotated[
        SpellbookId,
        Path(...),
    ],
    patch: Annotated[SpellbookPatch, spellbook_patch.Body()],
) -> JSONValue:
    doc = get_spellbook(spellbook_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="spellbook not found")
    updated = patch.apply(doc)
    save_spellbook(spellbook_id, updated)
    return updated


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
    summary="Patch an apprentice (mixed pointer backends)",
    description="Use slash pointers for built-ins and rune pointers for custom ops.",
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
